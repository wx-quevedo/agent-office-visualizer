import Foundation

// "Dónde quedamos": proyectos con su alerta, plan por etapas, prompt actual.
// Portado de frontend/src/components/donde/logica.ts.

struct ProyectoVista: Identifiable, Equatable {
    var id: String
    var nombre: String
    var datos: ProyectoApi
    var agentes: [Agente]
    var ultima: String?
    var alerta: TipoAlerta
}

enum TipoAlerta: Int, Equatable {
    case permiso = 0, atasco, pregunta, decision, trabajando, listo, sinActividad

    var urgencia: Int { min(rawValue, 4) }
}

struct Etapa: Equatable, Identifiable {
    var corto: String
    var etiqueta: String
    var nombre: String
    var estado: Estado
    var id: String { etiqueta + corto }

    enum Estado { case hecha, actual, pendiente }
}

struct PromptVista: Equatable {
    var numero: Int
    var nombre: String
    var estado: String // hecho, en_curso, espera, detenido, pendiente
    var actual: Bool
}

enum LogicaDonde {
    static func normal(_ ruta: String?) -> String {
        var s = (ruta ?? "").replacingOccurrences(of: "\\", with: "/").lowercased()
        while s.hasSuffix("/") { s.removeLast() }
        return s
    }

    /// El motor puede mandar solo el nombre de la carpeta; el monitor, la ruta completa.
    static func mismaCarpeta(_ a: String?, _ b: String?) -> Bool {
        guard let a, let b, !a.isEmpty, !b.isEmpty else { return false }
        let x = normal(a), y = normal(b)
        return x == y || (!x.contains("/") && y.hasSuffix("/" + x)) || (!y.contains("/") && x.hasSuffix("/" + y))
    }

    static let estadosTrabajo: Set<Int> = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 16, 17]

    static func alerta(_ p: ProyectoApi, _ agentes: [Agente]) -> TipoAlerta {
        let vivos = agentes.filter { $0.estado.numero != 21 }
        if vivos.contains(where: { $0.estado.numero == 13 }) { return .permiso }
        if vivos.contains(where: { $0.atasco != nil }) { return .atasco }
        if vivos.contains(where: { $0.estado.numero == 14 || $0.pregunta_pendiente != nil }) { return .pregunta }
        if !p.espera_decision.isEmpty { return .decision }
        if vivos.contains(where: { estadosTrabajo.contains($0.estado.numero) }) { return .trabajando }
        if !vivos.isEmpty || p.ultima_actividad != nil || p.ultimo_commit != nil { return .listo }
        return .sinActividad
    }

    static func idProyecto(_ carpeta: String) -> String { Logica.nombreCarpeta(carpeta).lowercased() }

    private static func masReciente(_ isos: [String?]) -> String? {
        var mejor: (String, Date)?
        for i in isos {
            guard let i, let d = FechaISO.leer(i) else { continue }
            if mejor == nil || d > mejor!.1 { mejor = (i, d) }
        }
        return mejor?.0
    }

    /// Proyectos del monitor más las carpetas con agentes sin informe. Urgentes primero, luego los más recientes.
    static func armar(_ api: [ProyectoApi], _ agentes: [Agente]) -> [ProyectoVista] {
        var usados = Set<String>()
        var ids = Set<String>()
        var salida: [ProyectoVista] = []
        func agregar(_ datos: ProyectoApi, _ suyos: [Agente]) {
            var id = idProyecto(datos.carpeta)
            if ids.contains(id), let m = datos.maquina { id += "-" + m.lowercased() }
            ids.insert(id)
            let ultima = masReciente(suyos.map { $0.ultimo_evento?.hora } + [
                datos.ultima_actividad?.ultimo_evento, datos.ultima_actividad?.ultimo_turno?.inicio, datos.ultimo_commit?.fecha,
            ])
            salida.append(ProyectoVista(id: id, nombre: Logica.nombreCarpeta(datos.carpeta), datos: datos,
                                        agentes: suyos, ultima: ultima, alerta: alerta(datos, suyos)))
        }
        for p in api {
            let suyos = agentes.filter { a in
                mismaCarpeta(a.agente.proyecto, p.carpeta)
                    && (a.agente.maquina == nil || p.maquina == nil || a.agente.maquina == p.maquina)
            }
            suyos.forEach { usados.insert($0.id) }
            agregar(p, suyos)
        }
        var sueltos: [(String, [Agente])] = []
        for a in agentes where !usados.contains(a.id) {
            guard let pr = a.agente.proyecto, !pr.isEmpty else { continue }
            let clave = normal(pr)
            if let i = sueltos.firstIndex(where: { $0.0 == clave }) { sueltos[i].1.append(a) } else { sueltos.append((clave, [a])) }
        }
        for (_, lista) in sueltos {
            agregar(ProyectoApi(carpeta: lista[0].agente.proyecto ?? "", maquina: lista[0].agente.maquina), lista)
        }
        return salida.sorted { x, y in
            if x.alerta.urgencia != y.alerta.urgencia { return x.alerta.urgencia < y.alerta.urgencia }
            let dx = FechaISO.leer(x.ultima) ?? .distantPast, dy = FechaISO.leer(y.ultima) ?? .distantPast
            if dx != dy { return dx > dy }
            return x.nombre < y.nombre
        }
    }

    // MARK: - Etapas

    private static let reEtapa = try! NSRegularExpression(
        pattern: #"^(etapa|fase|phase|stage|sprint|hito|milestone)\s+(\d+)(?:\.(\d+))?\s*[,:.\-–—]?\s*(.*)$"#,
        options: .caseInsensitive)

    private struct Coincidencia {
        var tipo: String
        var numero: String
        var sub: String?
        var resto: String
    }

    private static func etapa(_ texto: String) -> Coincidencia? {
        let t = texto.trimmingCharacters(in: .whitespaces)
        guard let m = reEtapa.firstMatch(in: t, range: NSRange(t.startIndex..., in: t)) else { return nil }
        func g(_ i: Int) -> String? { Range(m.range(at: i), in: t).map { String(t[$0]) } }
        return Coincidencia(tipo: g(1) ?? "", numero: g(2) ?? "", sub: g(3), resto: g(4) ?? "")
    }

    private static func mayuscula(_ t: String) -> String { t.prefix(1).uppercased() + t.dropFirst() }

    /// Bloques de etapas: solo las principales ("Etapa 2") si el plan las tiene.
    static func etapas(_ plan: [ProyectoApi.ItemPlan], posicion: String?) -> [Etapa] {
        let conNumero = plan.map { ($0, etapa($0.nombre)) }
        let principales = conNumero.filter { $0.1 != nil && $0.1!.sub == nil }
        let lista = principales.count >= 2 ? principales : conNumero
        if lista.isEmpty { return [] }
        var actual = -1
        if let posicion, let pos = etapa(posicion) {
            actual = lista.firstIndex { $0.1 != nil && $0.1!.numero == pos.numero && $0.1!.tipo.lowercased() == pos.tipo.lowercased() } ?? -1
        }
        if actual < 0, let posicion { actual = lista.firstIndex { $0.0.nombre == posicion } ?? -1 }
        if actual < 0 { actual = lista.firstIndex { $0.0.estado == "en_curso" } ?? -1 }
        if actual < 0 { actual = lista.firstIndex { $0.0.estado != "hecho" } ?? -1 }
        return lista.enumerated().map { n, par in
            let (i, m) = par
            let estado: Etapa.Estado = n == actual ? .actual : i.estado == "hecho" ? .hecha : .pendiente
            if let m {
                let num = m.sub.map { "\(m.numero).\($0)" } ?? m.numero
                return Etapa(corto: num, etiqueta: "\(mayuscula(m.tipo.lowercased())) \(num)",
                             nombre: mayuscula(m.resto.trimmingCharacters(in: .whitespaces)), estado: estado)
            }
            return Etapa(corto: String(n + 1), etiqueta: "Paso \(n + 1)", nombre: i.nombre, estado: estado)
        }
    }

    // MARK: - Prompts de la etapa

    private static func estadoDeTurno(_ r: String) -> String {
        switch r {
        case "completado": return "hecho"
        case "esperando": return "espera"
        case "en_curso": return "en_curso"
        default: return "detenido"
        }
    }

    static func promptsDeEtapa(_ p: ProyectoApi) -> [PromptVista] {
        let plan = p.prompts ?? []
        var turnos = p.prompts_turnos ?? []
        let numeros: [Int]
        if !plan.isEmpty {
            numeros = plan.map(\.numero)
            let (mi, ma) = (numeros.min()!, numeros.max()!)
            turnos = turnos.filter { $0.numero >= mi && $0.numero <= ma }
        } else {
            turnos = Array(turnos.suffix(4))
            numeros = turnos.map(\.numero)
        }
        var lista: [PromptVista] = numeros.map { n in
            let pp = plan.first { $0.numero == n }
            let tt = turnos.first { $0.numero == n }
            let estado: String
            if pp?.estado == "hecho" { estado = "hecho" }
            else if let tt { estado = estadoDeTurno(tt.resultado) }
            else if pp?.estado == "en_curso" { estado = "en_curso" }
            else { estado = "pendiente" }
            return PromptVista(numero: n, nombre: mayuscula(pp?.nombre ?? tt?.nombre ?? ""), estado: estado, actual: false)
        }
        let i = lista.firstIndex { $0.estado == "en_curso" || $0.estado == "espera" } ?? lista.firstIndex { $0.estado != "hecho" }
        if let i { lista[i].actual = true }
        return lista
    }

    /// Quién hace el siguiente paso, según su texto.
    static func quienHace(_ texto: String?) -> String? {
        guard let texto, !texto.isEmpty else { return nil }
        let t = texto.trimmingCharacters(in: .whitespaces)
        if t.range(of: #"\b(washington|t[uú])\b"#, options: [.regularExpression, .caseInsensitive]) != nil
            || t.range(of: #"^(aprobar|aprueba|decidir|decide|revisar|revisa|probar|elegir|elige|confirmar|confirma|ejecutar|ejecuta)\b"#,
                       options: [.regularExpression, .caseInsensitive]) != nil {
            return "Quién: tú."
        }
        if t.range(of: #"\bprompt\s+\d+|\bagente\b|\bclaude\b"#, options: [.regularExpression, .caseInsensitive]) != nil {
            return "Quién: el agente."
        }
        return nil
    }

    /// Segundos de trabajo de hoy de las sesiones de ese proyecto.
    static func segundosHoy(_ consumo: Consumo?, carpeta: String) -> Double? {
        guard let consumo else { return nil }
        return consumo.por_sesion.filter { mismaCarpeta($0.proyecto, carpeta) }.reduce(0) { $0 + $1.segundos_trabajo }
    }
}

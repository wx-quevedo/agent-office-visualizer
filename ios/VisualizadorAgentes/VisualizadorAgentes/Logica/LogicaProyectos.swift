import Foundation

// Proyectos (etapa 4): la lista unificada (con y sin orquestador), su estado y
// color, los nombres de modelos y esfuerzos, el nombre de un proyecto nuevo, el
// chat mezclado con las órdenes y sus textos. Portado de
// frontend/src/components/proyectos/logica.ts. Se prueba en ProyectosTests.

/// Estado de un proyecto en la lista, con su color del boceto Main.
enum EstadoLista: Equatable {
    case porAprobar(Int)
    case permiso
    case atascado
    case trabajando
    case detenido(String)
    case listo(String)

    var texto: String {
        switch self {
        case .porAprobar(let n): return n == 1 ? "Orden por aprobar" : "\(n) órdenes por aprobar"
        case .permiso: return "Te pide permiso"
        case .atascado: return "Atascado"
        case .trabajando: return "Trabajando"
        case .detenido(let t), .listo(let t): return t
        }
    }
}

/// Un proyecto de la lista: con equipo (creado desde la oficina) o solo con su
/// PROJECT.md y sus agentes (sin orquestador).
struct ProyectoLista: Identifiable, Equatable {
    var id: String
    var nombre: String
    var cuenta: String?
    var maquina: String?
    var equipo: ProyectoEquipo?
    var donde: ProyectoVista?
    var agentes: [Agente]

    var conOrquestador: Bool { equipo != nil }
}

/// La pantalla de un proyecto: su clave en la lista y la sección abierta.
struct RutaProyecto: Hashable {
    var id: String
    var seccion: SeccionProyecto
    /// Clave del aviso que se responde ("mensaje:<id>" u "orden:<id>"): el chat la deja a la vista.
    var aviso: String? = nil
}

enum SeccionProyecto: String, CaseIterable, Identifiable, Hashable {
    case chat = "Chat"
    case equipo = "Equipo"
    case donde = "Dónde quedamos"
    var id: String { rawValue }
}

enum LogicaProyectos {
    // MARK: - Nombres

    static let modelos: [(valor: String, texto: String)] = [
        ("opus", "Opus 5.5"), ("sonnet", "Sonnet 5.5"), ("haiku", "Haiku 5.5"), ("fable", "Fable 5.1"),
    ]
    static let esfuerzos: [(valor: String, texto: String)] = [
        ("low", "bajo"), ("medium", "medio"), ("high", "alto"), ("xhigh", "muy alto"), ("max", "máximo"),
    ]
    static let plantillas: [(valor: String, texto: String)] = [
        ("web", "Web (Next.js)"), ("unity", "Unity"), ("expo", "App (Expo)"), ("vacia", "Vacía"),
    ]
    static let maxAgentes = 4

    static func nombreModelo(_ v: String?) -> String {
        guard let v, !v.isEmpty else { return "Modelo sin anotar" }
        return modelos.first { $0.valor == v }?.texto ?? Logica.nombreModelo(v) ?? v
    }

    static func nombreEsfuerzo(_ v: String?) -> String {
        guard let v, !v.isEmpty else { return "sin anotar" }
        return esfuerzos.first { $0.valor == v }?.texto ?? v
    }

    /// "Opus 5.5 · esfuerzo alto".
    static func modeloYEsfuerzo(_ modelo: String?, _ esfuerzo: String?) -> String {
        "\(nombreModelo(modelo)) · esfuerzo \(nombreEsfuerzo(esfuerzo))"
    }

    static func nombreRol(_ m: ProyectoEquipo.Miembro, agentes: Int) -> String {
        if m.rol == "orquestador" { return "Orquestador" }
        if agentes > 1, let n = m.nombre.split(separator: "-").last, Int(n) != nil { return "Agente de código \(n)" }
        return "Agente de código"
    }

    static func iniciales(_ m: ProyectoEquipo.Miembro) -> String { m.rol == "orquestador" ? "OR" : "AC" }

    /// Estado del miembro cuando la oficina no lo ve (sin sesión todavía).
    static func estadoMiembro(_ e: String) -> String {
        switch e {
        case "pendiente": return "Pendiente"
        case "activo": return "Libre, sin órdenes"
        case "pausado": return "En pausa"
        case "detenido": return "Detenido"
        case "error": return "Con error"
        default: return e
        }
    }

    // MARK: - Lista

    /// Proyectos con equipo primero (los más recientes), luego los que solo tiene el
    /// monitor. Un proyecto con equipo se une a su "Dónde quedamos" por la carpeta.
    static func lista(equipos: [ProyectoEquipo], donde: [ProyectoVista], agentes: [Agente]) -> [ProyectoLista] {
        var usados = Set<String>()
        var salida: [ProyectoLista] = []
        for p in equipos {
            // Primero el id que da el servidor; por carpeta o por nombre solo si viene null.
            let d: ProyectoVista?
            if let idDonde = p.donde_quedamos_id {
                d = donde.first { $0.datos.id == idDonde }
            } else {
                d = donde.first { v in
                    !usados.contains(v.id) && (LogicaDonde.mismaCarpeta(v.datos.carpeta, p.ruta)
                        || (v.nombre.lowercased() == p.nombre.lowercased() && (v.datos.maquina == nil || v.datos.maquina == p.maquina)))
                }
            }
            if let d { usados.insert(d.id) }
            let sesiones = Set(p.equipo.compactMap(\.session_id))
            let suyos = agentes.filter { sesiones.contains($0.id) || (d?.agentes.contains($0) ?? false) }
            salida.append(ProyectoLista(id: "e-" + p.id, nombre: p.nombre, cuenta: p.cuenta, maquina: p.maquina,
                                        equipo: p, donde: d, agentes: suyos))
        }
        for v in donde where !usados.contains(v.id) {
            salida.append(ProyectoLista(id: "m-" + v.id, nombre: v.nombre,
                                        cuenta: v.agentes.first?.agente.cuenta, maquina: v.datos.maquina ?? v.agentes.first?.agente.maquina,
                                        equipo: nil, donde: v, agentes: v.agentes))
        }
        return salida
    }

    /// "3 con orquestador · 4 sin orquestador".
    static func resumen(_ lista: [ProyectoLista]) -> String {
        let con = lista.filter(\.conOrquestador).count
        return "\(con) con orquestador · \(lista.count - con) sin orquestador"
    }

    static let estadosDetenidos: [String: String] = [
        "pausado": "En pausa", "pausando": "Pausando", "detenido": "Detenido", "deteniendo": "Deteniendo",
    ]

    /// Lo más urgente primero: órdenes por aprobar, permiso, atasco, trabajando, detenido.
    static func estado(_ p: ProyectoLista) -> EstadoLista {
        if let n = p.equipo?.ordenes_por_aprobar, n > 0 { return .porAprobar(n) }
        let vivos = p.agentes.filter { $0.estado.numero != 21 }
        if vivos.contains(where: { $0.estado.numero == 13 }) { return .permiso }
        if vivos.contains(where: { $0.atasco != nil }) || p.equipo?.estado == "error" { return .atascado }
        if let e = p.equipo, let t = estadosDetenidos[e.estado] { return .detenido(t) }
        let trabaja = vivos.contains { LogicaDonde.estadosTrabajo.contains($0.estado.numero) }
            || p.equipo?.equipo.contains { m in m.oficina.map { LogicaDonde.estadosTrabajo.contains($0.numero) } ?? false } == true
        if trabaja { return .trabajando }
        if let e = p.equipo {
            switch e.estado {
            case "creando": return .listo("Creando")
            case "reanudando": return .listo("Reanudando")
            default: return .listo("En espera")
            }
        }
        if vivos.contains(where: { $0.estado.numero == 14 }) { return .listo("Te hizo una pregunta") }
        return .listo(vivos.isEmpty ? "Sin actividad" : "Listo")
    }

    /// Qué hace o dónde va: lo que hace el equipo, o la posición del PROJECT.md.
    static func dondeVa(_ p: ProyectoLista) -> String {
        if let e = p.equipo {
            if e.estado == "error" { return e.error ?? "Hubo un error sin detalle." }
            if let h = e.haciendo, !h.isEmpty { return h }
            if e.estado == "creando" { return "Creando la carpeta y el equipo…" }
        }
        if let d = p.donde?.datos, d.tiene_project_md {
            let prompt = LogicaDonde.promptsDeEtapa(d).first { $0.actual }
            let pos = d.posicion ?? "Sin posición anotada"
            if let prompt { return "\(pos) · Prompt \(prompt.numero)" + (prompt.nombre.isEmpty ? "" : " (\(prompt.nombre.lowercased()))") }
            return pos
        }
        if let a = p.agentes.first(where: { $0.estado.numero != 21 }) { return Logica.detalleActual(a) }
        return p.equipo != nil ? "En espera" : "Sin PROJECT.md"
    }

    /// "Orquestador + 2 agentes" o "Sin orquestador · 1 agente".
    static func equipoTexto(_ p: ProyectoLista) -> String {
        if let e = p.equipo {
            let n = e.equipo.filter { $0.rol == "agente" }.count
            return "Orquestador + \(n) \(n == 1 ? "agente" : "agentes")"
        }
        let n = p.agentes.filter { $0.estado.numero != 21 }.count
        return n == 0 ? "Sin orquestador" : "Sin orquestador · \(n) \(n == 1 ? "agente" : "agentes")"
    }

    // MARK: - Proyecto nuevo

    /// nil si el nombre sirve; si no, qué falta, en una frase (misma regla que el backend).
    static func errorNombre(_ nombre: String) -> String? {
        if nombre.isEmpty { return "Escribe un nombre para el proyecto." }
        if nombre.count > 50 { return "El nombre puede tener hasta 50 caracteres." }
        if nombre.contains(where: \.isUppercase) { return "Usa solo minúsculas." }
        if nombre.range(of: "^[a-z0-9-]+$", options: .regularExpression) == nil {
            return "Usa solo letras minúsculas sin tildes, números y guiones."
        }
        if nombre.hasPrefix("-") || nombre.hasSuffix("-") { return "El nombre no puede empezar ni terminar con un guion." }
        if nombre.range(of: "^(con|prn|aux|nul|com[0-9]|lpt[0-9])$", options: .regularExpression) != nil {
            return "Ese nombre está reservado por Windows; elige otro."
        }
        return nil
    }

    /// La carpeta que se va a crear: ruta base de la máquina + nombre.
    static func rutaNueva(_ base: String?, _ nombre: String) -> String? {
        guard var b = base, !b.isEmpty else { return nil }
        let sep = (b.range(of: "^[A-Za-z]:", options: .regularExpression) != nil || b.contains("\\")) ? "\\" : "/"
        while b.hasSuffix("\\") || b.hasSuffix("/") { b.removeLast() }
        return b + sep + nombre
    }

    // MARK: - Chat

    enum ItemChat: Identifiable, Equatable {
        case mensaje(MensajeChat)
        case orden(Orden)

        var id: String {
            switch self {
            case .mensaje(let m): return "m-" + m.id
            case .orden(let o): return "o-" + o.id
            }
        }

        var creado: String {
            switch self {
            case .mensaje(let m): return m.creado
            case .orden(let o): return o.creado
            }
        }
    }

    /// Mensajes y órdenes por fecha; en un empate va primero el mensaje
    /// (el orquestador explica y luego propone).
    static func mezclar(_ mensajes: [MensajeChat], _ ordenes: [Orden]) -> [ItemChat] {
        let items = mensajes.map(ItemChat.mensaje) + ordenes.map(ItemChat.orden)
        return items.enumerated().sorted { a, b in
            let ta = FechaISO.leer(a.element.creado) ?? .distantPast
            let tb = FechaISO.leer(b.element.creado) ?? .distantPast
            if ta != tb { return ta < tb }
            let ma = { if case .mensaje = a.element { return 0 } else { return 1 } }()
            let mb = { if case .mensaje = b.element { return 0 } else { return 1 } }()
            if ma != mb { return ma < mb }
            return a.offset < b.offset
        }.map(\.element)
    }

    static func estadoOrden(_ e: String) -> (texto: String, tono: TonoProyecto) {
        switch e {
        case "por_aprobar": return ("por aprobar", .morado)
        case "aprobada": return ("aprobada, en cola", .azul)
        case "rechazada": return ("rechazada", .rojo)
        case "en_curso": return ("en curso", .azul)
        case "terminada": return ("terminada", .verde)
        case "fallida": return ("fallida", .rojo)
        default: return (e, .gris)
        }
    }

    static func tituloOrden(_ o: Orden) -> String { "Orden \(o.numero) para \(o.agente)" }

    /// El título corto de la orden (Prompt 42), o "Orden N" si el servidor no lo trae.
    static func tituloCorto(_ o: Orden) -> String {
        let t = o.titulo?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return t.isEmpty ? "Orden \(o.numero)" : t
    }

    /// "Estimado: 1 h a 1 h 30 min · dificultad 4 de 10".
    static func estimadoYDificultad(_ o: Orden) -> String? {
        var partes: [String] = []
        if let e = o.estimado?.trimmingCharacters(in: .whitespaces), !e.isEmpty { partes.append("Estimado: \(e)") }
        if let d = o.dificultad?.trimmingCharacters(in: .whitespaces), !d.isEmpty {
            if let m = d.range(of: #"^\d{1,2}(?:\s*/\s*10)?$"#, options: .regularExpression),
               let n = Int(d[m].prefix { $0.isNumber }), (1...10).contains(n) {
                partes.append("dificultad \(n) de 10")
            } else {
                partes.append("dificultad \(d)")
            }
        }
        return partes.isEmpty ? nil : partes.joined(separator: " · ")
    }

    static func quienDecidio(_ por: String?) -> String? {
        switch por {
        case "web": return "Tú desde la web"
        case "app": return "Tú desde la app"
        case "celular": return "Tú desde el celular"
        case "pc": return "Tú desde la PC"
        case "automatico": return "Automático"
        default: return nil
        }
    }

    /// El texto editado solo cuenta si cambió (si no, se aprueba la propuesta tal cual).
    static func textoEditado(_ o: Orden, _ texto: String) -> String? {
        let t = texto.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty || t == o.texto_propuesto.trimmingCharacters(in: .whitespacesAndNewlines) ? nil : t
    }

    static func motivoValido(_ m: String) -> String? {
        let t = m.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? nil : String(t.prefix(500))
    }

    /// Nota sobre el chat cuando el equipo no corre.
    static func notaChat(_ estado: String) -> String? {
        switch estado {
        case "pausado": return "El equipo está pausado: el orquestador leerá tus mensajes cuando lo reanudes."
        case "detenido": return "El equipo está detenido: el orquestador leerá tus mensajes cuando lo reanudes."
        case "creando": return "Creando el equipo: podrás escribirle al orquestador cuando termine."
        default: return nil
        }
    }

    // MARK: - Reglas

    static let tiposRegla: [(valor: String, texto: String)] = [
        ("idioma", "Idioma"), ("interfaz", "Interfaz"), ("git", "Git"), ("documentacion", "Documentación"),
        ("ordenes", "Órdenes"), ("entrega", "Entrega"), ("herramientas", "Herramientas"), ("pruebas", "Pruebas"),
        ("otra", "Otra"),
    ]

    static func nombreTipo(_ t: String) -> String { tiposRegla.first { $0.valor == t }?.texto ?? t }
}

/// Colores de la etapa 4 (boceto Main): por aprobar morado, trabajando verde,
/// atascado rojo, permiso azul, detenido gris.
enum TonoProyecto { case morado, verde, rojo, azul, gris }

extension EstadoLista {
    var tono: TonoProyecto {
        switch self {
        case .porAprobar: return .morado
        case .permiso: return .azul
        case .atascado: return .rojo
        case .trabajando: return .verde
        case .detenido, .listo: return .gris
        }
    }
}

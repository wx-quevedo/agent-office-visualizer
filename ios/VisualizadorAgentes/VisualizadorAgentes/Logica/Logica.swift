import Foundation

// Lógica pura de la oficina, la ficha y "Dónde quedamos", portada de
// frontend/src/components/{oficina,ficha,donde,permisos}/logica.ts.
// Sin SwiftUI ni red: se prueba en LogicaTests.

// MARK: - Grupos y conteos

enum Grupo { case espera, trabajando, inactivos, cerrados }

enum Cuenta: String, CaseIterable, Identifiable {
    case todas, personal, demo
    var id: String { rawValue }
    var titulo: String {
        switch self {
        case .todas: return "Todas"
        case .personal: return "Personal"
        case .demo: return "Demo Org"
        }
    }
}

enum Logica {
    static let cerradoVisible: TimeInterval = 3600

    /// Estados 13 y 14: te esperan (permiso o respuesta).
    static func grupo(_ numero: Int) -> Grupo {
        if numero == 13 || numero == 14 { return .espera }
        if numero == 21 { return .cerrados }
        if numero == 11 || numero >= 18 { return .inactivos }
        return .trabajando
    }

    static func esVisible(_ a: Agente, ahora: Date) -> Bool {
        guard a.estado.numero == 21 else { return true }
        if a.pregunta_pendiente != nil { return true }
        guard let desde = FechaISO.leer(a.cierre?.desde ?? a.estado.desde) else { return true }
        return ahora.timeIntervalSince(desde) < cerradoVisible
    }

    static func filtrar(_ agentes: [Agente], cuenta: Cuenta, ahora: Date) -> [Agente] {
        agentes.filter { a in
            esVisible(a, ahora: ahora) && (cuenta == .todas || a.agente.cuenta == cuenta.rawValue)
        }
    }

    static func estaAtascado(_ a: Agente) -> Bool { a.atasco != nil && a.estado.numero != 21 }

    /// Lo que espera por ti: permisos, preguntas y atascos (la insignia de Decisiones).
    static func pendientes(_ agentes: [Agente]) -> Int {
        agentes.filter { a in
            a.estado.numero != 21 && (grupo(a.estado.numero) == .espera || a.atasco != nil)
        }.count
    }

    /// "5 trabajando · 2 te esperan · 1 atascado".
    static func resumenConteo(_ agentes: [Agente]) -> String {
        var trabajando = 0, esperan = 0, atascados = 0
        for a in agentes {
            if estaAtascado(a) { atascados += 1; continue }
            switch grupo(a.estado.numero) {
            case .espera: esperan += 1
            case .trabajando: trabajando += 1
            default: break
            }
        }
        var partes = ["\(trabajando) trabajando", "\(esperan) \(esperan == 1 ? "te espera" : "te esperan")"]
        if atascados > 0 { partes.append("\(atascados) \(atascados == 1 ? "atascado" : "atascados")") }
        return partes.joined(separator: " · ")
    }

    /// Los que te esperan (permiso o pregunta), el que más lleva esperando primero.
    static func teEsperan(_ agentes: [Agente]) -> [Agente] {
        agentes.filter { grupo($0.estado.numero) == .espera }
            .sorted { (FechaISO.leer($0.estado.desde) ?? .distantFuture) < (FechaISO.leer($1.estado.desde) ?? .distantFuture) }
    }

    /// Orden de la lista: te esperan, atascados, trabajando, inactivos, cerrados.
    static func ordenLista(_ agentes: [Agente]) -> [Agente] {
        func rango(_ a: Agente) -> Int {
            if grupo(a.estado.numero) == .espera { return 0 }
            if estaAtascado(a) { return 1 }
            switch grupo(a.estado.numero) {
            case .trabajando: return 2
            case .inactivos: return 3
            default: return 4
            }
        }
        return agentes.sorted { x, y in
            let (rx, ry) = (rango(x), rango(y))
            if rx != ry { return rx < ry }
            let dx = FechaISO.leer(x.estado.desde) ?? .distantFuture
            let dy = FechaISO.leer(y.estado.desde) ?? .distantFuture
            if dx != dy { return dx < dy }
            return x.id < y.id
        }
    }

    // MARK: - Textos

    static func nombreCarpeta(_ ruta: String?) -> String {
        guard let ruta, !ruta.isEmpty else { return "Sin proyecto" }
        let partes = ruta.split(whereSeparator: { $0 == "/" || $0 == "\\" })
        return partes.last.map(String.init) ?? ruta
    }

    static func nombre(_ a: Agente) -> String { nombreCarpeta(a.agente.proyecto) }

    /// "SkyNest" -> "SK", "vive-demo" -> "VB", "visualizador-agentes" -> "VA".
    static func iniciales(_ nombre: String) -> String {
        var separado = ""
        var previo: Character?
        for ch in nombre {
            if let p = previo, p.isLowercase, ch.isUppercase { separado.append(" ") }
            separado.append(ch)
            previo = ch
        }
        let palabras = separado
            .split(whereSeparator: { " _-.".contains($0) })
            .map(String.init)
            .filter { $0.contains(where: { $0.isLetter || $0.isNumber }) }
        if palabras.count >= 2 {
            return (String(palabras[0].prefix(1)) + String(palabras[1].prefix(1))).uppercased()
        }
        let una = (palabras.first ?? nombre).filter { $0.isLetter || $0.isNumber }
        let r = String(una.prefix(2)).uppercased()
        return r.isEmpty ? "?" : r
    }

    static func textoCuenta(_ cuenta: String?) -> String? {
        switch cuenta {
        case "demo": return "Demo Org"
        case "personal": return "Personal"
        default: return nil
        }
    }

    /// "claude-opus-5-5[1m]" -> "Opus 5.5".
    static func nombreModelo(_ modelo: String?) -> String? {
        guard let modelo, !modelo.isEmpty else { return nil }
        let patron = #"(opus|sonnet|haiku|fable)[-_ ]?(\d+)(?:[-_.](\d{1,2}))?(?!\d)"#
        guard let re = try? NSRegularExpression(pattern: patron, options: .caseInsensitive),
              let m = re.firstMatch(in: modelo, range: NSRange(modelo.startIndex..., in: modelo)) else { return modelo }
        func g(_ i: Int) -> String? {
            guard let r = Range(m.range(at: i), in: modelo) else { return nil }
            return String(modelo[r])
        }
        let familia = (g(1) ?? "").lowercased()
        let f = familia.prefix(1).uppercased() + familia.dropFirst()
        if let menor = g(3) { return "\(f) \(g(2) ?? "").\(menor)" }
        return "\(f) \(g(2) ?? "")"
    }

    static func nombreMaquina(_ m: String?) -> String? {
        guard let m, !m.isEmpty else { return nil }
        return m.prefix(1).uppercased() + m.dropFirst()
    }

    /// "Personal · Opus 5.5 · Alienware".
    static func subtitulo(_ a: Agente) -> String {
        [textoCuenta(a.agente.cuenta), nombreModelo(a.agente.modelo), nombreMaquina(a.agente.maquina)]
            .compactMap { $0 }.joined(separator: " · ")
    }

    static func miles(_ n: Double?) -> String {
        guard let n, n.isFinite else { return "—" }
        let s = String(Int(n.rounded()))
        var r = ""
        for (i, ch) in s.reversed().enumerated() {
            if i > 0 && i % 3 == 0 && ch != "-" { r.append("\u{00A0}") }
            r.append(ch)
        }
        return String(r.reversed())
    }

    /// "312 k" para cifras grandes, el número completo para las chicas.
    static func milesCorto(_ n: Double?) -> String {
        guard let n, n.isFinite else { return "—" }
        if n >= 1_000_000 { return String(format: "%.1f M", n / 1_000_000).replacingOccurrences(of: ".", with: ",") }
        if n >= 10_000 { return "\(Int((n / 1000).rounded())) k" }
        return miles(n)
    }

    /// "45 s", "34 min", "4 h 35 min".
    static func tiempoCorto(_ seg: Double?) -> String {
        guard let seg, seg.isFinite else { return "—" }
        let s = max(0, Int(seg))
        if s < 60 { return "\(s) s" }
        if s < 3600 { return "\(s / 60) min" }
        let m = (s % 3600) / 60
        return m > 0 ? "\(s / 3600) h \(m) min" : "\(s / 3600) h"
    }

    /// Reloj "2:14" o "1:05:09".
    static func reloj(_ seg: Double?) -> String {
        guard let seg, seg.isFinite else { return "—" }
        let s = max(0, Int(seg))
        if s >= 3600 { return String(format: "%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60) }
        return String(format: "%d:%02d", s / 60, s % 60)
    }

    static func segundosDesde(_ iso: String?, ahora: Date) -> Double? {
        guard let d = FechaISO.leer(iso) else { return nil }
        return max(0, ahora.timeIntervalSince(d))
    }

    static func hace(_ iso: String?, ahora: Date) -> String {
        guard let s = segundosDesde(iso, ahora: ahora) else { return "—" }
        return "hace \(tiempoCorto(s))"
    }

    static func horaMinuto(_ iso: String?, zona: TimeZone = .current) -> String {
        guard let d = FechaISO.leer(iso) else { return "—" }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zona
        let c = cal.dateComponents([.hour, .minute], from: d)
        return String(format: "%02d:%02d", c.hour ?? 0, c.minute ?? 0)
    }

    static let meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]

    /// "Hoy 10:36", "Ayer 18:20" o "9 oct 18:20".
    static func cuando(_ iso: String?, ahora: Date, zona: TimeZone = .current) -> String {
        guard let d = FechaISO.leer(iso) else { return "—" }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zona
        let dias = cal.dateComponents([.day], from: cal.startOfDay(for: d), to: cal.startOfDay(for: ahora)).day ?? 0
        let hm = horaMinuto(iso, zona: zona)
        if dias == 0 { return "Hoy \(hm)" }
        if dias == 1 { return "Ayer \(hm)" }
        let c = cal.dateComponents([.day, .month], from: d)
        return "\(c.day ?? 0) \(meses[(c.month ?? 1) - 1]) \(hm)"
    }

    static func esHoy(_ iso: String?, ahora: Date, zona: TimeZone = .current) -> Bool {
        guard let d = FechaISO.leer(iso) else { return false }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zona
        return cal.isDate(d, inSameDayAs: ahora)
    }

    static func recortar(_ texto: String, _ max: Int) -> String {
        let t = texto.split(whereSeparator: \.isWhitespace).joined(separator: " ")
        return t.count > max ? String(t.prefix(max - 1)) + "…" : t
    }

    // MARK: - Lo que hace o pide un agente

    static func evidencia(_ a: Agente, _ clave: String) -> String? {
        a.espera?.evidencia?[clave]?.texto
    }

    /// Archivo, comando o herramienta actual.
    static func detalleActual(_ a: Agente) -> String {
        if let e = a.espera_detalle { return e.texto }
        let h = evidencia(a, "herramienta"), c = evidencia(a, "comando")
        if h != nil || c != nil { return [h, c].compactMap { $0 }.joined(separator: ": ") }
        let eventos = a.eventos_recientes ?? []
        if let actual = a.herramienta_actual {
            if let e = eventos.first(where: { $0.tipo == "pre_tool_use" && $0.herramienta == actual }), let d = e.detalle {
                return "\(actual): \(d)"
            }
            return actual
        }
        return eventos.first(where: { $0.detalle != nil })?.detalle ?? a.estado.nombre
    }

    /// Resumen del agente auxiliar, si ya está listo.
    static func resumen(_ a: Agente, _ tipo: String) -> String? {
        guard let r = a.resumenes?[tipo], r.estado == "listo", let t = r.texto, !t.isEmpty else { return nil }
        return t
    }

    /// Lo que pide en una frase (lista de "Te esperan" y ficha).
    static func loQuePide(_ a: Agente) -> String {
        if a.estado.numero == 13 {
            if let r = resumen(a, "permiso") { return r }
            if let p = a.permiso { return fraseDePermiso(p.herramienta, p.detalle) }
            let h = evidencia(a, "herramienta") ?? a.herramienta_actual ?? ""
            return h.isEmpty ? "Permiso sin detalle" : fraseDePermiso(h, evidencia(a, "comando") ?? "")
        }
        if let r = resumen(a, "pregunta") { return r }
        if let q = a.pregunta_pendiente { return recortar(q, 90) }
        return "Espera tu respuesta"
    }

    /// Línea de estado de la lista con su tono.
    static func estadoCorto(_ a: Agente, ahora: Date) -> (texto: String, tono: Tono) {
        if a.estado.numero == 13 { return ("Te pide permiso", .azul) }
        if a.estado.numero == 14 { return ("Espera tu respuesta", .naranja) }
        if let at = a.atasco, a.estado.numero != 21 {
            let s = segundosDesde(at.desde, ahora: ahora)
            return (s.map { "Parece atascado · \(tiempoCorto($0))" } ?? "Parece atascado", .rojo)
        }
        switch grupo(a.estado.numero) {
        case .trabajando:
            let s = a.trabajo_continuo_s ?? segundosDesde(a.estado.desde, ahora: ahora)
            return (s.map { "Trabajando · \(tiempoCorto($0))" } ?? "Trabajando", .verde)
        case .cerrados:
            return ("Cerrado", .gris)
        default:
            if a.estado.numero == 19 || a.estado.numero == 20 { return ("Descansando", .gris) }
            return ("Listo", .gris)
        }
    }

    // MARK: - Permisos

    /// La oficina todavía puede decidir esta solicitud.
    static func sePuedeDecidir(_ p: Permiso?) -> Bool {
        guard let p else { return false }
        return p.estado == "pendiente" && p.esperando
    }

    static func textoSinBotones(_ p: Permiso) -> String {
        let desde = p.dispositivo == "celular" ? "el celular" : "la PC"
        switch p.estado {
        case "aprobada": return "Aprobado desde \(desde)."
        case "rechazada": return "Rechazado desde \(desde)" + (p.motivo.map { ": \($0)" } ?? ".")
        case "resuelta_fuera": return "Ya se respondió en VS Code."
        default: return "Responde en VS Code."
        }
    }

    /// El comando borra o sube algo (misma regla que la web, lista de /permisos/config).
    static func pideConfirmacion(herramienta: String, detalle: String, lista: [String]) -> Bool {
        let h = herramienta.lowercased()
        guard h == "bash" || h == "powershell" else { return false }
        let re = try! NSRegularExpression(pattern: #"\|\||&&|;|\||\r?\n|\(|\)|`|\$\("#)
        let texto = detalle.lowercased()
        let marcado = re.stringByReplacingMatches(in: texto, range: NSRange(texto.startIndex..., in: texto), withTemplate: "\u{0}")
        let partes = marcado.split(separator: "\u{0}").map { parte -> String in
            var p = parte.trimmingCharacters(in: .whitespaces)
            for pre in ["sudo ", "exec ", "call "] where p.hasPrefix(pre) {
                p = String(p.dropFirst(pre.count)).trimmingCharacters(in: .whitespaces)
                break
            }
            return p
        }.filter { !$0.isEmpty }
        for entrada in lista {
            let c = entrada.trimmingCharacters(in: .whitespaces).lowercased()
            if c.isEmpty { continue }
            for parte in partes {
                if parte == c || parte.hasPrefix(c + " ") { return true }
                if !c.contains(" ") && parte.split(whereSeparator: \.isWhitespace).map(String.init).contains(c) { return true }
            }
        }
        return false
    }

    /// Lo que pide un permiso, en una frase (el comando va debajo).
    static func fraseDePermiso(_ herramienta: String, _ detalle: String) -> String {
        let h = herramienta.lowercased()
        func hay(_ patron: String) -> Bool {
            detalle.range(of: patron, options: [.regularExpression, .caseInsensitive]) != nil
        }
        if h == "bash" || h == "powershell" {
            if hay(#"\bgit\s+reset\s+--hard\b"#) { return "Quiere descartar cambios del repositorio (git reset --hard)." }
            if hay(#"\b(rm|rmdir|del|rd|remove-item|git\s+clean)\b"#) { return "Quiere borrar archivos o carpetas." }
            if hay(#"\bgit\s+push\b"#) { return "Quiere subir los cambios al repositorio remoto (git push)." }
            if hay(#"\b(deploy|desplegar|publish)\b"#) { return "Quiere desplegar o publicar." }
            if hay(#"\bgit\s+commit\b"#) { return "Quiere guardar los cambios en un commit." }
            if hay(#"\b(npm|pnpm|yarn|bun)\s+(i|install|add)\b|\b(pip|uv)\s+(install|add|sync)\b"#) { return "Quiere instalar dependencias." }
            return "Quiere ejecutar un comando en \(h == "bash" ? "la terminal" : "PowerShell")."
        }
        let primero = String(detalle.split(whereSeparator: \.isWhitespace).first ?? "")
        switch h {
        case "edit", "multiedit": return "Quiere editar \(nombreCarpeta(primero))."
        case "write": return "Quiere crear o reemplazar \(nombreCarpeta(primero))."
        case "notebookedit": return "Quiere editar un cuaderno."
        case "webfetch": return "Quiere abrir una página web."
        case "websearch": return "Quiere buscar en la web."
        default: break
        }
        if h.hasPrefix("mcp__") {
            let partes = herramienta.components(separatedBy: "__")
            var servidor = partes.count > 1 ? partes[1] : ""
            if let r = servidor.range(of: #"^plugin_[^_]+_"#, options: .regularExpression) { servidor.removeSubrange(r) }
            let accion = partes.count > 2 ? partes[2] : ""
            return "Quiere usar \(accion.isEmpty ? "una herramienta" : accion) de \(servidor.isEmpty ? "un conector" : servidor)."
        }
        return "Quiere usar \(herramienta)."
    }

    // MARK: - Ficha

    struct AhoraMismo: Equatable {
        var texto: String
        var tiempo: String
        var razonable: String?
    }

    static func ahoraMismo(_ a: Agente, ahora: Date) -> AhoraMismo {
        if let c = a.cierre {
            return AhoraMismo(texto: "Sesión cerrada (\(c.motivo))", tiempo: reloj(segundosDesde(c.desde, ahora: ahora)), razonable: nil)
        }
        if let e = a.espera_detalle {
            let lim = e.limite_min.map { "Tiempo razonable para esto: hasta \(Int($0)) min" }
            return AhoraMismo(texto: e.base, tiempo: reloj(e.segundos), razonable: lim)
        }
        return AhoraMismo(texto: a.estado.nombre, tiempo: reloj(segundosDesde(a.estado.desde, ahora: ahora)), razonable: nil)
    }

    struct Cifra: Equatable, Identifiable {
        var titulo: String
        var valor: String
        var alerta = false
        var id: String { titulo }
    }

    static func tokensHoy(_ consumo: Consumo?, sesion: String) -> Double? {
        guard let consumo else { return nil }
        return consumo.por_sesion.first(where: { $0.session_id == sesion })?.tokens_salida ?? 0
    }

    static func cifras(_ a: Agente, tokens: Double?, ahora: Date) -> [Cifra] {
        let continuo = a.trabajo_continuo_s ?? 0
        let errores = a.indicadores?.errores_seguidos ?? 0
        let tercera: Cifra
        if let at = a.atasco {
            tercera = Cifra(titulo: "Atasco", valor: tiempoCorto(segundosDesde(at.desde, ahora: ahora)), alerta: true)
        } else if errores > 0 {
            tercera = Cifra(titulo: "Errores", valor: "\(errores) \(errores == 1 ? "seguido" : "seguidos")", alerta: errores >= 3)
        } else {
            tercera = Cifra(titulo: "Atascos", valor: "Ninguno")
        }
        return [
            Cifra(titulo: "Continuo", valor: continuo > 0 ? tiempoCorto(continuo) : "—"),
            Cifra(titulo: "Tokens hoy", valor: milesCorto(tokens)),
            tercera,
        ]
    }

    static func resultado(_ r: String) -> (texto: String, tono: Tono) {
        switch r {
        case "completado": return ("Completado", .verde)
        case "esperando": return ("Te esperó", .azul)
        case "interrumpido": return ("Interrumpido", .naranja)
        case "error": return ("Con error", .rojo)
        case "en_curso": return ("En curso", .azul)
        default: return (r, .gris)
        }
    }

    static func turnosDeHoy(_ turnos: [Turno], ahora: Date, zona: TimeZone = .current) -> [Turno] {
        turnos.filter { esHoy($0.inicio, ahora: ahora, zona: zona) }
    }
}

enum Tono { case azul, naranja, rojo, verde, gris }

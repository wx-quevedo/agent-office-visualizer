import Foundation

// Bandejas de Decisiones e Ideas (Prompt 33). Sin SwiftUI ni red: se prueba en BandejasTests.

enum LogicaBandejas {
    static let ordenTipo = ["permiso": 0, "pregunta": 1, "atasco": 2]

    /// Lo más urgente arriba: permisos, preguntas, atascos; dentro de cada tipo, lo que
    /// espera hace más tiempo (el backend ya las manda así; se reordena por si acaso).
    static func ordenar(_ items: [Decision]) -> [Decision] {
        items.sorted { a, b in
            let (ta, tb) = (ordenTipo[a.tipo] ?? 9, ordenTipo[b.tipo] ?? 9)
            if ta != tb { return ta < tb }
            let da = FechaISO.leer(a.desde) ?? .distantFuture
            let db = FechaISO.leer(b.desde) ?? .distantFuture
            if da != db { return da < db }
            return a.id < b.id
        }
    }

    static func tono(_ tipo: String) -> Tono {
        switch tipo {
        case "permiso": return .azul
        case "pregunta": return .naranja
        case "atasco": return .rojo
        default: return .gris
        }
    }

    /// "PERMISO · SkyNest".
    static func titulo(_ d: Decision) -> String {
        let tipo: String
        switch d.tipo {
        case "permiso": tipo = "Permiso"
        case "pregunta": tipo = "Pregunta"
        case "atasco": tipo = "Atascado"
        default: tipo = d.tipo.capitalized
        }
        return "\(tipo) · \(d.proyecto ?? Logica.nombreCarpeta(d.carpeta))"
    }

    /// La frase del auxiliar si existe; si no, una frase armada aquí.
    static func frase(_ d: Decision) -> String {
        if let r = d.resumen, !r.isEmpty { return r }
        switch d.tipo {
        case "permiso":
            return Logica.fraseDePermiso(d.permiso?.herramienta ?? "", d.detalle ?? "")
        case "pregunta":
            return d.pregunta?.preguntas.first?.texto ?? d.pregunta?.texto ?? d.detalle ?? "Te hizo una pregunta."
        case "atasco":
            return d.atasco?.motivo ?? d.detalle ?? "Parece atascado."
        default:
            return d.detalle ?? ""
        }
    }

    /// El detalle técnico que va debajo de la frase (nil si repetiría la frase).
    static func detalleTecnico(_ d: Decision) -> String? {
        let t: String?
        switch d.tipo {
        case "permiso":
            let h = d.permiso?.herramienta
            let det = d.detalle
            t = [h, det].compactMap { $0?.isEmpty == false ? $0 : nil }.joined(separator: ": ")
        case "atasco":
            t = [d.atasco?.ultimo_intento, d.atasco?.ultimo_error].compactMap { $0?.isEmpty == false ? $0 : nil }
                .joined(separator: "\n")
        default:
            t = nil
        }
        guard let t, !t.isEmpty, t != frase(d) else { return nil }
        return t
    }

    /// Solo con la solicitud esperando se puede aprobar o rechazar desde la app.
    static func sePuedeDecidir(_ d: Decision) -> Bool {
        d.tipo == "permiso" && d.permiso?.id != nil && d.permiso?.esperando == true
            && (d.permiso?.estado == nil || d.permiso?.estado == "pendiente")
    }

    /// "Respóndela en la PC (Alienware)".
    static func dondeResponder(_ d: Decision) -> String {
        if let m = Logica.nombreMaquina(d.maquina) { return "Respóndela en la PC (\(m))." }
        return "Respóndela en la PC."
    }

    static func hace(_ d: Decision, ahora: Date) -> String {
        if let s = Logica.segundosDesde(d.desde, ahora: ahora) { return Logica.tiempoCorto(s) }
        return d.hace_s.map(Logica.tiempoCorto) ?? ""
    }

    // MARK: - Resueltas hoy

    static func tono(resuelta r: Resuelta) -> Tono {
        let c = (r.como ?? "").lowercased()
        if c.hasPrefix("aprobad") { return .verde }
        if c.hasPrefix("rechazad") { return .rojo }
        if c.contains("venci") { return .naranja }
        return .gris
    }

    /// "SkyNest · Bash: rm -rf build · desde app iOS".
    static func texto(resuelta r: Resuelta) -> String {
        var partes: [String] = []
        if let p = r.proyecto, !p.isEmpty { partes.append(p) }
        if let t = r.texto, !t.isEmpty { partes.append(Logica.recortar(t, 80)) }
        if let q = r.quien, !q.isEmpty { partes.append("desde \(q == "PC" ? "la PC" : q)") }
        return partes.joined(separator: " · ")
    }

    // MARK: - Ideas

    static let sinProyecto = "Sin proyecto todavía"

    /// Texto listo para guardar (sin espacios de más), o nil si está vacío.
    static func textoIdea(_ t: String) -> String? {
        let limpio = t.trimmingCharacters(in: .whitespacesAndNewlines)
        return limpio.isEmpty ? nil : String(limpio.prefix(2000))
    }

    /// Proyectos del selector: los del backend sin repetir (sin distinguir mayúsculas),
    /// en orden alfabético. "Sin proyecto todavía" lo agrega la vista como nil.
    static func proyectos(_ lista: [String]) -> [String] {
        var vistos = Set<String>()
        return lista.filter { !$0.isEmpty && vistos.insert($0.lowercased()).inserted }
            .sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
    }

    static func estado(_ i: Idea) -> (texto: String, tono: Tono) {
        switch i.estado {
        case "archivada": return ("Archivada", .gris)
        case "asignada": return ("Asignada", .verde)
        default: return i.proyecto == nil ? ("Sin asignar", .naranja) : ("Nueva", .azul)
        }
    }

    /// Las guardadas: las más recientes primero, sin las archivadas.
    static func guardadas(_ ideas: [Idea]) -> [Idea] {
        ideas.filter { $0.estado != "archivada" }.sorted {
            (FechaISO.leer($0.creada) ?? .distantPast) > (FechaISO.leer($1.creada) ?? .distantPast)
        }
    }
}

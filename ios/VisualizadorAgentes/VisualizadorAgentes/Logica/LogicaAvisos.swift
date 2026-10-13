import Foundation

// Avisos de los orquestadores (Prompt 43), con las mismas reglas que la web
// (frontend/src/components/avisos/logicaOrquestador.ts). Se prueba en AvisosTests.

enum AccionAviso: String {
    case ignorar, esperar
}

enum LogicaAvisos {
    /// Solo se recuerdan las últimas claves anunciadas.
    static let maxAvisadas = 200
    static let claveAvisadas = "avisosOrquestadorAvisados"

    /// Claves de una lectura contra las ya anunciadas. En la primera lectura no se
    /// anuncia nada (solo se anotan); después, cada clave nueva se anuncia una vez.
    static func revisar(_ claves: [String], avisadas: [String], primera: Bool) -> (nuevas: [String], avisadas: [String]) {
        let ya = Set(avisadas)
        var sinVer: [String] = []
        for c in claves where !ya.contains(c) && !sinVer.contains(c) { sinVer.append(c) }
        let todas = avisadas + sinVer
        return (primera ? [] : sinVer, Array(todas.suffix(maxAvisadas)))
    }

    /// Insignia de Decisiones: lo que tiene una acción posible. `decisiones_pendientes`
    /// ya cuenta permisos, atascos y órdenes (sin proyectos de prueba); se suman las
    /// preguntas de los orquestadores, que se responden en el chat.
    static func insignia(pendientes: Int, avisos: [AvisoOrquestador]) -> Int {
        pendientes + avisos.filter { $0.tipo == "pregunta" }.count
    }

    /// Preguntas de los orquestadores, la más antigua primero.
    static func preguntas(_ avisos: [AvisoOrquestador]) -> [AvisoOrquestador] {
        avisos.filter { $0.tipo == "pregunta" }
            .sorted { (FechaISO.leer($0.desde) ?? .distantPast) < (FechaISO.leer($1.desde) ?? .distantPast) }
    }

    /// El aviso de una orden (si no se ignoró ni está en espera).
    static func deOrden(_ avisos: [AvisoOrquestador], _ ordenId: String) -> AvisoOrquestador? {
        avisos.first { $0.clave == "orden:" + ordenId }
    }

    /// A qué apunta una clave en el chat: el id del elemento ("m-<id>" u "o-<id>").
    static func itemChat(_ clave: String?) -> String? {
        guard let clave, let i = clave.firstIndex(of: ":") else { return nil }
        let tipo = clave[..<i], id = clave[clave.index(after: i)...]
        guard !id.isEmpty else { return nil }
        switch tipo {
        case "mensaje": return "m-" + id
        case "orden": return "o-" + id
        default: return nil
        }
    }

    /// Título, cuerpo e identificador de la notificación nativa de un aviso.
    static func contenido(_ a: AvisoOrquestador) -> (id: String, titulo: String, cuerpo: String) {
        (a.clave, titulo(a), Logica.recortar(MarkdownLigero.sinHTML(a.texto), 240))
    }

    /// No se notifica el aviso de un proyecto cuyo chat ya está a la vista.
    static func debeNotificar(_ a: AvisoOrquestador, chatAbierto: String?) -> Bool {
        a.proyecto_id != chatAbierto
    }

    /// "prueba-44" se marca solo como proyecto de prueba (misma regla que el servidor).
    static func esNombrePrueba(_ nombre: String) -> Bool {
        nombre.trimmingCharacters(in: .whitespaces).lowercased().hasPrefix("prueba-")
    }

    /// "avisos-44: el orquestador te hizo una pregunta".
    static func titulo(_ a: AvisoOrquestador) -> String {
        "\(a.proyecto): el orquestador \(a.tipo == "orden" ? "propone una orden" : "te hizo una pregunta")"
    }

    static func leerAvisadas(_ d: UserDefaults = .standard) -> [String] {
        d.stringArray(forKey: claveAvisadas) ?? []
    }

    static func guardarAvisadas(_ v: [String], _ d: UserDefaults = .standard) {
        d.set(Array(v.suffix(maxAvisadas)), forKey: claveAvisadas)
    }
}

import Foundation

/// La sesión de este iPhone: la cookie de 30 días que da POST /auth/entrar
/// (la misma que usa la web). Se guarda en el Llavero, nunca en UserDefaults.
struct Credencial: Codable, Equatable, Sendable {
    var servidor: URL
    var cookieNombre: String
    var cookieValor: String
    var expira: Date?

    /// Cookie para el WKWebView de la oficina 3D.
    func cookie() -> HTTPCookie? {
        guard let host = servidor.host() else { return nil }
        var p: [HTTPCookiePropertyKey: Any] = [
            .name: cookieNombre,
            .value: cookieValor,
            .domain: host,
            .path: "/",
        ]
        if servidor.scheme == "https" { p[.secure] = "TRUE" }
        if let expira { p[.expires] = expira }
        return HTTPCookie(properties: p)
    }
}

enum ErrorAPI: Error, Equatable {
    /// Sin sesión o la sesión venció (401 fuera de /auth/entrar).
    case sinSesion
    case contrasenaIncorrecta
    case demasiadosIntentos(segundos: Int)
    case servidor(codigo: Int, mensaje: String?)
    case red
    case datos

    var mensaje: String {
        switch self {
        case .sinSesion: return "La sesión terminó. Vuelve a entrar."
        case .contrasenaIncorrecta: return "Contraseña incorrecta."
        case .demasiadosIntentos(let s): return "Demasiados intentos. Espera \(s) s antes de volver a probar."
        case .servidor(_, let m?): return m
        case .servidor(let c, nil): return "El servidor respondió con un error (HTTP \(c))."
        case .red: return "No hay conexión con el servidor."
        case .datos: return "El servidor envió datos que la app no entiende."
        }
    }
}

/// Cliente del backend (FastAPI en /api/v1). Manda la cookie de sesión y, en
/// las peticiones que cambian algo, el encabezado X-Visualizador: 1 (CSRF), como la web.
final class ClienteAPI: @unchecked Sendable {
    static let servidorPorDefecto = URL(string: "https://agents.example.com")!
    static let nombresCookie = ["__Host-visualizador_sesion", "visualizador_sesion"]

    let servidor: URL
    let credencial: Credencial?
    private let sesion: URLSession

    init(servidor: URL, credencial: Credencial? = nil, sesion: URLSession? = nil) {
        self.servidor = servidor
        self.credencial = credencial
        self.sesion = sesion ?? ClienteAPI.sesionNueva()
    }

    convenience init(credencial: Credencial) {
        self.init(servidor: credencial.servidor, credencial: credencial)
    }

    /// Sin almacén de cookies propio: la cookie va a mano desde el Llavero.
    static func sesionNueva(protocolos: [AnyClass] = []) -> URLSession {
        let c = URLSessionConfiguration.ephemeral
        c.httpCookieStorage = nil
        c.httpShouldSetCookies = false
        c.timeoutIntervalForRequest = 15
        c.waitsForConnectivity = false
        if !protocolos.isEmpty { c.protocolClasses = protocolos + (c.protocolClasses ?? []) }
        return URLSession(configuration: c)
    }

    /// "agents.example.com" o "https://agents.example.com/" -> https://agents.example.com
    static func normalizarServidor(_ texto: String) -> URL? {
        var t = texto.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, !t.contains(" ") else { return nil }
        if !t.lowercased().hasPrefix("http://") && !t.lowercased().hasPrefix("https://") {
            // Otro esquema (ftp://, file://...) no es un servidor de la oficina.
            if t.contains("://") { return nil }
            t = "https://" + t
        }
        while t.hasSuffix("/") { t.removeLast() }
        guard let u = URL(string: t), let host = u.host(), !host.isEmpty,
              u.scheme == "https" || u.scheme == "http" else { return nil }
        return u
    }

    func url(_ ruta: String) -> URL {
        URL(string: servidor.absoluteString + ruta)!
    }

    // MARK: - Acceso

    /// POST /auth/entrar: contraseña -> sesión de 30 días de este dispositivo.
    func entrar(contrasena: String, dispositivo: String) async throws -> Credencial {
        let cuerpo = try JSONSerialization.data(withJSONObject: [
            "contrasena": contrasena, "dispositivo": dispositivo,
        ])
        let (datos, r) = try await enviar("/api/v1/auth/entrar", metodo: "POST", cuerpo: cuerpo, conSesion: false)
        switch r.statusCode {
        case 200:
            break
        case 401:
            throw ErrorAPI.contrasenaIncorrecta
        case 429:
            throw ErrorAPI.demasiadosIntentos(segundos: Self.segundosDeEspera(datos, r))
        default:
            throw ErrorAPI.servidor(codigo: r.statusCode, mensaje: Self.mensajeDeError(datos))
        }
        let encabezados = r.allHeaderFields.reduce(into: [String: String]()) { d, kv in
            if let k = kv.key as? String, let v = kv.value as? String { d[k] = v }
        }
        let cookies = HTTPCookie.cookies(withResponseHeaderFields: encabezados, for: url("/"))
        guard let c = cookies.first(where: { Self.nombresCookie.contains($0.name) }) else {
            throw ErrorAPI.servidor(codigo: r.statusCode, mensaje: "El servidor no devolvió una sesión.")
        }
        return Credencial(servidor: servidor, cookieNombre: c.name, cookieValor: c.value, expira: c.expiresDate)
    }

    /// POST /auth/salir: cierra esta sesión en el servidor (si hay red).
    func salir() async {
        _ = try? await enviar("/api/v1/auth/salir", metodo: "POST", cuerpo: nil, conSesion: true)
    }

    // MARK: - Lecturas

    func estado() async throws -> EstadoOficina { try await leer("/api/v1/agents/state") }

    func historial(sesion id: String, porPagina: Int = 20) async throws -> Historial {
        let enc = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await leer("/api/v1/agents/\(enc)/historial?por_pagina=\(porPagina)")
    }

    func consumo() async throws -> Consumo { try await leer("/api/v1/consumo") }

    func proyectos() async throws -> [ProyectoApi] {
        let r: ProyectosRespuesta = try await leer("/api/v1/proyectos")
        return r.proyectos
    }

    func configPermisos() async throws -> ConfigPermisos { try await leer("/api/v1/permisos/config") }

    // MARK: - Cambios

    /// El mismo endpoint que la web: aprobar o rechazar una solicitud de permiso.
    /// Queda registrado como "app iOS".
    func decidir(permiso id: String, aprobar: Bool, motivo: String? = nil) async throws -> Permiso {
        var cuerpo: [String: Any] = ["decision": aprobar ? "aprobar" : "rechazar", "dispositivo": "app"]
        if let m = motivo?.trimmingCharacters(in: .whitespacesAndNewlines), !m.isEmpty { cuerpo["motivo"] = m }
        let enc = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        let (datos, r) = try await enviar(
            "/api/v1/permisos/solicitudes/\(enc)/decision", metodo: "POST",
            cuerpo: try JSONSerialization.data(withJSONObject: cuerpo), conSesion: true)
        try Self.comprobar(datos, r)
        return try Self.decodificar(datos)
    }

    /// Latido de presencia (la app abierta cuenta como "celular", igual que la web en el teléfono).
    func presencia(cliente: String) async throws {
        let cuerpo = try JSONSerialization.data(withJSONObject: ["cliente": cliente, "dispositivo": "celular"])
        let (datos, r) = try await enviar("/api/v1/agents/presence", metodo: "POST", cuerpo: cuerpo, conSesion: true)
        try Self.comprobar(datos, r)
    }

    // MARK: - Bandejas (Prompt 33)

    func decisiones() async throws -> Bandeja { try await leer("/api/v1/decisiones") }

    /// "Ya lo vi": saca el atasco de la bandeja sin tocar al agente.
    func atascoVisto(_ id: String) async throws {
        _ = try await cambiar("/api/v1/decisiones/atascos/visto", "POST", ["id": id, "dispositivo": "app"])
    }

    func ideas(archivadas: Bool = false) async throws -> IdeasRespuesta {
        try await leer("/api/v1/ideas" + (archivadas ? "?archivadas=true" : ""))
    }

    func crearIdea(texto: String, proyecto: String?, dictada: Bool) async throws -> Idea {
        var cuerpo: [String: Any] = ["texto": texto, "origen": dictada ? "dictada" : "escrita"]
        if let proyecto { cuerpo["proyecto"] = proyecto }
        return try Self.decodificar(try await cambiar("/api/v1/ideas", "POST", cuerpo))
    }

    /// Cambia el proyecto de una idea (nil: "Sin proyecto todavía").
    func cambiarProyecto(idea id: String, proyecto: String?) async throws -> Idea {
        let cuerpo: [String: Any] = ["proyecto": proyecto.map { $0 as Any } ?? NSNull()]
        return try Self.decodificar(try await cambiar("/api/v1/ideas/\(Self.ruta(id))", "PATCH", cuerpo))
    }

    func archivar(idea id: String, archivar: Bool = true) async throws -> Idea {
        try Self.decodificar(try await cambiar("/api/v1/ideas/\(Self.ruta(id))/archivar", "POST", ["archivar": archivar]))
    }

    private static func ruta(_ id: String) -> String {
        id.addingPercentEncoding(withAllowedCharacters: .alphanumerics.union(CharacterSet(charactersIn: "-_."))) ?? id
    }

    private func cambiar(_ ruta: String, _ metodo: String, _ cuerpo: [String: Any]) async throws -> Data {
        let (datos, r) = try await enviar(ruta, metodo: metodo,
                                          cuerpo: try JSONSerialization.data(withJSONObject: cuerpo), conSesion: true)
        try Self.comprobar(datos, r)
        return datos
    }

    // MARK: - Proyectos con equipo (etapa 4)

    func proyectosEquipo() async throws -> [ProyectoEquipo] {
        let r: ProyectosEquipoRespuesta = try await leer("/api/v1/proyectos-creados")
        return r.proyectos
    }

    func proyectoEquipo(_ id: String) async throws -> ProyectoEquipo {
        try await leer("/api/v1/proyectos-creados/\(Self.ruta(id))")
    }

    func maquinasEquipo() async throws -> [MaquinaEquipo] {
        let r: MaquinasRespuesta = try await leer("/api/v1/proyectos-creados/maquinas")
        return r.maquinas
    }

    func crearProyecto(_ p: NuevoProyecto) async throws -> ProyectoEquipo {
        try Self.decodificar(try await cambiar("/api/v1/proyectos-creados", "POST", Self.json(p)))
    }

    /// pausar, reanudar o detener el equipo.
    func accionEquipo(_ id: String, _ accion: String) async throws -> ProyectoEquipo {
        try Self.decodificar(try await cambiar("/api/v1/proyectos-creados/\(Self.ruta(id))/\(accion)", "POST", [:]))
    }

    func autoAprobar(_ id: String, activo: Bool) async throws -> ProyectoEquipo {
        try Self.decodificar(try await cambiar("/api/v1/proyectos-creados/\(Self.ruta(id))/auto-aprobar", "POST", ["activo": activo]))
    }

    func agregarAgente(_ id: String, modelo: String, esfuerzo: String) async throws -> ProyectoEquipo {
        try Self.decodificar(try await cambiar("/api/v1/proyectos-creados/\(Self.ruta(id))/agentes", "POST",
                                               ["modelo": modelo, "esfuerzo": esfuerzo]))
    }

    func chat(_ id: String) async throws -> ChatRespuesta {
        try await leer("/api/v1/proyectos-creados/\(Self.ruta(id))/chat")
    }

    func escribir(_ id: String, texto: String) async throws -> MensajeChat {
        try Self.decodificar(try await cambiar("/api/v1/proyectos-creados/\(Self.ruta(id))/chat", "POST", ["texto": texto]))
    }

    /// Aprobar una orden; `texto` solo si se editó (queda como texto final).
    func aprobarOrden(_ id: String, texto: String? = nil) async throws -> Orden {
        var cuerpo: [String: Any] = ["dispositivo": "app"]
        if let texto { cuerpo["texto"] = texto }
        return try Self.decodificar(try await cambiar("/api/v1/ordenes/\(Self.ruta(id))/aprobar", "POST", cuerpo))
    }

    func rechazarOrden(_ id: String, motivo: String) async throws -> Orden {
        try Self.decodificar(try await cambiar("/api/v1/ordenes/\(Self.ruta(id))/rechazar", "POST",
                                               ["motivo": motivo, "dispositivo": "app"]))
    }

    /// Solo las órdenes del proyecto (las más nuevas primero), sin los mensajes del chat.
    func ordenes(_ id: String) async throws -> [Orden] {
        let r: OrdenesRespuesta = try await leer("/api/v1/proyectos-creados/\(Self.ruta(id))/ordenes")
        return r.ordenes
    }

    /// Marca o desmarca un proyecto de prueba.
    func marcarPrueba(_ id: String, prueba: Bool) async throws -> ProyectoEquipo {
        try Self.decodificar(try await cambiar("/api/v1/proyectos-creados/\(Self.ruta(id))/prueba", "POST", ["prueba": prueba]))
    }

    func avisosOrquestador() async throws -> [AvisoOrquestador] {
        let r: AvisosRespuesta = try await leer("/api/v1/avisos-orquestador")
        return r.avisos
    }

    /// Ignorar o Esperar un aviso (se guarda en el servidor).
    func accionAviso(_ clave: String, _ accion: AccionAviso) async throws {
        _ = try await cambiar("/api/v1/avisos-orquestador/\(accion.rawValue)", "POST", ["clave": clave])
    }

    func reglasDe(_ id: String) async throws -> ReglasDeProyecto {
        try await leer("/api/v1/proyectos-creados/\(Self.ruta(id))/reglas")
    }

    func ajustarRegla(proyecto id: String, regla: String, activa: Bool) async throws -> ReglasDeProyecto {
        try Self.decodificar(try await cambiar("/api/v1/proyectos-creados/\(Self.ruta(id))/reglas/\(Self.ruta(regla))",
                                               "POST", ["activa": activa]))
    }

    func reglas() async throws -> ReglasRespuesta { try await leer("/api/v1/reglas") }

    func crearRegla(texto: String, tipo: String, activaPorDefecto: Bool) async throws -> Regla {
        try Self.decodificar(try await cambiar("/api/v1/reglas", "POST",
                                               ["texto": texto, "tipo": tipo, "activa_por_defecto": activaPorDefecto]))
    }

    private static func json<T: Encodable>(_ v: T) throws -> [String: Any] {
        (try JSONSerialization.jsonObject(with: JSONEncoder().encode(v)) as? [String: Any]) ?? [:]
    }

    // MARK: - Base

    private func leer<T: Decodable>(_ ruta: String) async throws -> T {
        let (datos, r) = try await enviar(ruta, metodo: "GET", cuerpo: nil, conSesion: true)
        try Self.comprobar(datos, r)
        return try Self.decodificar(datos)
    }

    private func enviar(_ ruta: String, metodo: String, cuerpo: Data?, conSesion: Bool) async throws -> (Data, HTTPURLResponse) {
        var p = URLRequest(url: url(ruta))
        p.httpMethod = metodo
        p.cachePolicy = .reloadIgnoringLocalCacheData
        p.setValue("application/json", forHTTPHeaderField: "Accept")
        if let cuerpo {
            p.httpBody = cuerpo
            p.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if metodo != "GET" && metodo != "HEAD" { p.setValue("1", forHTTPHeaderField: "X-Visualizador") }
        if conSesion, let c = credencial {
            p.setValue("\(c.cookieNombre)=\(c.cookieValor)", forHTTPHeaderField: "Cookie")
        }
        do {
            let (d, r) = try await sesion.data(for: p)
            guard let h = r as? HTTPURLResponse else { throw ErrorAPI.red }
            return (d, h)
        } catch let e as ErrorAPI {
            throw e
        } catch {
            throw ErrorAPI.red
        }
    }

    static func comprobar(_ datos: Data, _ r: HTTPURLResponse) throws {
        if (200..<300).contains(r.statusCode) { return }
        if r.statusCode == 401 { throw ErrorAPI.sinSesion }
        throw ErrorAPI.servidor(codigo: r.statusCode, mensaje: mensajeDeError(datos))
    }

    static func decodificar<T: Decodable>(_ datos: Data) throws -> T {
        do {
            return try JSONDecoder().decode(T.self, from: datos)
        } catch {
            throw ErrorAPI.datos
        }
    }

    /// {"detail": "texto"} o {"detail": {"mensaje": "...", "segundos": n}}.
    static func mensajeDeError(_ datos: Data) -> String? {
        guard let j = try? JSONSerialization.jsonObject(with: datos) as? [String: Any] else { return nil }
        if let d = j["detail"] as? String { return d }
        if let d = j["detail"] as? [String: Any], let m = d["mensaje"] as? String { return m }
        return nil
    }

    static func segundosDeEspera(_ datos: Data, _ r: HTTPURLResponse) -> Int {
        if let j = try? JSONSerialization.jsonObject(with: datos) as? [String: Any],
           let d = j["detail"] as? [String: Any], let s = d["segundos"] as? Int { return s }
        if let h = r.value(forHTTPHeaderField: "Retry-After"), let s = Int(h) { return s }
        return 60
    }
}

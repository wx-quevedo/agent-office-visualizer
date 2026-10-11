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
    func decidir(permiso id: String, aprobar: Bool, motivo: String? = nil) async throws -> Permiso {
        var cuerpo: [String: Any] = ["decision": aprobar ? "aprobar" : "rechazar", "dispositivo": "celular"]
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

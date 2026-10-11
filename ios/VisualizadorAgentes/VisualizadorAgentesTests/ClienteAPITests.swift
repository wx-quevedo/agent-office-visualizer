import XCTest
@testable import VisualizadorAgentes

/// Responde las peticiones de URLSession sin red.
final class ProtocoloFalso: URLProtocol {
    nonisolated(unsafe) static var responder: ((URLRequest) -> (Int, [String: String], Data))?
    nonisolated(unsafe) static var recibidas: [URLRequest] = []

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        var p = request
        // URLSession pasa el cuerpo como stream: se lee para poder revisarlo.
        if p.httpBody == nil, let s = p.httpBodyStream {
            s.open()
            var d = Data()
            var buf = [UInt8](repeating: 0, count: 4096)
            while s.hasBytesAvailable {
                let n = s.read(&buf, maxLength: buf.count)
                if n <= 0 { break }
                d.append(buf, count: n)
            }
            s.close()
            p.httpBody = d
        }
        Self.recibidas.append(p)
        guard let r = Self.responder else {
            client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
            return
        }
        let (codigo, encabezados, datos) = r(p)
        let resp = HTTPURLResponse(url: p.url!, statusCode: codigo, httpVersion: "HTTP/1.1", headerFields: encabezados)!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: datos)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

final class ClienteAPITests: XCTestCase {
    let servidor = URL(string: "https://agents.ejemplo.com")!
    let cred = Credencial(servidor: URL(string: "https://agents.ejemplo.com")!,
                          cookieNombre: "__Host-visualizador_sesion", cookieValor: "vas_abc", expira: nil)

    override func setUp() {
        ProtocoloFalso.responder = nil
        ProtocoloFalso.recibidas = []
    }

    func cliente(_ c: Credencial? = nil) -> ClienteAPI {
        ClienteAPI(servidor: servidor, credencial: c, sesion: ClienteAPI.sesionNueva(protocolos: [ProtocoloFalso.self]))
    }

    func json(_ s: String) -> Data { Data(s.utf8) }

    func testNormalizaElServidor() {
        XCTAssertEqual(ClienteAPI.normalizarServidor("agents.example.com")?.absoluteString, "https://agents.example.com")
        XCTAssertEqual(ClienteAPI.normalizarServidor(" https://agents.example.com/ ")?.absoluteString, "https://agents.example.com")
        XCTAssertEqual(ClienteAPI.normalizarServidor("http://192.168.1.5:8000")?.absoluteString, "http://192.168.1.5:8000")
        XCTAssertNil(ClienteAPI.normalizarServidor(""))
        XCTAssertNil(ClienteAPI.normalizarServidor("no es un servidor"))
        XCTAssertNil(ClienteAPI.normalizarServidor("ftp://x.com"))
    }

    func testEntrarGuardaLaCookieDeSesion() async throws {
        ProtocoloFalso.responder = { _ in
            (200, ["Set-Cookie": "__Host-visualizador_sesion=vas_nuevo; Max-Age=2592000; Path=/; HttpOnly; Secure; SameSite=lax"],
             Data(#"{"ok": true}"#.utf8))
        }
        let c = try await cliente().entrar(contrasena: "secreta-larga", dispositivo: "iPhone de prueba")
        XCTAssertEqual(c.cookieNombre, "__Host-visualizador_sesion")
        XCTAssertEqual(c.cookieValor, "vas_nuevo")
        XCTAssertEqual(c.servidor, servidor)
        XCTAssertNotNil(c.expira)

        let p = try XCTUnwrap(ProtocoloFalso.recibidas.first)
        XCTAssertEqual(p.url?.path(), "/api/v1/auth/entrar")
        XCTAssertEqual(p.httpMethod, "POST")
        XCTAssertEqual(p.value(forHTTPHeaderField: "X-Visualizador"), "1")
        XCTAssertNil(p.value(forHTTPHeaderField: "Cookie"))
        let cuerpo = try XCTUnwrap(JSONSerialization.jsonObject(with: p.httpBody ?? Data()) as? [String: String])
        XCTAssertEqual(cuerpo["contrasena"], "secreta-larga")
        XCTAssertEqual(cuerpo["dispositivo"], "iPhone de prueba")
    }

    func testContrasenaIncorrectaYDemasiadosIntentos() async {
        ProtocoloFalso.responder = { _ in (401, [:], Data(#"{"detail": {"mensaje": "Contraseña incorrecta."}}"#.utf8)) }
        do {
            _ = try await cliente().entrar(contrasena: "x", dispositivo: "d")
            XCTFail("debía fallar")
        } catch {
            XCTAssertEqual(error as? ErrorAPI, .contrasenaIncorrecta)
        }
        ProtocoloFalso.responder = { _ in
            (429, ["Retry-After": "11"], Data(#"{"detail": {"mensaje": "Demasiados intentos.", "segundos": 11}}"#.utf8))
        }
        do {
            _ = try await cliente().entrar(contrasena: "x", dispositivo: "d")
            XCTFail("debía fallar")
        } catch {
            XCTAssertEqual(error as? ErrorAPI, .demasiadosIntentos(segundos: 11))
        }
    }

    func testEntrarSinCookieEsUnError() async {
        ProtocoloFalso.responder = { _ in (200, [:], Data(#"{"ok": true}"#.utf8)) }
        do {
            _ = try await cliente().entrar(contrasena: "x", dispositivo: "d")
            XCTFail("debía fallar")
        } catch {
            guard case .servidor = error as? ErrorAPI else { return XCTFail("error inesperado \(error)") }
        }
    }

    func testLecturaMandaLaCookieYSin401() async throws {
        ProtocoloFalso.responder = { _ in (200, [:], Data(#"{"generado": "2026-10-11T10:00:00+00:00", "agentes": []}"#.utf8)) }
        let e = try await cliente(cred).estado()
        XCTAssertEqual(e.agentes.count, 0)
        let p = try XCTUnwrap(ProtocoloFalso.recibidas.first)
        XCTAssertEqual(p.url?.path(), "/api/v1/agents/state")
        XCTAssertEqual(p.value(forHTTPHeaderField: "Cookie"), "__Host-visualizador_sesion=vas_abc")
        XCTAssertNil(p.value(forHTTPHeaderField: "X-Visualizador"))
    }

    func testSesionVencidaDa401() async {
        ProtocoloFalso.responder = { _ in (401, [:], Data(#"{"detail": "Inicia sesión para continuar."}"#.utf8)) }
        do {
            _ = try await cliente(cred).estado()
            XCTFail("debía fallar")
        } catch {
            XCTAssertEqual(error as? ErrorAPI, .sinSesion)
        }
    }

    func testDecidirUsaElMismoEndpointQueLaWeb() async throws {
        ProtocoloFalso.responder = { _ in
            (200, [:], Data(#"{"id": "p1", "herramienta": "Bash", "detalle": "ls", "esperando": false, "estado": "aprobada", "dispositivo": "celular"}"#.utf8))
        }
        let p = try await cliente(cred).decidir(permiso: "p1", aprobar: true)
        XCTAssertEqual(p.estado, "aprobada")
        let r = try XCTUnwrap(ProtocoloFalso.recibidas.first)
        XCTAssertEqual(r.url?.path(), "/api/v1/permisos/solicitudes/p1/decision")
        XCTAssertEqual(r.httpMethod, "POST")
        XCTAssertEqual(r.value(forHTTPHeaderField: "X-Visualizador"), "1")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Cookie"), "__Host-visualizador_sesion=vas_abc")
        let cuerpo = try XCTUnwrap(JSONSerialization.jsonObject(with: r.httpBody ?? Data()) as? [String: String])
        XCTAssertEqual(cuerpo, ["decision": "aprobar", "dispositivo": "app"])
    }

    func testDecidirYaDecididaDevuelveElMensaje() async {
        ProtocoloFalso.responder = { _ in (409, [:], Data(#"{"detail": "La solicitud ya se decidió."}"#.utf8)) }
        do {
            _ = try await cliente(cred).decidir(permiso: "p1", aprobar: false)
            XCTFail("debía fallar")
        } catch {
            XCTAssertEqual(error as? ErrorAPI, .servidor(codigo: 409, mensaje: "La solicitud ya se decidió."))
            XCTAssertEqual((error as? ErrorAPI)?.mensaje, "La solicitud ya se decidió.")
        }
    }

    func testSinRedEsErrorDeRed() async {
        ProtocoloFalso.responder = nil
        do {
            _ = try await cliente(cred).estado()
            XCTFail("debía fallar")
        } catch {
            XCTAssertEqual(error as? ErrorAPI, .red)
        }
    }

    func testDatosRarosSonErrorDeDatos() async {
        ProtocoloFalso.responder = { _ in (200, [:], Data("<html>".utf8)) }
        do {
            _ = try await cliente(cred).consumo()
            XCTFail("debía fallar")
        } catch {
            XCTAssertEqual(error as? ErrorAPI, .datos)
        }
    }

    func testRutasDeLectura() async throws {
        ProtocoloFalso.responder = { p in
            switch p.url?.path() {
            case "/api/v1/agents/abc/historial": return (200, [:], Data(#"{"turnos": []}"#.utf8))
            case "/api/v1/proyectos": return (200, [:], Data(#"{"proyectos": [{"carpeta": "E:\\x"}]}"#.utf8))
            case "/api/v1/permisos/config": return (200, [:], Data(#"{"politica": "siempre", "espera_seg": 90, "confirmar": ["rm"]}"#.utf8))
            default: return (404, [:], Data())
            }
        }
        let c = cliente(cred)
        _ = try await c.historial(sesion: "abc", porPagina: 5)
        XCTAssertEqual(ProtocoloFalso.recibidas.last?.url?.query(), "por_pagina=5")
        let pr = try await c.proyectos()
        XCTAssertEqual(pr.first?.carpeta, "E:\\x")
        XCTAssertEqual(pr.first?.plan, [])
        let conf = try await c.configPermisos()
        XCTAssertEqual(conf.confirmar, ["rm"])
    }

    func testCookieParaElWebView() throws {
        let c = try XCTUnwrap(cred.cookie())
        XCTAssertEqual(c.name, "__Host-visualizador_sesion")
        XCTAssertEqual(c.value, "vas_abc")
        XCTAssertEqual(c.domain, "agents.ejemplo.com")
        XCTAssertEqual(c.path, "/")
        XCTAssertTrue(c.isSecure)
    }
}

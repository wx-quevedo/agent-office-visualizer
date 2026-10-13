import XCTest
@testable import VisualizadorAgentes

/// Prompt 46: estados de los mensajes, respuesta en vivo, canal SSE, notificaciones y versión.
final class ChatVivoTests: XCTestCase {
    func m(_ id: String, _ autor: String = "washington", estado: String? = nil, leido: String? = nil, texto: String = "x") -> MensajeChat {
        MensajeChat(id: id, autor: autor, texto: texto, creado: "2026-10-13T10:00:00+00:00", estado: estado, leido: leido)
    }

    func vivo(_ estado: String, _ parcial: String = "") -> EnVivo {
        EnVivo(estado: estado, parcial: parcial, mensaje_id: "a", desde: nil, actualizado: nil)
    }

    func testMarcaEnviadoYLeido() {
        XCTAssertEqual(LogicaChatVivo.marca(m("a", estado: "enviado")), "Enviado")
        XCTAssertEqual(LogicaChatVivo.marca(m("a", estado: "leido", leido: "2026-10-13T10:00:01+00:00")), "Leído")
        XCTAssertEqual(LogicaChatVivo.marca(m("a", estado: "respondiendo", leido: "x")), "Leído")
        XCTAssertNil(LogicaChatVivo.marca(m("b", "orquestador")))
        // Un servidor anterior, sin estado: sin marca.
        XCTAssertNil(LogicaChatVivo.marca(m("a")))
    }

    func testBurbujaPuntosYTexto() {
        XCTAssertEqual(LogicaChatVivo.burbuja(nil), .ninguna)
        XCTAssertEqual(LogicaChatVivo.burbuja(vivo("libre")), .ninguna)
        XCTAssertEqual(LogicaChatVivo.burbuja(vivo("leido")), .ninguna)
        XCTAssertEqual(LogicaChatVivo.burbuja(vivo("respondiendo")), .puntos)
        XCTAssertEqual(LogicaChatVivo.burbuja(vivo("respondiendo", "  \n")), .puntos)
        XCTAssertEqual(LogicaChatVivo.burbuja(vivo("respondiendo", "1. **Primero**")), .texto("1. **Primero**"))
    }

    func testUnirRecientesPorId() {
        let antes = [m("a", estado: "enviado"), m("b", "orquestador")]
        let recientes = [m("a", estado: "leido", leido: "x"), m("c", "orquestador", texto: "final")]
        let u = LogicaChatVivo.unir(antes, recientes)
        XCTAssertEqual(u.map(\.id), ["a", "b", "c"])
        XCTAssertEqual(u[0].estado, "leido")
        XCTAssertEqual(u[2].texto, "final")
        // Repetir la misma lectura no duplica.
        XCTAssertEqual(LogicaChatVivo.unir(u, recientes).count, 3)
    }

    func testCuandoSondearLaRutaLiviana() {
        XCTAssertTrue(LogicaChatVivo.debeSondear(vivo("respondiendo"), []))
        XCTAssertTrue(LogicaChatVivo.debeSondear(vivo("libre"), [m("a", estado: "enviado")]))
        XCTAssertFalse(LogicaChatVivo.debeSondear(vivo("libre"), [m("a", estado: "leido", leido: "x")]))
        XCTAssertFalse(LogicaChatVivo.debeSondear(nil, []))
    }

    static let eventoJSON = #"{"version": "17-3", "en_vivo": {"estado": "respondiendo", "parcial": "1. Uno", "mensaje_id": "a", "desde": "x", "actualizado": "y"}, "recientes": [{"id": "a", "autor": "washington", "texto": "hola", "creado": "2026-10-13T10:00:00+00:00", "estado": "respondiendo", "leido": "2026-10-13T10:00:01+00:00"}]}"#

    func testLectorSSE() throws {
        var l = LectorSSE()
        XCTAssertNil(l.linea("retry: 1000"))
        XCTAssertNil(l.linea(""))
        XCTAssertNil(l.linea(": pulso"))
        XCTAssertNil(l.linea("event: chat"))
        // El JSON completo se entrega con su línea data, sin esperar la línea en blanco.
        let e = try XCTUnwrap(l.linea("data: " + Self.eventoJSON))
        XCTAssertEqual(e.version, "17-3")
        XCTAssertEqual(e.en_vivo.parcial, "1. Uno")
        XCTAssertEqual(e.recientes.first?.estado, "respondiendo")
        XCTAssertNil(l.linea(""))
        // Otro tipo de evento no se entrega.
        XCTAssertNil(l.linea("event: otro"))
        XCTAssertNil(l.linea("data: " + Self.eventoJSON))
        XCTAssertNil(l.linea(""))
        // Datos partidos en dos líneas data.
        XCTAssertNil(l.linea("event: chat"))
        XCTAssertNil(l.linea("data: {\"version\": \"1\","))
        let partido = try XCTUnwrap(l.linea("data: \"en_vivo\": {\"estado\": \"libre\"}, \"recientes\": []}"))
        XCTAssertEqual(partido.en_vivo.estado, "libre")
    }

    func testChatConEnVivo() throws {
        let c = try JSONDecoder().decode(ChatRespuesta.self, from: Data(#"""
        {"mensajes": [{"id": "a", "autor": "washington", "texto": "hola", "creado": "x", "estado": "enviado", "leido": null},
                      {"id": "b", "autor": "orquestador", "texto": "ok", "creado": "y", "estado": null, "leido": null}],
         "ordenes": [], "en_vivo": {"estado": "leido", "parcial": "", "mensaje_id": "a", "desde": "x", "actualizado": "x"}}
        """#.utf8))
        XCTAssertEqual(c.mensajes[0].estado, "enviado")
        XCTAssertNil(c.mensajes[1].estado)
        XCTAssertEqual(c.en_vivo?.estado, "leido")
        // Un servidor anterior, sin en_vivo ni estados.
        let viejo = try JSONDecoder().decode(ChatRespuesta.self, from: Data(#"{"mensajes": [{"id": "a", "autor": "washington", "texto": "h", "creado": "x"}], "ordenes": []}"#.utf8))
        XCTAssertNil(viejo.en_vivo)
    }

    func testNotificacionUnaPorAvisoYSinChatAbierto() throws {
        let a = try XCTUnwrap(try JSONDecoder().decode(AvisosRespuesta.self, from: Data(AvisosTests.avisosJSON.utf8)).avisos.last)
        let c = LogicaAvisos.contenido(a)
        XCTAssertEqual(c.id, a.clave) // el identificador es la clave: nunca se repite
        XCTAssertEqual(c.titulo, "avisos-44: el orquestador te hizo una pregunta")
        XCTAssertEqual(c.cuerpo, "¿Qué quieres construir en este proyecto?")
        XCTAssertTrue(LogicaAvisos.debeNotificar(a, chatAbierto: nil))
        XCTAssertTrue(LogicaAvisos.debeNotificar(a, chatAbierto: "otro"))
        XCTAssertFalse(LogicaAvisos.debeNotificar(a, chatAbierto: a.proyecto_id))
    }

    func testVersionVisible() {
        XCTAssertTrue(VersionApp.texto.hasPrefix("Versión "))
        XCTAssertTrue(VersionApp.texto.contains("(build "))
    }

    // MARK: - Cliente

    let cred = Credencial(servidor: URL(string: "https://agents.ejemplo.com")!,
                          cookieNombre: "__Host-visualizador_sesion", cookieValor: "vas_abc", expira: nil)

    override func setUp() {
        ProtocoloFalso.responder = nil
        ProtocoloFalso.recibidas = []
    }

    func testRutaLivianaYCanalSSE() async throws {
        ProtocoloFalso.responder = { p in
            switch p.url?.path() {
            case "/api/v1/proyectos-creados/p46/chat/en-vivo": return (200, [:], Data(Self.eventoJSON.utf8))
            case "/api/v1/proyectos-creados/p46/chat/eventos":
                let cuerpo = "retry: 1000\n\nevent: chat\ndata: \(Self.eventoJSON)\n\n: pulso\n\n"
                return (200, ["Content-Type": "text/event-stream"], Data(cuerpo.utf8))
            default: return (404, [:], Data())
            }
        }
        let c = ClienteAPI(servidor: cred.servidor, credencial: cred, sesion: ClienteAPI.sesionNueva(protocolos: [ProtocoloFalso.self]))
        let e = try await c.chatEnVivo("p46")
        XCTAssertEqual(e.en_vivo.estado, "respondiendo")
        var recibidos: [ChatEnVivo] = []
        for try await ev in c.eventosChat("p46") { recibidos.append(ev) }
        XCTAssertEqual(recibidos.map(\.version), ["17-3"])
        let p = try XCTUnwrap(ProtocoloFalso.recibidas.last)
        XCTAssertEqual(p.value(forHTTPHeaderField: "Accept"), "text/event-stream")
        XCTAssertEqual(p.value(forHTTPHeaderField: "Cookie"), "__Host-visualizador_sesion=vas_abc")
    }

    func testCanalSSESinSesion() async {
        ProtocoloFalso.responder = { _ in (401, [:], Data()) }
        let c = ClienteAPI(servidor: cred.servidor, credencial: cred, sesion: ClienteAPI.sesionNueva(protocolos: [ProtocoloFalso.self]))
        do {
            for try await _ in c.eventosChat("p46") {}
            XCTFail("debía fallar")
        } catch {
            XCTAssertEqual(error as? ErrorAPI, .sinSesion)
        }
    }
}

import XCTest
@testable import VisualizadorAgentes

/// Prompt 44: título de la orden, ruta de órdenes, donde_quedamos_id, avisos de los
/// orquestadores y proyectos de prueba.
final class AvisosTests: XCTestCase {
    static let ordenJSON = #"""
    {"id": "0123456789abcdef0123456789abcdef", "proyecto_id": "p44", "proyecto": "avisos-44", "numero": 1,
     "agente": "agente", "texto_propuesto": "Agregar una línea", "texto_final": null, "texto": "Agregar una línea",
     "titulo": "Fase 1 · Prompt 1: una línea en el README", "titulo_propio": true, "editada": false,
     "estimado": "5 min", "dificultad": "1", "estado": "por_aprobar", "motivo": null, "decidido_por": null,
     "decidido": null, "resumen": null, "creado": "2026-10-12T20:00:00+00:00", "actualizado": "2026-10-12T20:00:00+00:00"}
    """#

    static var avisosJSON: String {
        #"""
        {"avisos": [
          {"proyecto_id": "p44", "proyecto": "avisos-44", "maquina": "alienware", "cuenta": "personal",
           "clave": "orden:0123456789abcdef0123456789abcdef", "tipo": "orden",
           "texto": "Orden 1 para agente: Fase 1 · Prompt 1: una línea en el README",
           "desde": "2026-10-12T20:00:00+00:00", "mensaje_id": null, "hace_s": 30, "orden": ORDEN},
          {"proyecto_id": "p44", "proyecto": "avisos-44", "maquina": "alienware", "cuenta": "personal",
           "clave": "mensaje:fedcba9876543210fedcba9876543210", "tipo": "pregunta",
           "texto": "¿Qué quieres construir en este proyecto?", "desde": "2026-10-12T19:59:00+00:00",
           "mensaje_id": "fedcba9876543210fedcba9876543210", "hace_s": 90, "orden": null}
        ]}
        """#.replacingOccurrences(of: "ORDEN", with: ordenJSON)
    }

    func avisos() throws -> [AvisoOrquestador] {
        try JSONDecoder().decode(AvisosRespuesta.self, from: Data(Self.avisosJSON.utf8)).avisos
    }

    func testDecodificaAvisosYTitulo() throws {
        let a = try avisos()
        XCTAssertEqual(a.count, 2)
        XCTAssertEqual(a[0].orden?.titulo, "Fase 1 · Prompt 1: una línea en el README")
        XCTAssertEqual(a[0].orden?.titulo_propio, true)
        XCTAssertEqual(a[1].mensaje_id, "fedcba9876543210fedcba9876543210")
        XCTAssertNil(a[1].orden)
    }

    func testTituloCortoConRespaldo() throws {
        var o = try JSONDecoder().decode(Orden.self, from: Data(Self.ordenJSON.utf8))
        XCTAssertEqual(LogicaProyectos.tituloCorto(o), "Fase 1 · Prompt 1: una línea en el README")
        o.titulo = "  "
        XCTAssertEqual(LogicaProyectos.tituloCorto(o), "Orden 1")
        o.titulo = nil
        XCTAssertEqual(LogicaProyectos.tituloCorto(o), "Orden 1")
    }

    func testCadaClaveSeAnunciaUnaVez() {
        // Primera lectura: solo se anotan (no se anuncia lo que ya estaba).
        var r = LogicaAvisos.revisar(["mensaje:a", "orden:b"], avisadas: [], primera: true)
        XCTAssertEqual(r.nuevas, [])
        XCTAssertEqual(r.avisadas, ["mensaje:a", "orden:b"])
        // Después, solo la clave nueva, una vez.
        r = LogicaAvisos.revisar(["mensaje:a", "orden:b", "mensaje:c", "mensaje:c"], avisadas: r.avisadas, primera: false)
        XCTAssertEqual(r.nuevas, ["mensaje:c"])
        r = LogicaAvisos.revisar(["mensaje:c"], avisadas: r.avisadas, primera: false)
        XCTAssertEqual(r.nuevas, [])
        // Se recuerdan solo las últimas.
        let muchas = (0..<250).map { "mensaje:\($0)" }
        XCTAssertEqual(LogicaAvisos.revisar(muchas, avisadas: [], primera: false).avisadas.count, LogicaAvisos.maxAvisadas)
    }

    func testInsigniaSoloConAccion() throws {
        let a = try avisos()
        // decisiones_pendientes ya cuenta la orden; se suma solo la pregunta del orquestador.
        XCTAssertEqual(LogicaAvisos.insignia(pendientes: 1, avisos: a), 2)
        XCTAssertEqual(LogicaAvisos.insignia(pendientes: 0, avisos: []), 0)
        XCTAssertEqual(LogicaAvisos.preguntas(a).map(\.tipo), ["pregunta"])
        XCTAssertEqual(LogicaAvisos.deOrden(a, "0123456789abcdef0123456789abcdef")?.tipo, "orden")
        XCTAssertNil(LogicaAvisos.deOrden(a, "otra"))
    }

    func testResponderApuntaAlChat() {
        XCTAssertEqual(LogicaAvisos.itemChat("mensaje:abc"), "m-abc")
        XCTAssertEqual(LogicaAvisos.itemChat("orden:abc"), "o-abc")
        XCTAssertNil(LogicaAvisos.itemChat("otra:abc"))
        XCTAssertNil(LogicaAvisos.itemChat("mensaje:"))
        XCTAssertNil(LogicaAvisos.itemChat(nil))
        XCTAssertEqual(LogicaAvisos.titulo(try! avisos()[1]), "avisos-44: el orquestador te hizo una pregunta")
    }

    func testNombreDePrueba() {
        XCTAssertTrue(LogicaAvisos.esNombrePrueba("prueba-44"))
        XCTAssertTrue(LogicaAvisos.esNombrePrueba(" Prueba-x"))
        XCTAssertFalse(LogicaAvisos.esNombrePrueba("avisos-44"))
        XCTAssertFalse(LogicaAvisos.esNombrePrueba("prueba"))
    }

    func testUnionPorDondeQuedamosId() throws {
        var p = try JSONDecoder().decode(ProyectosEquipoRespuesta.self, from: Data(ProyectosTests.proyectosJSON.utf8)).proyectos[0]
        // La carpeta del monitor no se parece en nada: manda el id del servidor.
        p.donde_quedamos_id = "alienware:e:/otra-carpeta"
        let monitor = [
            ProyectoApi(id: "alienware:e:/agents/prueba-39", carpeta: "E:\\Agents\\prueba-39", maquina: "alienware", tiene_project_md: true, posicion: "Por carpeta"),
            ProyectoApi(id: "alienware:e:/otra-carpeta", carpeta: "E:\\otra-carpeta", maquina: "alienware", tiene_project_md: true, posicion: "Por id"),
        ]
        let donde = LogicaDonde.armar(monitor, [])
        var lista = LogicaProyectos.lista(equipos: [p], donde: donde, agentes: [])
        XCTAssertEqual(lista[0].donde?.datos.posicion, "Por id")
        // Sin id, el respaldo por carpeta.
        p.donde_quedamos_id = nil
        lista = LogicaProyectos.lista(equipos: [p], donde: donde, agentes: [])
        XCTAssertEqual(lista[0].donde?.datos.posicion, "Por carpeta")
        // Y el campo prueba.
        XCTAssertFalse(p.esPrueba)
        p.prueba = true
        XCTAssertTrue(p.esPrueba)
    }

    // MARK: - Cliente

    let cred = Credencial(servidor: URL(string: "https://agents.ejemplo.com")!,
                          cookieNombre: "__Host-visualizador_sesion", cookieValor: "vas_abc", expira: nil)

    override func setUp() {
        ProtocoloFalso.responder = nil
        ProtocoloFalso.recibidas = []
    }

    func cuerpo(_ p: URLRequest?) throws -> [String: Any] {
        try XCTUnwrap(JSONSerialization.jsonObject(with: p?.httpBody ?? Data()) as? [String: Any])
    }

    func testRutasNuevas() async throws {
        let proyecto = try JSONSerialization.data(withJSONObject:
            ((try JSONSerialization.jsonObject(with: Data(ProyectosTests.proyectosJSON.utf8)) as! [String: Any])["proyectos"] as! [Any])[0])
        ProtocoloFalso.responder = { p in
            switch (p.httpMethod, p.url?.path()) {
            case ("GET", "/api/v1/proyectos-creados/p39/ordenes"): return (200, [:], Data("{\"ordenes\": [\(Self.ordenJSON)]}".utf8))
            case ("GET", "/api/v1/avisos-orquestador"): return (200, [:], Data(Self.avisosJSON.utf8))
            case ("POST", "/api/v1/avisos-orquestador/ignorar"), ("POST", "/api/v1/avisos-orquestador/esperar"):
                return (200, [:], Data(#"{"clave": "x", "estado": "ignorado"}"#.utf8))
            case ("POST", "/api/v1/proyectos-creados/p39/prueba"), ("POST", "/api/v1/proyectos-creados"): return (200, [:], proyecto)
            default: return (404, [:], Data())
            }
        }
        let c = ClienteAPI(servidor: cred.servidor, credencial: cred, sesion: ClienteAPI.sesionNueva(protocolos: [ProtocoloFalso.self]))
        let o = try await c.ordenes("p39")
        XCTAssertEqual(o.first?.titulo, "Fase 1 · Prompt 1: una línea en el README")
        let a = try await c.avisosOrquestador()
        XCTAssertEqual(a.count, 2)

        try await c.accionAviso("mensaje:fedcba9876543210fedcba9876543210", .esperar)
        XCTAssertEqual(ProtocoloFalso.recibidas.last?.url?.path(), "/api/v1/avisos-orquestador/esperar")
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["clave"] as? String, "mensaje:fedcba9876543210fedcba9876543210")
        XCTAssertEqual(ProtocoloFalso.recibidas.last?.value(forHTTPHeaderField: "X-Visualizador"), "1")
        try await c.accionAviso("orden:0123456789abcdef0123456789abcdef", .ignorar)
        XCTAssertEqual(ProtocoloFalso.recibidas.last?.url?.path(), "/api/v1/avisos-orquestador/ignorar")

        _ = try await c.marcarPrueba("p39", prueba: true)
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["prueba"] as? Bool, true)

        _ = try await c.crearProyecto(NuevoProyecto(nombre: "prueba-44", maquina: "alienware", cuenta: "personal", plantilla: "vacia",
                                                    orquestador: .init(modelo: "haiku", esfuerzo: "low"),
                                                    agentes: [.init(modelo: "haiku", esfuerzo: "low")], auto_aprobar: false, prueba: true))
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["prueba"] as? Bool, true)
        // Sin prueba, el campo no se manda (el servidor decide por el nombre).
        _ = try await c.crearProyecto(NuevoProyecto(nombre: "avisos-44", maquina: "alienware", cuenta: "personal", plantilla: "vacia",
                                                    orquestador: .init(modelo: "haiku", esfuerzo: "low"),
                                                    agentes: [.init(modelo: "haiku", esfuerzo: "low")], auto_aprobar: false))
        XCTAssertNil(try cuerpo(ProtocoloFalso.recibidas.last)["prueba"])
    }
}

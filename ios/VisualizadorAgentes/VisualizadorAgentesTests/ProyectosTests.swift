import XCTest
@testable import VisualizadorAgentes

/// Etapa 4 en la app: proyectos con equipo, chat, órdenes, reglas y markdown.
final class ProyectosTests: XCTestCase {
    static let proyectosJSON = #"""
    {"proyectos": [
      {"id": "p39", "nombre": "prueba-39", "maquina": "alienware", "cuenta": "personal",
       "ruta": "E:\\Agents\\prueba-39", "plantilla": "vacia", "estado": "activo", "auto_aprobar": false,
       "error": null, "creado": "2026-10-12T15:00:00+00:00", "actualizado": "2026-10-12T15:00:00+00:00",
       "haciendo": null, "ordenes_por_aprobar": 1,
       "equipo": [
         {"id": "m1", "proyecto_id": "p39", "rol": "orquestador", "nombre": "orquestador", "modelo": "opus",
          "esfuerzo": "high", "session_id": "s-orq", "estado": "activo", "orden": 0, "actualizado": "x",
          "oficina": {"numero": 11, "nombre": "Listo", "desde": "2026-10-12T15:01:00+00:00", "espera": null}},
         {"id": "m2", "proyecto_id": "p39", "rol": "agente", "nombre": "agente-1", "modelo": "sonnet",
          "esfuerzo": "medium", "session_id": null, "estado": "pendiente", "orden": 1, "actualizado": "x", "oficina": null}
       ]},
      {"id": "p40", "nombre": "pausado", "maquina": "alienware", "cuenta": "demo", "ruta": "E:\\Agents\\pausado",
       "plantilla": "web", "estado": "pausado", "auto_aprobar": true, "error": null, "creado": "2026-10-11T15:00:00+00:00",
       "actualizado": "x", "haciendo": null, "ordenes_por_aprobar": 0, "equipo": []}
    ]}
    """#

    static let chatJSON = #"""
    {"mensajes": [
      {"id": "a", "autor": "washington", "texto": "Propón una orden pequeña", "creado": "2026-10-12T15:10:00+00:00"},
      {"id": "b", "autor": "orquestador", "texto": "Listo. **Propongo** esto:\n- una línea", "creado": "2026-10-12T15:11:00+00:00"}
     ],
     "ordenes": [
      {"id": "o1", "proyecto_id": "p39", "proyecto": "prueba-39", "numero": 1, "agente": "agente-1",
       "texto_propuesto": "Agregar una línea al README", "texto_final": null, "texto": "Agregar una línea al README",
       "editada": false, "estimado": "5 min", "dificultad": "1", "estado": "por_aprobar", "motivo": null,
       "decidido_por": null, "decidido": null, "resumen": null, "creado": "2026-10-12T15:11:00+00:00",
       "actualizado": "2026-10-12T15:11:00+00:00"}
     ]}
    """#

    func proyectos() throws -> [ProyectoEquipo] {
        try JSONDecoder().decode(ProyectosEquipoRespuesta.self, from: Data(Self.proyectosJSON.utf8)).proyectos
    }

    func testDecodificaProyectosChatYReglas() throws {
        let p = try proyectos()
        XCTAssertEqual(p.count, 2)
        XCTAssertEqual(p[0].equipo.count, 2)
        XCTAssertEqual(p[0].equipo[0].oficina?.numero, 11)
        XCTAssertNil(p[0].equipo[1].oficina)
        let c = try JSONDecoder().decode(ChatRespuesta.self, from: Data(Self.chatJSON.utf8))
        XCTAssertEqual(c.mensajes.count, 2)
        XCTAssertEqual(c.ordenes.first?.estimado, "5 min")
        let r = try JSONDecoder().decode(ReglasDeProyecto.self, from: Data(#"""
        {"reglas": [{"id": "idioma", "texto": "Español", "tipo": "idioma", "activa_por_defecto": true, "orden": 0,
                     "ajustada": false, "activa": true}],
         "comandos": [{"id": "git-status", "comando": "git status", "activo_por_defecto": true, "orden": 0, "ajustado": false, "activo": true}]}
        """#.utf8))
        XCTAssertEqual(r.reglas.first?.activa, true)
        XCTAssertEqual(r.comandos?.first?.comando, "git status")
        let m = try JSONDecoder().decode(MaquinasRespuesta.self, from: Data(#"""
        {"maquinas": [{"id": "alienware", "nombre": "Alienware", "sistema": "windows", "version_monitor": "0.6.0",
          "ultima_conexion": "x", "encendida": true, "ruta_base": "E:\\Agents", "disponible": true, "motivo": null}]}
        """#.utf8))
        XCTAssertEqual(m.maquinas.first?.ruta_base, "E:\\Agents")
    }

    func testDecisionDeOrden() throws {
        let json = #"""
        {"pendientes": [{"tipo": "orden", "id": "o1", "session_id": "s-orq", "proyecto": "prueba-39", "carpeta": "E:\\Agents\\prueba-39",
          "cuenta": "personal", "maquina": "alienware", "desde": "2026-10-12T15:11:00+00:00", "hace_s": 60,
          "resumen": "Orden 1 para agente-1: Agregar una línea", "detalle": "Agregar una línea al README",
          "orden": {"id": "o1", "proyecto_id": "p39", "proyecto": "prueba-39", "numero": 1, "agente": "agente-1",
            "texto_propuesto": "x", "texto_final": null, "texto": "x", "editada": false, "estimado": null, "dificultad": null,
            "estado": "por_aprobar", "motivo": null, "decidido_por": null, "decidido": null, "resumen": null,
            "creado": "2026-10-12T15:11:00+00:00", "actualizado": "2026-10-12T15:11:00+00:00"}},
          {"tipo": "permiso", "id": "p-9", "session_id": "s-1", "desde": "2026-10-12T15:00:00+00:00",
           "permiso": {"id": "p-9", "herramienta": "Bash", "esperando": true, "estado": "pendiente"}}],
         "conteo": {"orden": 1, "permiso": 1, "pregunta": 0, "atasco": 0, "total": 2}, "resueltas_hoy": []}
        """#
        let b = try JSONDecoder().decode(Bandeja.self, from: Data(json.utf8))
        XCTAssertEqual(b.conteo?.orden, 1)
        XCTAssertEqual(b.pendientes[0].orden?.agente, "agente-1")
        // Las órdenes van primero aunque el permiso sea más antiguo.
        XCTAssertEqual(LogicaBandejas.ordenar(b.pendientes).map(\.tipo), ["orden", "permiso"])
        XCTAssertEqual(LogicaBandejas.titulo(b.pendientes[0]), "Orden · prueba-39")
    }

    // MARK: - Lista

    func agente(_ id: String, _ numero: Int, proyecto: String, atasco: Bool = false) throws -> Agente {
        let at = atasco ? #", "atasco": {"tipo": "x", "motivo": "repite", "desde": "2026-10-12T15:00:00+00:00"}"# : ""
        return try JSONDecoder().decode(Agente.self, from: Data("""
        {"agente": {"session_id": "\(id)", "proyecto": "\(proyecto.replacingOccurrences(of: "\\", with: "\\\\"))", "cuenta": "personal", "maquina": "alienware"},
         "estado": {"numero": \(numero), "nombre": "e", "desde": "2026-10-12T15:00:00+00:00"}\(at)}
        """.utf8))
    }

    func testListaUnificadaYEstados() throws {
        let equipos = try proyectos()
        let monitor = [
            ProyectoApi(carpeta: "E:\\Agents\\prueba-39", maquina: "alienware", tiene_project_md: true, posicion: "Etapa 1"),
            ProyectoApi(carpeta: "E:\\SkyNest", maquina: "alienware", tiene_project_md: true),
            ProyectoApi(carpeta: "E:\\vive-demo", maquina: "alienware", tiene_project_md: false),
        ]
        let agentes = [try agente("s1", 13, proyecto: "E:\\SkyNest"), try agente("s2", 5, proyecto: "E:\\vive-demo", atasco: true)]
        let donde = LogicaDonde.armar(monitor, agentes)
        let lista = LogicaProyectos.lista(equipos: equipos, donde: donde, agentes: agentes)
        XCTAssertEqual(lista.map(\.nombre), ["prueba-39", "pausado", "SkyNest", "vive-demo"])
        XCTAssertEqual(lista[0].donde?.datos.posicion, "Etapa 1") // unido por la carpeta
        XCTAssertEqual(LogicaProyectos.resumen(lista), "2 con orquestador · 2 sin orquestador")

        XCTAssertEqual(LogicaProyectos.estado(lista[0]), .porAprobar(1))
        XCTAssertEqual(LogicaProyectos.estado(lista[0]).tono, .morado)
        XCTAssertEqual(LogicaProyectos.estado(lista[1]), .detenido("En pausa"))
        XCTAssertEqual(LogicaProyectos.estado(lista[1]).tono, .gris)
        XCTAssertEqual(LogicaProyectos.estado(lista[2]), .permiso)
        XCTAssertEqual(LogicaProyectos.estado(lista[2]).tono, .azul)
        XCTAssertEqual(LogicaProyectos.estado(lista[3]), .atascado)
        XCTAssertEqual(LogicaProyectos.estado(lista[3]).tono, .rojo)

        XCTAssertEqual(LogicaProyectos.equipoTexto(lista[0]), "Orquestador + 1 agente")
        XCTAssertEqual(LogicaProyectos.equipoTexto(lista[2]), "Sin orquestador · 1 agente")
        XCTAssertEqual(LogicaProyectos.dondeVa(lista[0]), "Etapa 1")
        XCTAssertEqual(LogicaProyectos.dondeVa(lista[3]), "e")
    }

    func testTrabajando() throws {
        var e = try proyectos()[0]
        e.ordenes_por_aprobar = 0
        e.equipo[0].oficina?.numero = 5
        let p = ProyectoLista(id: "e-p39", nombre: "prueba-39", equipo: e, donde: nil, agentes: [])
        XCTAssertEqual(LogicaProyectos.estado(p), .trabajando)
        XCTAssertEqual(LogicaProyectos.estado(p).tono, .verde)
    }

    // MARK: - Proyecto nuevo

    func testNombreYCarpeta() {
        XCTAssertNil(LogicaProyectos.errorNombre("landing-inmersoft"))
        XCTAssertEqual(LogicaProyectos.errorNombre(""), "Escribe un nombre para el proyecto.")
        XCTAssertEqual(LogicaProyectos.errorNombre("Landing"), "Usa solo minúsculas.")
        XCTAssertEqual(LogicaProyectos.errorNombre("año"), "Usa solo letras minúsculas sin tildes, números y guiones.")
        XCTAssertEqual(LogicaProyectos.errorNombre("-x"), "El nombre no puede empezar ni terminar con un guion.")
        XCTAssertEqual(LogicaProyectos.errorNombre("con"), "Ese nombre está reservado por Windows; elige otro.")
        XCTAssertEqual(LogicaProyectos.rutaNueva("E:\\Agents\\", "x"), "E:\\Agents\\x")
        XCTAssertEqual(LogicaProyectos.rutaNueva("/Users/w/Agents", "x"), "/Users/w/Agents/x")
        XCTAssertNil(LogicaProyectos.rutaNueva(nil, "x"))
        XCTAssertEqual(LogicaProyectos.modeloYEsfuerzo("opus", "high"), "Opus 5.5 · esfuerzo alto")
        XCTAssertEqual(LogicaProyectos.modeloYEsfuerzo("sonnet", "xhigh"), "Sonnet 5.5 · esfuerzo muy alto")
    }

    // MARK: - Chat y órdenes

    func testChatMezcladoYTextos() throws {
        let c = try JSONDecoder().decode(ChatRespuesta.self, from: Data(Self.chatJSON.utf8))
        let items = LogicaProyectos.mezclar(c.mensajes, c.ordenes)
        // Mismo instante: primero el mensaje del orquestador, luego su orden.
        XCTAssertEqual(items.map(\.id), ["m-a", "m-b", "o-o1"])
        let o = c.ordenes[0]
        XCTAssertEqual(LogicaProyectos.estimadoYDificultad(o), "Estimado: 5 min · dificultad 1 de 10")
        XCTAssertEqual(LogicaProyectos.estadoOrden("rechazada").texto, "rechazada")
        XCTAssertNil(LogicaProyectos.textoEditado(o, "  Agregar una línea al README \n"))
        XCTAssertEqual(LogicaProyectos.textoEditado(o, "Agregar dos líneas"), "Agregar dos líneas")
        XCTAssertNil(LogicaProyectos.motivoValido("   "))
        XCTAssertEqual(LogicaProyectos.motivoValido(" prueba de la app "), "prueba de la app")
        XCTAssertEqual(LogicaProyectos.quienDecidio("app"), "Tú desde la app")
    }

    func testMarkdownSinHTML() {
        let b = MarkdownLigero.bloques("""
        ## Plan
        Hola **mundo**.
        Sigue aquí.

        - uno
        * dos
        1. primero
        ```
        let x = 1
        ```
        <b>negrita</b> &amp; <script>alert(1)</script>
        """)
        XCTAssertEqual(b, [
            .titulo("Plan"),
            .parrafo("Hola **mundo**.\nSigue aquí."),
            .vineta("uno"), .vineta("dos"), .numerada(1, "primero"),
            .codigo("let x = 1"),
            .parrafo("negrita & alert(1)"),
        ])
        let a = MarkdownLigero.enLinea("Hola **mundo** y `x`")
        XCTAssertEqual(String(a.characters), "Hola mundo y x")
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

    func testRutasDeProyectos() async throws {
        let orden = try JSONSerialization.data(withJSONObject: (try JSONSerialization.jsonObject(with: Data(Self.chatJSON.utf8)) as! [String: Any])["ordenes"].map { ($0 as! [Any])[0] }!)
        let proyecto = try JSONSerialization.data(withJSONObject: (try JSONSerialization.jsonObject(with: Data(Self.proyectosJSON.utf8)) as! [String: Any])["proyectos"].map { ($0 as! [Any])[0] }!)
        let reglas = Data(#"{"reglas": [], "comandos": []}"#.utf8)
        ProtocoloFalso.responder = { p in
            switch (p.httpMethod, p.url?.path()) {
            case ("GET", "/api/v1/proyectos-creados"): return (200, [:], Data(Self.proyectosJSON.utf8))
            case ("GET", "/api/v1/proyectos-creados/p39/chat"): return (200, [:], Data(Self.chatJSON.utf8))
            case ("POST", "/api/v1/proyectos-creados/p39/chat"):
                return (201, [:], Data(#"{"id": "z", "autor": "washington", "texto": "hola", "creado": "x"}"#.utf8))
            case ("POST", "/api/v1/ordenes/o1/rechazar"), ("POST", "/api/v1/ordenes/o1/aprobar"): return (200, [:], orden)
            case ("POST", "/api/v1/proyectos-creados"), ("POST", "/api/v1/proyectos-creados/p39/pausar"),
                 ("POST", "/api/v1/proyectos-creados/p39/auto-aprobar"): return (201, [:], proyecto)
            case ("POST", "/api/v1/proyectos-creados/p39/reglas/emojis"): return (200, [:], reglas)
            default: return (404, [:], Data())
            }
        }
        let c = ClienteAPI(servidor: cred.servidor, credencial: cred, sesion: ClienteAPI.sesionNueva(protocolos: [ProtocoloFalso.self]))
        let lista = try await c.proyectosEquipo()
        XCTAssertEqual(lista.count, 2)
        let chat = try await c.chat("p39")
        XCTAssertEqual(chat.ordenes.count, 1)

        _ = try await c.escribir("p39", texto: "hola")
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["texto"] as? String, "hola")
        XCTAssertEqual(ProtocoloFalso.recibidas.last?.value(forHTTPHeaderField: "X-Visualizador"), "1")

        _ = try await c.rechazarOrden("o1", motivo: "prueba de la app")
        var b = try cuerpo(ProtocoloFalso.recibidas.last)
        XCTAssertEqual(b["motivo"] as? String, "prueba de la app")
        XCTAssertEqual(b["dispositivo"] as? String, "app")

        _ = try await c.aprobarOrden("o1")
        b = try cuerpo(ProtocoloFalso.recibidas.last)
        XCTAssertNil(b["texto"])
        XCTAssertEqual(b["dispositivo"] as? String, "app")
        _ = try await c.aprobarOrden("o1", texto: "otra cosa")
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["texto"] as? String, "otra cosa")

        _ = try await c.crearProyecto(NuevoProyecto(nombre: "x", maquina: "alienware", cuenta: "personal", plantilla: "web",
                                                    orquestador: .init(modelo: "opus", esfuerzo: "high"),
                                                    agentes: [.init(modelo: "sonnet", esfuerzo: "medium")], auto_aprobar: false))
        b = try cuerpo(ProtocoloFalso.recibidas.last)
        XCTAssertEqual(b["plantilla"] as? String, "web")
        XCTAssertEqual((b["orquestador"] as? [String: String])?["modelo"], "opus")
        XCTAssertEqual((b["agentes"] as? [[String: String]])?.count, 1)
        XCTAssertEqual(b["auto_aprobar"] as? Bool, false)

        _ = try await c.accionEquipo("p39", "pausar")
        _ = try await c.autoAprobar("p39", activo: true)
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["activo"] as? Bool, true)
        _ = try await c.ajustarRegla(proyecto: "p39", regla: "emojis", activa: false)
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["activa"] as? Bool, false)
    }
}

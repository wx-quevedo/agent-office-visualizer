import XCTest
@testable import VisualizadorAgentes

/// Bandejas de Decisiones e Ideas (Prompt 33): decodificación, orden, textos, ideas y cliente.
final class BandejasTests: XCTestCase {
    static let decisionesJSON = #"""
    {
      "pendientes": [
        {"tipo": "atasco", "id": "s-2:atasco:error_repetido:2026-10-12T10:00:00+00:00", "session_id": "s-2",
         "proyecto": "vive-demo", "carpeta": "E:\\vive-demo", "cuenta": "demo", "maquina": "alienware",
         "desde": "2026-10-12T10:00:00+00:00", "hace_s": 1080, "resumen": null, "detalle": "Repitió 3 veces el mismo error",
         "atasco": {"tipo": "error_repetido", "motivo": "Repitió 3 veces el mismo error", "ultimo_intento": "npm run build",
                    "ultimo_error": "Falta DATABASE_URL"}},
        {"tipo": "pregunta", "id": "s-3:pregunta:ab12", "session_id": "s-3", "proyecto": "visualizador-agentes",
         "carpeta": "E:\\visualizador-agentes", "cuenta": "personal", "maquina": "alienware",
         "desde": "2026-10-12T10:12:00+00:00", "hace_s": 360, "resumen": "Pregunta cómo enviar las notificaciones.",
         "detalle": "¿Las notificaciones push van por el servidor propio o por un servicio externo?",
         "pregunta": {"texto": "¿Las notificaciones push van por el servidor propio o por un servicio externo?",
                      "preguntas": [{"texto": "¿Las notificaciones push van por el servidor propio o por un servicio externo?",
                                     "encabezado": "Push", "multiple": false,
                                     "opciones": [{"etiqueta": "Directo desde el VPS a Apple (recomendado)", "descripcion": null},
                                                  {"etiqueta": "Con un servicio externo", "descripcion": "Más simple"}]}],
                      "responder_en": "pc"}},
        {"tipo": "permiso", "id": "p-9", "session_id": "s-1", "proyecto": "SkyNest", "carpeta": "E:\\Agents\\SkyNest",
         "cuenta": "personal", "maquina": "alienware", "desde": "2026-10-12T10:17:20+00:00", "hace_s": 40,
         "resumen": "Quiere borrar la carpeta de compilación de Unity.", "detalle": "Remove-Item -Recurse Library",
         "permiso": {"id": "p-9", "herramienta": "PowerShell", "esperando": true, "segundos_restantes": 50, "estado": "pendiente"}},
        {"tipo": "permiso", "id": "p-1", "session_id": "s-5", "proyecto": "server-monitor", "carpeta": null, "cuenta": "personal",
         "maquina": null, "desde": "2026-10-12T09:00:00+00:00", "hace_s": 4800, "resumen": null, "detalle": "git push",
         "permiso": {"id": "p-1", "herramienta": "Bash", "esperando": false, "segundos_restantes": 0, "estado": "pendiente"}}
      ],
      "conteo": {"permiso": 2, "pregunta": 1, "atasco": 1, "total": 4},
      "resueltas_hoy": [
        {"tipo": "permiso", "id": "p-0", "proyecto": "server-monitor", "cuenta": "personal", "maquina": "alienware",
         "texto": "Bash: systemctl restart nginx", "como": "Aprobado", "motivo": null, "quien": "app iOS",
         "cuando": "2026-10-12T09:48:00+00:00"},
        {"tipo": "permiso", "id": "p-00", "proyecto": "Buscapez", "cuenta": "demo", "maquina": "alienware",
         "texto": "Bash: git push origin main", "como": "Rechazado", "motivo": "Todavía no", "quien": "PC",
         "cuando": "2026-10-12T08:10:00+00:00"},
        {"tipo": "atasco", "id": "x", "proyecto": "vive-demo", "texto": "Error repetido", "como": "Ya lo vi",
         "quien": "app iOS", "cuando": "2026-10-12T08:00:00+00:00"}
      ]
    }
    """#

    func bandeja() throws -> Bandeja {
        try JSONDecoder().decode(Bandeja.self, from: Data(Self.decisionesJSON.utf8))
    }

    func testDecodificaLaBandeja() throws {
        let b = try bandeja()
        XCTAssertEqual(b.pendientes.count, 4)
        XCTAssertEqual(b.conteo?.total, 4)
        XCTAssertEqual(b.resueltas_hoy.count, 3)
        let q = try XCTUnwrap(b.pendientes.first { $0.tipo == "pregunta" })
        XCTAssertEqual(q.pregunta?.preguntas.first?.opciones.map(\.etiqueta),
                       ["Directo desde el VPS a Apple (recomendado)", "Con un servicio externo"])
        XCTAssertEqual(q.pregunta?.responder_en, "pc")
        let a = try XCTUnwrap(b.pendientes.first { $0.tipo == "atasco" })
        XCTAssertEqual(a.atasco?.ultimo_error, "Falta DATABASE_URL")
    }

    func testOrdenPermisosPreguntasAtascosYAntiguedad() throws {
        let orden = LogicaBandejas.ordenar(try bandeja().pendientes).map(\.id)
        XCTAssertEqual(orden, ["p-1", "p-9", "s-3:pregunta:ab12", "s-2:atasco:error_repetido:2026-10-12T10:00:00+00:00"])
    }

    func testTextosDeLasTarjetas() throws {
        let b = try bandeja()
        let p9 = try XCTUnwrap(b.pendientes.first { $0.id == "p-9" })
        XCTAssertEqual(LogicaBandejas.titulo(p9), "Permiso · SkyNest")
        XCTAssertEqual(LogicaBandejas.frase(p9), "Quiere borrar la carpeta de compilación de Unity.")
        XCTAssertEqual(LogicaBandejas.detalleTecnico(p9), "PowerShell: Remove-Item -Recurse Library")
        XCTAssertTrue(LogicaBandejas.sePuedeDecidir(p9))
        XCTAssertEqual(LogicaBandejas.tono(p9.tipo), .azul)

        // Sin frase del auxiliar se arma una; si no espera a la oficina, no se decide aquí.
        let p1 = try XCTUnwrap(b.pendientes.first { $0.id == "p-1" })
        XCTAssertEqual(LogicaBandejas.frase(p1), "Quiere subir los cambios al repositorio remoto (git push).")
        XCTAssertFalse(LogicaBandejas.sePuedeDecidir(p1))

        let q = try XCTUnwrap(b.pendientes.first { $0.tipo == "pregunta" })
        XCTAssertEqual(LogicaBandejas.titulo(q), "Pregunta · visualizador-agentes")
        XCTAssertEqual(LogicaBandejas.dondeResponder(q), "Respóndela en la PC (Alienware).")
        XCTAssertNil(LogicaBandejas.detalleTecnico(q))
        XCTAssertEqual(LogicaBandejas.tono(q.tipo), .naranja)

        let a = try XCTUnwrap(b.pendientes.first { $0.tipo == "atasco" })
        XCTAssertEqual(LogicaBandejas.titulo(a), "Atascado · vive-demo")
        XCTAssertEqual(LogicaBandejas.frase(a), "Repitió 3 veces el mismo error")
        XCTAssertEqual(LogicaBandejas.detalleTecnico(a), "npm run build\nFalta DATABASE_URL")
        XCTAssertEqual(LogicaBandejas.tono(a.tipo), .rojo)
        XCTAssertEqual(LogicaBandejas.hace(a, ahora: FechaISO.leer("2026-10-12T10:18:00+00:00")!), "18 min")
    }

    func testResueltasHoy() throws {
        let r = try bandeja().resueltas_hoy
        XCTAssertEqual(LogicaBandejas.tono(resuelta: r[0]), .verde)
        XCTAssertEqual(LogicaBandejas.tono(resuelta: r[1]), .rojo)
        XCTAssertEqual(LogicaBandejas.tono(resuelta: r[2]), .gris)
        XCTAssertEqual(LogicaBandejas.texto(resuelta: r[0]), "server-monitor · Bash: systemctl restart nginx · desde app iOS")
        XCTAssertEqual(LogicaBandejas.texto(resuelta: r[1]), "Buscapez · Bash: git push origin main · desde la PC")
    }

    func testEstadoConDecisionesPendientesYOpciones() throws {
        let json = #"""
        {"generado": "2026-10-12T10:00:00+00:00", "decisiones_pendientes": 3, "agentes": [
          {"agente": {"session_id": "s-3", "proyecto": "x"}, "estado": {"numero": 14, "nombre": "Pregunta"},
           "pregunta_pendiente": "¿A o B?",
           "pregunta_opciones": [{"texto": "¿A o B?", "encabezado": null, "multiple": true,
                                  "opciones": [{"etiqueta": "A", "descripcion": null}, {"etiqueta": "B", "descripcion": "la otra"}]}]}
        ]}
        """#
        let e = try JSONDecoder().decode(EstadoOficina.self, from: Data(json.utf8))
        XCTAssertEqual(e.decisiones_pendientes, 3)
        XCTAssertEqual(e.agentes[0].pregunta_opciones?.first?.opciones.last?.descripcion, "la otra")
        XCTAssertEqual(e.agentes[0].pregunta_opciones?.first?.multiple, true)
        // Un backend anterior, sin el conteo: no falla.
        let viejo = try JSONDecoder().decode(EstadoOficina.self, from: Data(#"{"agentes": []}"#.utf8))
        XCTAssertNil(viejo.decisiones_pendientes)
    }

    // MARK: - Ideas

    static let ideasJSON = #"""
    {"ideas": [
      {"id": "i1", "texto": "Modo fiesta", "proyecto": "visualizador-agentes", "origen": "escrita", "estado": "asignada",
       "creada": "2026-10-11T10:00:00+00:00", "actualizada": "2026-10-11T10:00:00+00:00"},
      {"id": "i2", "texto": "Revisar el correo de bienvenida", "proyecto": null, "origen": "dictada", "estado": "nueva",
       "creada": "2026-10-12T09:00:00+00:00", "actualizada": "2026-10-12T09:00:00+00:00"},
      {"id": "i3", "texto": "Vieja", "proyecto": "SkyNest", "origen": "escrita", "estado": "archivada",
       "creada": "2026-10-12T11:00:00+00:00", "actualizada": "2026-10-12T11:00:00+00:00"}
    ], "proyectos": ["visualizador-agentes", "SkyNest", "skynest", "", "Buscapez"]}
    """#

    func testIdeas() throws {
        let r = try JSONDecoder().decode(IdeasRespuesta.self, from: Data(Self.ideasJSON.utf8))
        XCTAssertEqual(r.ideas.count, 3)
        XCTAssertEqual(LogicaBandejas.guardadas(r.ideas).map(\.id), ["i2", "i1"])
        XCTAssertEqual(LogicaBandejas.proyectos(r.proyectos), ["Buscapez", "SkyNest", "visualizador-agentes"])
        XCTAssertEqual(LogicaBandejas.estado(r.ideas[0]).texto, "Asignada")
        XCTAssertEqual(LogicaBandejas.estado(r.ideas[1]).texto, "Sin asignar")
        XCTAssertEqual(LogicaBandejas.estado(r.ideas[1]).tono, .naranja)
        XCTAssertEqual(LogicaBandejas.estado(r.ideas[2]).texto, "Archivada")
        XCTAssertNil(LogicaBandejas.textoIdea("   \n "))
        XCTAssertEqual(LogicaBandejas.textoIdea("  Una idea \n"), "Una idea")
        XCTAssertEqual(LogicaBandejas.textoIdea(String(repeating: "a", count: 3000))?.count, 2000)
    }

    // MARK: - Cliente

    let cred = Credencial(servidor: URL(string: "https://agents.ejemplo.com")!,
                          cookieNombre: "__Host-visualizador_sesion", cookieValor: "vas_abc", expira: nil)

    override func setUp() {
        ProtocoloFalso.responder = nil
        ProtocoloFalso.recibidas = []
    }

    func cliente() -> ClienteAPI {
        ClienteAPI(servidor: cred.servidor, credencial: cred, sesion: ClienteAPI.sesionNueva(protocolos: [ProtocoloFalso.self]))
    }

    func cuerpo(_ p: URLRequest?) throws -> [String: Any] {
        try XCTUnwrap(JSONSerialization.jsonObject(with: p?.httpBody ?? Data()) as? [String: Any])
    }

    let ideaJSON = Data(#"{"id": "i9", "texto": "x", "proyecto": null, "origen": "dictada", "estado": "nueva"}"#.utf8)

    func testRutasDeLasBandejas() async throws {
        ProtocoloFalso.responder = { [ideaJSON] p in
            switch (p.httpMethod, p.url?.path()) {
            case ("GET", "/api/v1/decisiones"): return (200, [:], Data(Self.decisionesJSON.utf8))
            case ("POST", "/api/v1/decisiones/atascos/visto"): return (200, [:], Data(#"{"id": "a", "visto": "x"}"#.utf8))
            case ("GET", "/api/v1/ideas"): return (200, [:], Data(Self.ideasJSON.utf8))
            case ("POST", "/api/v1/ideas"): return (201, [:], ideaJSON)
            case ("PATCH", "/api/v1/ideas/i9"): return (200, [:], ideaJSON)
            case ("POST", "/api/v1/ideas/i9/archivar"): return (200, [:], ideaJSON)
            default: return (404, [:], Data())
            }
        }
        let c = cliente()
        _ = try await c.decisiones()

        try await c.atascoVisto("s-2:atasco:x")
        var p = ProtocoloFalso.recibidas.last
        XCTAssertEqual(p?.value(forHTTPHeaderField: "X-Visualizador"), "1")
        XCTAssertEqual(try cuerpo(p)["id"] as? String, "s-2:atasco:x")
        XCTAssertEqual(try cuerpo(p)["dispositivo"] as? String, "app")

        _ = try await c.ideas(archivadas: true)
        XCTAssertEqual(ProtocoloFalso.recibidas.last?.url?.query(), "archivadas=true")

        _ = try await c.crearIdea(texto: "x", proyecto: nil, dictada: true)
        p = ProtocoloFalso.recibidas.last
        XCTAssertEqual(try cuerpo(p)["origen"] as? String, "dictada")
        XCTAssertNil(try cuerpo(p)["proyecto"])

        // Quitar el proyecto manda null (no omitirlo: omitido no cambia nada).
        _ = try await c.cambiarProyecto(idea: "i9", proyecto: nil)
        p = ProtocoloFalso.recibidas.last
        XCTAssertEqual(p?.httpMethod, "PATCH")
        XCTAssertTrue(try cuerpo(p)["proyecto"] is NSNull)
        _ = try await c.cambiarProyecto(idea: "i9", proyecto: "SkyNest")
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["proyecto"] as? String, "SkyNest")

        _ = try await c.archivar(idea: "i9")
        XCTAssertEqual(try cuerpo(ProtocoloFalso.recibidas.last)["archivar"] as? Bool, true)
    }

    func testRechazarConMotivo() async throws {
        ProtocoloFalso.responder = { _ in
            (200, [:], Data(#"{"id": "p9", "herramienta": "Bash", "detalle": "ls", "esperando": false, "estado": "rechazada"}"#.utf8))
        }
        _ = try await cliente().decidir(permiso: "p9", aprobar: false, motivo: "  Todavía no  ")
        let c = try cuerpo(ProtocoloFalso.recibidas.last)
        XCTAssertEqual(c["decision"] as? String, "rechazar")
        XCTAssertEqual(c["motivo"] as? String, "Todavía no")
        XCTAssertEqual(c["dispositivo"] as? String, "app")
    }
}

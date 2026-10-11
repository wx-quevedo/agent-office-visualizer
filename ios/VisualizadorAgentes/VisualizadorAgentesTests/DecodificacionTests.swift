import XCTest
@testable import VisualizadorAgentes

/// Decodificación de las respuestas reales del backend (mismas formas que la web).
final class DecodificacionTests: XCTestCase {
    func decodificar<T: Decodable>(_ s: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(s.utf8))
    }

    static let estadoJSON = #"""
    {
      "generado": "2026-10-11T19:55:32.326000+00:00",
      "presencia": {"estado": "conectado", "motivo": "1 navegador(es)", "navegadores_conectados": 1,
                    "dispositivos": ["celular"], "ultimo_encargo": null, "desconectado_desde": null},
      "agentes": [
        {
          "agente": {"session_id": "s-1", "proyecto": "E:\\Agents\\SkyNest", "cuenta": "personal",
                     "maquina": "alienware", "modelo": "claude-opus-5-5[1m]"},
          "estado": {"numero": 13, "nombre": "Esperando permiso", "desde": "2026-10-11T19:55:00+00:00"},
          "espera": {"tipo": "permiso", "evidencia": {"herramienta": "PowerShell", "comando": "Remove-Item -Recurse Library", "n": 3, "ok": true, "x": null}},
          "espera_detalle": {"texto": "Espera tu permiso para PowerShell", "base": "Espera tu permiso", "segundos": 32.5, "limite_min": null},
          "atasco": null,
          "trabajo_continuo_s": 2040,
          "herramienta_actual": "PowerShell",
          "ultimo_evento": {"tipo": "permission_request", "hora": "2026-10-11T19:55:00+00:00"},
          "subagentes_activos": 0,
          "pregunta_pendiente": null,
          "cierre": null,
          "proceso": {"pid": 1234, "creado": 1760000000.5},
          "indicadores": {"herramientas_por_minuto": 2.5, "tokens_por_minuto": 1200, "tokens_totales": 312480,
                          "tokens_contexto": null, "tokens_motivo": null, "minutos_con_actividad": 34,
                          "contexto_usado_pct": 41.2, "errores_seguidos": 0, "errores_motivo": null},
          "eventos_recientes": [{"hora": "2026-10-11T19:55:00+00:00", "tipo": "pre_tool_use", "agente": null,
                                 "herramienta": "PowerShell", "detalle": "Remove-Item -Recurse Library"}],
          "permiso": {"id": "p-9", "session_id": "s-1", "herramienta": "PowerShell", "detalle": "Remove-Item -Recurse Library",
                      "cuenta": "personal", "proyecto": "SkyNest", "creada": "2026-10-11T19:55:00+00:00", "esperando": true,
                      "vence": "2026-10-11T19:56:30+00:00", "segundos_restantes": 58, "estado": "pendiente",
                      "motivo": null, "dispositivo": null, "decidida": null},
          "resumenes": {"permiso": {"clave": "k", "estado": "listo", "texto": "Quiere borrar la carpeta de compilación."}},
          "campo_nuevo_del_motor": {"lo": "que sea"}
        },
        {
          "agente": {"session_id": "s-2", "proyecto": "vive-demo", "cuenta": "demo"},
          "estado": {"numero": 5, "nombre": "Ejecutando un comando", "desde": "2026-10-11T19:40:00Z"},
          "espera": null,
          "atasco": {"tipo": "error_repetido", "motivo": "Repitió 3 veces el mismo error", "desde": "2026-10-11T19:37:00+00:00",
                     "ultimos_intentos": ["npm run build"], "ultimo_error": "Falta DATABASE_URL"},
          "herramienta_actual": null,
          "ultimo_evento": {"tipo": null, "hora": null},
          "subagentes_activos": 0,
          "pregunta_pendiente": null,
          "cierre": null,
          "proceso": null,
          "indicadores": {"errores_seguidos": 3},
          "eventos_recientes": []
        }
      ]
    }
    """#

    func testEstadoDeLaOficina() throws {
        let e: EstadoOficina = try decodificar(Self.estadoJSON)
        XCTAssertEqual(e.agentes.count, 2)
        XCTAssertEqual(e.presencia?.dispositivos, ["celular"])
        let a = e.agentes[0]
        XCTAssertEqual(a.id, "s-1")
        XCTAssertEqual(a.estado.numero, 13)
        XCTAssertEqual(a.espera?.evidencia?["comando"]?.texto, "Remove-Item -Recurse Library")
        XCTAssertEqual(a.espera?.evidencia?["n"], .numero(3))
        XCTAssertEqual(a.espera?.evidencia?["ok"], .booleano(true))
        XCTAssertEqual(a.espera?.evidencia?["x"], .nulo)
        XCTAssertEqual(a.permiso?.id, "p-9")
        XCTAssertTrue(a.permiso?.esperando ?? false)
        XCTAssertEqual(a.resumenes?["permiso"]?.texto, "Quiere borrar la carpeta de compilación.")
        XCTAssertEqual(a.indicadores?.tokens_totales, 312480)
        XCTAssertEqual(a.trabajo_continuo_s, 2040)
        let b = e.agentes[1]
        XCTAssertEqual(b.atasco?.ultimo_error, "Falta DATABASE_URL")
        XCTAssertNil(b.permiso)
        XCTAssertNil(b.espera_detalle)
    }

    func testHistorial() throws {
        let h: Historial = try decodificar(#"""
        {"session_id": "s-1", "proyecto": "SkyNest", "pagina": 1, "por_pagina": 20, "total": 2, "paginas": 1,
         "turnos": [
          {"numero": 2, "inicio": "2026-10-11T13:02:00+00:00", "fin": null, "duracion_s": 120, "pedido": "Fase 7A · Prompt 1",
           "herramientas": {"Bash": 3}, "total_herramientas": 3, "archivos_editados": [], "commits": [],
           "errores": 0, "tokens_salida": null, "resultado": "en_curso", "pregunta": null},
          {"numero": 1, "inicio": "2026-10-11T12:12:00+00:00", "fin": "2026-10-11T12:40:00+00:00", "duracion_s": 1680,
           "pedido": null, "herramientas": {}, "total_herramientas": 48, "archivos_editados": ["a.cs"],
           "commits": [{"hora": "2026-10-11T12:39:00+00:00", "mensaje": "fix: enemigos"}],
           "errores": 1, "tokens_salida": 52735, "resultado": "completado", "pregunta": null}
         ]}
        """#)
        XCTAssertEqual(h.turnos.count, 2)
        XCTAssertEqual(h.turnos[0].resultado, "en_curso")
        XCTAssertNil(h.turnos[0].fin)
        XCTAssertEqual(h.turnos[1].commits?.first?.mensaje, "fix: enemigos")
        XCTAssertEqual(h.turnos[1].tokens_salida, 52735)
    }

    func testConsumo() throws {
        let c: Consumo = try decodificar(#"""
        {"dia": "2026-10-11", "total": {"sesiones": 3, "tokens_salida": 707246, "segundos_trabajo": 9000, "segundos_con_agentes": 16500},
         "por_sesion": [{"session_id": "s-1", "proyecto": "E:\\Agents\\SkyNest", "tokens_salida": 312480, "segundos_trabajo": 2040, "continuo_s": 2040}],
         "auxiliar": {"etiqueta": "auxiliar", "total": {"llamadas": 0, "fallos": 0, "tokens_entrada": 0, "tokens_salida": 0, "segundos": 0}, "por_cuenta": []}}
        """#)
        XCTAssertEqual(c.total.segundos_con_agentes, 16500)
        XCTAssertEqual(Logica.tokensHoy(c, sesion: "s-1"), 312480)
        XCTAssertEqual(Logica.tokensHoy(c, sesion: "otra"), 0)
    }

    func testProyectos() throws {
        let r: ProyectosRespuesta = try decodificar(#"""
        {"proyectos": [
          {"carpeta": "E:\\visualizador-agentes", "maquina": "alienware", "tiene_project_md": true,
           "titulo": "Oficina de agentes",
           "plan": [{"nombre": "Etapa 0, base", "estado": "hecho"}, {"nombre": "Etapa 1: acceso", "estado": "hecho"},
                    {"nombre": "Etapa 1.1 sesiones", "estado": "hecho"}, {"nombre": "Etapa 2 ver bien", "estado": "hecho"},
                    {"nombre": "Etapa 3 App iOS", "estado": "en_curso"}, {"nombre": "Etapa 4 orquestador", "estado": "pendiente"}],
           "posicion": "Etapa 3", "siguiente_paso": "Prompt 31 arma la app base",
           "espera_decision": ["Disco del VPS al 85 %"],
           "ultimo_commit": {"hash": "ac1946abcdef", "mensaje": "feat: avisos resumidos", "fecha": "2026-10-11T16:20:00+00:00"},
           "modificado": "2026-10-11T16:20:00+00:00", "error": null, "recibido": "2026-10-11T16:21:00+00:00",
           "ultima_actividad": null,
           "prompts": [{"numero": 30, "nombre": "bocetos de la app", "estado": "hecho"}, {"numero": 31, "nombre": "app base", "estado": "pendiente"}],
           "prompts_turnos": [{"numero": 31, "nombre": "app base", "inicio": "2026-10-11T17:00:00+00:00", "duracion_s": 600,
                               "commits": [], "resultado": "en_curso", "session_id": "s-9"}]},
          {"carpeta": "/Users/w/otro"}
        ]}
        """#)
        XCTAssertEqual(r.proyectos.count, 2)
        let p = r.proyectos[0]
        XCTAssertEqual(p.plan.count, 6)
        XCTAssertEqual(p.espera_decision, ["Disco del VPS al 85 %"])
        XCTAssertEqual(p.prompts_turnos?.first?.resultado, "en_curso")
        XCTAssertFalse(r.proyectos[1].tiene_project_md)
        XCTAssertEqual(r.proyectos[1].espera_decision, [])

        let etapas = LogicaDonde.etapas(p.plan, posicion: p.posicion)
        XCTAssertEqual(etapas.map(\.corto), ["0", "1", "2", "3", "4"])
        XCTAssertEqual(etapas.map(\.estado), [.hecha, .hecha, .hecha, .actual, .pendiente])
        XCTAssertEqual(etapas[3].nombre, "App iOS")
        let prompts = LogicaDonde.promptsDeEtapa(p)
        XCTAssertEqual(prompts.first { $0.actual }?.numero, 31)
        XCTAssertEqual(prompts.first { $0.actual }?.estado, "en_curso")
    }

    func testFechasISO() throws {
        let a = try XCTUnwrap(FechaISO.leer("2026-10-11T19:55:32.326123+00:00"))
        let b = try XCTUnwrap(FechaISO.leer("2026-10-11T19:55:32.326Z"))
        XCTAssertEqual(a.timeIntervalSince1970, b.timeIntervalSince1970, accuracy: 0.001)
        XCTAssertNotNil(FechaISO.leer("2026-10-11T19:55:32+00:00"))
        XCTAssertNotNil(FechaISO.leer("2026-10-11T19:55:32"))
        XCTAssertNotNil(FechaISO.leer("2026-10-11T14:55:32-05:00"))
        XCTAssertNil(FechaISO.leer("ayer"))
        XCTAssertNil(FechaISO.leer(nil))
    }
}

import XCTest
@testable import VisualizadorAgentes

final class LogicaTests: XCTestCase {
    let ahora = FechaISO.leer("2026-10-11T20:00:00+00:00")!
    let utc = TimeZone(identifier: "UTC")!

    func agentes() throws -> [Agente] {
        try JSONDecoder().decode(EstadoOficina.self, from: Data(DecodificacionTests.estadoJSON.utf8)).agentes
    }

    func testGruposYConteo() throws {
        XCTAssertEqual(Logica.grupo(13), .espera)
        XCTAssertEqual(Logica.grupo(14), .espera)
        XCTAssertEqual(Logica.grupo(21), .cerrados)
        XCTAssertEqual(Logica.grupo(19), .inactivos)
        XCTAssertEqual(Logica.grupo(5), .trabajando)
        let a = try agentes()
        XCTAssertEqual(Logica.resumenConteo(a), "0 trabajando · 1 te espera · 1 atascado")
        XCTAssertEqual(Logica.pendientes(a), 2)
        XCTAssertEqual(Logica.teEsperan(a).map(\.id), ["s-1"])
        XCTAssertEqual(Logica.ordenLista(a).map(\.id), ["s-1", "s-2"])
    }

    func testFiltroPorCuenta() throws {
        let a = try agentes()
        XCTAssertEqual(Logica.filtrar(a, cuenta: .todas, ahora: ahora).count, 2)
        XCTAssertEqual(Logica.filtrar(a, cuenta: .personal, ahora: ahora).map(\.id), ["s-1"])
        XCTAssertEqual(Logica.filtrar(a, cuenta: .demo, ahora: ahora).map(\.id), ["s-2"])
    }

    func testTextosDeLaFila() throws {
        let a = try agentes()
        XCTAssertEqual(Logica.nombre(a[0]), "SkyNest")
        XCTAssertEqual(Logica.subtitulo(a[0]), "Personal · Opus 5.5 · Alienware")
        XCTAssertEqual(Logica.loQuePide(a[0]), "Quiere borrar la carpeta de compilación.")
        XCTAssertEqual(Logica.estadoCorto(a[0], ahora: ahora).texto, "Te pide permiso")
        XCTAssertEqual(Logica.estadoCorto(a[1], ahora: ahora).texto, "Parece atascado · 23 min")
        XCTAssertEqual(Logica.estadoCorto(a[1], ahora: ahora).tono, .rojo)
    }

    func testIniciales() {
        XCTAssertEqual(Logica.iniciales("SkyNest"), "SN")
        XCTAssertEqual(Logica.iniciales("vive-demo"), "VB")
        XCTAssertEqual(Logica.iniciales("visualizador-agentes"), "VA")
        XCTAssertEqual(Logica.iniciales("monitor"), "MO")
        XCTAssertEqual(Logica.iniciales("---"), "?")
    }

    func testModelosYTiempos() {
        XCTAssertEqual(Logica.nombreModelo("claude-opus-5-5[1m]"), "Opus 5.5")
        XCTAssertEqual(Logica.nombreModelo("claude-haiku-5-5"), "Haiku 5.5")
        XCTAssertEqual(Logica.nombreModelo("gpt-x"), "gpt-x")
        XCTAssertEqual(Logica.tiempoCorto(45), "45 s")
        XCTAssertEqual(Logica.tiempoCorto(2040), "34 min")
        XCTAssertEqual(Logica.tiempoCorto(16500), "4 h 35 min")
        XCTAssertEqual(Logica.reloj(134), "2:14")
        XCTAssertEqual(Logica.reloj(3909), "1:05:09")
        XCTAssertEqual(Logica.miles(312480), "312\u{00A0}480")
        XCTAssertEqual(Logica.milesCorto(312480), "312 k")
        XCTAssertEqual(Logica.cuando("2026-10-11T16:20:00+00:00", ahora: ahora, zona: utc), "Hoy 16:20")
        XCTAssertEqual(Logica.cuando("2026-10-10T18:20:00+00:00", ahora: ahora, zona: utc), "Ayer 18:20")
        XCTAssertEqual(Logica.cuando("2026-10-09T18:20:00+00:00", ahora: ahora, zona: utc), "9 oct 18:20")
    }

    func testComandoPeligroso() {
        let lista = ModeloApp.confirmarPorDefecto
        XCTAssertTrue(Logica.pideConfirmacion(herramienta: "PowerShell", detalle: "Remove-Item -Recurse Library", lista: lista))
        XCTAssertTrue(Logica.pideConfirmacion(herramienta: "Bash", detalle: "cd x && sudo rm -rf build", lista: lista))
        XCTAssertTrue(Logica.pideConfirmacion(herramienta: "Bash", detalle: "npm run deploy", lista: lista))
        XCTAssertTrue(Logica.pideConfirmacion(herramienta: "Bash", detalle: "git push origin main", lista: lista))
        XCTAssertFalse(Logica.pideConfirmacion(herramienta: "Bash", detalle: "ls -la", lista: lista))
        XCTAssertFalse(Logica.pideConfirmacion(herramienta: "Bash", detalle: "git status", lista: lista))
        XCTAssertFalse(Logica.pideConfirmacion(herramienta: "Edit", detalle: "rm.txt", lista: lista))
    }

    func testFraseDePermiso() {
        XCTAssertEqual(Logica.fraseDePermiso("Bash", "rm -rf build"), "Quiere borrar archivos o carpetas.")
        XCTAssertEqual(Logica.fraseDePermiso("Bash", "git push"), "Quiere subir los cambios al repositorio remoto (git push).")
        XCTAssertEqual(Logica.fraseDePermiso("Edit", "E:\\x\\a.cs"), "Quiere editar a.cs.")
        XCTAssertEqual(Logica.fraseDePermiso("mcp__plugin_miro_miro__crear", ""), "Quiere usar crear de miro.")
    }

    func testPermisoDecidible() throws {
        let p = try XCTUnwrap(try agentes()[0].permiso)
        XCTAssertTrue(Logica.sePuedeDecidir(p))
        var q = p
        q.estado = "aprobada"
        q.dispositivo = "celular"
        XCTAssertFalse(Logica.sePuedeDecidir(q))
        XCTAssertEqual(Logica.textoSinBotones(q), "Aprobado desde el celular.")
    }

    func testFichaAhoraMismoYCifras() throws {
        let a = try agentes()
        let am = Logica.ahoraMismo(a[0], ahora: ahora)
        XCTAssertEqual(am.texto, "Espera tu permiso")
        XCTAssertEqual(am.tiempo, "0:32")
        XCTAssertNil(am.razonable)
        let c = Logica.cifras(a[0], tokens: 312480, ahora: ahora)
        XCTAssertEqual(c.map(\.valor), ["34 min", "312 k", "Ninguno"])
        let c2 = Logica.cifras(a[1], tokens: nil, ahora: ahora)
        XCTAssertEqual(c2[2].titulo, "Atasco")
        XCTAssertTrue(c2[2].alerta)
    }

    func testProyectosConAgentes() throws {
        let a = try agentes()
        let api = [ProyectoApi(carpeta: "E:\\Agents\\SkyNest", maquina: "alienware", tiene_project_md: true),
                   ProyectoApi(carpeta: "/Users/w/tranquilo", tiene_project_md: true, ultimo_commit: .init(hash: "abc", mensaje: nil, fecha: nil))]
        let p = LogicaDonde.armar(api, a)
        // SkyNest pide permiso (primero), vive-demo está atascado y no tiene informe, el tranquilo al final.
        XCTAssertEqual(p.map(\.nombre), ["SkyNest", "vive-demo", "tranquilo"])
        XCTAssertEqual(p.map(\.alerta), [.permiso, .atasco, .listo])
        XCTAssertTrue(LogicaDonde.mismaCarpeta("SkyNest", "E:\\Agents\\SkyNest"))
        XCTAssertEqual(LogicaDonde.quienHace("Aprobar estos bocetos"), "Quién: tú.")
        XCTAssertEqual(LogicaDonde.quienHace("El Prompt 31 arma la app"), "Quién: el agente.")
    }
}

# ruff: noqa: E501  (datos de prueba: comandos y JSON reales en una línea)
"""Etapa 2.1: esperas específicas, historial por turno, consumo, atascos y datos de máquinas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import esperas
from app.core.agent_state_engine import AgentStateEngine, Thresholds, record_from_event
from app.core.atascos import Umbrales, clave_error, detectar
from app.core.consumo import continuo, del_dia, tokens_entre
from app.core.datos_maquinas import DatosMaquinas, cuenta_de_carpeta, set_datos_maquinas
from app.core.historial import mensaje_commit, pagina, turnos, una_linea
from app.models.events import AnyEvent, EventAdapter

T0 = datetime(2026, 10, 11, 14, 0, tzinfo=UTC)
REGLAS = esperas.cargar_reglas(None)


def ev(tipo: str, s: float, sid: str = "prueba-vb", **data: Any) -> AnyEvent:
    return EventAdapter.validate_python(
        {
            "event_type": tipo,
            "session_id": sid,
            "timestamp": T0 + timedelta(seconds=s),
            "data": data,
        }
    )


def recs(*eventos: AnyEvent) -> list[Any]:
    return [record_from_event(e, i) for i, e in enumerate(eventos)]


def bash(tipo: str, s: float, cmd: str, **extra: Any) -> AnyEvent:
    return ev(tipo, s, tool_name="Bash", tool_input={"command": cmd}, **extra)


# -- esperas específicas ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("herramienta", "comando", "descripcion", "segundos", "texto"),
    [
        ("Bash", "npm install", None, 40, "Instalando dependencias (npm), 40 s"),
        ("Bash", "cd frontend && pnpm i", None, 75, "Instalando dependencias (pnpm), 1 min"),
        ("Bash", "uv run pytest -q tests/", None, 185, "Corriendo pruebas (pytest), 3 min"),
        ("Bash", "npx vitest run", None, 30, "Corriendo pruebas (vitest), 30 s"),
        ("PowerShell", "npm test", None, 30, "Corriendo pruebas (npm), 30 s"),
        (
            "Bash",
            '"C:/Program Files/Unity/Hub/Editor/6000.0/Editor/Unity.exe"'
            " -batchmode -quit -projectPath x",
            None,
            125,
            "Unity: compilando scripts, 2 min",
        ),
        ("Bash", "blender -b escena.blend -f 1", None, 600, "Blender: render, 10 min"),
        ("mcp__unity__recompile_scripts", None, None, 50, "Unity: compilando scripts, 50 s"),
        ("mcp__unityMCP__run_tests", None, None, 50, "Unity: corriendo pruebas, 50 s"),
        ("mcp__github__create_pull_request", None, None, 5, "github: create pull request, 5 s"),
        ("Task", None, "Revisar el código", 90, "Subagente: Revisar el código, 1 min"),
        ("Bash", "npx tsc --noEmit", None, 20, "Revisando tipos (tsc), 20 s"),
        ("Bash", "git push origin main", None, 4, "Subiendo cambios (git push), 4 s"),
        ("Bash", "sleep 30", None, 12, "Esperando (sleep 30), 12 s"),
        ("Bash", "ffprobe video.mp4", None, 5, "Ejecutando ffprobe, 5 s"),
        (
            "Bash",
            "NODE_ENV=prod C:\\tools\\mi-herramienta.exe --x",
            None,
            3700,
            "Ejecutando mi-herramienta, 1 h 1 min",
        ),
        ("WebFetch", "https://ejemplo.com", None, 8, "Leyendo una página web, 8 s"),
        ("Grep", "patron", None, 1, "Leyendo archivos, 1 s"),
    ],
)
def test_esperas_especificas(
    herramienta: str, comando: str | None, descripcion: str | None, segundos: float, texto: str
) -> None:
    assert esperas.describir(herramienta, comando, descripcion, segundos, REGLAS)["texto"] == texto


def test_limites_razonables_por_tipo() -> None:
    assert esperas.describir("Bash", "pytest", None, 1, REGLAS)["limite_min"] == 20
    assert esperas.describir("Bash", "npm run dev", None, 1, REGLAS)["limite_min"] is None
    assert esperas.describir("Bash", "rarisimo", None, 1, REGLAS)["limite_min"] == 10


def test_tabla_editable(tmp_path: Path) -> None:
    ruta = tmp_path / "esperas.txt"
    ruta.write_text(
        "# comentario\nmi-script ## Generando el informe ## 5\n(roto ## inválida\nsin texto\n",
        encoding="utf-8",
    )
    reglas = esperas.cargar_reglas(ruta)
    assert len(reglas) == len(REGLAS) + 1  # las propias primero, luego las de fábrica
    d = esperas.describir("Bash", "python mi-script.py", None, 61, reglas)
    assert d["texto"] == "Generando el informe, 1 min" and d["limite_min"] == 5
    assert esperas.describir("Bash", "pytest", None, 1, reglas)["texto"].startswith("Corriendo")
    # sin archivo (o vacío): las de fábrica
    assert esperas.cargar_reglas(tmp_path / "no-existe.txt") == REGLAS
    (tmp_path / "vacio.txt").write_text("# nada\n", encoding="utf-8")
    assert esperas.cargar_reglas(tmp_path / "vacio.txt") == REGLAS
    nuevo = tmp_path / "datos" / "esperas.txt"
    esperas.crear_archivo(nuevo)
    assert nuevo.read_text(encoding="utf-8").startswith("# Esperas")


def test_duracion() -> None:
    assert [esperas.duracion(s) for s in (0, 59, 60, 3599, 3600, 3660)] == [
        "0 s",
        "59 s",
        "1 min",
        "59 min",
        "1 h",
        "1 h 1 min",
    ]


# -- historial por turno ------------------------------------------------------------------


def test_historial_por_turno() -> None:
    r = recs(
        ev("user_prompt_submit", 0, prompt="Arregla el login\ny agrega pruebas"),
        ev("pre_tool_use", 5, tool_name="Read", tool_input={"file_path": "a.py"}),
        ev("post_tool_use", 6, tool_name="Read", tool_input={"file_path": "a.py"}),
        ev("pre_tool_use", 10, tool_name="Edit", tool_input={"file_path": "E:/p/a.py"}),
        ev("post_tool_use", 11, tool_name="Edit", tool_input={"file_path": "E:/p/a.py"}),
        bash("pre_tool_use", 20, 'git commit -m "fix: login"'),
        bash("post_tool_use", 21, 'git commit -m "fix: login"'),
        ev("stop", 30),
        ev("user_prompt_submit", 100, prompt="Ahora el registro"),
        bash("pre_tool_use", 105, "pytest"),
        bash("post_tool_use_failure", 110, "pytest", error="2 failed"),
        ev("user_prompt_submit", 200, prompt="Olvídalo"),
        bash("pre_tool_use", 205, "ls"),
        bash("post_tool_use_failure", 206, "ls", error="cancelado", is_interrupt=True),
        ev("user_prompt_submit", 300, prompt="Revisa el deploy"),
        bash("pre_tool_use", 305, "ls"),
    )
    muestras = [(T0, 0), (T0 + timedelta(seconds=30), 500), (T0 + timedelta(seconds=110), 800)]
    lista = turnos(r, muestras, T0 + timedelta(seconds=400))
    assert [t["resultado"] for t in lista] == ["completado", "error", "interrumpido", "en_curso"]
    t1 = lista[0]
    assert t1["pedido"] == "Arregla el login"
    assert t1["herramientas"] == {"Read": 1, "Edit": 1, "Bash": 1}
    assert t1["archivos_editados"] == ["E:/p/a.py"]
    assert t1["commits"][0]["mensaje"] == "fix: login"
    assert t1["duracion_s"] == 30 and t1["tokens_salida"] == 500
    assert lista[1]["errores"] == 1 and lista[1]["tokens_salida"] == 300
    assert lista[3]["duracion_s"] == 100 and lista[3]["fin"] is None
    # turno abierto que espera permiso o respuesta
    assert (
        turnos(r, muestras, T0 + timedelta(seconds=400), esperando=True)[-1]["resultado"]
        == "esperando"
    )


def test_historial_pregunta_y_sin_pedido() -> None:
    r = recs(
        bash("pre_tool_use", 0, "ls"),
        bash("post_tool_use", 1, "ls"),
        ev("user_prompt_submit", 10, prompt="¿Lo despliego?"),
    )
    lista = turnos(r, [], T0 + timedelta(seconds=20))
    assert lista[0]["pedido"] is None and lista[0]["tokens_salida"] is None
    assert lista[1]["pedido"] == "¿Lo despliego?"


def test_paginacion_y_textos() -> None:
    lista = [{"numero": i} for i in range(1, 46)]
    p = pagina(lista, 2, 20)
    assert p["total"] == 45 and p["paginas"] == 3
    assert [t["numero"] for t in p["turnos"]][:2] == [25, 24]
    assert una_linea("  hola   mundo \n segunda") == "hola mundo"
    assert una_linea("x" * 300, 10) == "x" * 9 + "…"
    assert mensaje_commit("git commit -m 'feat: algo'") == "feat: algo"
    assert mensaje_commit("git commit -F - <<'EOF'\nfix: cosa\n\ncuerpo\nEOF") == "fix: cosa"


def test_historial_del_motor_y_del_registro(tmp_path: Path) -> None:
    from app.core.agent_event_store import AgentEventStore

    store = AgentEventStore(tmp_path / "e.db")
    store.start()
    reloj = [T0 + timedelta(seconds=60)]
    motor = AgentStateEngine(Thresholds(), store=store, clock=lambda: reloj[0], lectura_local=False)
    for e in (
        ev("session_start", 0, transcript_path="C:/u/.claude-demo/projects/p/x.jsonl"),
        ev("user_prompt_submit", 1, prompt="Hola"),
        ev("stop", 20),
    ):
        motor.accept(e)
    store.flush()
    h = motor.historial("prueba-vb")
    assert h is not None and h["cuenta"] == "demo" and h["turnos"][0]["resultado"] == "completado"
    # una sesión que ya no está en memoria se arma desde el registro
    otro = AgentStateEngine(Thresholds(), store=store, clock=lambda: reloj[0], lectura_local=False)
    h2 = otro.historial("prueba-vb")
    assert h2 is not None and h2["total"] == 1
    assert otro.historial("no-existe") is None
    store.close()


# -- detector de atascos -------------------------------------------------------------------


def _limite(rec: Any) -> tuple[float | None, str]:
    d = esperas.describir(rec.tool_name, rec.command, rec.descripcion, 0, REGLAS)
    lm = d["limite_min"]
    return (float(lm) if isinstance(lm, (int, float)) else None, str(d["base"]))


def _detectar(
    r: list[Any], ahora_s: float, pendientes: list[Any] | None = None, esperando: bool = False
):  # type: ignore[no-untyped-def]
    return detectar(
        r, pendientes or [], T0 + timedelta(seconds=ahora_s), esperando, _limite, Umbrales()
    )


def test_atasco_mismo_error_repetido() -> None:
    r = recs(
        ev("user_prompt_submit", 0, prompt="Compila"),
        *[
            x
            for i, ruta in enumerate(["C:/a/b.cs", "C:/a/c.cs", "C:/x/y.cs"])
            for x in (
                bash("pre_tool_use", 10 + i * 10, f"dotnet build {i}"),
                bash(
                    "post_tool_use_failure",
                    15 + i * 10,
                    f"dotnet build {i}",
                    error=f"error CS0103 in {ruta}({20 + i},5): name 'Foo' does not exist",
                ),
            )
        ],
    )
    a = _detectar(r, 60)
    assert a is not None and a["tipo"] == "error_repetido" and "3 veces" in a["motivo"]
    assert len(a["ultimos_intentos"]) == 3 and a["ultimo_error"]


def test_no_es_atasco_errores_distintos_o_ya_resuelto() -> None:
    distintos = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        bash("post_tool_use_failure", 1, "a", error="falta el módulo x"),
        bash("post_tool_use_failure", 2, "b", error="permiso denegado"),
        bash("post_tool_use_failure", 3, "c", error="tiempo agotado"),
    )
    assert _detectar(distintos, 10) is None
    resuelto = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        *[bash("post_tool_use_failure", i, "t", error="falló la prueba 7") for i in (1, 2, 3)],
        bash("post_tool_use", 4, "t"),
    )
    assert _detectar(resuelto, 10) is None
    otro_turno = recs(
        *[bash("post_tool_use_failure", i, "t", error="falló") for i in (1, 2)],
        ev("stop", 3),
        ev("user_prompt_submit", 4, prompt="y"),
        bash("post_tool_use_failure", 5, "t", error="falló"),
    )
    assert _detectar(otro_turno, 10) is None


def test_atasco_herramienta_larga() -> None:
    pre = bash("pre_tool_use", 10, "uv run pytest -q")
    r = recs(ev("user_prompt_submit", 0, prompt="Pruebas"), pre)
    pendiente = r[-1]
    assert _detectar(r, 10 + 19 * 60, [pendiente]) is None
    a = _detectar(r, 10 + 21 * 60, [pendiente])
    assert a is not None and a["tipo"] == "herramienta_larga"
    assert "Corriendo pruebas (pytest)" in a["motivo"] and "20 min" in a["motivo"]


def test_no_es_atasco_servidor_ni_segundo_plano() -> None:
    r = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        bash("pre_tool_use", 1, "npm run dev"),
        bash("pre_tool_use", 2, "pytest", tool_input_extra=None),
    )
    servidor = r[1]
    assert _detectar(r[:2], 7200, [servidor]) is None
    fondo = record_from_event(
        ev(
            "pre_tool_use",
            2,
            tool_name="Bash",
            tool_input={"command": "pytest", "run_in_background": True},
        ),
        9,
    )
    a = _detectar(r[:2] + [fondo], 7200, [fondo])
    assert a is None or a["tipo"] != "herramienta_larga"


def test_atasco_sin_avances() -> None:
    lecturas = [
        x
        for i in range(10)
        for x in (
            ev(
                "pre_tool_use", 60 + i * 200, tool_name="Read", tool_input={"file_path": f"f{i}.py"}
            ),
            ev(
                "post_tool_use",
                61 + i * 200,
                tool_name="Read",
                tool_input={"file_path": f"f{i}.py"},
            ),
        )
    ]
    r = recs(ev("user_prompt_submit", 0, prompt="Investiga"), *lecturas)
    # casi todo es leer: el umbral es 1,5 veces (45 min)
    assert _detectar(r, 2100) is None
    a = _detectar(r, 2800)
    assert a is not None and a["tipo"] == "sin_avances" and "46 min" in a["motivo"]
    # una edición reciente es avance
    con_edicion = r + recs(
        ev("pre_tool_use", 2000, tool_name="Edit", tool_input={"file_path": "a.py"}),
        ev("post_tool_use", 2001, tool_name="Edit", tool_input={"file_path": "a.py"}),
    )
    assert _detectar(con_edicion, 2800) is None
    # esperando permiso o respuesta, o turno terminado: no es atasco
    assert _detectar(r, 2800, esperando=True) is None
    assert _detectar(r + recs(ev("stop", 2050)), 2800) is None
    # turno corto: todavía no
    assert _detectar(r, 1700) is None


def test_clave_de_error_ignora_numeros_rutas_e_ids() -> None:
    def falla(herramienta: str, comando: str, error: str) -> Any:
        return recs(
            ev(
                "post_tool_use_failure",
                0,
                tool_name=herramienta,
                tool_input={"command": comando},
                error=error,
            )
        )[0]

    a = clave_error(falla("Bash", "python build.py", "Error en C:\\p\\a.py línea 12: id 0xdeadbeef"))
    b = clave_error(falla("Bash", "python build.py", "Error en /home/x/b.py línea 99: id 0x1234abcd"))
    assert a == b
    assert clave_error(falla("Edit", "x", "x")) != clave_error(falla("Bash", "x", "x"))
    # "Exit code N" no es el error: cuenta la línea siguiente y el programa
    npm = clave_error(falla("Bash", "npm run build", "Exit code 2\nerror TS2304: no existe X"))
    pytest_ = clave_error(falla("Bash", "pytest", "Exit code 1\n3 failed"))
    assert npm != pytest_


# -- consumo -------------------------------------------------------------------------------


def test_tokens_entre() -> None:
    m = [(T0 + timedelta(minutes=10), 100), (T0 + timedelta(minutes=70), 400)]
    assert tokens_entre(m, T0, T0 + timedelta(hours=2)) == 400  # empieza dentro: base 0
    assert tokens_entre(m, T0 + timedelta(minutes=30), T0 + timedelta(hours=2)) == 300
    assert tokens_entre(m, T0 - timedelta(hours=2), T0 - timedelta(hours=1)) == 0
    assert tokens_entre([], T0, T0) is None


def test_consumo_del_dia_por_cuenta_y_modelo() -> None:
    r1 = recs(
        ev("user_prompt_submit", 0, prompt="a"),
        ev("stop", 600),
        ev("user_prompt_submit", 700, prompt="b"),
    )
    r2 = recs(ev("user_prompt_submit", 0, sid="otra", prompt="c"), ev("stop", 300, sid="otra"))
    ahora = T0 + timedelta(seconds=1000)
    datos = del_dia(
        [
            {
                "session_id": "s1",
                "cuenta": "personal",
                "modelo": "claude-opus-5-5",
                "records": r1,
                "muestras": [(T0 + timedelta(seconds=600), 1000), (ahora, 1500)],
            },
            {
                "session_id": "s2",
                "cuenta": "demo",
                "modelo": "claude-sonnet-5-5",
                "records": r2,
                "muestras": [(T0 + timedelta(seconds=300), 200)],
            },
        ],
        T0 - timedelta(hours=1),
        ahora,
        ahora,
    )
    assert datos["total"]["tokens_salida"] == 1700
    assert datos["total"]["segundos_trabajo"] == 600 + 300 + 300
    assert datos["total"]["segundos_con_agentes"] == 900  # 0-600 y 700-1000
    cuentas = {c["cuenta"]: c for c in datos["por_cuenta"]}
    assert cuentas["personal"]["tokens_salida"] == 1500 and cuentas["demo"]["tokens_salida"] == 200
    assert {m["modelo"] for m in datos["por_modelo"]} == {"claude-opus-5-5", "claude-sonnet-5-5"}
    s1 = next(s for s in datos["por_sesion"] if s["session_id"] == "s1")
    assert s1["continuo_s"] == 1000 and s1["turnos"] == 2  # pausa de 100 s: mismo tramo


def test_trabajo_continuo_une_pausas_cortas() -> None:
    r = recs(
        ev("user_prompt_submit", 0, prompt="a"),
        ev("stop", 100),
        ev("user_prompt_submit", 200, prompt="b"),  # pausa de 100 s: sigue el tramo
    )
    lista = turnos(r, [], T0 + timedelta(seconds=300))
    assert continuo(lista, T0 + timedelta(seconds=300)) == 300
    terminado = turnos(r[:2], [], T0 + timedelta(seconds=300))
    assert continuo(terminado, T0 + timedelta(seconds=300)) == 0


# -- datos de las máquinas y rutas -----------------------------------------------------------


def test_cuenta_de_carpeta() -> None:
    assert cuenta_de_carpeta("C:\\Users\\w\\.claude") == "personal"
    assert cuenta_de_carpeta("C:/Users/w/.claude-demo/") == "demo"
    assert cuenta_de_carpeta(None) == "desconocida"


def test_limites_y_proyectos_persisten(tmp_path: Path) -> None:
    d = DatosMaquinas(tmp_path)
    futuro = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    pasado = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    d.registrar_limites(
        "alienware",
        "C:/Users/w/.claude",
        {
            "cinco_horas": {"usado_pct": 23.5, "reinicia": futuro},
            "semanal": {"usado_pct": 41, "reinicia": pasado},
        },
    )
    d.registrar_proyectos(
        "alienware", [{"carpeta": "E:/proyecto", "posicion": "Etapa 2"}, {"x": 1}]
    )
    otra = DatosMaquinas(tmp_path)  # reinicio del backend
    vista = otra.vista_limites()
    assert vista[0]["cuenta"] == "personal"
    assert vista[0]["cinco_horas"]["vencida"] is False and vista[0]["semanal"]["vencida"] is True
    assert otra.vista_proyectos()[0]["posicion"] == "Etapa 2"


def test_rutas_de_ver_bien(tmp_path: Path) -> None:
    from app.main import app

    set_datos_maquinas(DatosMaquinas(tmp_path))
    try:
        c = TestClient(app)
        r = c.post(
            "/api/v1/maquinas/limites",
            json={
                "cuentas": [
                    {
                        "cuenta_dir": "C:/u/.claude-demo",
                        "cinco_horas": {"usado_pct": 10, "reinicia": "2026-10-11T20:00:00Z"},
                    }
                ]
            },
        )
        assert r.status_code == 200 and r.json()["cuentas"] == ["demo"]
        assert (
            c.post(
                "/api/v1/maquinas/limites", json={"cuentas": [{"cinco_horas": {"usado_pct": 150}}]}
            ).status_code
            == 422
        )
        assert c.get("/api/v1/limites").json()["cuentas"][0]["cuenta"] == "demo"
        r = c.post(
            "/api/v1/maquinas/proyectos",
            json={
                "proyectos": [
                    {
                        "carpeta": "E:/p",
                        "tiene_project_md": True,
                        "plan": [{"nombre": "Etapa 1", "estado": "hecho"}],
                    }
                ]
            },
        )
        assert r.json() == {"recibidos": 1}
        assert c.get("/api/v1/proyectos").json()["proyectos"][0]["carpeta"] == "E:/p"
        consumo = c.get("/api/v1/consumo").json()
        assert {"dia", "total", "por_cuenta", "por_modelo", "por_sesion"} <= consumo.keys()
        assert c.get("/api/v1/consumo?dia=2000-01-01").status_code == 422
        assert c.get("/api/v1/agents/no-existe/historial").status_code == 404
    finally:
        set_datos_maquinas(None)


# -- casos de la revisión independiente -------------------------------------------------


@pytest.mark.parametrize(
    ("comando", "texto"),
    [
        ('git commit -m "push fix"', "Haciendo commit, 1 min"),
        ('git commit -m "fix: retry pull logic"', "Haciendo commit, 1 min"),
        ("git commit -F - <<'EOF'\nfix: pytest y npm install\nEOF", "Haciendo commit, 1 min"),
        ("grep -rn pytest docs/", "Ejecutando grep, 1 min"),
        ("cat pytest.ini", "Ejecutando cat, 1 min"),
        ("cat ~/.ssh/config", "Ejecutando cat, 1 min"),
        ("cd E:/proyectos/blender-addon && uv run pytest", "Corriendo pruebas (pytest), 1 min"),
        ("python -m pytest -q", "Corriendo pruebas (pytest), 1 min"),
        ("cd backend && uv run python informe.py", "Ejecutando python informe.py, 1 min"),
        ("cd frontend && npm run lint", "Revisando el código (npm), 1 min"),
        ("npm start", "Servidor de desarrollo, 1 min"),
        ("tail -f registro.log", "Siguiendo un registro, 1 min"),
        ("sleep 5m", "Esperando (sleep 5m), 1 min"),
        ("Start-Sleep -Milliseconds 500", "Esperando (500 ms), 1 min"),
        (
            '& "C:/Program Files/Unity/Hub/Editor/6000.0.23f1/Editor/Unity.exe" -batchmode'
            " -projectPath x -executeMethod Build.Run -quit",
            "Unity: compilando el proyecto, 1 min",
        ),
        (
            '"/c/Program Files/Blender Foundation/Blender 4.2/blender.exe" -b f.blend -o //out/ -a',
            "Blender: render, 1 min",
        ),
        ('ssh -t <VPS_USER>@<VPS_IP> "sudo ls"', "Trabajando en un servidor remoto, 1 min"),
    ],
)
def test_esperas_por_posicion_de_comando(comando: str, texto: str) -> None:
    assert esperas.describir("Bash", comando, None, 65, REGLAS)["texto"] == texto


def test_esperas_mcp_de_plugins_y_subagente_sin_descripcion() -> None:
    assert esperas.describir("mcp__plugin_miro_miro__board_get", None, None, 5, REGLAS)[
        "texto"
    ] == ("miro: board get, 5 s")
    assert esperas.describir("mcp__claude-in-chrome__navigate", None, None, 5, REGLAS)["texto"] == (
        "Navegador: navigate, 5 s"
    )
    d = esperas.describir("Task", None, None, 5, REGLAS)
    assert d["texto"] == "Subagente, 5 s" and d["limite_min"] == 60


def test_commits_en_mensajes_y_heredoc() -> None:
    assert mensaje_commit("git commit -am 'quick fix'") == "quick fix"
    assert (
        mensaje_commit("git commit -m \"$(cat <<'EOF'\nfix: algo\n\ncuerpo\nEOF\n)\"")
        == "fix: algo"
    )
    r = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        bash("pre_tool_use", 1, "echo 'recordar: git commit'"),
        bash("post_tool_use", 2, "echo 'recordar: git commit'"),
    )
    assert turnos(r, [], T0 + timedelta(seconds=10))[0]["commits"] == []
    from app.core.historial import COMMIT

    assert not COMMIT.search("python -c \"for c in ['cd a && git commit -m x']\"")
    assert not COMMIT.search("python - <<'EOF'\ngit commit -m x\nEOF")
    assert COMMIT.search('git add -A && git commit -q -m "a && b"')


def test_no_es_atasco_esperar_al_usuario_ni_interrupciones() -> None:
    pregunta = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        ev("pre_tool_use", 1, tool_name="AskUserQuestion", tool_input={}),
    )
    assert _detectar(pregunta, 900, [pregunta[-1]]) is None
    permiso = recs(ev("user_prompt_submit", 0, prompt="x"), bash("pre_tool_use", 1, "rm -rf x"))
    assert _detectar(permiso, 900, [permiso[-1]], esperando=True) is None
    interrupciones = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        *[
            bash("post_tool_use_failure", i, "ls", error="interrumpido", is_interrupt=True)
            for i in (1, 2, 3)
        ],
    )
    assert _detectar(interrupciones, 10) is None
    distintos = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        bash("post_tool_use_failure", 1, "npm run build", error="Exit code 2\nerror TS2304"),
        bash("post_tool_use_failure", 2, "pytest", error="Exit code 1\n3 failed"),
        bash("post_tool_use_failure", 3, "ls nope", error="Exit code 2\nNo such file"),
    )
    assert _detectar(distintos, 10) is None


def test_trabajo_despues_del_stop_sin_pedido_nuevo() -> None:
    r = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        ev("stop", 5),
        *[
            x
            for i in range(4)
            for x in (
                bash("pre_tool_use", 10 + i * 2, "dotnet build"),
                bash("post_tool_use_failure", 11 + i * 2, "dotnet build", error="CS0103 Foo"),
            )
        ],
    )
    a = _detectar(r, 30)
    assert a is not None and a["tipo"] == "error_repetido"


def test_escrituras_por_terminal_y_mcp_son_avance() -> None:
    def trabajo(cmd_o_herramienta: str, mcp: bool) -> list[Any]:
        eventos: list[AnyEvent] = [ev("user_prompt_submit", 0, prompt="x")]
        for i in range(12):
            s = 60 + i * 200
            if mcp:
                eventos += [
                    ev("pre_tool_use", s, tool_name=cmd_o_herramienta, tool_input={}),
                    ev("post_tool_use", s + 1, tool_name=cmd_o_herramienta, tool_input={}),
                ]
            else:
                eventos += [
                    bash("pre_tool_use", s, cmd_o_herramienta),
                    bash("post_tool_use", s + 1, cmd_o_herramienta),
                ]
        return recs(*eventos)

    assert _detectar(trabajo("Set-Content -Path a.txt -Value x", False), 2500) is None
    assert _detectar(trabajo("sed -i 's/a/b/' x.py", False), 2500) is None
    assert _detectar(trabajo("mcp__UnityMCP__manage_script", True), 2500) is None
    a = _detectar(trabajo("git status", False), 2500)
    assert a is not None and a["tipo"] == "sin_avances"


def test_ventana_sin_avances_despues_de_una_herramienta_larga() -> None:
    r = recs(
        ev("user_prompt_submit", 0, prompt="x"),
        bash("pre_tool_use", 10, "pytest", tool_use_id="t1"),
        bash("post_tool_use", 10 + 25 * 60, "pytest", tool_use_id="t1"),
        *[bash("pre_tool_use", 1600 + i * 60, f"git log {i}") for i in range(5)],
    )
    # 30 min desde el pedido, pero solo 5 desde que terminaron las pruebas
    assert _detectar(r, 1900) is None

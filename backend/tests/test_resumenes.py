"""Avisos resumidos (etapa 2.4): avisos vigentes, frases, interruptor, consumo del
auxiliar y el filtro de los eventos de su carpeta."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.agent_state_engine import AgentStateEngine, Thresholds, override_state_engine
from app.core.resumenes import Resumenes, avisos_del_agente, es_auxiliar, set_resumenes
from app.models.events import EventAdapter

T0 = datetime(2026, 10, 11, 14, 0, tzinfo=UTC)
AUXILIAR = "C:\\Users\\w\\.visualizador-monitor\\auxiliar"


def _agente(numero: int, **extra: Any) -> dict[str, Any]:
    return {
        "agente": {"session_id": "s1", "proyecto": "E:/Test/SkyNest", "cuenta": "personal"},
        "estado": {"numero": numero, "nombre": "x", "desde": "2026-10-11T14:00:00+00:00"},
        "espera": None,
        "pregunta_pendiente": None,
        "atasco": None,
        **extra,
    }


def test_es_auxiliar() -> None:
    assert es_auxiliar(AUXILIAR)
    assert es_auxiliar(None, "c:/users/w/.visualizador-monitor/auxiliar/sub")
    assert not es_auxiliar("E:/visualizador-agentes", None)
    assert not es_auxiliar("C:/Users/w/.visualizador-monitor/auxiliares")


def test_avisos_de_cada_tipo() -> None:
    permiso = {"id": "abc", "herramienta": "PowerShell", "detalle": "Remove-Item -Recurse x"}
    [p] = avisos_del_agente(_agente(13), permiso)
    assert p["tipo"] == "permiso" and p["clave"] == "s1:permiso:abc"
    assert p["datos"] == {"herramienta": "PowerShell", "detalle": "Remove-Item -Recurse x"}
    # Sin solicitud registrada: lo que dice la espera.
    [p2] = avisos_del_agente(
        _agente(13, espera={"evidencia": {"herramienta": "Bash", "comando": "git push"}})
    )
    assert p2["datos"]["detalle"] == "git push"

    [q] = avisos_del_agente(_agente(14, pregunta_pendiente="¿Publico?"))
    assert q["tipo"] == "pregunta" and q["datos"] == {"pregunta": "¿Publico?"}
    [q2] = avisos_del_agente(_agente(14, pregunta_pendiente="¿Otra cosa?"))
    assert q2["clave"] != q["clave"]  # otra pregunta, otro resumen

    [t] = avisos_del_agente(
        _agente(11),
        ultimo_turno={"pedido": "Corregir el login", "commits": [{}], "archivos_editados": []},
    )
    assert t["tipo"] == "termino" and t["datos"] == {"pedido": "Corregir el login", "commits": 1}

    atasco = {
        "tipo": "error_repetido",
        "motivo": "Repite el mismo error 3 veces",
        "desde": "2026-10-11T13:50:00+00:00",
        "ultimos_intentos": ["Bash: npm test", "Bash: npm run build"],
        "ultimo_error": "falta DATABASE_URL",
    }
    avisos = avisos_del_agente(_agente(4, atasco=atasco))
    assert [a["tipo"] for a in avisos] == ["atasco"]
    assert avisos[0]["datos"]["ultimo_intento"] == "Bash: npm run build"
    assert avisos_del_agente(_agente(4)) == []


def test_frases_interruptor_y_consumo(tmp_path: Path) -> None:
    r = Resumenes(tmp_path)
    avisos = avisos_del_agente(_agente(14, pregunta_pendiente="¿Publico?"))
    assert r.vista(avisos)["pregunta"]["estado"] == "pendiente"
    r.registrar(
        avisos[0]["clave"],
        "SkyNest te pregunta si publica la versión nueva.",
        "alienware",
        {
            "llamo": True,
            "segundos": 2.5,
            "tokens_entrada": 756,
            "tokens_salida": 20,
            "cuenta": "personal",
            "costo_usd": 0.0002,
        },
        T0,
    )
    vista = r.vista(avisos)["pregunta"]
    assert vista == {
        "clave": avisos[0]["clave"],
        "estado": "listo",
        "texto": "SkyNest te pregunta si publica la versión nueva.",
    }
    r.registrar(
        "s1:permiso:x",
        None,
        "alienware",
        {"llamo": True, "segundos": 8, "cuenta": "demo", "motivo": "tiempo_agotado"},
        T0,
    )
    r.registrar("s1:permiso:y", None, "alienware", {"llamo": False, "motivo": "sin_cuenta"}, T0)
    assert r.obtener("s1:permiso:x")["estado"] == "fallo"  # type: ignore[index]
    c = r.consumo(T0 - timedelta(hours=1), T0 + timedelta(hours=1))
    assert c["etiqueta"] == "auxiliar"
    assert c["total"]["llamadas"] == 2 and c["total"]["fallos"] == 1
    assert c["total"]["tokens_entrada"] == 756 and c["total"]["segundos"] == 10.5
    assert [x["cuenta"] for x in c["por_cuenta"]] == ["demo", "personal"]
    # El interruptor persiste.
    r.cambiar(False)
    assert Resumenes(tmp_path).activos is False
    assert r.vista(avisos)["pregunta"]["estado"] == "apagado"


def test_el_motor_ignora_los_eventos_del_auxiliar() -> None:
    motor = AgentStateEngine(Thresholds(), clock=lambda: T0 + timedelta(seconds=5))
    for sid, carpeta in (("auxiliar-1", AUXILIAR), ("prueba-real", "E:/Test/SkyNest")):
        motor.accept(
            EventAdapter.validate_python(
                {
                    "event_type": "user_prompt_submit",
                    "session_id": sid,
                    "timestamp": T0,
                    "data": {"project_dir": carpeta, "prompt": "hola"},
                }
            )
        )
    assert list(motor.sessions) == ["prueba-real"]


def test_rutas_de_avisos(tmp_path: Path) -> None:
    from app.main import app

    reloj = [T0 + timedelta(seconds=30)]
    motor = AgentStateEngine(
        Thresholds(),
        clock=lambda: reloj[0],
        browsers_provider=lambda: 1,
        process_alive=lambda p, c: True,
    )
    for tipo, s, datos in (
        ("user_prompt_submit", 0, {"prompt": "Corregir el login"}),
        ("pre_tool_use", 1, {"tool_name": "Read", "tool_input": {"file_path": "a.py"}}),
        ("post_tool_use", 2, {"tool_name": "Read"}),
        ("stop", 5, {}),
    ):
        motor.accept(
            EventAdapter.validate_python(
                {
                    "event_type": tipo,
                    "session_id": "prueba-avisos",
                    "timestamp": T0 + timedelta(seconds=s),
                    "data": {"project_dir": "E:/Test/SkyNest", **datos},
                }
            )
        )
    override_state_engine(motor)
    set_resumenes(Resumenes(tmp_path))
    try:
        c = TestClient(app)
        numero = c.get("/api/v1/agents/state").json()["agentes"][0]["estado"]["numero"]
        assert numero == 11
        avisos = c.get("/api/v1/maquinas/avisos").json()["avisos"]
        assert [a["tipo"] for a in avisos] == ["termino"]
        aviso = avisos[0]
        assert aviso["proyecto"] == "SkyNest" and aviso["datos"]["pedido"] == "Corregir el login"
        r = c.post(
            "/api/v1/maquinas/resumenes",
            json={
                "clave": aviso["clave"],
                "texto": "SkyNest terminó de corregir el login y está listo para lo siguiente.",
                "metricas": {
                    "llamo": True,
                    "segundos": 3.1,
                    "tokens_salida": 18,
                    "cuenta": "personal",
                },
            },
        )
        assert r.json() == {"estado": "listo"}
        assert c.get("/api/v1/maquinas/avisos").json()["avisos"] == []  # ya resumido
        estado = c.get("/api/v1/agents/state").json()["agentes"][0]
        assert estado["resumenes"]["termino"]["texto"].startswith("SkyNest terminó")
        consumo = c.get("/api/v1/consumo").json()["auxiliar"]
        assert consumo["etiqueta"] == "auxiliar"
        # Interruptor apagado: el monitor no recibe avisos y la oficina lo sabe.
        assert c.put("/api/v1/avisos/config", json={"resumenes": False}).json() == {
            "resumenes": False
        }
        assert c.get("/api/v1/maquinas/avisos").json() == {"activos": False, "avisos": []}
        assert c.get("/api/v1/avisos/config").json() == {"resumenes": False}
        # Una tarea terminada vieja no se resume.
        c.put("/api/v1/avisos/config", json={"resumenes": True})
        set_resumenes(Resumenes(tmp_path / "otra"))
        reloj[0] = T0 + timedelta(minutes=10)
        assert c.get("/api/v1/maquinas/avisos").json()["avisos"] == []
    finally:
        override_state_engine(None)
        set_resumenes(None)


# -- revisión independiente (etapa 2.4) -------------------------------------------------


def test_el_backend_enmascara_lo_que_manda_al_monitor() -> None:
    from app.core.secretos import enmascarar

    permiso = {"id": "x", "herramienta": "Bash", "detalle": "mysql -u root -pHunter2 app"}
    [p] = avisos_del_agente(_agente(13), permiso)
    assert "Hunter2" not in p["datos"]["detalle"]
    # La misma regla que el monitor (archivo idéntico).
    monitor = Path(__file__).parents[2] / "monitor" / "src" / "visualizador_monitor" / "secretos.py"
    propio = Path(__file__).parents[1] / "app" / "core" / "secretos.py"
    if monitor.is_file():
        assert monitor.read_bytes() == propio.read_bytes()
    assert enmascarar("curl -u admin:Clave123 x") == "curl -u admin:[secreto] x"


def test_una_frase_lista_no_se_reemplaza_y_una_con_secretos_no_se_guarda(tmp_path: Path) -> None:
    r = Resumenes(tmp_path)
    r.registrar("s1:pregunta:a", "SkyNest te pregunta algo.", "alienware", {}, T0)
    r.registrar("s1:pregunta:a", "Texto inyectado.", "alienware", {}, T0)
    assert r.obtener("s1:pregunta:a")["texto"] == "SkyNest te pregunta algo."  # type: ignore[index]
    fila = r.registrar(
        "s1:pregunta:b", "SkyNest usa ghp_abcdefghijklmnopqrstuvwx12", "alienware", {}, T0
    )
    assert fila["estado"] == "fallo" and fila["texto"] is None


def test_solo_la_maquina_de_la_sesion_y_solo_avisos_vigentes(tmp_path: Path) -> None:
    from app.main import app

    motor = AgentStateEngine(
        Thresholds(), clock=lambda: T0 + timedelta(seconds=30), browsers_provider=lambda: 1
    )
    for tipo, s in (("user_prompt_submit", 0), ("stop", 5)):
        motor.accept(
            EventAdapter.validate_python(
                {
                    "event_type": tipo,
                    "session_id": "prueba-otra",
                    "machine_id": "torre",
                    "timestamp": T0 + timedelta(seconds=s),
                    "data": {"project_dir": "E:/x", "prompt": "hola"},
                }
            )
        )
    override_state_engine(motor)
    set_resumenes(Resumenes(tmp_path))
    try:
        c = TestClient(app)
        # Sin token, la máquina es la local (alienware): la sesión es de "torre".
        assert c.get("/api/v1/maquinas/avisos").json()["avisos"] == []
        r = c.post(
            "/api/v1/maquinas/resumenes", json={"clave": "prueba-otra:termino:x", "texto": "x"}
        )
        assert r.status_code == 403
        assert (
            c.post(
                "/api/v1/maquinas/resumenes", json={"clave": "no-existe:x", "texto": "x"}
            ).status_code
            == 403
        )
    finally:
        override_state_engine(None)
        set_resumenes(None)


def test_el_aviso_vencido_no_guarda_frase(tmp_path: Path) -> None:
    from app.main import app

    motor = AgentStateEngine(
        Thresholds(), clock=lambda: T0 + timedelta(seconds=30), browsers_provider=lambda: 1
    )
    motor.accept(
        EventAdapter.validate_python(
            {
                "event_type": "user_prompt_submit",
                "session_id": "prueba-vencido",
                "timestamp": T0,
                "data": {"project_dir": "E:/x", "prompt": "hola"},
            }
        )
    )
    override_state_engine(motor)
    set_resumenes(Resumenes(tmp_path))
    try:
        c = TestClient(app)
        r = c.post(
            "/api/v1/maquinas/resumenes",
            json={
                "clave": "prueba-vencido:permiso:viejo",
                "texto": "x",
                "metricas": {"llamo": True, "cuenta": "personal"},
            },
        )
        assert r.json() == {"estado": "vencido"}
        consumo = c.get("/api/v1/consumo").json()["auxiliar"]
        assert consumo["total"]["llamadas"] == 1  # el consumo sí se anota
    finally:
        override_state_engine(None)
        set_resumenes(None)


def test_solicitud_de_permiso_del_auxiliar_ignorada() -> None:
    from app.main import app

    c = TestClient(app)
    r = c.post(
        "/api/v1/permisos/solicitudes",
        json={
            "id": "prueba-aux-1",
            "session_id": "prueba-aux",
            "herramienta": "Bash",
            "entrada": {"command": "ls"},
            "cuenta": "personal",
            "proyecto": AUXILIAR,
        },
    )
    assert r.status_code == 200 and r.json()["estado"] == "ignorada"
    assert r.json()["esperar"] is False


def test_un_13_que_es_una_pregunta_se_resume_como_pregunta() -> None:
    a = _agente(
        13,
        espera={"evidencia": {"herramienta": "AskUserQuestion", "comando": "¿Cómo sigo?"}},
        pregunta_pendiente="La clave fue rechazada. ¿Cómo sigo?",
    )
    [p] = avisos_del_agente(a)
    assert p["tipo"] == "permiso" and p["como"] == "pregunta"
    assert p["datos"] == {"pregunta": "La clave fue rechazada. ¿Cómo sigo?"}

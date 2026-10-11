"""Bandejas de Decisiones e Ideas (etapa 3, Prompt 33)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import permisos
from app.core.agent_state_engine import (
    AgentStateEngine,
    Thresholds,
    override_state_engine,
    preguntas_de,
)
from app.core.bandejas import Bandejas, pendientes, set_bandejas
from app.core.datos_maquinas import DatosMaquinas, set_datos_maquinas
from app.core.permisos import RegistroPermisos
from app.core.resumenes import Resumenes, set_resumenes
from app.models.events import EventAdapter

# 2026-10-12 15:00 en Guayaquil (UTC-5).
T0 = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)
ASK = {
    "questions": [
        {
            "question": "¿Las notificaciones push van por el servidor propio o por uno externo?",
            "header": "Push",
            "options": [
                {"label": "Directo desde el VPS a Apple", "description": "Recomendado"},
                {"label": "Con un servicio externo"},
            ],
            "multiSelect": False,
        }
    ]
}


def _agente(sid: str, numero: int, desde: datetime, **extra: Any) -> dict[str, Any]:
    return {
        "agente": {
            "session_id": sid,
            "proyecto": f"E:/{sid}",
            "cuenta": "personal",
            "maquina": "alienware",
        },
        "estado": {"numero": numero, "nombre": "x", "desde": desde.isoformat()},
        "espera": None,
        "pregunta_pendiente": None,
        "pregunta_opciones": None,
        "atasco": None,
        "permiso": None,
        "resumenes": {},
        **extra,
    }


def _atasco(desde: datetime) -> dict[str, Any]:
    return {
        "tipo": "error_repetido",
        "motivo": "Repite el mismo error 3 veces (Bash)",
        "desde": desde.isoformat(),
        "ultimos_intentos": ["Bash: npm test", "Bash: npm run build"],
        "ultimo_error": "falta DATABASE_URL",
    }


# -- la bandeja (pura) ---------------------------------------------------------------


def test_preguntas_de_toma_las_opciones() -> None:
    [p] = preguntas_de(ASK["questions"]) or []
    assert p["texto"].startswith("¿Las notificaciones push")
    assert p["encabezado"] == "Push" and p["multiple"] is False
    assert [o["etiqueta"] for o in p["opciones"]] == [
        "Directo desde el VPS a Apple",
        "Con un servicio externo",
    ]
    assert p["opciones"][0]["descripcion"] == "Recomendado"
    assert preguntas_de([]) is None and preguntas_de(["x", {"question": ""}]) is None


def test_orden_por_urgencia_y_antiguedad() -> None:
    agentes = [
        _agente("atascado", 4, T0, atasco=_atasco(T0 - timedelta(minutes=18))),
        _agente(
            "pregunta",
            14,
            T0 - timedelta(minutes=6),
            pregunta_pendiente="¿Push propio o externo?",
            resumenes={"pregunta": {"estado": "listo", "texto": "pregunta te pregunta algo."}},
        ),
        _agente(
            "permiso-nuevo",
            13,
            T0 - timedelta(seconds=40),
            permiso={
                "id": "p2",
                "herramienta": "Bash",
                "detalle": "rm -rf build",
                "creada": (T0 - timedelta(seconds=40)).isoformat(),
                "esperando": True,
                "segundos_restantes": 50,
                "estado": "pendiente",
            },
        ),
        _agente(
            "permiso-viejo",
            13,
            T0 - timedelta(minutes=3),
            espera={"evidencia": {"herramienta": "Bash", "comando": "git push"}},
        ),
        _agente("trabajando", 4, T0),
    ]
    items = pendientes(agentes, set(), T0)
    assert [(i["tipo"], i["session_id"]) for i in items] == [
        ("permiso", "permiso-viejo"),
        ("permiso", "permiso-nuevo"),
        ("pregunta", "pregunta"),
        ("atasco", "atascado"),
    ]
    viejo, nuevo, pregunta, atasco = items
    assert viejo["detalle"] == "git push" and viejo["permiso"]["esperando"] is False
    assert nuevo["permiso"]["id"] == "p2" and nuevo["hace_s"] == 40
    assert pregunta["resumen"] == "pregunta te pregunta algo."
    assert pregunta["pregunta"]["responder_en"] == "pc"
    assert atasco["atasco"]["ultimo_intento"] == "Bash: npm run build"
    assert atasco["hace_s"] == 18 * 60
    assert {i["proyecto"] for i in items} == {
        "permiso-viejo",
        "permiso-nuevo",
        "pregunta",
        "atascado",
    }
    # "Ya lo vi": el atasco sale; un agente cerrado no deja atasco en la bandeja.
    assert [i["tipo"] for i in pendientes(agentes, {atasco["id"]}, T0)][-1] == "pregunta"
    cerrado = _agente("cerrado", 21, T0, atasco=_atasco(T0))
    assert pendientes([cerrado], set(), T0) == []


def test_un_13_de_ask_user_question_es_pregunta() -> None:
    a = _agente(
        "ask",
        13,
        T0,
        espera={"evidencia": {"herramienta": "AskUserQuestion", "comando": "¿Push?"}},
        pregunta_pendiente="¿Push?",
        pregunta_opciones=preguntas_de(ASK["questions"]),
        resumenes={"permiso": {"estado": "listo", "texto": "ask te pregunta por el push."}},
    )
    [item] = pendientes([a], set(), T0)
    assert item["tipo"] == "pregunta"
    assert item["resumen"] == "ask te pregunta por el push."
    assert len(item["pregunta"]["preguntas"][0]["opciones"]) == 2


# -- persistencia ------------------------------------------------------------------------


def test_esquema_con_version_y_migracion(tmp_path: Path) -> None:
    b = Bandejas(tmp_path)
    assert b.version() == 1
    Bandejas(tmp_path)  # reabrir no rompe ni repite
    with sqlite3.connect(tmp_path / "bandejas.db") as db:
        tablas = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"ideas", "atascos_vistos", "preguntas"} <= tablas


def test_ideas(tmp_path: Path) -> None:
    b = Bandejas(tmp_path, clock=lambda: T0)
    a = b.crear_idea("  Modo fiesta cuando todos terminan  ", None, "dictada")
    assert (a["texto"], a["proyecto"], a["origen"], a["estado"]) == (
        "Modo fiesta cuando todos terminan",
        None,
        "dictada",
        "nueva",
    )
    c = b.crear_idea("Probar la arena con 20 enemigos", "SkyNest", "escrita")
    assert c["estado"] == "asignada"
    assert b.cambiar_idea(a["id"], proyecto="visualizador-agentes")["estado"] == "asignada"  # type: ignore[index]
    assert b.cambiar_idea(a["id"], proyecto=None)["estado"] == "nueva"  # type: ignore[index]
    assert b.cambiar_idea(a["id"], texto="Modo fiesta")["texto"] == "Modo fiesta"  # type: ignore[index]
    assert b.archivar_idea(c["id"])["estado"] == "archivada"  # type: ignore[index]
    # Archivada sigue archivada aunque cambie el proyecto; desarchivar la devuelve.
    assert b.cambiar_idea(c["id"], proyecto="Otro")["estado"] == "archivada"  # type: ignore[index]
    assert [i["id"] for i in b.ideas()] == [a["id"]]
    assert {i["id"] for i in b.ideas(archivadas=True)} == {a["id"], c["id"]}
    assert b.archivar_idea(c["id"], archivar=False)["estado"] == "asignada"  # type: ignore[index]
    with pytest.raises(ValueError):
        b.crear_idea("   ", None, "escrita")
    assert b.cambiar_idea("no-existe", proyecto=None) is None


def test_preguntas_respondidas_y_atascos_vistos_en_resueltas_de_hoy(tmp_path: Path) -> None:
    reloj = [T0]
    b = Bandejas(tmp_path, clock=lambda: reloj[0])
    pregunta = _agente("q", 14, T0 - timedelta(minutes=2), pregunta_pendiente="¿Sigo?")
    cerrada = _agente("q2", 14, T0 - timedelta(minutes=2), pregunta_pendiente="¿Otra?")
    atascado = _agente("at", 4, T0, atasco=_atasco(T0 - timedelta(minutes=5)))
    items = pendientes([pregunta, cerrada, atascado], b.vistos(), T0)
    b.sincronizar(items, [pregunta, cerrada, atascado])
    assert b.resueltas_hoy() == []
    # Se responde en la PC una; la otra sesión se cierra; el atasco se marca visto.
    reloj[0] = T0 + timedelta(minutes=1)
    cerrada["estado"]["numero"] = 21
    b.sincronizar([], [cerrada])
    atasco = next(i for i in items if i["tipo"] == "atasco")
    b.marcar_visto(atasco, "app")
    resueltas = {r["id"]: r for r in b.resueltas_hoy()}
    assert resueltas[items[0]["id"]]["como"] in ("Respondida en la PC", "La sesión se cerró")
    comos = sorted(r["como"] for r in resueltas.values())
    assert comos == ["La sesión se cerró", "Respondida en la PC", "Ya lo vi"]
    assert resueltas[atasco["id"]]["quien"] == "app iOS"
    assert atasco["id"] in b.vistos()
    # Al día siguiente ya no son "de hoy".
    reloj[0] = T0 + timedelta(days=1)
    assert b.resueltas_hoy() == []


def test_permisos_resueltos_de_hoy(tmp_path: Path) -> None:
    reg = RegistroPermisos(tmp_path, clock=lambda: T0, presencia=lambda: (False, True))
    reg.guardar_config(permisos.validar_config({"politica": "siempre"}))
    reg.crear(
        "p1",
        "s1",
        "Bash",
        {"command": "systemctl restart nginx"},
        "personal",
        "server-monitor",
        "alienware",
    )
    reg.crear(
        "p2", "s2", "Bash", {"command": "git push origin main"}, "personal", "buscapez", "alienware"
    )
    reg.crear("p3", "s3", "AskUserQuestion", {"questions": []}, "personal", "x", "alienware")
    reg.decidir("p1", True, None, "app")
    reg.decidir("p2", False, "No a main", "pc")
    reg.decidir("p3", True, None, "app")
    b = Bandejas(tmp_path, clock=lambda: T0 + timedelta(minutes=5))
    resueltas = b.resueltas_hoy()
    assert [(r["id"], r["como"], r["quien"]) for r in sorted(resueltas, key=lambda r: r["id"])] == [
        ("p1", "Aprobado", "app iOS"),
        ("p2", "Rechazado", "PC"),
    ]
    assert next(r for r in resueltas if r["id"] == "p2")["motivo"] == "No a main"


# -- rutas ------------------------------------------------------------------------------


@pytest.fixture
def entorno(tmp_path: Path) -> Iterator[tuple[TestClient, AgentStateEngine]]:
    from app.main import app

    motor = AgentStateEngine(
        Thresholds(),
        clock=lambda: T0 + timedelta(seconds=30),
        browsers_provider=lambda: 1,
        process_alive=lambda p, c: True,
    )
    override_state_engine(motor)
    set_bandejas(Bandejas(tmp_path, clock=lambda: T0))
    set_resumenes(Resumenes(tmp_path))
    set_datos_maquinas(DatosMaquinas(tmp_path))
    reg = RegistroPermisos(tmp_path, clock=lambda: T0, presencia=lambda: (False, True))
    permisos.set_registro(reg)
    try:
        yield TestClient(app), motor
    finally:
        override_state_engine(None)
        set_bandejas(None)
        set_resumenes(None)
        set_datos_maquinas(None)
        permisos.set_registro(None)


def _evento(motor: AgentStateEngine, tipo: str, s: float, sid: str, **datos: Any) -> None:
    motor.accept(
        EventAdapter.validate_python(
            {
                "event_type": tipo,
                "session_id": sid,
                "timestamp": T0 + timedelta(seconds=s),
                "data": {"project_dir": f"E:/{sid}", **datos},
            }
        )
    )


def test_ruta_de_decisiones_con_pregunta_real(entorno: tuple[TestClient, AgentStateEngine]) -> None:
    c, motor = entorno
    _evento(motor, "user_prompt_submit", 0, "prueba-pregunta", prompt="Decide el push")
    _evento(
        motor,
        "pre_tool_use",
        5,
        "prueba-pregunta",
        tool_name="AskUserQuestion",
        tool_use_id="q1",
        tool_input=ASK,
    )
    estado = c.get("/api/v1/agents/state").json()
    [agente] = estado["agentes"]
    assert agente["estado"]["numero"] == 14
    assert agente["pregunta_opciones"][0]["opciones"][1]["etiqueta"] == "Con un servicio externo"
    assert estado["decisiones_pendientes"] == 1
    d = c.get("/api/v1/decisiones").json()
    assert d["conteo"] == {"permiso": 0, "pregunta": 1, "atasco": 0, "total": 1}
    [item] = d["pendientes"]
    assert item["tipo"] == "pregunta" and item["proyecto"] == "prueba-pregunta"
    assert (
        item["pregunta"]["preguntas"][0]["opciones"][0]["etiqueta"]
        == "Directo desde el VPS a Apple"
    )
    assert d["resueltas_hoy"] == []
    # Se responde en la PC: la herramienta termina y la pregunta pasa a resueltas.
    _evento(
        motor, "post_tool_use", 20, "prueba-pregunta", tool_name="AskUserQuestion", tool_use_id="q1"
    )
    d = c.get("/api/v1/decisiones").json()
    assert d["pendientes"] == []
    assert [(r["tipo"], r["como"]) for r in d["resueltas_hoy"]] == [
        ("pregunta", "Respondida en la PC")
    ]


def test_ya_lo_vi_y_404(entorno: tuple[TestClient, AgentStateEngine]) -> None:
    c, _ = entorno
    assert c.post("/api/v1/decisiones/atascos/visto", json={"id": "no:existe"}).status_code == 404


def test_rutas_de_ideas(entorno: tuple[TestClient, AgentStateEngine]) -> None:
    c, motor = entorno
    _evento(motor, "user_prompt_submit", 0, "SkyNest", prompt="hola")
    r = c.post(
        "/api/v1/ideas", json={"texto": "Revisar el correo de bienvenida", "origen": "dictada"}
    )
    assert r.status_code == 201
    idea = r.json()
    assert idea["estado"] == "nueva" and idea["proyecto"] is None and idea["origen"] == "dictada"
    assert c.post("/api/v1/ideas", json={"texto": ""}).status_code == 422
    assert c.post("/api/v1/ideas", json={"texto": "x", "origen": "otra"}).status_code == 422
    r = c.patch(f"/api/v1/ideas/{idea['id']}", json={"proyecto": "SkyNest"})
    assert r.json()["estado"] == "asignada" and r.json()["proyecto"] == "SkyNest"
    # Sin "proyecto" en el cuerpo no cambia; con null queda sin proyecto.
    assert (
        c.patch(f"/api/v1/ideas/{idea['id']}", json={"texto": "Revisar el correo"}).json()[
            "proyecto"
        ]
        == "SkyNest"
    )
    assert (
        c.patch(f"/api/v1/ideas/{idea['id']}", json={"proyecto": None}).json()["estado"] == "nueva"
    )
    lista = c.get("/api/v1/ideas").json()
    assert [i["id"] for i in lista["ideas"]] == [idea["id"]]
    assert "SkyNest" in lista["proyectos"]
    assert c.post(f"/api/v1/ideas/{idea['id']}/archivar").json()["estado"] == "archivada"
    assert c.get("/api/v1/ideas").json()["ideas"] == []
    assert len(c.get("/api/v1/ideas?archivadas=true").json()["ideas"]) == 1
    assert c.patch("/api/v1/ideas/no-existe", json={"proyecto": "x"}).status_code == 404
    assert c.post("/api/v1/ideas/no-existe/archivar").status_code == 404


def test_la_app_decide_como_app(entorno: tuple[TestClient, AgentStateEngine]) -> None:
    c, _ = entorno
    permisos.get_registro().guardar_config(permisos.validar_config({"politica": "siempre"}))
    c.post(
        "/api/v1/permisos/solicitudes",
        json={
            "id": "prueba-app-1",
            "session_id": "prueba-app",
            "herramienta": "Bash",
            "entrada": {"command": "ls"},
            "cuenta": "personal",
            "proyecto": "E:/prueba-app",
        },
    )
    r = c.post(
        "/api/v1/permisos/solicitudes/prueba-app-1/decision",
        json={"decision": "aprobar", "dispositivo": "app"},
    )
    assert r.status_code == 200 and r.json()["dispositivo"] == "app"

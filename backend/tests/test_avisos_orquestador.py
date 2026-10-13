"""Avisos de los orquestadores que se pueden atender y proyectos de prueba (Prompt 43)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import acceso as acceso_mod
from app.core.acceso import Acceso
from app.core.agent_state_engine import AgentStateEngine, Thresholds, override_state_engine
from app.core.proyectos_equipo import (
    ProyectoError,
    ProyectosEquipo,
    es_pregunta,
    pregunta_de,
    set_proyectos_equipo,
)

T0 = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
HAIKU = {"modelo": "haiku", "esfuerzo": "low"}
ACTIVOS = [{"nombre": "orquestador", "estado": "activo"}, {"nombre": "agente", "estado": "activo"}]


def _activo(r: ProyectosEquipo, nombre: str, prueba: bool | None = None) -> str:
    p = r.crear(nombre, "alienware", "personal", "web", HAIKU, [HAIKU], False, "E:\\Agents", prueba)
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo("alienware", enc["id"], True, None, None, ACTIVOS)
    return p["id"]


def test_pregunta_del_orquestador() -> None:
    assert es_pregunta("Listo el plan. ¿Lo apruebas?")
    assert not es_pregunta("Listo el plan.")
    assert not es_pregunta("Usa `a?b` y\n```\nx = y ? 1 : 2\n```\nlisto.")
    texto = "Hola.\n\n1. **Objetivo:** ¿qué quieres?\n2. **Para quién:** ¿quién lo usa?\nGracias."
    assert pregunta_de(texto) == "Para quién: ¿quién lo usa?"
    assert len(pregunta_de("¿" + "x" * 400 + "?")) == 240


def test_proyectos_de_prueba(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    assert r.proyecto(_activo(r, "prueba-43"))["prueba"] is True  # type: ignore[index]
    assert r.proyecto(_activo(r, "tienda"))["prueba"] is False  # type: ignore[index]
    assert r.proyecto(_activo(r, "otra", prueba=True))["prueba"] is True  # type: ignore[index]
    pid = _activo(r, "prueba-falsa", prueba=False)
    assert r.proyecto(pid)["prueba"] is False  # type: ignore[index]
    assert r.marcar_prueba(pid, True)["prueba"] is True
    with pytest.raises(ProyectoError):
        r.marcar_prueba("nada", True)


def test_migracion_5_marca_los_prueba_existentes(tmp_path: Path) -> None:
    from app.core.proyectos_equipo import _MIGRACIONES  # pyright: ignore[reportPrivateUsage]

    db = sqlite3.connect(tmp_path / "proyectos.db")
    for v in (1, 2, 3, 4):
        for sql in _MIGRACIONES[v]:
            db.execute(sql)
    for i, nombre in enumerate(("prueba-37", "prueba-39", "tienda")):
        db.execute(
            "INSERT INTO proyectos (id, nombre, maquina, cuenta, ruta, plantilla, estado,"
            " auto_aprobar, creado, actualizado) VALUES (?,?,'alienware','personal','x','vacia',"
            "'activo',0,'2026','2026')",
            (f"p{i}", nombre),
        )
    db.execute("PRAGMA user_version = 4")
    db.commit()
    db.close()
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    assert r.version() == 5
    assert r.ids_de_prueba() == {"p0", "p1"}


def test_avisos_pregunta_ignorar_y_esperar(tmp_path: Path) -> None:
    reloj = [T0]
    r = ProyectosEquipo(tmp_path, clock=lambda: reloj[0])
    pid = _activo(r, "tienda")

    def paso(segundos: int = 10) -> None:
        reloj[0] += timedelta(seconds=segundos)

    r.respuesta_orquestador("alienware", pid, "m-000001", "Hola. ¿Para quién es la tienda?")
    [a] = r.avisos(reloj[0])
    assert (a["tipo"], a["proyecto"], a["texto"]) == (
        "pregunta",
        "tienda",
        "Hola. ¿Para quién es la tienda?",
    )
    assert a["clave"] == f"mensaje:{a['mensaje_id']}" and a["orden"] is None
    # Leerlo varias veces no lo duplica: es el mismo aviso (misma clave).
    assert [x["clave"] for x in r.avisos(reloj[0])] == [a["clave"]]
    # Washington contesta: deja de esperar.
    paso()
    r.escribir(pid, "Para clientes.")
    assert r.avisos(reloj[0]) == []
    # Una respuesta sin pregunta no avisa.
    paso()
    r.respuesta_orquestador("alienware", pid, "m-000002", "Listo, armo el plan.")
    assert r.avisos(reloj[0]) == []
    # Esperar: silenciado hasta que el orquestador escriba otro mensaje.
    paso()
    r.respuesta_orquestador("alienware", pid, "m-000003", "¿Usamos Next.js?")
    [b] = r.avisos(reloj[0])
    assert r.esperar_aviso(b["clave"]) == {"clave": b["clave"], "estado": "en_espera"}
    assert r.avisos(reloj[0]) == []
    paso()
    r.respuesta_orquestador("alienware", pid, "m-000004", "Perdón, otra cosa: ¿y la fecha?")
    [c] = r.avisos(reloj[0])
    assert c["clave"] != b["clave"] and c["texto"] == "Perdón, otra cosa: ¿y la fecha?"
    # Ignorar: ese aviso no vuelve.
    r.ignorar_aviso(c["clave"])
    assert r.avisos(reloj[0]) == []
    with pytest.raises(ProyectoError) as e:
        r.ignorar_aviso("mensaje:" + "0" * 32)
    assert e.value.status == 404


def test_avisos_de_orden(tmp_path: Path) -> None:
    reloj = [T0]
    r = ProyectosEquipo(tmp_path, clock=lambda: reloj[0])
    pid = _activo(r, "tienda")
    r.respuesta_orquestador("alienware", pid, "m-000001", "Propongo la primera orden.")
    o = r.proponer_orden(
        "alienware", pid, "orden-0001", "agente", "Crea el proyecto", titulo="Fase 1 · Prompt 1"
    )
    [a] = r.avisos(reloj[0])
    assert a["tipo"] == "orden" and a["clave"] == f"orden:{o['id']}"
    assert a["texto"] == "Orden 1 para agente: Fase 1 · Prompt 1" and a["orden"]["id"] == o["id"]
    # Esperar una orden: vuelve cuando el orquestador escribe algo nuevo.
    r.esperar_aviso(a["clave"])
    assert r.avisos(reloj[0]) == []
    reloj[0] += timedelta(seconds=5)
    r.respuesta_orquestador("alienware", pid, "m-000002", "Sigo esperando tu decisión.")
    assert [x["clave"] for x in r.avisos(reloj[0])] == [a["clave"]]
    # Al decidirla, ya no hay aviso.
    r.aprobar(o["id"], None, "web")
    assert r.avisos(reloj[0]) == []


def test_un_proyecto_de_prueba_no_avisa_ni_entra_en_decisiones(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r, "prueba-43")
    r.respuesta_orquestador("alienware", pid, "m-000001", "¿Qué hacemos?")
    o = r.proponer_orden("alienware", pid, "orden-0001", "agente", "Algo")
    assert r.avisos(T0) == [] and r.decisiones(T0) == []
    assert r.por_aprobar(con_pruebas=False) == {} and r.por_aprobar() == {pid: 1}
    # El chat y las órdenes siguen normales.
    assert [m["autor"] for m in r.mensajes(pid)] == ["orquestador"]
    assert r.orden(o["id"])["proyecto_prueba"] is True  # type: ignore[index]
    # En Decisiones tampoco entra lo de sus sesiones.
    sesiones = r.sesiones_de_prueba()
    items = [
        {"tipo": "permiso", "session_id": next(iter(sesiones))},
        {"tipo": "atasco", "session_id": "otra"},
    ]
    assert r.filtrar_decisiones(items) == [{"tipo": "atasco", "session_id": "otra"}]


def test_las_preguntas_del_equipo_no_entran_en_decisiones(tmp_path: Path) -> None:
    """Una pregunta de una sesión del equipo se contesta en el chat (avisos del
    orquestador), no desde la bandeja: allí no tendría ninguna acción."""
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    _activo(r, "tienda")
    equipo = next(iter(r.sesiones_lanzadas()))
    items = [
        {"tipo": "pregunta", "session_id": equipo},
        {"tipo": "permiso", "session_id": equipo},
        {"tipo": "pregunta", "session_id": "sesion-normal"},
    ]
    assert r.filtrar_decisiones(items) == items[1:]


def test_prueba_inactiva_se_detiene_sola(tmp_path: Path) -> None:
    reloj = [T0]
    r = ProyectosEquipo(tmp_path, clock=lambda: reloj[0])
    prueba = _activo(r, "prueba-43")
    normal = _activo(r, "tienda")
    orq = r.proyecto(prueba)["equipo"][0]["session_id"]  # type: ignore[index]
    reloj[0] = T0 + timedelta(minutes=29)
    assert r.detener_pruebas_inactivas({}) == []
    # Actividad reciente del equipo (un evento de su sesión): no se detiene.
    reloj[0] = T0 + timedelta(minutes=45)
    reciente = (T0 + timedelta(minutes=40)).isoformat()
    assert r.detener_pruebas_inactivas({orq: reciente}) == []
    # 30 min sin nada: se detiene (y nunca un proyecto normal).
    reloj[0] = T0 + timedelta(minutes=71)
    assert r.detener_pruebas_inactivas({orq: reciente}) == [prueba]
    assert r.proyecto(prueba)["estado"] == "deteniendo"  # type: ignore[index]
    assert r.proyecto(normal)["estado"] == "activo"  # type: ignore[index]
    assert [e["tipo"] for e in r.encargos_pendientes("alienware")] == ["detener"]
    assert r.detener_pruebas_inactivas({}) == []  # ya no está activo


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[tuple[TestClient, ProyectosEquipo]]:
    from app.main import app

    acc = Acceso(tmp_path / "acceso.db", secreto="s", clock=lambda: T0)
    acc.registrar_maquina("alienware", "Alienware", "windows")
    acceso_mod.set_acceso(acc)
    reg = ProyectosEquipo(tmp_path, clock=lambda: T0)
    set_proyectos_equipo(reg)
    override_state_engine(AgentStateEngine(Thresholds(), clock=lambda: T0 + timedelta(seconds=30)))
    try:
        yield TestClient(app), reg
    finally:
        acceso_mod.set_acceso(None)
        set_proyectos_equipo(None)
        override_state_engine(None)


def test_rutas(cliente: tuple[TestClient, ProyectosEquipo]) -> None:
    c, reg = cliente
    api = "/api/v1"
    pid = _activo(reg, "tienda")
    prueba = _activo(reg, "prueba-43")
    for p in (pid, prueba):
        c.post(
            f"{api}/maquinas/chat",
            json={"proyecto_id": p, "origen_id": f"r-{p[:8]}", "texto": "¿Seguimos?"},
        )
    [a] = c.get(f"{api}/avisos-orquestador").json()["avisos"]
    assert a["proyecto"] == "tienda" and a["tipo"] == "pregunta"
    r = c.post(f"{api}/avisos-orquestador/esperar", json={"clave": a["clave"]})
    assert r.json() == {"clave": a["clave"], "estado": "en_espera"}
    assert c.get(f"{api}/avisos-orquestador").json()["avisos"] == []
    assert c.post(f"{api}/avisos-orquestador/ignorar", json={"clave": "x:y"}).status_code == 422
    nada = {"clave": "orden:" + "0" * 32}
    assert c.post(f"{api}/avisos-orquestador/ignorar", json=nada).status_code == 404
    # El campo prueba en la API.
    assert c.get(f"{api}/proyectos-creados/{prueba}").json()["prueba"] is True
    r = c.post(f"{api}/proyectos-creados/{prueba}/prueba", json={"prueba": False})
    assert r.json()["prueba"] is False
    assert len(c.get(f"{api}/avisos-orquestador").json()["avisos"]) == 1
    # Las órdenes de los proyectos de prueba no cuentan en el contador de Decisiones.
    reg.marcar_prueba(prueba, True)
    reg.proponer_orden("alienware", prueba, "orden-0001", "agente", "Algo")
    assert c.get(f"{api}/agents/state").json()["decisiones_pendientes"] == 0
    assert c.get(f"{api}/decisiones").json()["conteo"]["orden"] == 0

"""API para la app (etapa 4, Prompt 42): título corto de cada orden, vínculo de cada
proyecto con equipo con su entrada de "Dónde quedamos" y la ruta solo de órdenes."""

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
from app.core.datos_maquinas import DatosMaquinas, id_donde_quedamos, set_datos_maquinas
from app.core.proyectos_equipo import ProyectosEquipo, set_proyectos_equipo, titulo_de

T0 = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
HAIKU = {"modelo": "haiku", "esfuerzo": "low"}
ACTIVOS = [{"nombre": "orquestador", "estado": "activo"}, {"nombre": "agente", "estado": "activo"}]


def _activo(r: ProyectosEquipo, nombre: str = "prueba-42") -> str:
    p = r.crear(nombre, "alienware", "personal", "web", HAIKU, [HAIKU], False, "E:\\Agents")
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo("alienware", enc["id"], True, None, "E:\\Agents\\" + nombre, ACTIVOS)
    return p["id"]


@pytest.mark.parametrize(
    ("titulo", "texto", "esperado"),
    [
        (
            "  Fase 1 · Prompt 1:  base del sitio ",
            "Crear todo",
            "Fase 1 · Prompt 1: base del sitio",
        ),
        (None, "## **Crear** el proyecto `Next.js`\nDetalle", "Crear el proyecto Next.js"),
        (None, "\n\n- Primera tarea\n- Segunda", "Primera tarea"),
        (None, "1. Instalar dependencias", "Instalar dependencias"),
        ("", "> Revisar el formulario", "Revisar el formulario"),
        (None, "", "Orden"),
    ],
)
def test_titulo_de(titulo: str | None, texto: str, esperado: str) -> None:
    assert titulo_de(titulo, texto) == esperado


def test_titulo_largo_se_recorta() -> None:
    t = titulo_de(None, "palabra " * 30)
    assert len(t) == 80 and t.endswith("…")


def test_la_orden_guarda_su_titulo_o_lo_deriva(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    con = r.proponer_orden(
        "alienware",
        pid,
        "orden-0001",
        "agente",
        "Crea el proyecto.",
        "1 h",
        "4",
        "Fase 1 · Prompt 1: base del sitio",
    )
    assert con["titulo"] == "Fase 1 · Prompt 1: base del sitio" and con["titulo_propio"] is True
    sin = r.proponer_orden(
        "alienware", pid, "orden-0002", "agente", "**Agregar** el formulario\nY más"
    )
    assert sin["titulo"] == "Agregar el formulario" and sin["titulo_propio"] is False
    # Editar el texto al aprobar no cambia el título que dio el orquestador.
    assert r.aprobar(con["id"], "Otro texto", "web")["titulo"] == con["titulo"]
    # La bandeja de Decisiones usa el título en su resumen.
    [d] = r.decisiones(T0)
    assert d["resumen"] == "Orden 2 para agente: Agregar el formulario"


def test_migracion_4_conserva_las_ordenes(tmp_path: Path) -> None:
    """Una base del esquema 3 (sin título) sube al 4: las órdenes viejas derivan el título."""
    from app.core.proyectos_equipo import _MIGRACIONES  # pyright: ignore[reportPrivateUsage]

    db = sqlite3.connect(tmp_path / "proyectos.db")
    for v in (1, 2, 3):
        for sql in _MIGRACIONES[v]:
            db.execute(sql)
    db.execute(
        "INSERT INTO proyectos (id, nombre, maquina, cuenta, ruta, plantilla, estado, auto_aprobar,"
        " creado, actualizado) VALUES ('p1','viejo','alienware','personal','E:\\\\A\\\\viejo',"
        "'vacia','activo',0,'2026','2026')"
    )
    db.execute(
        "INSERT INTO ordenes (id, proyecto_id, numero, agente, texto_propuesto, estado, creado,"
        " actualizado) VALUES ('o1','p1',1,'agente',?,'terminada','2026','2026')",
        ("Hacer la portada\ncon detalle",),
    )
    db.execute("PRAGMA user_version = 3")
    db.commit()
    db.close()
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    assert r.version() == 4
    [o] = r.ordenes("p1")
    assert o["titulo"] == "Hacer la portada" and o["titulo_propio"] is False


def test_id_de_donde_quedamos_estable() -> None:
    a = id_donde_quedamos("alienware", "E:\\Agents\\prueba-42")
    assert a == id_donde_quedamos("alienware", "e:/agents/prueba-42/")
    assert a != id_donde_quedamos("torre", "E:\\Agents\\prueba-42")
    assert len(a) == 16


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[tuple[TestClient, ProyectosEquipo, DatosMaquinas]]:
    from app.main import app

    acc = Acceso(tmp_path / "acceso.db", secreto="s", clock=lambda: T0)
    acc.registrar_maquina("alienware", "Alienware", "windows")
    acceso_mod.set_acceso(acc)
    reg = ProyectosEquipo(tmp_path, clock=lambda: T0)
    set_proyectos_equipo(reg)
    datos = DatosMaquinas(tmp_path)
    set_datos_maquinas(datos)
    override_state_engine(AgentStateEngine(Thresholds(), clock=lambda: T0 + timedelta(seconds=30)))
    try:
        yield TestClient(app), reg, datos
    finally:
        acceso_mod.set_acceso(None)
        set_proyectos_equipo(None)
        set_datos_maquinas(None)
        override_state_engine(None)


def test_rutas(cliente: tuple[TestClient, ProyectosEquipo, DatosMaquinas]) -> None:
    c, reg, datos = cliente
    api = "/api/v1"
    pid = _activo(reg)
    # Sin entrada en "Dónde quedamos" todavía: el vínculo es null.
    assert c.get(f"{api}/proyectos-creados/{pid}").json()["donde_quedamos_id"] is None
    # El monitor informa el PROJECT.md de la carpeta (con otra forma de escribir la ruta).
    datos.registrar_proyectos(
        "alienware", [{"carpeta": "e:/agents/prueba-42", "nombre": "prueba-42"}]
    )
    datos.registrar_proyectos("alienware", [{"carpeta": "E:\\Otro\\proyecto", "nombre": "otro"}])
    lista = c.get(f"{api}/proyectos").json()["proyectos"]
    ids = {p["carpeta"]: p["id"] for p in lista}
    p = c.get(f"{api}/proyectos-creados/{pid}").json()
    assert p["donde_quedamos_id"] == ids["e:/agents/prueba-42"]
    assert (
        c.get(f"{api}/proyectos-creados").json()["proyectos"][0]["donde_quedamos_id"]
        == p["donde_quedamos_id"]
    )
    # Ruta solo de órdenes.
    titulada = {
        "proyecto_id": pid,
        "origen_id": "orden-0001",
        "agente": "agente",
        "texto": "Crear el proyecto Next.js",
        "estimado": "1 h",
        "dificultad": "4",
        "titulo": "Fase 1 · Prompt 1: base del sitio",
    }
    assert c.post(f"{api}/maquinas/ordenes", json=titulada).status_code == 200
    sin_titulo = {
        **titulada,
        "origen_id": "orden-0002",
        "texto": "Agregar el formulario\nY validar",
    }
    del sin_titulo["titulo"]
    o2 = c.post(f"{api}/maquinas/ordenes", json=sin_titulo).json()
    c.post(
        f"{api}/ordenes/{o2['id']}/rechazar", json={"motivo": "Todavía no", "dispositivo": "app"}
    )
    ordenes = c.get(f"{api}/proyectos-creados/{pid}/ordenes").json()["ordenes"]
    assert [o["numero"] for o in ordenes] == [2, 1]
    assert [o["titulo"] for o in ordenes] == [
        "Agregar el formulario",
        "Fase 1 · Prompt 1: base del sitio",
    ]
    rechazada = ordenes[0]
    assert (rechazada["estado"], rechazada["decidido_por"], rechazada["motivo"]) == (
        "rechazada",
        "app",
        "Todavía no",
    )
    for campo in ("estimado", "dificultad", "decidido", "creado", "agente", "texto"):
        assert campo in rechazada
    solo = c.get(f"{api}/proyectos-creados/{pid}/ordenes?estado=por_aprobar").json()["ordenes"]
    assert [o["numero"] for o in solo] == [1]
    assert c.get(f"{api}/proyectos-creados/{pid}/ordenes?estado=nada").status_code == 422
    assert c.get(f"{api}/proyectos-creados/nada/ordenes").status_code == 404
    # El título también sale en el chat y en Decisiones.
    assert (
        c.get(f"{api}/proyectos-creados/{pid}/chat")
        .json()["ordenes"][0]["titulo"]
        .startswith("Fase 1")
    )
    d = c.get(f"{api}/decisiones").json()["pendientes"][0]
    assert d["orden"]["titulo"] == "Fase 1 · Prompt 1: base del sitio"

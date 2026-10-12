"""Proyectos con equipo (etapa 4, Prompt 37): nombre, encargos, estados, máquinas."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import acceso as acceso_mod
from app.core.acceso import Acceso
from app.core.agent_state_engine import AgentStateEngine, Thresholds, override_state_engine
from app.core.proyectos_equipo import (
    ProyectoError,
    ProyectosEquipo,
    ruta_de,
    set_proyectos_equipo,
    validar_nombre,
    version_tupla,
)
from app.models.events import EventAdapter

T0 = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
ORQ = {"modelo": "opus", "esfuerzo": "high"}
AGENTE = {"modelo": "sonnet", "esfuerzo": "medium"}


@pytest.mark.parametrize("nombre", ["prueba-37", "skynest", "a", "app2", "mi-app-de-prueba"])
def test_nombres_validos(nombre: str) -> None:
    assert validar_nombre(nombre) == nombre


@pytest.mark.parametrize(
    "nombre",
    [
        "",
        "Prueba",
        "con espacio",
        "punto.algo",
        "..",
        "a/b",
        "a\\b",
        "C:",
        "-empieza",
        "termina-",
        "ñandú",
        "x" * 51,
        "con",
        "lpt1",
    ],
)
def test_nombres_rechazados(nombre: str) -> None:
    with pytest.raises(ProyectoError) as e:
        validar_nombre(nombre)
    assert e.value.status == 422


def test_ruta_y_version() -> None:
    assert ruta_de("E:\\Agents", "prueba-37") == "E:\\Agents\\prueba-37"
    assert ruta_de("/home/w/Agents/", "x") == "/home/w/Agents/x"
    assert version_tupla("0.4.0") == (0, 4, 0) and version_tupla("0.3.0") < (0, 4, 0)
    assert version_tupla(None) == ()


def _registro(tmp_path: Path, reloj: list[datetime]) -> ProyectosEquipo:
    return ProyectosEquipo(tmp_path, clock=lambda: reloj[0])


def test_crear_y_ciclo_de_encargos(tmp_path: Path) -> None:
    reloj = [T0]
    r = _registro(tmp_path, reloj)
    assert r.version() == 3
    p = r.crear("prueba-37", "alienware", "personal", "vacia", ORQ, [AGENTE], False, "E:\\Agents")
    assert p["estado"] == "creando" and p["ruta"] == "E:\\Agents\\prueba-37"
    assert [
        (m["rol"], m["nombre"], m["modelo"], m["esfuerzo"], m["estado"]) for m in p["equipo"]
    ] == [
        ("orquestador", "orquestador", "opus", "high", "pendiente"),
        ("agente", "agente", "sonnet", "medium", "pendiente"),
    ]
    assert all(len(m["session_id"]) == 36 for m in p["equipo"])
    # Mismo nombre en la misma máquina: no.
    with pytest.raises(ProyectoError) as e:
        r.crear("prueba-37", "alienware", "personal", "vacia", ORQ, [AGENTE], False, "E:\\Agents")
    assert e.value.status == 409
    # El monitor de otra máquina no lo ve; el de la suya lo toma una sola vez.
    assert r.encargos_pendientes("torre") == []
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "crear" and enc["nombre"] == "prueba-37" and enc["cuenta"] == "personal"
    assert [m["session_id"] for m in enc["equipo"]] == [m["session_id"] for m in p["equipo"]]
    assert r.encargos_pendientes("alienware") == []
    # Si no informa en 3 min, se vuelve a entregar.
    reloj[0] = T0 + timedelta(minutes=4)
    assert [x["id"] for x in r.encargos_pendientes("alienware")] == [enc["id"]]
    # Otra máquina no puede informar ese encargo.
    with pytest.raises(ProyectoError):
        r.informar_encargo("torre", enc["id"], True, None, None, [])
    activos = [
        {"nombre": "orquestador", "estado": "activo"},
        {"nombre": "agente", "estado": "activo"},
    ]
    r.informar_encargo("alienware", enc["id"], True, None, "E:\\Agents\\prueba-37", activos)
    p = r.proyecto(p["id"])
    assert p is not None and p["estado"] == "activo"
    assert {m["estado"] for m in p["equipo"]} == {"activo"}
    # Pausar y reanudar son encargos; los estados intermedios lo muestran.
    assert r.pausar(p["id"])["estado"] == "pausando"
    with pytest.raises(ProyectoError) as e:
        r.pausar(p["id"])
    assert e.value.status == 409
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "pausar"
    pausados = [
        {"nombre": "orquestador", "estado": "pausado"},
        {"nombre": "agente", "estado": "pausado"},
    ]
    r.informar_encargo("alienware", enc["id"], True, None, None, pausados)
    assert r.proyecto(p["id"])["estado"] == "pausado"  # type: ignore[index]
    assert r.reanudar(p["id"])["estado"] == "reanudando"
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo("alienware", enc["id"], True, None, None, activos)
    assert r.proyecto(p["id"])["estado"] == "activo"  # type: ignore[index]
    # Informar dos veces no cambia nada.
    assert r.informar_encargo("alienware", enc["id"], False, "x", None, [])["estado"] == "hecho"
    lanzadas = r.sesiones_lanzadas()
    assert {v["rol"] for v in lanzadas.values()} == {"orquestador", "agente"}


def test_error_al_crear(tmp_path: Path) -> None:
    r = _registro(tmp_path, [T0])
    p = r.crear("existe", "alienware", "demo", "web", ORQ, [AGENTE, AGENTE], True, "E:\\Agents")
    assert [m["nombre"] for m in p["equipo"]] == ["orquestador", "agente-1", "agente-2"]
    assert p["auto_aprobar"] is True and p["cuenta"] == "demo"
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo("alienware", enc["id"], False, "La carpeta ya existe.", None, [])
    p = r.proyecto(p["id"])
    assert p is not None and p["estado"] == "error" and p["error"] == "La carpeta ya existe."
    # Sin nada lanzado no hay equipo que reanudar.
    with pytest.raises(ProyectoError):
        r.reanudar(p["id"])


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ({"cuenta": "otra"}, "cuenta"),
        ({"plantilla": "django"}, "Plantilla"),
        ({"agentes": []}, "agentes"),
        ({"orquestador": {"modelo": "opus", "esfuerzo": "turbo"}}, "Esfuerzo"),
        ({"orquestador": {"modelo": "rm -rf /", "esfuerzo": "low"}}, "Modelo"),
    ],
)
def test_crear_valida(tmp_path: Path, cambio: dict[str, Any], texto: str) -> None:
    r = _registro(tmp_path, [T0])
    args: dict[str, Any] = {
        "nombre": "x",
        "maquina": "alienware",
        "cuenta": "personal",
        "plantilla": "vacia",
        "orquestador": ORQ,
        "agentes": [AGENTE],
        "auto_aprobar": False,
        "ruta_base": "E:\\Agents",
    }
    args.update(cambio)
    with pytest.raises(ProyectoError) as e:
        r.crear(**args)
    assert texto in e.value.mensaje


def test_vista_de_maquinas(tmp_path: Path) -> None:
    r = _registro(tmp_path, [T0])
    r.anotar_ruta_base("alienware", "E:\\Agents")
    r.anotar_ruta_base("vieja", "D:\\Agents")
    maquinas = [
        {
            "id": "alienware",
            "nombre": "Alienware",
            "version_monitor": "0.4.0",
            "ultima_conexion": (T0 - timedelta(seconds=20)).isoformat(),
        },
        {
            "id": "apagada",
            "nombre": "Torre",
            "version_monitor": "0.4.0",
            "ultima_conexion": (T0 - timedelta(minutes=10)).isoformat(),
        },
        {
            "id": "vieja",
            "nombre": "Vieja",
            "version_monitor": "0.3.0",
            "ultima_conexion": T0.isoformat(),
        },
        {"id": "nueva", "nombre": "Nueva", "version_monitor": None, "ultima_conexion": None},
    ]
    v = {m["id"]: m for m in r.vista_maquinas(maquinas)}
    assert v["alienware"]["disponible"] and v["alienware"]["ruta_base"] == "E:\\Agents"
    assert not v["apagada"]["disponible"] and v["apagada"]["motivo"] == "Apagada o sin monitor"
    assert not v["vieja"]["disponible"] and "actualízalo" in v["vieja"]["motivo"]
    assert not v["nueva"]["encendida"]


# -- rutas -------------------------------------------------------------------------------


@pytest.fixture
def entorno(tmp_path: Path) -> Iterator[tuple[TestClient, AgentStateEngine]]:
    from app.main import app

    reloj = [T0]
    acc = Acceso(tmp_path / "acceso.db", secreto="s", clock=lambda: reloj[0])
    acc.registrar_maquina("alienware", "Alienware", "windows")
    acc.registrar_maquina("torre", "Torre", "windows")
    acceso_mod.set_acceso(acc)
    set_proyectos_equipo(ProyectosEquipo(tmp_path, clock=lambda: reloj[0]))
    motor = AgentStateEngine(
        Thresholds(), clock=lambda: T0 + timedelta(seconds=30), browsers_provider=lambda: 1
    )
    override_state_engine(motor)
    try:
        yield TestClient(app), motor
    finally:
        acceso_mod.set_acceso(None)
        set_proyectos_equipo(None)
        override_state_engine(None)


def test_rutas_de_punta_a_punta(entorno: tuple[TestClient, AgentStateEngine]) -> None:
    c, motor = entorno
    nuevo = {
        "nombre": "prueba-37",
        "maquina": "alienware",
        "cuenta": "personal",
        "plantilla": "vacia",
        "orquestador": {"modelo": "haiku", "esfuerzo": "low"},
        "agentes": [{"modelo": "haiku", "esfuerzo": "low"}],
    }
    # Sin latido la máquina no se puede elegir.
    r = c.post("/api/v1/proyectos-creados", json=nuevo)
    assert r.status_code == 409 and "Apagada" in r.json()["detail"]
    # El latido del monitor (sin token: la máquina local es alienware) trae la ruta base.
    r = c.post(
        "/api/v1/maquinas/latido",
        json={
            "version_monitor": "0.4.0",
            "hostname": "x",
            "sistema": "windows",
            "ruta_proyectos": "E:\\Agents",
        },
    )
    assert r.status_code == 200
    maquinas = {m["id"]: m for m in c.get("/api/v1/proyectos-creados/maquinas").json()["maquinas"]}
    assert (
        maquinas["alienware"]["disponible"] and maquinas["alienware"]["ruta_base"] == "E:\\Agents"
    )
    assert not maquinas["torre"]["disponible"]
    assert (
        c.post("/api/v1/proyectos-creados", json={**nuevo, "nombre": "Mal Nombre"}).status_code
        == 422
    )
    assert (
        c.post("/api/v1/proyectos-creados", json={**nuevo, "maquina": "no-existe"}).status_code
        == 404
    )
    r = c.post("/api/v1/proyectos-creados", json=nuevo)
    assert r.status_code == 201
    p = r.json()
    assert p["estado"] == "creando" and p["ruta"] == "E:\\Agents\\prueba-37"
    assert c.post("/api/v1/proyectos-creados", json=nuevo).status_code == 409
    # El monitor toma el encargo y lo informa.
    [enc] = c.get("/api/v1/maquinas/encargos").json()["encargos"]
    assert enc["tipo"] == "crear" and enc["plantilla"] == "vacia"
    orq, agente = enc["equipo"]
    r = c.post(
        f"/api/v1/maquinas/encargos/{enc['id']}",
        json={
            "ok": True,
            "ruta": "E:\\Agents\\prueba-37",
            "miembros": [
                {"nombre": "orquestador", "estado": "activo"},
                {"nombre": "agente", "estado": "activo"},
            ],
        },
    )
    assert r.json() == {"estado": "hecho"}
    # La sesión del orquestador llega por los hooks: la oficina le pone modelo y esfuerzo.
    motor.accept(
        EventAdapter.validate_python(
            {
                "event_type": "session_start",
                "session_id": orq["session_id"],
                "timestamp": T0,
                "data": {"project_dir": "E:\\Agents\\prueba-37"},
            }
        )
    )
    estado = c.get("/api/v1/agents/state").json()
    [a] = estado["agentes"]
    assert a["agente"]["modelo"] == "haiku" and a["agente"]["esfuerzo"] == "low"
    assert a["agente"]["rol"] == "orquestador" and a["agente"]["proyecto_equipo"] == p["id"]
    vista = c.get(f"/api/v1/proyectos-creados/{p['id']}").json()
    assert vista["estado"] == "activo" and vista["ordenes_por_aprobar"] == 0
    assert vista["equipo"][0]["oficina"]["numero"] is not None
    assert vista["equipo"][1]["oficina"] is None  # el agente todavía no mandó eventos
    # Pausar y reanudar.
    assert c.post(f"/api/v1/proyectos-creados/{p['id']}/pausar").json()["estado"] == "pausando"
    assert c.post(f"/api/v1/proyectos-creados/{p['id']}/pausar").status_code == 409
    [enc] = c.get("/api/v1/maquinas/encargos").json()["encargos"]
    assert enc["tipo"] == "pausar"
    c.post(
        f"/api/v1/maquinas/encargos/{enc['id']}",
        json={"ok": True, "miembros": [{"nombre": "agente", "estado": "pausado"}]},
    )
    assert c.get(f"/api/v1/proyectos-creados/{p['id']}").json()["estado"] == "pausado"
    # Estado periódico de los equipos.
    r = c.post(
        "/api/v1/maquinas/equipos",
        json={
            "equipos": [
                {
                    "proyecto_id": p["id"],
                    "miembros": [{"nombre": "orquestador", "estado": "detenido"}],
                }
            ]
        },
    )
    assert r.json() == {"actualizados": 1}
    assert (
        c.get("/api/v1/proyectos-creados").json()["proyectos"][0]["equipo"][0]["estado"]
        == "detenido"
    )
    assert c.get("/api/v1/proyectos-creados/no-existe").status_code == 404
    assert agente["rol"] == "agente"


def test_las_rutas_de_maquina_son_de_ingesta() -> None:
    from app.api.acceso_middleware import es_ingesta

    assert es_ingesta("GET", "/api/v1/maquinas/encargos")
    assert es_ingesta("POST", "/api/v1/maquinas/encargos/abc123")
    assert es_ingesta("POST", "/api/v1/maquinas/equipos")
    assert not es_ingesta("POST", "/api/v1/proyectos-creados")
    assert not es_ingesta("POST", "/api/v1/maquinas/encargos/../x")


def test_en_espera_al_retomar_sin_mensaje() -> None:
    """El monitor se reinició y retomó la sesión sin escribirle: la oficina la vio
    terminar, pero el monitor la informa viva. Se muestra "En espera", sin cierre."""
    from app.core.proyectos_equipo import vista_lanzada

    a = {
        "agente": {"session_id": "s1", "proyecto": "E:/Agents/p", "modelo": None},
        "estado": {"numero": 21, "nombre": "Cerrado", "desde": "2026-10-12T15:00:00+00:00"},
        "cierre": {"motivo": "session_end", "desde": "2026-10-12T15:00:00+00:00"},
    }
    lanzada = {
        "modelo": "haiku",
        "esfuerzo": "low",
        "rol": "agente",
        "proyecto_id": "p1",
        "estado": "activo",
        "actualizado": "2026-10-12T15:05:00+00:00",
    }
    v = vista_lanzada(a, lanzada)
    assert v["estado"] == {
        "numero": 18,
        "nombre": "En espera",
        "desde": "2026-10-12T15:05:00+00:00",
    }
    assert v["cierre"] is None and v["en_espera"] is True
    assert v["agente"]["modelo"] == "haiku" and v["agente"]["rol"] == "agente"
    # Pausada: sigue cerrada. Trabajando: no se toca. Sin lanzar: igual que siempre.
    assert vista_lanzada(a, {**lanzada, "estado": "pausado"})["estado"]["numero"] == 21
    trabajando = {**a, "estado": {"numero": 5, "nombre": "Escribiendo código", "desde": "x"}}
    assert vista_lanzada(trabajando, lanzada)["estado"]["numero"] == 5
    assert vista_lanzada(a, None) is a

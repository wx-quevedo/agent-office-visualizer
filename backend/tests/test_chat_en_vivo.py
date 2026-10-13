"""Respuesta del orquestador que se va escribiendo, con leído y escribiendo (Prompt 45)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes.proyectos_equipo import eventos_chat
from app.core import acceso as acceso_mod
from app.core.acceso import Acceso
from app.core.agent_state_engine import AgentStateEngine, Thresholds, override_state_engine
from app.core.proyectos_equipo import ProyectoError, ProyectosEquipo, set_proyectos_equipo

T0 = datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
HAIKU = {"modelo": "haiku", "esfuerzo": "low"}
ACTIVOS = [{"nombre": "orquestador", "estado": "activo"}, {"nombre": "agente", "estado": "activo"}]
TURNO = "turno-0001"


def _activo(r: ProyectosEquipo, nombre: str = "tienda") -> str:
    p = r.crear(nombre, "alienware", "personal", "web", HAIKU, [HAIKU], False, "E:\\Agents")
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo("alienware", enc["id"], True, None, None, ACTIVOS)
    return p["id"]


def test_estados_de_un_mensaje_de_washington(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    m = r.escribir(pid, "Explícame el plan.")
    assert (m["estado"], m["leido"]) == ("enviado", None)
    assert r.mensajes(pid)[0]["estado"] == "enviado"
    # El monitor se lo entregó a la sesión: leído (con la hora).
    r.informar_en_vivo("alienware", pid, TURNO, "leido", mensaje_id=m["id"])
    [visto] = r.mensajes(pid)
    assert visto["estado"] == "leido" and visto["leido"] == T0.isoformat()
    assert r.en_vivo(pid)["estado"] == "leido"
    # La sesión empezó a trabajar: respondiendo, sin texto todavía.
    r.informar_en_vivo("alienware", pid, TURNO, "respondiendo")
    assert r.mensajes(pid)[0]["estado"] == "respondiendo"
    vivo = r.en_vivo(pid)
    assert vivo["estado"] == "respondiendo" and vivo["parcial"] == ""
    assert vivo["mensaje_id"] == m["id"]  # se conserva dentro del mismo turno
    # Terminó: libre, y el mensaje queda leído.
    r.informar_en_vivo("alienware", pid, TURNO, "libre")
    assert r.en_vivo(pid)["estado"] == "libre"
    assert r.mensajes(pid)[0]["estado"] == "leido"


def test_el_final_reemplaza_al_parcial(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    r.escribir(pid, "¿Cómo lo organizarías?")
    v0 = r.version_chat(pid)
    r.informar_en_vivo("alienware", pid, TURNO, "respondiendo", "1. **Primero**")
    v1 = r.version_chat(pid)
    r.informar_en_vivo("alienware", pid, TURNO, "respondiendo", "1. **Primero**, la base.\n2.")
    assert len({v0, v1, r.version_chat(pid)}) == 3  # cada novedad cambia la versión
    vivo = r.chat_en_vivo(pid)
    assert vivo["en_vivo"]["parcial"].endswith("2.")
    assert vivo["en_vivo"]["desde"] == T0.isoformat()
    # Los parciales no son mensajes: el chat solo tiene el de Washington.
    assert [m["autor"] for m in r.mensajes(pid)] == ["washington"]
    # El final llega con su turno: en la misma lectura, el parcial pasa a libre y el
    # mensaje final ya está en los recientes.
    r.respuesta_orquestador(
        "alienware", pid, "final-0001", "1. Primero, la base.\n2. Luego.", TURNO
    )
    vivo = r.chat_en_vivo(pid)
    assert vivo["en_vivo"]["estado"] == "libre" and vivo["en_vivo"]["parcial"] == ""
    assert vivo["recientes"][-1]["texto"] == "1. Primero, la base.\n2. Luego."
    assert vivo["recientes"][-1]["estado"] is None
    # Un parcial atrasado de ese turno ya no revive la burbuja.
    r.informar_en_vivo("alienware", pid, TURNO, "respondiendo", "1. **Primero**")
    assert r.en_vivo(pid)["estado"] == "libre"
    # Un turno nuevo sí.
    r.informar_en_vivo("alienware", pid, "turno-0002", "respondiendo", "Otra")
    assert r.en_vivo(pid)["parcial"] == "Otra"


def test_los_parciales_no_generan_avisos(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    r.informar_en_vivo("alienware", pid, TURNO, "respondiendo", "¿Qué quieres hacer primero?")
    assert r.avisos(T0) == []
    r.respuesta_orquestador("alienware", pid, "final-0001", "¿Qué quieres hacer primero?", TURNO)
    [aviso] = r.avisos(T0)
    assert aviso["tipo"] == "pregunta"


def test_sin_noticias_la_respuesta_vence_y_pausar_la_corta(tmp_path: Path) -> None:
    reloj = [T0]
    r = ProyectosEquipo(tmp_path, clock=lambda: reloj[0])
    pid = _activo(r)
    r.informar_en_vivo("alienware", pid, TURNO, "respondiendo", "Hola")
    reloj[0] = T0 + timedelta(seconds=59)
    assert r.en_vivo(pid)["estado"] == "respondiendo"
    reloj[0] = T0 + timedelta(seconds=61)
    assert r.en_vivo(pid)["estado"] == "libre"
    r.informar_en_vivo("alienware", pid, "turno-0002", "respondiendo", "Hola")
    r.pausar(pid)
    assert r.en_vivo(pid)["estado"] == "libre"


def test_solo_la_maquina_del_proyecto(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    with pytest.raises(ProyectoError):
        r.informar_en_vivo("otra", pid, TURNO, "respondiendo", "x")
    assert r.en_vivo(pid)["estado"] == "libre"


def test_migracion_6(tmp_path: Path) -> None:
    from app.core.proyectos_equipo import _MIGRACIONES  # pyright: ignore[reportPrivateUsage]

    db = sqlite3.connect(tmp_path / "proyectos.db")
    for v in (1, 2, 3, 4, 5):
        for sql in _MIGRACIONES[v]:
            db.execute(sql)
    db.execute(
        "INSERT INTO proyectos (id, nombre, maquina, cuenta, ruta, plantilla, estado,"
        " auto_aprobar, creado, actualizado) VALUES ('p','tienda','alienware','personal','x',"
        "'vacia','activo',0,'2026','2026')"
    )
    db.execute(
        "INSERT INTO mensajes (id, proyecto_id, autor, texto, creado) "
        "VALUES ('m', 'p', 'washington', 'hola', '2026')"
    )
    db.execute("PRAGMA user_version = 5")
    db.commit()
    db.close()
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    assert r.version() == 6
    [m] = r.mensajes("p")
    assert (m["estado"], m["leido"]) == ("enviado", None)


class _Pedido:
    """Lo que eventos_chat usa del pedido: si el cliente se fue."""

    def __init__(self) -> None:
        self.fuera = False

    async def is_disconnected(self) -> bool:
        return self.fuera


def test_eventos_sse(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    set_proyectos_equipo(r)
    pid = _activo(r)
    pedido = _Pedido()
    recibidos: list[str] = []

    async def correr() -> None:
        gen = eventos_chat(pedido, pid, duracion=5.0, mirar=0.01, pulso=0.05)  # type: ignore[arg-type]
        async for trozo in gen:
            recibidos.append(trozo)
            eventos = [x for x in recibidos if x.startswith("event: chat")]
            if len(eventos) == 1 and not any(x.startswith(":") for x in recibidos):
                continue  # espera un pulso antes de cambiar algo
            if len(eventos) == 1:
                r.informar_en_vivo("alienware", pid, TURNO, "respondiendo", "Escribiendo")
            elif len(eventos) == 2:
                pedido.fuera = True

    try:
        asyncio.run(correr())
    finally:
        set_proyectos_equipo(None)
    assert recibidos[0] == "retry: 1000\n\n"
    eventos = [x for x in recibidos if x.startswith("event: chat")]
    assert len(eventos) == 2
    datos: list[dict[str, Any]] = [json.loads(x.split("data: ", 1)[1]) for x in eventos]
    assert datos[0]["en_vivo"]["estado"] == "libre"
    assert datos[1]["en_vivo"] == {
        "estado": "respondiendo",
        "parcial": "Escribiendo",
        "mensaje_id": None,
        "desde": T0.isoformat(),
        "actualizado": T0.isoformat(),
    }
    assert ": pulso\n\n" in recibidos


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
    pid = _activo(reg)
    m = c.post(f"{api}/proyectos-creados/{pid}/chat", json={"texto": "Hola"}).json()
    assert m["estado"] == "enviado"
    r = c.post(
        f"{api}/maquinas/chat/en-vivo",
        json={"proyecto_id": pid, "turno": TURNO, "estado": "leido", "mensaje_id": m["id"]},
    )
    assert r.status_code == 200
    c.post(
        f"{api}/maquinas/chat/en-vivo",
        json={"proyecto_id": pid, "turno": TURNO, "estado": "respondiendo", "parcial": "Ho"},
    )
    chat = c.get(f"{api}/proyectos-creados/{pid}/chat").json()
    assert chat["en_vivo"]["parcial"] == "Ho"
    assert chat["mensajes"][0]["estado"] == "respondiendo"
    liviano = c.get(f"{api}/proyectos-creados/{pid}/chat/en-vivo").json()
    assert set(liviano) == {"version", "en_vivo", "recientes"}
    c.post(
        f"{api}/maquinas/chat",
        json={"proyecto_id": pid, "origen_id": "final-0001", "texto": "Hola.", "turno": TURNO},
    )
    liviano = c.get(f"{api}/proyectos-creados/{pid}/chat/en-vivo").json()
    assert liviano["en_vivo"]["estado"] == "libre"
    assert [x["estado"] for x in liviano["recientes"]] == ["leido", None]
    # Validaciones: estado desconocido, id de mensaje mal formado, proyecto inexistente.
    malo = {"proyecto_id": pid, "turno": TURNO, "estado": "pensando"}
    assert c.post(f"{api}/maquinas/chat/en-vivo", json=malo).status_code == 422
    malo = {"proyecto_id": pid, "turno": TURNO, "estado": "leido", "mensaje_id": "x"}
    assert c.post(f"{api}/maquinas/chat/en-vivo", json=malo).status_code == 422
    assert c.get(f"{api}/proyectos-creados/nada/chat/en-vivo").status_code == 404
    assert c.get(f"{api}/proyectos-creados/nada/chat/eventos").status_code == 404

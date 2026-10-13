"""Respuesta del orquestador que se va escribiendo, con leído y escribiendo (Prompt 45)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from test_ordenes import PID, _listo, _mensaje, _sids

from visualizador_monitor.cliente import Respuesta, SinConexion
from visualizador_monitor.equipos import (
    RUTA_EN_VIVO,
    HiloEnVivo,
    Miembro,
    Proyecto,
    comando_sesion,
    parcial_visible,
)


def _proyecto() -> Proyecto:
    orq = Miembro(
        "orquestador", "orquestador", "haiku", "low", "1" * 8 + "-1111-1111-1111-" + "1" * 12
    )
    ag = Miembro("agente", "agente", "haiku", "low", "2" * 8 + "-2222-2222-2222-" + "2" * 12)
    return Proyecto(PID, "prueba-45", "E:\\Agents\\prueba-45", "personal", miembros=[orq, ag])


def test_solo_el_orquestador_pide_mensajes_parciales() -> None:
    p = _proyecto()
    orq, ag = p.miembros
    assert "--include-partial-messages" in comando_sesion(["claude"], p, orq, False)
    assert "--include-partial-messages" not in comando_sesion(["claude"], p, ag, False)


def test_parcial_visible_sin_ordenes() -> None:
    assert parcial_visible("Hola.\n\n1. **Uno**") == "Hola.\n\n1. **Uno**"
    completo = 'Te propongo esto.\n<orden agente="agente" titulo="Base">Crea x</orden>\nListo.'
    assert parcial_visible(completo) == "Te propongo esto.\n\nListo."
    assert parcial_visible('Va una orden:\n<orden agente="agente">Crea') == "Va una orden:"
    assert parcial_visible("Va una orden:\n<ord") == "Va una orden:"
    assert parcial_visible("a < b y <x") == "a < b y <x"


def test_leido_respondiendo_parcial_y_final(tmp_path: Path) -> None:
    g, srv, _, enc = _listo(tmp_path, env={"FALSO_PAUSA": "0.15"})
    orq_sid, _ = _sids(enc)
    texto = "Uno, dos, tres, cuatro y cinco."
    m = _mensaje(f"lento:{texto}")
    assert g.procesar(m)["ok"]
    vistos: list[dict[str, Any]] = []
    fin = time.monotonic() + 20
    while time.monotonic() < fin:
        g.atender()
        vistos += g.en_vivo()
        if vistos and not g.sesiones[orq_sid].ocupada():
            break
        time.sleep(0.02)
    g.atender()
    g.vaciar_salida(srv)  # type: ignore[arg-type]
    assert vistos, "nunca hubo respuesta en curso"
    turnos = {v["turno"] for v in vistos}
    assert len(turnos) == 1
    [turno] = turnos
    # Primero leído (entregado a la sesión), con el mensaje de Washington.
    assert vistos[0]["estado"] == "leido" and vistos[0]["mensaje_id"] == m["mensaje_id"]
    # Después respondiendo, con el texto que crece hasta la respuesta completa.
    parciales = [v["parcial"] for v in vistos if v["estado"] == "respondiendo"]
    assert parciales and all(texto.startswith(x) for x in parciales)
    distintos = list(dict.fromkeys(parciales))
    assert len(distintos) >= 3, distintos
    assert all(len(a) <= len(b) for a, b in zip(distintos, distintos[1:], strict=False))
    # El final lleva el turno y después sale libre, en ese orden.
    rutas = [r for r, _ in srv.posts]
    final = [d for r, d in srv.posts if r == "/api/v1/maquinas/chat" and d.get("turno") == turno]
    assert final and final[0]["texto"] == texto
    # (El saludo inicial también fue un turno, con su propio libre.)
    [libre] = [d for r, d in srv.posts if r == RUTA_EN_VIVO and d["turno"] == turno]
    assert libre == {
        "proyecto_id": PID,
        "turno": turno,
        "estado": "libre",
        "mensaje_id": m["mensaje_id"],
    }
    assert rutas.index(RUTA_EN_VIVO, len(rutas) - 1) > max(
        i for i, (r, d) in enumerate(srv.posts) if d.get("turno") == turno and r != RUTA_EN_VIVO
    )
    assert g.en_vivo() == []


class _Equipos:
    def __init__(self) -> None:
        self.vivos: list[dict[str, Any]] = []

    def en_vivo(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.vivos]


class _Srv:
    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.respuesta = Respuesta(200, {})
        self.caido = False

    def post_json(self, ruta: str, datos: dict[str, Any], timeout: float = 5.0) -> Respuesta:
        if self.caido:
            raise SinConexion("x")
        assert ruta == RUTA_EN_VIVO
        self.posts.append(datos)
        return self.respuesta


def test_hilo_en_vivo_manda_solo_lo_nuevo() -> None:
    eq, srv = _Equipos(), _Srv()
    h = HiloEnVivo(srv, eq, pulso=0.3, sin_ruta=60)  # type: ignore[arg-type]
    vivo = {"proyecto_id": PID, "turno": "t" * 32, "estado": "leido", "parcial": ""}
    eq.vivos = [vivo]
    assert h.ronda() == 1
    assert h.ronda() == 0  # nada cambió
    eq.vivos = [{**vivo, "estado": "respondiendo", "parcial": "Ho"}]
    assert h.ronda() == 1
    eq.vivos = [{**vivo, "estado": "respondiendo", "parcial": "Hola"}]
    assert h.ronda() == 1
    assert [p["parcial"] for p in srv.posts] == ["", "Ho", "Hola"]
    time.sleep(0.35)
    assert h.ronda() == 1  # pulso: sin cambios, pero pasó el tiempo
    # Sin conexión: no se pierde, se reintenta en la ronda siguiente.
    eq.vivos = [{**vivo, "estado": "respondiendo", "parcial": "Hola, Washington"}]
    srv.caido = True
    assert h.ronda() == 0
    srv.caido = False
    assert h.ronda() == 1
    # Un servidor sin la ruta: se calla un rato.
    eq.vivos = [{**vivo, "estado": "respondiendo", "parcial": "Hola, Washington."}]
    srv.respuesta = Respuesta(404, {"detail": "Not Found"})
    assert h.ronda() == 1 - 1
    srv.respuesta = Respuesta(200, {})
    assert h.ronda() == 0
    # Un 404 del proyecto (no de la ruta) no lo calla.
    h2 = HiloEnVivo(srv, eq)  # type: ignore[arg-type]
    srv.respuesta = Respuesta(404, {"detail": "No existe ese proyecto para esta máquina."})
    assert h2.ronda() == 1
    srv.respuesta = Respuesta(200, {})
    eq.vivos = [{**vivo, "estado": "respondiendo", "parcial": "otra"}]
    assert h2.ronda() == 1

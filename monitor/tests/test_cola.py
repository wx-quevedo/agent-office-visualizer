from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from visualizador_monitor.cola import Cola


class Reloj:
    def __init__(self) -> None:
        self.t = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.t

    def avanzar(self, s: float) -> None:
        self.t += timedelta(seconds=s)


def test_orden_de_llegada(tmp_path: Path) -> None:
    c = Cola(tmp_path / "c.db")
    for i in range(3):
        c.agregar("/api/v1/events", f"{i}".encode())
    vistos = []
    while (e := c.siguiente()) is not None:
        vistos.append(e.cuerpo)
        c.enviado(e)
    assert vistos == [b"0", b"1", b"2"]
    assert c.resumen()["ultimo_envio"] is not None


def test_mismo_id_no_se_duplica(tmp_path: Path) -> None:
    c = Cola(tmp_path / "c.db")
    assert c.agregar("/r", b"a", evento_id="x1") == "x1"
    c.agregar("/r", b"a", evento_id="x1")
    assert c.pendientes() == 1


def test_espera_progresiva_y_nada_se_adelanta(tmp_path: Path) -> None:
    reloj = Reloj()
    c = Cola(tmp_path / "c.db", clock=reloj)
    c.agregar("/r", b"primero")
    c.agregar("/r", b"segundo")
    esperas = []
    for _ in range(8):
        e = c.siguiente()
        assert e is not None and e.cuerpo == b"primero"
        esperas.append(c.posponer(e, "sin conexión"))
        assert c.siguiente() is None  # el segundo no se adelanta
        reloj.avanzar(esperas[-1])
    assert esperas == [1, 2, 4, 8, 16, 32, 60, 60]


def test_reintentar_ya(tmp_path: Path) -> None:
    reloj = Reloj()
    c = Cola(tmp_path / "c.db", clock=reloj)
    c.agregar("/r", b"x")
    e = c.siguiente()
    assert e is not None
    c.posponer(e, "caído", espera=60)
    assert c.siguiente() is None
    c.reintentar_ya()
    assert c.siguiente() is not None


def test_descartar_no_frena_a_los_demas(tmp_path: Path) -> None:
    c = Cola(tmp_path / "c.db")
    c.agregar("/r", b"malo")
    c.agregar("/r", b"bueno")
    e = c.siguiente()
    assert e is not None
    c.descartar(e, "HTTP 422")
    e2 = c.siguiente()
    assert e2 is not None and e2.cuerpo == b"bueno"
    assert "HTTP 422" in str(c.resumen()["ultimo_descarte"])


def test_sobrevive_a_un_reinicio(tmp_path: Path) -> None:
    ruta = tmp_path / "c.db"
    c = Cola(ruta)
    ids = [c.agregar("/r", f"{i}".encode()) for i in range(5)]
    e = c.siguiente()
    assert e is not None
    c.posponer(e, "caído")
    del c
    otra = Cola(ruta)  # el monitor volvió a arrancar
    assert otra.pendientes() == 5
    otra.reintentar_ya()
    e = otra.siguiente()
    assert e is not None and e.evento_id == ids[0] and e.intentos == 1


def test_tope_de_la_cola(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from visualizador_monitor import cola as modulo

    monkeypatch.setattr(modulo, "MAX_PENDIENTES", 3)
    c = Cola(tmp_path / "c.db")
    for i in range(5):
        c.agregar("/r", f"{i}".encode())
    assert c.pendientes() == 3
    e = c.siguiente()
    assert e is not None and e.cuerpo == b"2"  # se descartan los más viejos
    assert "descartados" in str(c.resumen()["ultimo_descarte"])

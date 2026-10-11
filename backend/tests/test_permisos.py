"""Permission requests answered from the office (app/core/permisos.py and its routes)."""

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import permisos as rutas
from app.core import permisos
from app.core.permisos import Configuracion, PermisoError, RegistroPermisos


class Reloj:
    def __init__(self) -> None:
        self.t = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.t

    def avanzar(self, s: float) -> None:
        self.t += timedelta(seconds=s)


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def reg(tmp_path: Path, reloj: Reloj) -> RegistroPermisos:
    return RegistroPermisos(tmp_path, clock=reloj)


def crear(reg: RegistroPermisos, id_: str = "solicitud-1", en_la_pc: bool = False, **kw: Any):
    datos: dict[str, Any] = {
        "session_id": "prueba-permisos",
        "herramienta": "Bash",
        "entrada": {"command": "git status", "description": "Estado"},
        "cuenta": "personal",
        "proyecto": "demo",
    }
    datos.update(kw)
    return reg.crear(
        id_,
        datos["session_id"],
        datos["herramienta"],
        datos["entrada"],
        datos["cuenta"],
        datos["proyecto"],
        en_la_pc=en_la_pc,
    )


# -- policy and presence ------------------------------------------------------------


def test_por_defecto_espera_solo_fuera_de_la_pc(reg: RegistroPermisos) -> None:
    assert reg.config.politica == "solo_fuera_de_la_pc"
    assert reg.config.espera_seg == 90
    fuera = crear(reg, "solicitud-a", en_la_pc=False)
    assert fuera.esperando and fuera.vence is not None
    en_pc = crear(reg, "solicitud-b", en_la_pc=True, session_id="otra")
    assert not en_pc.esperando and en_pc.vence is None


@pytest.mark.parametrize(
    ("politica", "en_pc", "espera"),
    [("siempre", True, True), ("siempre", False, True), ("nunca", False, False)],
)
def test_politicas(reg: RegistroPermisos, politica: str, en_pc: bool, espera: bool) -> None:
    reg.guardar_config(Configuracion(politica=politica))  # type: ignore[arg-type]
    assert crear(reg, en_la_pc=en_pc).esperando is espera


def test_detalle_es_el_comando_completo(reg: RegistroPermisos) -> None:
    s = crear(reg, entrada={"command": "git push origin main && echo listo"})
    assert s.detalle == "git push origin main && echo listo"
    s2 = crear(
        reg,
        "solicitud-2",
        session_id="s2",
        herramienta="Write",
        entrada={"file_path": "E:/a.txt", "content": "x"},
    )
    assert s2.detalle == "E:/a.txt"


def test_registrar_es_idempotente(reg: RegistroPermisos) -> None:
    a = crear(reg)
    b = crear(reg)
    assert a is b


# -- decision ------------------------------------------------------------------------


def test_se_decide_una_sola_vez_y_queda_en_el_registro(reg: RegistroPermisos) -> None:
    crear(reg)
    s = reg.decidir("solicitud-1", False, "  Usa la rama de prueba  ", "celular")
    assert (s.estado, s.motivo, s.dispositivo) == ("rechazada", "Usa la rama de prueba", "celular")
    with pytest.raises(PermisoError) as e:
        reg.decidir("solicitud-1", True, None, "pc")
    assert e.value.status == 409
    fila = reg.historial()[0]
    assert fila["estado"] == "rechazada" and fila["dispositivo"] == "celular"
    assert fila["detalle"] == "git status" and fila["politica"] == "solo_fuera_de_la_pc"


def test_aprobar_no_guarda_motivo(reg: RegistroPermisos) -> None:
    crear(reg)
    assert reg.decidir("solicitud-1", True, "ignorado", "pc").motivo is None


def test_vencida_se_rechaza_con_error_claro(reg: RegistroPermisos, reloj: Reloj) -> None:
    crear(reg)
    reloj.avanzar(91)
    with pytest.raises(PermisoError) as e:
        reg.decidir("solicitud-1", True, None, "pc")
    assert e.value.status == 410
    assert "VS Code" in e.value.mensaje
    assert reg.obtener("solicitud-1").estado == "vencida"  # type: ignore[union-attr]


def test_sin_espera_no_se_puede_decidir_desde_la_oficina(reg: RegistroPermisos) -> None:
    crear(reg, en_la_pc=True)
    with pytest.raises(PermisoError) as e:
        reg.decidir("solicitud-1", True, None, "pc")
    assert e.value.status == 409


def test_inexistente_404(reg: RegistroPermisos) -> None:
    with pytest.raises(PermisoError) as e:
        reg.decidir("no-existe-123", True, None, "pc")
    assert e.value.status == 404


# -- answered in VS Code -----------------------------------------------------------------


def test_respuesta_en_vscode_la_marca_resuelta(reg: RegistroPermisos, reloj: Reloj) -> None:
    crear(reg)
    # A parallel call of another tool does not count...
    reg.resolver_sesion("prueba-permisos", "post_tool_use", "Read", {"file_path": "x"})
    reg.resolver_sesion("prueba-permisos", "pre_tool_use", "Read", {"file_path": "x"})
    assert reg.obtener("solicitud-1").estado == "pendiente"  # type: ignore[union-attr]
    # ...the same tool running does (it was approved in VS Code).
    reg.resolver_sesion("prueba-permisos", "post_tool_use", "Bash", {"command": "git status"})
    s = reg.obtener("solicitud-1")
    assert s is not None and s.estado == "resuelta_fuera"
    with pytest.raises(PermisoError) as e:
        reg.decidir("solicitud-1", True, None, "pc")
    assert e.value.status == 409


@pytest.mark.parametrize("evento", ["stop", "user_prompt_submit", "session_end"])
def test_fin_del_turno_la_resuelve(reg: RegistroPermisos, evento: str) -> None:
    crear(reg)
    reg.resolver_sesion("prueba-permisos", evento)
    assert reg.obtener("solicitud-1").estado == "resuelta_fuera"  # type: ignore[union-attr]


def test_pre_tool_use_posterior_la_resuelve(reg: RegistroPermisos, reloj: Reloj) -> None:
    crear(reg)
    reloj.avanzar(5)
    reg.resolver_sesion("prueba-permisos", "pre_tool_use", "Read", {"file_path": "x"})
    assert reg.obtener("solicitud-1").estado == "resuelta_fuera"  # type: ignore[union-attr]


def test_otra_sesion_no_la_toca(reg: RegistroPermisos) -> None:
    crear(reg)
    reg.resolver_sesion("otra", "stop")
    assert reg.obtener("solicitud-1").estado == "pendiente"  # type: ignore[union-attr]


# -- long-poll -----------------------------------------------------------------------


async def test_long_poll_despierta_al_decidir(tmp_path: Path) -> None:
    reg = RegistroPermisos(tmp_path)
    crear(reg)

    async def decidir_luego() -> None:
        await asyncio.sleep(0.1)
        reg.decidir("solicitud-1", True, None, "pc")

    tarea = asyncio.create_task(decidir_luego())
    inicio = asyncio.get_running_loop().time()
    s = await reg.esperar("solicitud-1", 5)
    await tarea
    assert s is not None and s.estado == "aprobada"
    assert asyncio.get_running_loop().time() - inicio < 2


async def test_long_poll_sin_decision_vuelve_pendiente(tmp_path: Path) -> None:
    reg = RegistroPermisos(tmp_path)
    crear(reg)
    s = await reg.esperar("solicitud-1", 0.2)
    assert s is not None and s.estado == "pendiente"


# -- configuration -----------------------------------------------------------------


def test_config_se_guarda_y_valida(tmp_path: Path) -> None:
    reg = RegistroPermisos(tmp_path)
    cfg = permisos.validar_config(
        {"politica": "siempre", "espera_seg": 120, "confirmar": ["rm", " rm ", "git push"]}
    )
    reg.guardar_config(cfg)
    assert json.loads((tmp_path / "permisos.json").read_text(encoding="utf-8"))["confirmar"] == [
        "rm",
        "git push",
    ]
    assert RegistroPermisos(tmp_path).config.espera_seg == 120
    for malo in (
        {"politica": "a veces"},
        {"espera_seg": 5},
        {"espera_seg": 10_000},
        {"espera_seg": "90"},
        {"confirmar": "rm"},
    ):
        with pytest.raises(ValueError):
            permisos.validar_config(malo)


# -- routes ------------------------------------------------------------------------


class MotorFalso:
    def __init__(self) -> None:
        self.pc = False

    def en_la_pc(self) -> bool:
        return self.pc


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reg = RegistroPermisos(tmp_path)
    permisos.set_registro(reg)
    motor = MotorFalso()
    monkeypatch.setattr(rutas, "get_state_engine", lambda: motor)
    app = FastAPI()
    app.include_router(rutas.router, prefix="/api/v1")
    yield TestClient(app), motor, reg
    permisos.set_registro(None)


def nueva(id_: str = "solicitud-1") -> dict[str, Any]:
    return {
        "id": id_,
        "session_id": "prueba-permisos",
        "herramienta": "Bash",
        "entrada": {"command": "git status"},
        "cuenta": "personal",
        "proyecto": "demo",
    }


def test_rutas_flujo_completo(client) -> None:  # type: ignore[no-untyped-def]
    c, motor, _ = client
    r = c.post("/api/v1/permisos/solicitudes", json=nueva())
    assert r.status_code == 200
    body = r.json()
    assert body["esperar"] is True and body["segundos_restantes"] == 90
    assert (
        c.get("/api/v1/permisos/solicitudes/solicitud-1?espera=0.2").json()["estado"] == "pendiente"
    )
    r = c.post(
        "/api/v1/permisos/solicitudes/solicitud-1/decision",
        json={"decision": "rechazar", "motivo": "No ahora", "dispositivo": "celular"},
    )
    assert r.status_code == 200 and r.json()["estado"] == "rechazada"
    r = c.post("/api/v1/permisos/solicitudes/solicitud-1/decision", json={"decision": "aprobar"})
    assert r.status_code == 409
    assert "ya fue decidida" in r.json()["detail"]
    s = c.get("/api/v1/permisos/solicitudes/solicitud-1?espera=5").json()
    assert (s["estado"], s["motivo"]) == ("rechazada", "No ahora")
    # At the PC (default policy): registered, no wait.
    motor.pc = True
    assert (
        c.post("/api/v1/permisos/solicitudes", json=nueva("solicitud-2")).json()["esperar"] is False
    )


def test_rutas_config_y_errores(client) -> None:  # type: ignore[no-untyped-def]
    c, _, _ = client
    assert c.get("/api/v1/permisos/config").json()["politica"] == "solo_fuera_de_la_pc"
    r = c.put(
        "/api/v1/permisos/config",
        json={"politica": "siempre", "espera_seg": 60, "confirmar": ["rm"]},
    )
    assert r.status_code == 200 and r.json()["espera_seg"] == 60
    assert c.put("/api/v1/permisos/config", json={"espera_seg": 3}).status_code == 422
    assert (
        c.post(
            "/api/v1/permisos/solicitudes/nada-1234/decision", json={"decision": "aprobar"}
        ).status_code
        == 404
    )
    assert c.get("/api/v1/permisos/solicitudes/nada-1234").status_code == 404
    malo = nueva()
    malo["id"] = "con espacios!"
    assert c.post("/api/v1/permisos/solicitudes", json=malo).status_code == 422


def test_registro_sqlite_propio(client) -> None:  # type: ignore[no-untyped-def]
    c, _, reg = client
    c.post("/api/v1/permisos/solicitudes", json=nueva())
    c.post(
        "/api/v1/permisos/solicitudes/solicitud-1/decision",
        json={"decision": "aprobar", "dispositivo": "pc"},
    )
    with sqlite3.connect(reg.ruta_db) as db:
        fila = db.execute("SELECT estado, dispositivo, decidida FROM permisos").fetchone()
    assert fila[0] == "aprobada" and fila[1] == "pc" and fila[2]

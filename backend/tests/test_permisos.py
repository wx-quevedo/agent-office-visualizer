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


class Dispositivos:
    """Where the office is open (PC and phone heartbeats within the presence window)."""

    def __init__(self, pc: bool = False, celular: bool = True) -> None:
        self.pc = pc
        self.celular = celular

    def __call__(self) -> tuple[bool, bool]:
        return self.pc, self.celular


@pytest.fixture
def disp() -> Dispositivos:
    return Dispositivos()


@pytest.fixture
def reg(tmp_path: Path, reloj: Reloj, disp: Dispositivos) -> RegistroPermisos:
    return RegistroPermisos(tmp_path, clock=reloj, presencia=disp)


def crear(reg: RegistroPermisos, id_: str = "solicitud-1", **kw: Any):
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
    )


# -- policy and presence ------------------------------------------------------------


@pytest.mark.parametrize(
    ("pc", "celular", "espera"),
    [
        (False, False, False),  # nobody has the office open
        (True, False, False),  # only the PC: VS Code answers
        (False, True, True),  # only the phone: the office waits
        (True, True, False),  # PC and phone: VS Code answers
    ],
)
def test_por_defecto_espera_solo_en_el_celular(
    reg: RegistroPermisos, disp: Dispositivos, pc: bool, celular: bool, espera: bool
) -> None:
    assert reg.config.politica == "solo_en_el_celular"
    assert reg.config.espera_seg == 90
    disp.pc, disp.celular = pc, celular
    s = crear(reg)
    assert s.esperando is espera
    assert (s.vence is not None) is espera


def test_el_celular_se_desconecta_durante_la_espera(
    reg: RegistroPermisos, disp: Dispositivos
) -> None:
    assert crear(reg).esperando
    disp.celular = False
    s = reg.obtener("solicitud-1")
    assert s is not None and s.estado == "pendiente" and not s.esperando
    assert s.vista(reg.clock())["esperando"] is False
    with pytest.raises(PermisoError) as e:
        reg.decidir("solicitud-1", True, None, "celular")
    assert e.value.status == 409
    assert reg.historial()[0]["esperando"] == 0


async def test_long_poll_suelta_cuando_el_celular_se_desconecta(tmp_path: Path) -> None:
    disp = Dispositivos()
    reg = RegistroPermisos(tmp_path, presencia=disp)
    crear(reg)

    async def desconectar() -> None:
        await asyncio.sleep(0.3)
        disp.celular = False

    tarea = asyncio.create_task(desconectar())
    inicio = asyncio.get_running_loop().time()
    s = await reg.esperar("solicitud-1", 10)
    await tarea
    assert s is not None and s.estado == "pendiente" and not s.esperando
    assert asyncio.get_running_loop().time() - inicio < 3


@pytest.mark.parametrize(
    ("politica", "pc", "celular", "espera"),
    [
        ("siempre", True, False, True),
        ("siempre", False, False, True),
        ("nunca", False, True, False),
    ],
)
def test_politicas(
    reg: RegistroPermisos,
    disp: Dispositivos,
    politica: str,
    pc: bool,
    celular: bool,
    espera: bool,
) -> None:
    reg.guardar_config(Configuracion(politica=politica))  # type: ignore[arg-type]
    disp.pc, disp.celular = pc, celular
    assert crear(reg).esperando is espera


def test_siempre_no_suelta_sin_celular(reg: RegistroPermisos, disp: Dispositivos) -> None:
    reg.guardar_config(Configuracion(politica="siempre"))
    crear(reg)
    disp.celular = False
    assert reg.obtener("solicitud-1").esperando  # type: ignore[union-attr]


def test_politica_antigua_se_convierte_al_cargar(tmp_path: Path) -> None:
    (tmp_path / "permisos.json").write_text(
        json.dumps({"politica": "solo_fuera_de_la_pc", "espera_seg": 120, "confirmar": ["rm"]}),
        encoding="utf-8",
    )
    reg = RegistroPermisos(tmp_path)
    assert reg.config.politica == "solo_en_el_celular"
    assert reg.config.espera_seg == 120 and reg.config.confirmar == ["rm"]
    guardado = json.loads((tmp_path / "permisos.json").read_text(encoding="utf-8"))
    assert guardado["politica"] == "solo_en_el_celular"
    assert permisos.validar_config({"politica": "solo_fuera_de_la_pc"}).politica == (
        "solo_en_el_celular"
    )


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
    assert fila["detalle"] == "git status" and fila["politica"] == "solo_en_el_celular"


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


def test_sin_espera_no_se_puede_decidir_desde_la_oficina(
    reg: RegistroPermisos, disp: Dispositivos
) -> None:
    disp.pc = True
    crear(reg)
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
    reg = RegistroPermisos(tmp_path, presencia=Dispositivos())
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
    reg = RegistroPermisos(tmp_path, presencia=Dispositivos())
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


@pytest.fixture
def client(tmp_path: Path):
    motor = Dispositivos()
    reg = RegistroPermisos(tmp_path, presencia=motor)
    permisos.set_registro(reg)
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
    assert c.get("/api/v1/permisos/config").json()["politica"] == "solo_en_el_celular"
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

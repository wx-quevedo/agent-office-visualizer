"""El monitor completo: API local, reenvío, permisos, estado y el comando hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import TOKEN, ServidorFalso, puerto_libre

from visualizador_monitor import config
from visualizador_monitor.app import Monitor
from visualizador_monitor.registro import configurar, logger, ruta_registro


def _pedir(
    m: Monitor,
    metodo: str,
    ruta: str,
    datos: Any = None,
    timeout: float = 10,
    cabeceras: dict[str, str] | None = None,
) -> Any:
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{m.cfg.puerto}{ruta}",
        data=cuerpo,
        method=metodo,
        headers={"Content-Type": "application/json", "X-API-Key": m.clave, **(cabeceras or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _esperar(cond: Callable[[], bool], s: float = 8.0) -> bool:
    fin = time.monotonic() + s
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def _evento(n: int, sid: str = "prueba-monitor-1") -> dict[str, Any]:
    return {
        "event_type": "pre_tool_use",
        "session_id": sid,
        "timestamp": "2026-10-10T12:00:00Z",
        "data": {"tool_name": "Bash", "n": n},
    }


@pytest.fixture
def arrancar(base: Path) -> Iterator[Callable[[str], Monitor]]:
    monitores: list[Monitor] = []

    def _arrancar(url: str) -> Monitor:
        cfg = config.Configuracion(
            servidor=url, token=TOKEN, puerto=puerto_libre(), cuentas=[], intervalo_latido=3600
        )
        configurar(base, TOKEN)
        m = Monitor(cfg, base)
        m.iniciar()
        monitores.append(m)
        return m

    yield _arrancar
    for m in monitores:
        m.detener()


def test_eventos_llegan_al_servidor_en_orden(
    servidor: ServidorFalso, arrancar: Callable[[str], Monitor]
) -> None:
    m = arrancar(servidor.url)
    for i in range(5):
        r = _pedir(m, "POST", "/api/v1/events", _evento(i))
        assert r["status"] == "accepted"
    assert _esperar(lambda: len(servidor.eventos()) == 5)
    assert [e["data"]["n"] for e in servidor.eventos()] == list(range(5))
    assert m.cola.pendientes() == 0


def test_corte_y_reinicio_del_monitor_retoma_la_cola(base: Path, arrancar: Any) -> None:
    puerto = puerto_libre()
    m = arrancar(f"http://127.0.0.1:{puerto}")  # servidor apagado
    for i in range(3):
        _pedir(m, "POST", "/api/v1/events", _evento(i))
    assert _esperar(lambda: m.conexion.conectado is False)
    assert m.cola.pendientes() == 3
    m.detener()

    falso = ServidorFalso(puerto)
    falso.arrancar()
    try:
        m2 = arrancar(falso.url)  # el monitor reinició y el servidor volvió
        assert _esperar(lambda: len(falso.eventos()) == 3, 10)
        assert [e["data"]["n"] for e in falso.eventos()] == [0, 1, 2]
        assert len(falso.ids_vistos) == 3
        assert m2.cola.pendientes() == 0
    finally:
        falso.detener()


def test_permiso_aprobado_pasa_por_el_monitor(
    servidor: ServidorFalso, arrancar: Callable[[str], Monitor]
) -> None:
    m = arrancar(servidor.url)
    r = _pedir(m, "POST", "/api/v1/permisos/solicitudes", {"id": "p1", "session_id": "s"})
    assert r["esperar"] is True
    servidor.permisos["p1"] = "aprobada"
    r = _pedir(m, "GET", "/api/v1/permisos/solicitudes/p1?espera=1")
    assert r["estado"] == "aprobada"
    pedido = next(p for p in servidor.pedidos if p.ruta == "/api/v1/permisos/solicitudes")
    assert pedido.cabeceras["Authorization"] == f"Bearer {TOKEN}"


def test_permiso_sin_servidor_responde_sin_decision_rapido(arrancar: Any) -> None:
    m = arrancar(f"http://127.0.0.1:{puerto_libre()}")
    t0 = time.monotonic()
    r = _pedir(m, "POST", "/api/v1/permisos/solicitudes", {"id": "p2"})
    assert r["esperar"] is False and r["estado"] == "sin_conexion"
    r = _pedir(m, "GET", "/api/v1/permisos/solicitudes/p2?espera=20")
    assert r == {"estado": "sin_conexion", "esperando": False}
    assert time.monotonic() - t0 < 5


def test_estado_sin_token(servidor: ServidorFalso, arrancar: Callable[[str], Monitor]) -> None:
    m = arrancar(servidor.url)
    texto = json.dumps(_pedir(m, "GET", "/estado"))
    assert TOKEN not in texto
    assert '"pendientes"' in texto


def test_puerto_ocupado_no_arranca_un_segundo_monitor(
    servidor: ServidorFalso, arrancar: Callable[[str], Monitor], base: Path
) -> None:
    m = arrancar(servidor.url)
    otro = Monitor(m.cfg, base)
    with pytest.raises(OSError):
        otro.iniciar()


def test_registro_nunca_escribe_el_token(base: Path) -> None:
    configurar(base, TOKEN)
    logger.error("token %s y otro vap_abcdefgh123 en Bearer %s", TOKEN, TOKEN)
    try:
        raise RuntimeError(f"falló con {TOKEN}")
    except RuntimeError:
        logger.exception("error")
    for h in logger.handlers:
        h.flush()
    texto = ruta_registro(base).read_text(encoding="utf-8")
    assert TOKEN not in texto and "vap_abcdefgh123" not in texto
    assert "vam_" in texto


def test_mascara_y_vista_de_la_configuracion() -> None:
    cfg = config.Configuracion(servidor="https://x", token=TOKEN)
    assert TOKEN not in json.dumps(cfg.vista())
    assert TOKEN not in config.mascara(f"a {TOKEN} b")


# -- el comando hook (lo que corre Claude Code) ---------------------------------


def _hook(base: Path, evento: str, entrada: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "VISUALIZADOR_MONITOR_DIR": str(base),
        "CLAUDE_OFFICE_HOOKS_CONFIG": str(base / "no-existe.env"),
    }
    env.pop("CLAUDE_OFFICE_PELIGROSOS", None)
    return subprocess.run(
        [sys.executable, "-m", "visualizador_monitor", "hook", evento],
        input=json.dumps(entrada),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def test_hook_manda_al_monitor_y_pide_aprobacion_de_peligrosos(
    servidor: ServidorFalso, arrancar: Callable[[str], Monitor], base: Path
) -> None:
    m = arrancar(servidor.url)
    config.guardar(m.cfg, base)
    r = _hook(
        base,
        "pre_tool_use",
        {
            "session_id": "prueba-monitor-hook",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force origin main"},
            "permission_mode": "auto",
            "cwd": str(base),
        },
    )
    assert r.returncode == 0
    salida = json.loads(r.stdout)
    assert salida["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert _esperar(
        lambda: any(e["session_id"] == "prueba-monitor-hook" for e in servidor.eventos())
    )
    # el hook no llevaba token: lo agrega el monitor
    assert all(p.cabeceras.get("Authorization") == f"Bearer {TOKEN}" for p in servidor.pedidos)


def test_hook_comando_normal_no_pide_nada(base: Path) -> None:
    config.guardar(config.Configuracion(puerto=puerto_libre()), base)
    r = _hook(
        base,
        "pre_tool_use",
        {
            "session_id": "prueba-monitor-hook2",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
        },
    )
    assert r.returncode == 0
    assert r.stdout.strip() in ("", "{}")


def test_hook_con_el_monitor_apagado_no_bloquea(base: Path) -> None:
    config.guardar(config.Configuracion(puerto=puerto_libre()), base)
    t0 = time.monotonic()
    r = _hook(
        base,
        "permission_request",
        {
            "session_id": "prueba-monitor-hook3",
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        },
    )
    assert r.returncode == 0
    assert r.stdout.strip() in ("", "{}")
    assert time.monotonic() - t0 < 10


@pytest.mark.parametrize(
    "cabeceras",
    [
        {"X-API-Key": "otra-clave"},
        {"Origin": "https://pagina-cualquiera.example"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Host": "atacante.example:8765"},
        {"Content-Type": "text/plain"},
    ],
)
def test_api_local_rechaza_sin_clave_o_desde_un_navegador(
    servidor: ServidorFalso, arrancar: Callable[[str], Monitor], cabeceras: dict[str, str]
) -> None:
    """CSRF y DNS rebinding: una página web no puede inyectar eventos ni leer el estado."""
    m = arrancar(servidor.url)
    with pytest.raises(urllib.error.HTTPError) as e:
        _pedir(m, "POST", "/api/v1/events", _evento(1), cabeceras=cabeceras)
    assert e.value.code == 403
    assert m.cola.pendientes() == 0


def test_estado_sin_clave_no_responde(
    servidor: ServidorFalso, arrancar: Callable[[str], Monitor]
) -> None:
    m = arrancar(servidor.url)
    req = urllib.request.Request(f"http://127.0.0.1:{m.cfg.puerto}/estado")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 403


def test_permiso_espera_a_que_salgan_los_eventos_anteriores(arrancar: Any) -> None:
    """Sin vaciar la cola, la solicitud no se adelanta a sus eventos: sin decisión."""
    m = arrancar(f"http://127.0.0.1:{puerto_libre()}")
    _pedir(m, "POST", "/api/v1/events", _evento(1))
    t0 = time.monotonic()
    r = _pedir(m, "POST", "/api/v1/permisos/solicitudes", {"id": "p3"})
    assert r["esperar"] is False and r["estado"] == "cola_pendiente"
    assert time.monotonic() - t0 < 3

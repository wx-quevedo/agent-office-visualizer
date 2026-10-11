"""Etapa 2.1 en el monitor: límites desde la barra de estado, "Dónde quedamos" e instalador."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import TOKEN, ServidorFalso, puerto_libre

from visualizador_monitor import config
from visualizador_monitor.app import Monitor
from visualizador_monitor.barra import cuenta_dir, extraer, linea
from visualizador_monitor.cliente import Servidor
from visualizador_monitor.instalador import desinstalar, instalar
from visualizador_monitor.instalador_main import main as instalador_main
from visualizador_monitor.lector import Lector
from visualizador_monitor.registro import configurar

RESETS_5H = 1_791_745_200  # 2026-10-11 20:00 UTC
RESETS_SEMANA = 1_792_022_400

ENTRADA_BARRA = {
    "session_id": "s1",
    "transcript_path": "C:\\Users\\w\\.claude-demo\\projects\\E--p\\s1.jsonl",
    "model": {"id": "claude-opus-5-5", "display_name": "Opus"},
    "rate_limits": {
        "five_hour": {"used_percentage": 23.5, "resets_at": RESETS_5H},
        "seven_day": {"used_percentage": 41.2, "resets_at": RESETS_SEMANA},
    },
}


# -- barra de estado ---------------------------------------------------------------------


def test_extraer_limites_de_la_barra() -> None:
    e = extraer(ENTRADA_BARRA, entorno={})
    assert e["cuenta_dir"] == "C:/Users/w/.claude-demo"
    assert e["cinco_horas"] == {
        "usado_pct": 23.5,
        "reinicia": datetime.fromtimestamp(RESETS_5H, UTC).isoformat(),
    }
    assert e["semanal"]["usado_pct"] == 41.2
    assert e["modelo"] == "Opus"
    texto = linea(e)
    assert texto.startswith("Opus · 5 h: 23.5 % (") and "semana: 41.2 % (" in texto


def test_barra_sin_limites_ni_datos() -> None:
    e = extraer({"model": {"display_name": "Sonnet"}}, entorno={})
    assert e["cinco_horas"] is None and e["semanal"] is None
    assert linea(e) == "Sonnet"
    assert linea(extraer({}, entorno={})) == "Oficina de agentes"
    raro = extraer({"rate_limits": {"five_hour": {"used_percentage": 300}}}, entorno={})
    assert raro["cinco_horas"] is None


def test_cuenta_por_variable_de_entorno() -> None:
    assert (
        cuenta_dir({}, {"CLAUDE_CONFIG_DIR": "C:\\Users\\w\\.claude-demo\\"})
        == "C:\\Users\\w\\.claude-demo"
    )
    assert (
        cuenta_dir({"transcript_path": "/home/w/.claude/projects/x.jsonl"}, {}) == "/home/w/.claude"
    )
    assert cuenta_dir({"transcript_path": "/tmp/x.jsonl"}, {}) is None


@pytest.fixture
def monitor(base: Path, servidor: ServidorFalso) -> Iterator[Monitor]:
    cfg = config.Configuracion(
        servidor=servidor.url, token=TOKEN, puerto=puerto_libre(), cuentas=[], intervalo_latido=3600
    )
    config.guardar(cfg, base)
    configurar(base, TOKEN)
    m = Monitor(cfg, base)
    m.iniciar()
    yield m
    m.detener()


def _esperar(cond: Callable[[], bool], s: float = 8.0) -> bool:
    fin = time.monotonic() + s
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def test_comando_statusline_manda_los_limites_al_servidor(
    monitor: Monitor, base: Path, servidor: ServidorFalso
) -> None:
    env = {**os.environ, "VISUALIZADOR_MONITOR_DIR": str(base)}
    env.pop("CLAUDE_CONFIG_DIR", None)
    r = subprocess.run(
        [sys.executable, "-m", "visualizador_monitor", "statusline"],
        input=json.dumps(ENTRADA_BARRA).encode("utf-8"),
        capture_output=True,
        env=env,
        timeout=30,
    )
    assert r.returncode == 0
    salida = r.stdout.decode("utf-8")
    assert salida.startswith("Opus · 5 h: 23.5 %")
    assert ".claude-demo" in next(iter(monitor.lector.limites))
    assert monitor.lector.enviar_limites() is True
    enviados = [p.json() for p in servidor.pedidos if p.ruta == "/api/v1/maquinas/limites"]
    assert enviados[-1]["cuentas"][0]["semanal"]["usado_pct"] == 41.2
    assert monitor.lector.enviar_limites() is False  # nada nuevo


def test_statusline_sin_monitor_no_falla(base: Path) -> None:
    config.guardar(config.Configuracion(puerto=puerto_libre()), base)
    env = {**os.environ, "VISUALIZADOR_MONITOR_DIR": str(base)}
    t0 = time.monotonic()
    r = subprocess.run(
        [sys.executable, "-m", "visualizador_monitor", "statusline"],
        input=b"no es json",
        capture_output=True,
        env=env,
        timeout=30,
    )
    assert r.returncode == 0 and r.stdout.decode("utf-8").strip() == "Oficina de agentes"
    assert time.monotonic() - t0 < 10


# -- "Dónde quedamos" --------------------------------------------------------------------


def test_proyectos_se_mandan_si_cambian(tmp_path: Path, servidor: ServidorFalso) -> None:
    proyecto = tmp_path / "mi-proyecto"
    proyecto.mkdir()
    (proyecto / "PROJECT.md").write_text(
        "# Mi proyecto\n\n## Plan por etapas\n\n- **Etapa 1** (hecha): base\n- **Etapa 2**: API\n\n"
        "## Próximos pasos\n\n1. Escribir la API\n",
        encoding="utf-8",
    )
    sin_md = tmp_path / "otro"
    sin_md.mkdir()
    lector = Lector(Servidor(servidor.url, TOKEN), [])
    lector.vio_evento({"session_id": "a", "data": {"project_dir": str(proyecto)}})
    lector.vio_evento({"session_id": "b", "data": {"working_dir": str(sin_md)}})
    assert lector.proyectos() == 2
    lote = [p.json() for p in servidor.pedidos if p.ruta == "/api/v1/maquinas/proyectos"][-1]
    por = {p["carpeta"]: p for p in lote["proyectos"]}
    assert por[str(proyecto)]["posicion"] == "Etapa 2"
    assert por[str(proyecto)]["siguiente_paso"] == "Escribir la API"
    assert por[str(sin_md)]["tiene_project_md"] is False
    assert lector.proyectos() == 0  # sin cambios: no se repite
    (proyecto / "PROJECT.md").write_text(
        "# Mi proyecto\n\n## Próximos pasos\n\n- Otra cosa\n", encoding="utf-8"
    )
    assert lector.proyectos() == 1


# -- instalador: barra de estado y actualización ----------------------------------------


def _usuario(tmp_path: Path, con_barra: bool) -> Path:
    inicio = tmp_path / "usuario"
    for nombre in (".claude", ".claude-demo"):
        c = inicio / nombre
        (c / "projects").mkdir(parents=True)
        datos: dict[str, Any] = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": "*",
                        "hooks": [{"type": "command", "command": "claude-office-hook stop"}],
                    }
                ]
            }
        }
        if con_barra and nombre == ".claude":
            datos["statusLine"] = {"type": "command", "command": "mi-barra.sh"}
        (c / "settings.json").write_text(json.dumps(datos, indent=4), encoding="utf-8")
    return inicio


def _origen(tmp_path: Path) -> Path:
    o = tmp_path / "dist" / "visualizador-monitor"
    o.mkdir(parents=True)
    (o / "visualizador-monitor.exe").write_bytes(b"MZ")
    return o


def test_instalador_agrega_la_barra_y_respeta_la_propia(tmp_path: Path) -> None:
    inicio = _usuario(tmp_path, con_barra=True)
    antes = {n: (inicio / n / "settings.json").read_bytes() for n in (".claude", ".claude-demo")}
    instalar(
        servidor="https://x.example",
        token=TOKEN,
        origen=_origen(tmp_path),
        destino=tmp_path / "destino",
        inicio=inicio,
        tarea=False,
    )
    propia = json.loads((inicio / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert propia["statusLine"]["command"] == "mi-barra.sh"  # la de Washington no se toca
    demo = json.loads((inicio / ".claude-demo" / "settings.json").read_text(encoding="utf-8"))
    assert demo["statusLine"]["command"].endswith('visualizador-monitor.exe" statusline')
    desinstalar(inicio=inicio)
    for n, contenido in antes.items():
        assert (inicio / n / "settings.json").read_bytes() == contenido


def test_actualizar_conserva_token_y_servidor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inicio = _usuario(tmp_path, con_barra=False)
    destino = tmp_path / "destino"
    origen = _origen(tmp_path)
    instalar(
        servidor="https://x.example",
        token=TOKEN,
        origen=origen,
        destino=destino,
        inicio=inicio,
        puerto=8799,
        tarea=False,
    )
    comun = [
        "--inicio",
        str(inicio),
        "--destino",
        str(destino),
        "--origen",
        str(origen),
        "--sin-tarea",
        "--si",
    ]
    assert instalador_main([*comun, "--actualizar"]) == 0
    cfg = config.cargar(inicio / ".visualizador-monitor")
    assert cfg.token == TOKEN and cfg.servidor == "https://x.example" and cfg.puerto == 8799
    settings = json.loads((inicio / ".claude" / "settings.json").read_text(encoding="utf-8"))
    exe = json.loads(
        (inicio / ".visualizador-monitor" / "instalacion.json").read_text(encoding="utf-8")
    )["exe"]
    comando = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert comando.startswith(f'"{Path(exe).as_posix()}"')
    assert TOKEN not in capsys.readouterr().out
    # sin instalación previa no hace nada
    otro = _usuario(tmp_path / "otro", con_barra=False)
    assert (
        instalador_main(["--inicio", str(otro), "--destino", str(destino), "--actualizar", "--si"])
        == 1
    )

"""El instalador en una carpeta de usuario simulada (nunca la real)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TOKEN

from visualizador_monitor import config
from visualizador_monitor.instalador import desinstalar, instalar
from visualizador_monitor.instalador_main import main as instalador_main

EVENTOS = ["session_start", "pre_tool_use", "post_tool_use", "stop", "permission_request"]


def _settings(eventos: list[str], prefijo: str = "claude-office-hook") -> dict[str, Any]:
    hooks: dict[str, Any] = {}
    for ev in eventos:
        tipo = "".join(p.capitalize() for p in ev.split("_"))
        entrada: dict[str, Any] = {"type": "command", "command": f"{prefijo} {ev}"}
        if ev == "permission_request":
            entrada["timeout"] = 600
        hooks[tipo] = [{"matcher": "*", "hooks": [entrada]}]
    # una entrada ajena que no se toca
    hooks.setdefault("PreToolUse", []).append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "otro-hook --x"}]}
    )
    return {"model": "opus", "hooks": hooks, "permissions": {"allow": ["Bash(ls)"]}}


@pytest.fixture
def usuario(tmp_path: Path) -> Path:
    inicio = tmp_path / "usuario-simulado"
    a = inicio / ".claude"
    b = inicio / ".claude-demo"
    for c in (a, b):
        (c / "projects").mkdir(parents=True)
    # formato propio (sangría 4, claves sin orden) para comprobar la restauración exacta
    (a / "settings.json").write_text(json.dumps(_settings(EVENTOS), indent=4), encoding="utf-8")
    (b / "settings.json").write_text(
        json.dumps(_settings(EVENTOS, "C:/Users/x/.local/bin/claude-office-hook.exe")),
        encoding="utf-8",
    )
    (inicio / ".claude-sin-nada").mkdir()  # no es una cuenta
    return inicio


@pytest.fixture
def origen(tmp_path: Path) -> Path:
    o = tmp_path / "dist" / "visualizador-monitor"
    o.mkdir(parents=True)
    (o / "visualizador-monitor.exe").write_bytes(b"MZ falso")
    (o / "_internal").mkdir()
    return o


def _instalar(usuario: Path, origen: Path, tmp_path: Path) -> dict[str, Any]:
    return instalar(
        servidor="https://agents.example.test",
        token=TOKEN,
        origen=origen,
        destino=tmp_path / "LocalAppData" / "VisualizadorMonitor",
        inicio=usuario,
        tarea=False,
    )


def test_instala_respalda_y_cambia_solo_nuestras_entradas(
    usuario: Path, origen: Path, tmp_path: Path
) -> None:
    antes = {c: (usuario / c / "settings.json").read_bytes() for c in (".claude", ".claude-demo")}
    m = _instalar(usuario, origen, tmp_path)
    exe = Path(m["exe"])
    assert exe.is_file()
    assert [Path(c).name for c in m["cuentas"]] == [".claude", ".claude-demo"]
    for cuenta in (".claude", ".claude-demo"):
        ruta = usuario / cuenta / "settings.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        comandos = [h for grupos in datos["hooks"].values() for g in grupos for h in g["hooks"]]
        nuestros = [h for h in comandos if "visualizador-monitor.exe" in h["command"]]
        assert len(nuestros) == len(EVENTOS)
        assert all(h["command"].startswith(f'"{exe.as_posix()}" hook ') for h in nuestros)
        assert not any("claude-office-hook" in h["command"] for h in comandos)
        permiso = next(h for h in nuestros if h["command"].endswith("permission_request"))
        assert permiso["timeout"] == 600
        assert any(h["command"] == "otro-hook --x" for h in comandos)
        assert datos["model"] == "opus" and datos["permissions"] == {"allow": ["Bash(ls)"]}
        respaldos = list((usuario / cuenta).glob("settings.json.respaldo-visualizador-*"))
        assert len(respaldos) == 1 and respaldos[0].read_bytes() == antes[cuenta]
    cfg = config.cargar(usuario / ".visualizador-monitor")
    assert cfg.token == TOKEN and cfg.servidor == "https://agents.example.test"
    assert (usuario / ".visualizador-monitor" / "comandos-peligrosos.txt").is_file()
    manifiesto = (usuario / ".visualizador-monitor" / "instalacion.json").read_text(
        encoding="utf-8"
    )
    assert TOKEN not in manifiesto


def test_desinstalar_deja_todo_como_estaba(usuario: Path, origen: Path, tmp_path: Path) -> None:
    antes = {c: (usuario / c / "settings.json").read_bytes() for c in (".claude", ".claude-demo")}
    m = _instalar(usuario, origen, tmp_path)
    r = desinstalar(inicio=usuario)
    for cuenta in (".claude", ".claude-demo"):
        assert (usuario / cuenta / "settings.json").read_bytes() == antes[cuenta]
    assert r["destino_borrado"] and not Path(m["destino"]).exists()
    assert not (usuario / ".visualizador-monitor").exists()


def test_desinstalar_con_cambios_posteriores_solo_revierte_lo_nuestro(
    usuario: Path, origen: Path, tmp_path: Path
) -> None:
    _instalar(usuario, origen, tmp_path)
    ruta = usuario / ".claude" / "settings.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["model"] = "sonnet"  # Washington cambió algo después de instalar
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    desinstalar(inicio=usuario)
    final = json.loads(ruta.read_text(encoding="utf-8"))
    assert final["model"] == "sonnet"
    assert final["hooks"] == _settings(EVENTOS)["hooks"]


def test_reinstalar_y_desinstalar_vuelve_al_original(
    usuario: Path, origen: Path, tmp_path: Path
) -> None:
    antes = (usuario / ".claude" / "settings.json").read_bytes()
    _instalar(usuario, origen, tmp_path)
    m2 = _instalar(usuario, origen, tmp_path)  # actualización
    assert len(m2["settings"]) == 2
    desinstalar(inicio=usuario)
    assert (usuario / ".claude" / "settings.json").read_bytes() == antes


def test_valida_servidor_y_token(usuario: Path, origen: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        instalar(servidor="agents.x", token=TOKEN, origen=origen, inicio=usuario, tarea=False)
    with pytest.raises(ValueError):
        instalar(servidor="https://x", token="otro", origen=origen, inicio=usuario, tarea=False)
    with pytest.raises(ValueError):  # el token no viaja sin cifrar fuera de la PC
        instalar(
            servidor="http://agents.example.test",
            token=TOKEN,
            origen=origen,
            inicio=usuario,
            tarea=False,
        )
    assert not (usuario / ".visualizador-monitor").exists()


def test_programa_del_instalador_no_muestra_el_token(
    usuario: Path, origen: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    token_archivo = tmp_path / "token.txt"
    token_archivo.write_text(TOKEN + "\n", encoding="utf-8")
    destino = tmp_path / "LocalAppData" / "VisualizadorMonitor"
    comun = ["--inicio", str(usuario), "--destino", str(destino), "--si"]
    codigo = instalador_main(
        [
            *comun,
            "--servidor",
            "https://agents.example.test",
            "--token-archivo",
            str(token_archivo),
            "--origen",
            str(origen),
            "--sin-tarea",
        ]
    )
    assert codigo == 0
    assert instalador_main([*comun, "--desinstalar"]) == 0
    salida = capsys.readouterr().out
    assert TOKEN not in salida
    assert "Monitor instalado" in salida and "desinstalado" in salida


def test_settings_ilegible_no_cambia_nada(usuario: Path, origen: Path, tmp_path: Path) -> None:
    ruta_b = usuario / ".claude-demo" / "settings.json"
    ruta_b.write_text('{\n  // comentario\n  "hooks": {}\n}', encoding="utf-8")
    antes = (usuario / ".claude" / "settings.json").read_bytes()
    with pytest.raises(ValueError):
        _instalar(usuario, origen, tmp_path)
    assert (usuario / ".claude" / "settings.json").read_bytes() == antes
    assert not list((usuario / ".claude").glob("settings.json.respaldo-*"))
    assert not (tmp_path / "LocalAppData").exists()


def test_reinstalar_tras_cambios_y_desinstalar_conserva_los_cambios(
    usuario: Path, origen: Path, tmp_path: Path
) -> None:
    _instalar(usuario, origen, tmp_path)
    ruta = usuario / ".claude" / "settings.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["model"] = "sonnet"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    # una actualización: los hooks apuntan a la versión nueva (otra carpeta)
    m2 = _instalar(usuario, origen, tmp_path)
    carpetas = [d for d in Path(m2["destino"]).glob("v*") if d.is_dir()]
    # la actual y la anterior (las sesiones abiertas todavía la usan)
    assert len(carpetas) == 2 and Path(m2["exe"]).parent in carpetas
    _instalar(usuario, origen, tmp_path)
    assert len([d for d in Path(m2["destino"]).glob("v*") if d.is_dir()]) == 2
    desinstalar(inicio=usuario)
    final = json.loads(ruta.read_text(encoding="utf-8"))
    assert final["model"] == "sonnet"
    assert final["hooks"] == _settings(EVENTOS)["hooks"]


def test_desinstalar_sin_instalacion_no_toca_nada(usuario: Path) -> None:
    r = desinstalar(inicio=usuario)
    assert r.get("sin_manifiesto") is True


def test_guion_de_arranque(tmp_path: Path) -> None:
    from visualizador_monitor.instalador import guion_arranque

    g = guion_arranque(Path("C:/Users/o'brien/m/visualizador-monitor.exe"), tmp_path / "datos")
    assert "'C:\\Users\\o''brien\\m\\visualizador-monitor.exe'" in g or "o''brien" in g
    assert "detener" in g and "arranque.pid" in g and "servir" in g


def test_dos_instalaciones_en_el_mismo_segundo_no_pisan_el_original(
    usuario: Path, origen: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con la misma hora, el respaldo de la segunda no reemplaza al original."""
    from datetime import datetime

    from visualizador_monitor import instalador as modulo

    class Fija(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def, override]
            return datetime(2026, 10, 11, 12, 0, 0, 123456)

    monkeypatch.setattr(modulo, "datetime", Fija)
    antes = (usuario / ".claude" / "settings.json").read_bytes()
    _instalar(usuario, origen, tmp_path)
    with pytest.raises(FileExistsError):  # misma carpeta de versión: no se pisa
        _instalar(usuario, origen, tmp_path)
    monkeypatch.undo()
    _instalar(usuario, origen, tmp_path)
    desinstalar(inicio=usuario)
    assert (usuario / ".claude" / "settings.json").read_bytes() == antes

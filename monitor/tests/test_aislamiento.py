"""Sesiones del equipo aisladas de la configuración de usuario (etapa 4, Prompt 41): se
lanzan sin la fuente "user" y con un archivo propio que solo trae los hooks de la oficina
de su cuenta. Con el `claude` falso."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_equipos import _encargo, _esperar, _eventos, _gestor

from visualizador_monitor.hooks_oficina import hooks_de_oficina


def _hook(comando: str, timeout: int | None = None) -> dict[str, Any]:
    h: dict[str, Any] = {"type": "command", "command": comando}
    if timeout is not None:
        h["timeout"] = timeout
    return h


def _settings(exe: str, extra: bool = True) -> dict[str, Any]:
    """Un settings.json como el de Washington: los hooks de la oficina mezclados con
    otros y cientos de reglas de permiso."""
    oficina = f'"{exe}" hook'
    s: dict[str, Any] = {
        "model": "opus",
        "hooks": {
            "PermissionRequest": [
                {"matcher": "", "hooks": [_hook("powershell -File notificar.ps1")]},
                {"matcher": ".*", "hooks": [_hook(f"{oficina} permission_request", 600)]},
            ],
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [_hook("sh otro.sh"), _hook(f"{oficina} session_start", 2)],
                }
            ],
            "Stop": [{"matcher": "", "hooks": [_hook(f"{oficina} stop", 2)]}],
        },
    }
    if extra:
        s["permissions"] = {"allow": [f"Bash(cmd{n} *)" for n in range(629)]}
    return s


def test_solo_los_hooks_de_la_oficina() -> None:
    s = _settings("C:/x/visualizador-monitor.exe")
    h = hooks_de_oficina(s)
    assert set(h) == {"PermissionRequest", "SessionStart", "Stop"}
    assert h["PermissionRequest"] == [
        {
            "matcher": ".*",
            "hooks": [_hook('"C:/x/visualizador-monitor.exe" hook permission_request', 600)],
        }
    ]
    # Del grupo mezclado queda solo la entrada de la oficina, con su matcher.
    assert h["SessionStart"] == [
        {"matcher": "", "hooks": [_hook('"C:/x/visualizador-monitor.exe" hook session_start', 2)]}
    ]
    # El original no cambia y nada más del archivo pasa (ni permisos ni modelo).
    assert len(s["hooks"]["SessionStart"][0]["hooks"]) == 2
    assert "permissions" not in h and hooks_de_oficina({}) == {}
    assert hooks_de_oficina({"hooks": {"Stop": "roto"}}) == {}


def _inicio(registro: Path, sid: str) -> dict[str, Any]:
    for e in reversed(_eventos(registro)):
        if e["evento"] != "inicio":
            continue
        a = e["args"]
        for op in ("--session-id", "--resume"):
            if op in a and a[a.index(op) + 1] == sid:
                return e
    raise AssertionError(f"no arrancó {sid}")


def test_lanzar_y_retomar_aislados_con_la_cuenta_correcta(tmp_path: Path) -> None:
    registro = tmp_path / "registro.jsonl"
    g = _gestor(tmp_path, registro)
    home = tmp_path / "home"
    (home / ".claude" / "settings.json").write_text(
        json.dumps(_settings("C:/monitor/v1/visualizador-monitor.exe")), encoding="utf-8"
    )
    (home / ".claude-demo" / "settings.json").write_text(
        json.dumps(_settings("C:/monitor/demo/visualizador-monitor.exe", extra=False)),
        encoding="utf-8",
    )
    personal = _encargo(proyecto_id="a" * 32, nombre="personal-1")
    demo = _encargo(proyecto_id="b" * 32, nombre="demo-1", cuenta="demo")
    try:
        assert g.procesar(personal)["ok"] and g.procesar(demo)["ok"]
        for enc, cuenta, exe in (
            (personal, None, "C:/monitor/v1/"),
            (demo, ".claude-demo", "C:/monitor/demo/"),
        ):
            for m in enc["equipo"]:
                e = _inicio(registro, m["session_id"])
                a = e["args"]
                assert a[a.index("--setting-sources") + 1] == "project,local"
                ajustes = json.loads(Path(a[a.index("--settings") + 1]).read_text("utf-8"))
                # Solo los hooks de la oficina de SU cuenta; nada de las reglas de permiso.
                assert set(ajustes) <= {"hooks", "crossSessionInbound"}
                comandos = [
                    h["command"]
                    for grupos in ajustes["hooks"].values()
                    for gr in grupos
                    for h in gr["hooks"]
                ]
                assert comandos and all(exe in c for c in comandos)
                assert (ajustes.get("crossSessionInbound") == "refuse") == (m["rol"] == "agente")
                # La cuenta: Demo Org con su CLAUDE_CONFIG_DIR; la personal, sin variable.
                if cuenta is None:
                    assert e["config"] is None
                else:
                    assert e["config"].endswith(cuenta)
        # El monitor se actualiza (otra ruta del exe) y el equipo se retoma: el archivo se
        # reescribe con la ruta nueva y la sesión retomada sigue sin la fuente de usuario.
        (home / ".claude" / "settings.json").write_text(
            json.dumps(_settings("C:/monitor/v2/visualizador-monitor.exe")), encoding="utf-8"
        )
        assert g.procesar(_encargo("pausar", proyecto_id="a" * 32))["ok"]
        assert g.procesar(_encargo("reanudar", proyecto_id="a" * 32))["ok"]
        orq = personal["equipo"][0]["session_id"]
        assert _esperar(lambda: "--resume" in _inicio(registro, orq)["args"])
        a = _inicio(registro, orq)["args"]
        assert a[a.index("--setting-sources") + 1] == "project,local"
        texto = Path(a[a.index("--settings") + 1]).read_text("utf-8")
        assert "C:/monitor/v2/" in texto and "C:/monitor/v1/" not in texto
    finally:
        g.detener_todo()


def test_sin_settings_de_la_cuenta_arranca_igual(tmp_path: Path) -> None:
    registro = tmp_path / "registro.jsonl"
    g = _gestor(tmp_path, registro)
    enc = _encargo(proyecto_id="c" * 32, nombre="sin-hooks")
    try:
        assert g.procesar(enc)["ok"]
        a = _inicio(registro, enc["equipo"][1]["session_id"])["args"]
        assert json.loads(Path(a[a.index("--settings") + 1]).read_text("utf-8")) == {
            "hooks": {},
            "crossSessionInbound": "refuse",
        }
    finally:
        g.detener_todo()

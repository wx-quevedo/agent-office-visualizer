"""Dangerous commands always ask for approval (claude_office_hooks/peligrosos.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_office_hooks.peligrosos import (
    cargar_patrones,
    coincidencia,
    decision_pre_tool_use,
    leer_lista,
    texto_predeterminado,
)

PATRONES = leer_lista(texto_predeterminado())


@pytest.mark.parametrize(
    "comando",
    [
        "/bin/rm -rf /tmp/x",
        "\\rm -rf build",
        '"rm" -rf build',
        "rm \\\n  -rf build",
        "Remove-Item `\n  -Recurse -Force .\\dist",
        "del -Recurse -Force .\\dist",
        "rd -r -fo carpeta",
        "rmdir -Recurse carpeta",
        "git push -uf origin main",
        "git push origin +main",
        "git clean --force -d",
        "rm -rf node_modules",
        "rm -fr build",
        "rm -Rf /tmp/x",
        "rm -r -f dist",
        "rm --recursive --force dist",
        "cd app && rm -rf .next",
        "sudo rm -rf /var/www",
        "Remove-Item -Recurse -Force .\\dist",
        "Remove-Item .\\dist -Force -Recurse",
        "remove-item -rec -fo C:\\temp\\x",
        "ri -r -fo build",
        "del /s /q *.tmp",
        "del /q /s C:\\temp",
        "erase /S archivos",
        "rd /s /q build",
        "rmdir /s build",
        "git push --force origin main",
        "git push -f",
        "git push origin main --force-with-lease",
        "git -C repo push --force",
        "git reset --hard HEAD~1",
        "git reset --hard",
        "git clean -fd",
        "git clean -fdx",
        "git clean -f -d",
        "format D: /q",
        "Format-Volume -DriveLetter E",
        "Clear-Disk -Number 1",
        "diskpart /s script.txt",
        "mkfs.ext4 /dev/sdb1",
        "dd if=imagen.iso of=/dev/sdb",
        "sqlite3 db.sqlite 'DROP TABLE users;'",
        'psql -c "drop database produccion"',
        "mysql -e 'DROP SCHEMA prueba'",
    ],
)
def test_pide_aprobacion(comando: str) -> None:
    assert coincidencia(comando, PATRONES) is not None, comando


@pytest.mark.parametrize(
    "comando",
    [
        "rm -r build",
        "rm -f archivo.txt",
        "rm archivo.txt",
        "docker run --rm -it imagen",
        "docker run --rm -f Dockerfile .",
        "grep -rf patrones.txt .",
        "npm rm paquete",
        "git rm --cached archivo",
        "git push origin main",
        "git push --set-upstream origin rama",
        "git reset --soft HEAD~1",
        "git reset HEAD archivo",
        "git clean -n",
        "git clean -f",
        "npm run format",
        "prettier --write .",
        "Get-ChildItem | Format-Table",
        "Remove-Item -Recurse .\\dist",
        "Remove-Item -Force archivo.txt",
        "Remove-Item -Recurse -Filter *.log .\\logs",
        "del archivo.txt",
        "rd carpeta",
        "echo dropdown",
        "SELECT * FROM tabla WHERE drop_count > 1",
        "echo 'drop the table later'",
        "ls -la",
        "python -m pytest -q",
        "git status",
    ],
)
def test_no_pide_aprobacion(comando: str) -> None:
    assert coincidencia(comando, PATRONES) is None, comando


def test_decision_ask_solo_para_bash_y_powershell() -> None:
    d = decision_pre_tool_use(
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}, PATRONES
    )
    assert d is not None
    salida = d["hookSpecificOutput"]
    assert salida["hookEventName"] == "PreToolUse"
    assert salida["permissionDecision"] == "ask"
    assert "rm recursivo y forzado" in salida["permissionDecisionReason"]
    assert decision_pre_tool_use(
        {"tool_name": "PowerShell", "tool_input": {"command": "Remove-Item -Recurse -Force x"}},
        PATRONES,
    )
    assert (
        decision_pre_tool_use(
            {"tool_name": "Write", "tool_input": {"file_path": "rm -rf.txt"}}, PATRONES
        )
        is None
    )
    assert decision_pre_tool_use({"tool_name": "Bash", "tool_input": {}}, PATRONES) is None
    assert decision_pre_tool_use({"tool_name": "Bash", "tool_input": "x"}, PATRONES) is None


def test_lista_editable(tmp_path: Path) -> None:
    lista = tmp_path / "comandos-peligrosos.txt"
    lista.write_text(
        "# comentario\n"
        "\\bvercel\\b[^;&|\\n]*--prod\\b ## despliegue a producción en Vercel\n"
        "([inválida ## esta línea se ignora\n",
        encoding="utf-8",
    )
    patrones = cargar_patrones(lista)
    assert len(patrones) == 1
    assert coincidencia("vercel deploy --prod", patrones) == "despliegue a producción en Vercel"
    assert coincidencia("vercel deploy", patrones) is None
    # with this file, rm -rf is no longer in the list (it replaces the defaults)
    assert coincidencia("rm -rf x", patrones) is None


def test_sin_archivo_usa_la_lista_por_defecto(tmp_path: Path) -> None:
    patrones = cargar_patrones(tmp_path / "no-existe.txt")
    assert coincidencia("git reset --hard", patrones) == "git reset --hard"


def test_el_texto_por_defecto_trae_los_despliegues_comentados() -> None:
    texto = texto_predeterminado()
    assert "# \\bvercel" in texto
    assert len(leer_lista(texto)) == len(PATRONES)


def test_proceso_del_hook_pide_aprobacion(tmp_path: Path) -> None:
    """The hook process prints the "ask" decision on PreToolUse (backend off: still answers)."""
    lista = tmp_path / "lista.txt"
    lista.write_text(texto_predeterminado(), encoding="utf-8")
    env = {
        **os.environ,
        "CLAUDE_OFFICE_API_URL": "http://127.0.0.1:9/api/v1/events",
        "CLAUDE_OFFICE_EXTRA_API_URLS": "",
        "CLAUDE_OFFICE_PELIGROSOS": str(lista),
        "USERPROFILE": str(tmp_path),
        "HOME": str(tmp_path),
    }
    entrada = {
        "session_id": "prueba-peligroso",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push --force origin main"},
        "permission_mode": "auto",
    }
    r = subprocess.run(
        [sys.executable, "-m", "claude_office_hooks.main", "pre_tool_use"],
        input=json.dumps(entrada),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert r.returncode == 0 and r.stderr == ""
    salida = json.loads(r.stdout)["hookSpecificOutput"]
    assert salida["permissionDecision"] == "ask"
    entrada["tool_input"] = {"command": "git status"}
    r = subprocess.run(
        [sys.executable, "-m", "claude_office_hooks.main", "pre_tool_use"],
        input=json.dumps(entrada),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert r.stdout == ""


def test_comando_muy_largo_pide_aprobacion_sin_trabarse() -> None:
    import time

    patrones = cargar_patrones(None)
    t0 = time.monotonic()
    assert coincidencia("git " * 30_000, patrones) is not None  # 120 KB: pide sin revisar
    for relleno in ("git x ", "rm x ", "git -C x ", "del x "):
        largo = "echo " + relleno * (90_000 // len(relleno))  # 90 KB: se revisa entero
        assert coincidencia(largo, patrones) is None
    assert time.monotonic() - t0 < 3

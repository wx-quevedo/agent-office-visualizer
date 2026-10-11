"""Dangerous commands always ask for approval (stage 1.2).

On PreToolUse of Bash or PowerShell, when the command matches the list, the
hook answers with the decision "ask" of the hooks reference
(https://code.claude.com/docs/en/hooks#pretooluse-decision-control):

    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": "..."}}

so Claude Code shows its permission dialog even in Auto mode.

The list is a text file (one regular expression per line, case-insensitive,
``#`` starts a comment; an optional description after `` ## ``). Default
path: ``~/.visualizador-monitor/comandos-peligrosos.txt`` (or
CLAUDE_OFFICE_PELIGROSOS). Without the file, the built-in list below is used.
An invalid line is skipped; it never breaks the hook.

IMPORTANT: this module must not write to stdout/stderr itself.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, cast

# One command segment: up to a separator (;, &, |, new line), at most 400
# characters (the flags go right after the command; and so a long command with
# many "rm" or "del" is checked in linear time).
_SEG = r"[^;&|\n]{0,400}"
# Start of a command: line start, whitespace, separators, a parenthesis, a path
# (/bin/rm, C:\tools\rm) or a quote / escape ("rm", \rm).
_INICIO = r"(?:^|[\s;&|(`/\\\"'])"
_COMILLA = r"[\"']"

# git and its global options (-C repo, -c clave=valor, --no-pager...) before the
# subcommand. Only options: a long command full of "git" is checked in linear time.
_GIT = r"\bgit(?:\s+-[\w.-]+(?:=\S*|\s+(?!-)[^\s;&|]+)?)*\s+"

# (regex, description). Recursive and forced deletes need BOTH flags.
PREDETERMINADOS: list[tuple[str, str]] = [
    (
        rf"{_INICIO}rm{_COMILLA}?(?=\s)(?={_SEG}\s-(?:[a-z]*r[a-z]*|-recursive)\b)"
        rf"(?={_SEG}\s-(?:[a-z]*f[a-z]*|-force)\b)",
        "rm recursivo y forzado",
    ),
    (
        r"\b(?:remove-item|ri)\b(?=[^;|\n]{0,400}\s-r(?:e(?:c(?:u(?:r(?:s(?:e)?)?)?)?)?)?\b)"
        r"(?=[^;|\n]{0,400}\s-fo(?:r(?:c(?:e)?)?)?\b)",
        "Remove-Item -Recurse -Force",
    ),
    (rf"{_INICIO}(?:del|erase)\s{_SEG}/s\b", "del /s"),
    (rf"{_INICIO}(?:rd|rmdir)\s{_SEG}/s\b", "rd /s"),
    # PowerShell aliases of Remove-Item (del, erase, rd, rmdir, rm) with -Recurse
    (
        rf"{_INICIO}(?:del|erase|rd|rmdir)(?=\s)"
        rf"(?={_SEG}\s-r(?:e(?:c(?:u(?:r(?:s(?:e)?)?)?)?)?)?\b)",
        "borrado recursivo (alias de Remove-Item)",
    ),
    (
        rf"{_GIT}push\b{_SEG}\s(?:--force(?:-with-lease)?\b|-[a-z]*f[a-z]*\b|\+\S)",
        "git push --force",
    ),
    (rf"{_GIT}reset\b{_SEG}\s--hard\b", "git reset --hard"),
    (
        rf"{_GIT}clean\b(?={_SEG}\s(?:-[a-z]*f|--force\b))"
        rf"(?={_SEG}\s-[a-z]*[dx])",
        "git clean -fd",
    ),
    (rf"{_INICIO}format(?:\.com)?\s+[a-z]:", "formatear un disco"),
    (r"\b(?:format-volume|clear-disk|initialize-disk)\b", "formatear un disco"),
    (r"\bdiskpart\b", "diskpart"),
    (r"\bmkfs(?:\.\w+)?\b", "formatear un disco"),
    (rf"\bdd\s{_SEG}\bof=/dev/", "dd sobre un disco"),
    (r"\bdrop\s+(?:database|schema|table)\b", "DROP DATABASE / DROP TABLE"),
]

# Text of the default file (the installer writes it; Washington edits it).
ENCABEZADO = """# Comandos que siempre piden aprobación, aunque Claude Code esté en modo Auto.
# Una expresión regular por línea (sin distinguir mayúsculas). "#" al inicio: comentario.
# Opcional: " ## descripción" al final de la línea, la ve Claude como motivo.
# Despliegues a producción: quita el "#" de los que uses o agrega los tuyos, por ejemplo:
# \\bvercel\\b[^;&|\\n]*--prod\\b ## despliegue a producción en Vercel
# \\bfirebase\\s+deploy\\b ## despliegue a producción en Firebase
# \\bnpm\\s+run\\s+deploy:prod\\b ## despliegue a producción
"""


def texto_predeterminado() -> str:
    lineas = [ENCABEZADO]
    for regex, descripcion in PREDETERMINADOS:
        lineas.append(f"{regex} ## {descripcion}")
    return "\n".join(lineas) + "\n"


def ruta_lista() -> Path:
    raw = os.environ.get("CLAUDE_OFFICE_PELIGROSOS", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".visualizador-monitor" / "comandos-peligrosos.txt"


def leer_lista(texto: str) -> list[tuple[re.Pattern[str], str]]:
    """Compiled patterns of a list file; invalid lines are skipped."""
    patrones: list[tuple[re.Pattern[str], str]] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        regex, _, descripcion = linea.partition(" ## ")
        try:
            patrones.append((re.compile(regex.strip(), re.IGNORECASE), descripcion.strip()))
        except re.error:
            continue
    return patrones


def cargar_patrones(ruta: Path | None = None) -> list[tuple[re.Pattern[str], str]]:
    """Patterns of the list file, or the built-in list without a readable file."""
    try:
        ruta = ruta or ruta_lista()
        if ruta.is_file():
            patrones = leer_lista(ruta.read_text(encoding="utf-8"))
            if patrones:
                return patrones
    except Exception:
        pass
    return leer_lista(texto_predeterminado())


# Longer commands are not scanned (the patterns are not linear): they always ask.
MAX_COMANDO = 100_000
_CONTINUACION = re.compile(r"(?:\\|`)\r?\n")


def coincidencia(comando: str, patrones: list[tuple[re.Pattern[str], str]]) -> str | None:
    """Description (or regex) of the first dangerous pattern in the command, or None.

    Line continuations (``\\`` in bash, a backtick in PowerShell) are joined first.
    Limit: a script written to a file and run later (``bash x.sh``) is not seen."""
    if len(comando) > MAX_COMANDO:
        return "comando demasiado largo para revisarlo"
    comando = _CONTINUACION.sub(" ", comando)
    for patron, descripcion in patrones:
        if patron.search(comando):
            return descripcion or patron.pattern
    return None


def decision_pre_tool_use(
    raw_data: dict[str, Any], patrones: list[tuple[re.Pattern[str], str]] | None = None
) -> dict[str, Any] | None:
    """The "ask" decision for a dangerous Bash/PowerShell command, or None."""
    try:
        herramienta = str(raw_data.get("tool_name") or "")
        if herramienta.lower() not in ("bash", "powershell"):
            return None
        entrada = raw_data.get("tool_input")
        comando = (
            cast(dict[str, Any], entrada).get("command") if isinstance(entrada, dict) else None
        )
        if not isinstance(comando, str) or not comando.strip():
            return None
        motivo = coincidencia(comando, patrones if patrones is not None else cargar_patrones())
        if motivo is None:
            return None
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"Comando peligroso ({motivo}): pide aprobación aunque la sesión esté "
                    "en modo Auto."
                ),
            }
        }
    except Exception:
        return None

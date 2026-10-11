"""Barra de estado de Claude Code (etapa 2.1): la única fuente documentada de
los límites de la suscripción.

Claude Code ejecuta el comando ``statusLine`` de cada cuenta y le pasa por la
entrada estándar un JSON con, entre otros, ``rate_limits.five_hour`` y
``rate_limits.seven_day`` (``used_percentage`` de 0 a 100 y ``resets_at`` en
segundos Unix). Solo aparece en suscripciones Pro y Max y después de la primera
respuesta de la sesión; cada ventana puede faltar
(https://code.claude.com/docs/en/statusline).

``"<monitor>" statusline`` lee ese JSON, le pasa al monitor la cuenta (carpeta
``.claude`` o ``.claude-*``), las dos ventanas y el modelo, y escribe una línea
corta para la barra: ``Opus · 5 h: 23 % (15:45) · semana: 41 % (lun 00:00)``.
Nunca falla: sin datos, escribe solo el modelo.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from typing import Any, cast

_DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def cuenta_dir(datos: dict[str, Any], entorno: dict[str, str] | None = None) -> str | None:
    """Carpeta de la cuenta: CLAUDE_CONFIG_DIR o la ``.claude*`` de la transcripción."""
    entorno = dict(os.environ) if entorno is None else entorno
    config = entorno.get("CLAUDE_CONFIG_DIR", "").strip()
    if config:
        return config.rstrip("/\\")
    ruta = datos.get("transcript_path")
    if not isinstance(ruta, str) or not ruta:
        return None
    partes = ruta.replace("\\", "/").split("/")
    for i, p in enumerate(partes):
        if re.fullmatch(r"\.claude(?:-[\w.-]+)?", p, re.IGNORECASE):
            return "/".join(partes[: i + 1])
    return None


def _ventana(crudo: object) -> dict[str, Any] | None:
    if not isinstance(crudo, dict):
        return None
    v = cast(dict[str, Any], crudo)
    usado = v.get("used_percentage")
    reinicia = v.get("resets_at")
    out: dict[str, Any] = {}
    if isinstance(usado, (int, float)) and 0 <= usado <= 100:
        out["usado_pct"] = round(float(usado), 1)
    if isinstance(reinicia, (int, float)) and reinicia > 0:
        out["reinicia"] = datetime.fromtimestamp(float(reinicia), UTC).isoformat()
    return out or None


def extraer(datos: dict[str, Any], entorno: dict[str, str] | None = None) -> dict[str, Any]:
    """Lo que se le pasa al monitor (sin textos de la conversación)."""
    limites = datos.get("rate_limits")
    lim = cast(dict[str, Any], limites) if isinstance(limites, dict) else {}
    modelo = datos.get("model")
    nombre_modelo = (
        cast(dict[str, Any], modelo).get("display_name") or cast(dict[str, Any], modelo).get("id")
        if isinstance(modelo, dict)
        else None
    )
    return {
        "cuenta_dir": cuenta_dir(datos, entorno),
        "cinco_horas": _ventana(lim.get("five_hour")),
        "semanal": _ventana(lim.get("seven_day")),
        "modelo": str(nombre_modelo)[:100] if nombre_modelo else None,
        "visto": datetime.now(UTC).isoformat(),
    }


def _hora(iso: str, semanal: bool) -> str:
    ts = datetime.fromisoformat(iso).astimezone()
    return f"{_DIAS[ts.weekday()]} {ts:%H:%M}" if semanal else f"{ts:%H:%M}"


def linea(extraido: dict[str, Any]) -> str:
    """La línea de la barra de estado."""
    partes: list[str] = []
    if extraido.get("modelo"):
        partes.append(str(extraido["modelo"]))
    for clave, nombre, semanal in (("cinco_horas", "5 h", False), ("semanal", "semana", True)):
        v = extraido.get(clave)
        if isinstance(v, dict) and "usado_pct" in v:
            texto = f"{nombre}: {cast(dict[str, Any], v)['usado_pct']:g} %"
            if v.get("reinicia"):
                texto += f" ({_hora(str(v['reinicia']), semanal)})"
            partes.append(texto)
    return " · ".join(partes) or "Oficina de agentes"

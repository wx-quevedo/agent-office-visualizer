"""Permission requests answered from the office (PermissionRequest hook).

The hook registers the request in the visualizer backend and, when the
backend says so (policy and presence), waits for a decision taken in the
office with a long-poll. The answer printed on stdout follows the hooks
reference of Claude Code (https://code.claude.com/docs/en/hooks#permissionrequest-decision-control):

    {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                            "decision": {"behavior": "allow"}}}
    {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                            "decision": {"behavior": "deny", "message": "..."}}}

Without a decision nothing is printed and Claude Code goes on with its normal
permission dialog. Every error (backend down, slow, unknown answer) ends in
"no decision": this must never hang or block Claude Code.

Pure logic with the HTTP calls injected, tested in tests/test_permisos.py.
IMPORTANT: this module must not write to stdout/stderr itself.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any, cast

# Answer of the backend when registering (seconds to wait at most).
POST_TIMEOUT = 2.0
# Longest single long-poll; the backend caps it at 25 s too.
LONG_POLL = 20.0
# Margin over a long-poll before the request is given up (slow backend).
MARGEN_GET = 2.5
# Hard limit of the whole wait, below the hook timeout registered in
# settings.json (600 s by default for command hooks).
ESPERA_MAXIMA = 540.0
MAX_TEXTO = 4000

PostJson = Callable[[str, dict[str, Any], float], dict[str, Any] | None]
GetJson = Callable[[str, float], dict[str, Any] | None]


def base_permisos(api_url: str) -> str:
    """http://127.0.0.1:8000/api/v1/events -> http://127.0.0.1:8000/api/v1/permisos"""
    url = api_url.rstrip("/")
    if url.endswith("/events"):
        url = url[: -len("/events")]
    return url + "/permisos"


def cuenta_de(transcript_path: str | None) -> str:
    """Account of the session from its transcript folder (.claude-demo = Demo Org)."""
    return "demo" if transcript_path and ".claude-demo" in transcript_path else "personal"


def _recortar(entrada: Any) -> dict[str, Any]:
    """Tool input without huge texts (a Write content can be megabytes)."""
    if not isinstance(entrada, dict):
        return {}
    out: dict[str, Any] = {}
    items = cast(dict[Any, Any], entrada).items()
    for k, v in items:
        if isinstance(v, str) and len(v) > MAX_TEXTO:
            v = v[:MAX_TEXTO] + "…"
        elif not isinstance(v, (str, int, float, bool, type(None))):
            v = str(v)[:MAX_TEXTO]
        out[str(k)[:64]] = v
    return out


def salida_permitir() -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "allow"},
        }
    }


def salida_rechazar(motivo: str | None) -> dict[str, Any]:
    mensaje = "El usuario rechazó este permiso desde la oficina."
    if motivo:
        mensaje += f" Motivo: {motivo}"
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "deny", "message": mensaje},
        }
    }


def pedir_decision(
    raw_data: dict[str, Any],
    payload: dict[str, Any],
    api_url: str,
    post_json: PostJson,
    get_json: GetJson,
    reloj: Callable[[], float] = time.monotonic,
    espera_maxima: float = ESPERA_MAXIMA,
    dormir: Callable[[float], None] = time.sleep,
) -> dict[str, Any] | None:
    """Register the request and wait for the office; the hook output, or None."""
    try:
        inicio = reloj()
        base = base_permisos(api_url)
        id_ = uuid.uuid4().hex
        data = cast(dict[str, Any], payload.get("data") or {})
        nombre = data.get("project_name")
        proyecto = str(nombre)[:256] if nombre else None
        registro = post_json(
            f"{base}/solicitudes",
            {
                "id": id_,
                "session_id": str(payload.get("session_id") or "")[:128],
                "herramienta": str(raw_data.get("tool_name") or "desconocida")[:128],
                "entrada": _recortar(raw_data.get("tool_input")),
                "cuenta": cuenta_de(raw_data.get("transcript_path")),
                "proyecto": proyecto,
            },
            POST_TIMEOUT,
        )
        if not registro or not registro.get("esperar"):
            return None
        restante = float(registro.get("segundos_restantes") or 0)
        limite = inicio + min(restante, espera_maxima)
        while True:
            queda = limite - reloj()
            if queda < 0.5:
                return None
            pedir = min(LONG_POLL, queda)
            t0 = reloj()
            s = get_json(f"{base}/solicitudes/{id_}?espera={pedir:.1f}", pedir + MARGEN_GET)
            if not s:
                return None  # backend down or too slow
            estado = s.get("estado")
            if estado == "aprobada":
                return salida_permitir()
            if estado == "rechazada":
                motivo = s.get("motivo")
                return salida_rechazar(motivo if isinstance(motivo, str) else None)
            if estado != "pendiente":
                return None  # expired or answered in VS Code
            if reloj() - t0 < 1.0:
                dormir(1.0)  # a backend that does not hold the long-poll: do not hammer it
    except Exception:
        return None

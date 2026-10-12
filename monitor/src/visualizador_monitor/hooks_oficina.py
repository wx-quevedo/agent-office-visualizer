"""Los hooks de la oficina dentro de un settings.json de Claude Code.

El instalador los reconoce para actualizarlos o quitarlos, y los equipos (etapa 4) los
copian a la configuración propia de cada sesión que lanzan: esas sesiones no cargan la
configuración de usuario (sus reglas de permiso, sus otros hooks, su modelo), pero la
oficina las tiene que seguir viendo.
"""

from __future__ import annotations

import copy
from typing import Any

MARCA = "claude-office-hook"


def evento_de(comando: str) -> str | None:
    """El evento de una entrada nuestra: claude-office-hook <evento> o, de una
    instalación anterior, "<...>/visualizador-monitor.exe" hook <evento>."""
    partes = comando.split()
    for n, crudo in enumerate(partes):
        p = crudo.strip("\"'").removesuffix(".exe").removesuffix(".EXE")
        if p.endswith(MARCA) and n + 1 < len(partes):
            return partes[n + 1]
        if p.endswith("visualizador-monitor") and n + 2 < len(partes) and partes[n + 1] == "hook":
            return partes[n + 2]
    return None


def hooks_de_oficina(settings: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Solo los hooks de la oficina de un settings.json, con su matcher y su timeout
    tal como los dejó el instalador. Los demás hooks del usuario quedan fuera."""
    salida: dict[str, list[dict[str, Any]]] = {}
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return salida
    for tipo, grupos in hooks.items():
        if not isinstance(grupos, list):
            continue
        for grupo in grupos:
            if not isinstance(grupo, dict) or not isinstance(grupo.get("hooks"), list):
                continue
            propios = [
                copy.deepcopy(h)
                for h in grupo["hooks"]
                if isinstance(h, dict) and evento_de(str(h.get("command", ""))) is not None
            ]
            if propios:
                nuevo = {k: copy.deepcopy(v) for k, v in grupo.items() if k != "hooks"}
                nuevo["hooks"] = propios
                salida.setdefault(str(tipo), []).append(nuevo)
    return salida

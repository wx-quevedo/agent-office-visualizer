"""Sube a 600 s el tiempo límite del hook PermissionRequest de la oficina.

Para que la oficina pueda aprobar o rechazar permisos, el hook
``claude-office-hook permission_request`` debe poder esperar la decisión
(hasta 540 s). Claude Code lo corta en el ``timeout`` de settings.json, que la
instalación dejó en 2 s. Este script:

1. copia settings.json a settings.json.respaldo-AAAAMMDD-HHMMSS,
2. cambia solo el ``timeout`` de esa entrada a 600 (nada más),
3. muestra lo que cambió. Con --probar no escribe nada.

Uso (lo ejecuta Washington; una vez por cuenta):

    uv run --no-project python scripts/permisos/ajustar_timeout_permiso.py %USERPROFILE%/.claude/settings.json
    uv run --no-project python scripts/permisos/ajustar_timeout_permiso.py %USERPROFILE%/.claude-demo/settings.json

Para volver atrás: copiar el respaldo sobre settings.json.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

COMANDO = "claude-office-hook permission_request"
TIMEOUT = 600


def ajustar(settings: dict) -> list[str]:
    cambios: list[str] = []
    for grupo in settings.get("hooks", {}).get("PermissionRequest", []):
        for h in grupo.get("hooks", []):
            if COMANDO in str(h.get("command", "")) and h.get("timeout") != TIMEOUT:
                cambios.append(f"{h.get('command')}: timeout {h.get('timeout')} -> {TIMEOUT}")
                h["timeout"] = TIMEOUT
    return cambios


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--probar"]
    probar = "--probar" in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 2
    ruta = Path(args[0])
    texto = ruta.read_text(encoding="utf-8")
    settings = json.loads(texto)
    cambios = ajustar(settings)
    if not cambios:
        print(f"{ruta}: no hay nada que cambiar (no está el hook o ya tiene {TIMEOUT} s).")
        return 0
    for c in cambios:
        print(f"{ruta}: {c}")
    if probar:
        print("Prueba: no se escribió nada.")
        return 0
    respaldo = ruta.with_name(f"{ruta.name}.respaldo-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(ruta, respaldo)
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, ruta)
    print(f"Respaldo: {respaldo}")
    print("Listo. Reinicia las sesiones de Claude Code para que tomen el cambio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

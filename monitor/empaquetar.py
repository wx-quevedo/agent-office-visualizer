"""Arma el instalador de Windows del monitor (no depende del entorno de desarrollo).

    cd monitor
    uv run python empaquetar.py

1. ``dist/visualizador-monitor/`` (PyInstaller, carpeta): el monitor con Python
   incluido. En carpeta y no en un solo archivo para que cada hook arranque
   rápido (un solo archivo se descomprime en cada llamada).
2. ``build/monitor.zip``: esa carpeta comprimida.
3. ``dist/instalar-visualizador-monitor.exe`` (un solo archivo): el instalador,
   con ``monitor.zip`` adentro.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PAQUETE = RAIZ / "src" / "visualizador_monitor"
DIST = RAIZ / "dist"
BUILD = RAIZ / "build"


def _pyinstaller(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *args],
        cwd=RAIZ,
        check=True,
    )


def main() -> int:
    shutil.rmtree(DIST / "visualizador-monitor", ignore_errors=True)
    _pyinstaller(
        "--name",
        "visualizador-monitor",
        "--console",
        "--onedir",
        "--collect-submodules",
        "claude_office_hooks",
        "--collect-submodules",
        "visualizador_monitor",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD / "monitor"),
        "--specpath",
        str(BUILD),
        str(PAQUETE / "__main__.py"),
    )
    carpeta = DIST / "visualizador-monitor"
    zip_ruta = BUILD / "monitor.zip"
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(carpeta.rglob("*")):
            if f.is_file():
                z.write(f, Path("visualizador-monitor") / f.relative_to(carpeta))
    _pyinstaller(
        "--name",
        "instalar-visualizador-monitor",
        "--console",
        "--onefile",
        "--collect-submodules",
        "claude_office_hooks",
        "--collect-submodules",
        "visualizador_monitor",
        "--add-data",
        f"{zip_ruta};.",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD / "instalador"),
        "--specpath",
        str(BUILD),
        str(PAQUETE / "instalador_main.py"),
    )
    exe = DIST / "instalar-visualizador-monitor.exe"
    print(f"Instalador: {exe} ({exe.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

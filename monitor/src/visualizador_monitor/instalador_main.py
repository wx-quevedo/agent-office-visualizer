"""Instalador del monitor para Windows (entrada del .exe empaquetado).

    instalar-visualizador-monitor.exe                 # instala (pide servidor y token)
    instalar-visualizador-monitor.exe --desinstalar   # deja todo como estaba

Opciones para pruebas (no tocan la configuración real): --inicio (carpeta de
usuario simulada), --destino, --sin-tarea, --servidor, --token-archivo.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import sys
import tempfile
import zipfile
from pathlib import Path

from visualizador_monitor import config
from visualizador_monitor.cli import NOMBRE_TAREA
from visualizador_monitor.instalador import desinstalar, destino_por_defecto, instalar


def _origen_empaquetado(tmp: Path) -> Path:
    """La carpeta del monitor que viaja dentro del instalador (monitor.zip)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    zip_ruta = base / "monitor.zip"
    if not zip_ruta.is_file():
        raise SystemExit("Este instalador no trae el monitor empaquetado (monitor.zip).")
    with zipfile.ZipFile(zip_ruta) as z:
        z.extractall(tmp)
    return tmp / "visualizador-monitor"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="instalar-visualizador-monitor")
    p.add_argument("--desinstalar", action="store_true")
    p.add_argument("--servidor")
    p.add_argument("--token-archivo", help="archivo con el token (si no, se pide sin eco)")
    p.add_argument("--puerto", type=int, default=config.PUERTO_POR_DEFECTO)
    p.add_argument("--inicio", type=Path, help="carpeta de usuario (pruebas)")
    p.add_argument("--destino", type=Path, help="carpeta de instalación")
    p.add_argument("--origen", type=Path, help="carpeta del monitor ya empaquetado (pruebas)")
    p.add_argument("--sin-tarea", action="store_true", help="no registra el arranque (pruebas)")
    p.add_argument("--nombre-tarea", default=NOMBRE_TAREA, help=argparse.SUPPRESS)
    p.add_argument("--conservar-datos", action="store_true")
    p.add_argument("--si", action="store_true", help="no pide confirmación")
    a = p.parse_args(argv)
    inicio = a.inicio or Path.home()
    destino = a.destino or destino_por_defecto()

    print("Monitor de máquina de la oficina de agentes")
    if a.desinstalar:
        if (
            not a.si
            and input("¿Desinstalar y dejar todo como estaba? (s/n): ").strip().lower() != "s"
        ):
            print("No se cambió nada.")
            return 1
        r = desinstalar(destino=a.destino, inicio=inicio, conservar_datos=a.conservar_datos)
        if r.get("sin_manifiesto"):
            print("No hay una instalación registrada en esta cuenta; no se cambió nada.")
            return 1
        if r.get("pendientes_sin_enviar"):
            print(f"  Aviso: quedaron {r['pendientes_sin_enviar']} eventos sin enviar al servidor.")
        for x in r["revertidos"]:
            print(f"  Hooks restaurados en {x['ruta']} ({x['entradas']} entradas)")
        print("Listo: monitor desinstalado.")
        return 0

    servidor = (
        a.servidor or input("Dirección del servidor (https://agents.example.com): ")
    ).strip()
    servidor = servidor or "https://agents.example.com"
    if a.token_archivo:
        token = Path(a.token_archivo).read_text(encoding="utf-8").strip()
    else:
        token = getpass.getpass("Token de esta máquina (vam_..., no se muestra): ").strip()
    cuentas = config.cuentas_detectadas(inicio)
    print("Cuentas de Claude Code encontradas:")
    for c in cuentas:
        print(f"  {c}")
    if not cuentas:
        print("  (ninguna: el monitor se instala igual y no cambia hooks)")
    if not a.si and input("¿Instalar? (s/n): ").strip().lower() != "s":
        print("No se cambió nada.")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        origen = a.origen or _origen_empaquetado(Path(tmp))
        try:
            m = instalar(
                servidor=servidor,
                token=token,
                origen=origen,
                destino=destino,
                inicio=inicio,
                puerto=a.puerto,
                tarea=not a.sin_tarea,
                nombre_tarea=a.nombre_tarea,
            )
        except ValueError as e:
            print(f"No se instaló: {e}")
            return 2
    print(f"Monitor instalado en {m['destino']}")
    for ajuste in m["settings"]:
        print(
            f"  Hooks de {ajuste['ruta']}: {len(ajuste['cambios'])} entradas"
            f" (respaldo {ajuste['respaldo']})"
        )
    print(
        "  Arranque automático: " + ("registrado y en marcha" if m["tarea"] else m["tarea_detalle"])
    )
    print(f'Estado: "{m["exe"]}" estado')
    return 0


if __name__ == "__main__":
    # Con doble clic (sin argumentos) la ventana espera Enter antes de cerrarse.
    pausa = getattr(sys, "frozen", False) and len(sys.argv) == 1
    try:
        codigo = main()
    finally:
        if pausa:
            with contextlib.suppress(EOFError):
                input("Presiona Enter para cerrar...")
    sys.exit(codigo)

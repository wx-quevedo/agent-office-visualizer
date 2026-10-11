"""Comandos del monitor.

    visualizador-monitor servir              # el monitor (lo arranca la tarea programada)
    visualizador-monitor estado              # conexión, cola, último envío, cuentas
    visualizador-monitor registro [-n 50]    # últimas líneas del registro de errores
    visualizador-monitor reiniciar           # detiene y vuelve a arrancar el monitor
    visualizador-monitor configurar --servidor URL [--token-archivo F]
    visualizador-monitor peligrosos          # ruta de la lista de comandos peligrosos
    visualizador-monitor hook <evento>       # lo usan los hooks de Claude Code
    visualizador-monitor statusline          # barra de estado de Claude Code (límites)

El token nunca se muestra: se pide sin eco o se lee de un archivo.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import signal
import subprocess
import sys
import urllib.request
from pathlib import Path

from visualizador_monitor import VERSION, config
from visualizador_monitor.cola import Cola
from visualizador_monitor.registro import configurar as configurar_registro
from visualizador_monitor.registro import ruta_registro

NOMBRE_TAREA = "Visualizador monitor"


def _hook(evento: str) -> int:
    """Corre el hook de Claude Code apuntando a este monitor (sin token: lo tiene el monitor)."""
    base = config.directorio()
    try:
        cfg = config.cargar(base)
        puerto = cfg.puerto
    except Exception:
        puerto = config.PUERTO_POR_DEFECTO
    os.environ["CLAUDE_OFFICE_API_URL"] = f"http://127.0.0.1:{puerto}/api/v1/events"
    os.environ["CLAUDE_OFFICE_EXTRA_API_URLS"] = ""
    os.environ["CLAUDE_OFFICE_PRINCIPAL"] = "visualizador"
    os.environ["CLAUDE_OFFICE_TOKEN_MAQUINA"] = ""
    try:
        os.environ["CLAUDE_OFFICE_API_KEY"] = config.clave_local(base)  # la exige el monitor
    except OSError:
        os.environ["CLAUDE_OFFICE_API_KEY"] = ""
    os.environ.setdefault("CLAUDE_OFFICE_PELIGROSOS", str(base / "comandos-peligrosos.txt"))
    sys.argv = ["claude-office-hook", evento]
    try:
        from claude_office_hooks import main as hook_main

        hook_main.main()  # type: ignore[attr-defined]
    except SystemExit:
        pass
    except Exception:
        pass
    return 0  # un hook nunca bloquea a Claude Code


def _statusline() -> int:
    """Barra de estado de Claude Code: pasa los límites al monitor y escribe una línea."""
    from visualizador_monitor.barra import extraer, linea

    texto = "Oficina de agentes"
    try:
        crudo = sys.stdin.buffer.read(1_000_000) if sys.stdin else b""
        datos = json.loads(crudo.decode("utf-8", errors="replace") or "{}")
        if isinstance(datos, dict):
            extraido = extraer(datos)
            texto = linea(extraido)
            if extraido["cinco_horas"] or extraido["semanal"]:
                base = config.directorio()
                try:
                    puerto = config.cargar(base).puerto
                except Exception:
                    puerto = config.PUERTO_POR_DEFECTO
                req = urllib.request.Request(
                    f"http://127.0.0.1:{puerto}/api/v1/limites",
                    data=json.dumps(extraido).encode("utf-8"),
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": config.clave_local(base),
                    },
                )
                with urllib.request.urlopen(req, timeout=0.8):
                    pass
    except Exception:
        pass  # la barra nunca falla: sin monitor, solo se ve la línea
    try:
        # UTF-8 aunque la consola de Windows use otra página de códigos.
        sys.stdout.buffer.write((texto + "\n").encode("utf-8"))
        sys.stdout.flush()
    except Exception:
        pass
    return 0


def _servir(_: argparse.Namespace) -> int:
    from visualizador_monitor.app import Monitor
    from visualizador_monitor.registro import logger

    base = config.directorio()
    try:
        cfg = config.cargar(base)
    except (OSError, ValueError, TypeError) as e:
        configurar_registro(base)
        logger.error("No se pudo leer la configuración (%s)", type(e).__name__)
        print(f"No se pudo leer {config.ruta_config(base)}: revísala o vuelve a configurar.")
        return 2
    configurar_registro(base, cfg.token)

    if not cfg.servidor or not cfg.token:
        logger.error("Falta configurar el servidor o el token (visualizador-monitor configurar)")
        print("Falta configurar el servidor o el token: visualizador-monitor configurar")
        return 2
    monitor = Monitor(cfg, base)
    try:
        monitor.iniciar()
    except OSError as e:
        logger.error("No se pudo abrir 127.0.0.1:%s (%s): ¿ya corre otro monitor?", cfg.puerto, e)
        print(f"No se pudo abrir 127.0.0.1:{cfg.puerto}: ¿ya corre otro monitor?")
        return 3
    signal.signal(signal.SIGTERM, lambda *_: monitor.detener())
    try:
        monitor.bucle()
    except KeyboardInterrupt:
        pass
    finally:
        monitor.detener()
        logger.info("Monitor detenido")
    return 0


def _estado(_: argparse.Namespace) -> int:
    base = config.directorio()
    cfg = config.cargar(base)
    print(f"Monitor de máquina {VERSION}")
    print(f"  Configuración: {config.ruta_config(base)}")
    print(f"  Servidor:      {cfg.url_servidor or '(sin configurar)'}")
    print(f"  Token:         {'configurado' if cfg.token else 'falta'}")
    print(f"  Puerto local:  127.0.0.1:{cfg.puerto}")
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{cfg.puerto}/estado",
            headers={"X-API-Key": config.clave_local(base)},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            e = json.loads(r.read())
    except Exception:
        e = None
    if e is None:
        print("  Estado:        no está corriendo")
        resumen = Cola(base / "cola.db").resumen()
    else:
        c = e["conexion"]
        conexion = {True: "conectado", False: "sin conexión", None: "todavía sin intentos"}[
            c["conectado"]
        ]
        print(f"  Estado:        corriendo (PID {e['pid']}, desde {e['inicio']})")
        print(f"  Conexión:      {conexion}")
        if c["ultimo_error"]:
            print(f"  Último error:  {config.mascara(c['ultimo_error'], cfg.token)}")
        print(f"  Observaciones: último envío {e['ultimo_envio_observaciones'] or '-'}")
        print(f"  Sesiones:      {e['sesiones_vistas']} vistas")
        resumen = e["cola"]
    print(f"  Cola:          {resumen['pendientes']} pendientes")
    print(f"  Último envío:  {resumen['ultimo_envio'] or '-'}")
    if resumen.get("ultimo_descarte"):
        print(f"  Último descarte: {resumen['ultimo_descarte']}")
    print("  Cuentas:")
    for cuenta in cfg.cuentas:
        print(f"    {cuenta}")
    if not cfg.cuentas:
        print("    (ninguna detectada)")
    return 0 if e is not None else 1


def _registro(a: argparse.Namespace) -> int:
    ruta = ruta_registro(config.directorio())
    print(f"Registro: {ruta}")
    if not ruta.is_file():
        print("(vacío)")
        return 0
    lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    cfg = config.cargar()
    for linea in lineas[-a.lineas :]:
        print(config.mascara(linea, cfg.token))
    return 0


def _tarea_existe() -> bool:
    if os.name != "nt":
        return False
    r = subprocess.run(
        ["schtasks", "/Query", "/TN", NOMBRE_TAREA], capture_output=True, text=True, check=False
    )
    return r.returncode == 0


def _reiniciar(_: argparse.Namespace) -> int:
    base = config.directorio()
    pid_archivo = base / "monitor.pid"
    if pid_archivo.is_file():
        try:
            pid = int(pid_archivo.read_text(encoding="ascii").strip())
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False
                )
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"Monitor detenido (PID {pid}).")
        except (ValueError, OSError):
            pass
    if _tarea_existe():
        subprocess.run(["schtasks", "/Run", "/TN", NOMBRE_TAREA], capture_output=True, check=False)
        print(f"Arrancado a través de la tarea programada '{NOMBRE_TAREA}'.")
        return 0
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    comando = (
        [sys.executable]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "visualizador_monitor"]
    )
    subprocess.Popen(
        [*comando, "servir"],
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    print("Monitor arrancado en segundo plano.")
    return 0


def _configurar(a: argparse.Namespace) -> int:
    base = config.directorio()
    cfg = config.cargar(base)
    if a.servidor:
        try:
            cfg.servidor = config.validar_servidor(a.servidor)
        except ValueError as e:
            print(e)
            return 2
    if a.puerto:
        cfg.puerto = a.puerto
    if a.token_archivo:
        cfg.token = Path(a.token_archivo).read_text(encoding="utf-8").strip()
    elif a.pedir_token:
        cfg.token = getpass.getpass("Token de máquina (no se muestra): ").strip()
    if a.cuenta:
        cfg.cuentas = [str(Path(c)) for c in a.cuenta]
    ruta = config.guardar(cfg, base)
    print(f"Configuración guardada en {ruta}")
    print(json.dumps(cfg.vista(), ensure_ascii=False, indent=2))
    return 0


def _peligrosos(_: argparse.Namespace) -> int:
    from claude_office_hooks.peligrosos import texto_predeterminado

    ruta = config.directorio() / "comandos-peligrosos.txt"
    if not ruta.is_file():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto_predeterminado(), encoding="utf-8")
        print(f"Lista creada con los valores por defecto: {ruta}")
    else:
        print(f"Lista de comandos peligrosos: {ruta}")
    print("Edítala con cualquier editor; los hooks la leen en cada comando.")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["hook"]:
        return _hook(argv[1] if len(argv) > 1 else "")
    if argv[:1] == ["statusline"]:
        return _statusline()
    p = argparse.ArgumentParser(prog="visualizador-monitor", description="Monitor de máquina")
    p.add_argument("--version", action="version", version=f"visualizador-monitor {VERSION}")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("servir", help="corre el monitor").set_defaults(f=_servir)
    sub.add_parser("estado", help="estado del monitor").set_defaults(f=_estado)
    c = sub.add_parser("registro", help="registro de errores")
    c.add_argument("-n", "--lineas", type=int, default=50)
    c.set_defaults(f=_registro)
    sub.add_parser("reiniciar", help="detiene y vuelve a arrancar").set_defaults(f=_reiniciar)
    c = sub.add_parser("configurar", help="servidor, token, puerto y cuentas")
    c.add_argument("--servidor")
    c.add_argument("--puerto", type=int)
    c.add_argument("--token-archivo", help="archivo con el token (no se muestra)")
    c.add_argument("--pedir-token", action="store_true", help="pide el token sin eco")
    c.add_argument("--cuenta", action="append", help="carpeta de una cuenta (repetible)")
    c.set_defaults(f=_configurar)
    sub.add_parser("peligrosos", help="lista de comandos peligrosos").set_defaults(f=_peligrosos)
    a = p.parse_args(argv)
    return int(a.f(a))


if __name__ == "__main__":
    sys.exit(main())

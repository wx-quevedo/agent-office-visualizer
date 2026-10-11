"""Console commands for access (stage 1.1). Run from the backend folder of a copy:

    uv run python -m app.acceso_cli contrasena
    uv run python -m app.acceso_cli maquinas
    uv run python -m app.acceso_cli maquina-crear --id tower --nombre Tower \
        --sistema windows --hostname TOWER
    uv run python -m app.acceso_cli token-crear --maquina alienware
    uv run python -m app.acceso_cli tokens
    uv run python -m app.acceso_cli token-revocar <id>
    uv run python -m app.acceso_cli sesiones
    uv run python -m app.acceso_cli sesion-revocar <id>
    uv run python -m app.acceso_cli migrar

They use the .env of that copy (ACCESO_DB_PATH or the data folder of the event
log). The password is asked twice without echo and only its argon2 hash is
saved; a machine token is printed once and only its hash is saved.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.acceso import AccesoError, get_acceso, ruta_acceso


def _contrasena(_: argparse.Namespace) -> int:
    acceso = get_acceso()
    print(f"Base de acceso: {ruta_acceso()}")
    if acceso.hay_contrasena():
        print("Ya hay una contraseña: se reemplaza y se cierran todas las sesiones.")
    primera = getpass.getpass("Contraseña nueva: ")
    segunda = getpass.getpass("Repítela: ")
    if primera != segunda:
        print("No coinciden; no se cambió nada.")
        return 1
    try:
        acceso.fijar_contrasena(primera)
    except AccesoError as exc:
        print(exc)
        return 1
    print("Contraseña guardada (solo su hash argon2).")
    return 0


def _maquinas(_: argparse.Namespace) -> int:
    filas = get_acceso().maquinas()
    if not filas:
        print("No hay máquinas registradas.")
    for m in filas:
        print(
            f"{m['id']:<14} {m['nombre']:<16} {m['sistema']:<8} host={m['hostname'] or '-'}"
            f"  monitor={m['version_monitor'] or '-'}"
            f"  última conexión={m['ultima_conexion'] or '-'}"
        )
    return 0


def _maquina_crear(a: argparse.Namespace) -> int:
    try:
        m = get_acceso().registrar_maquina(a.id, a.nombre, a.sistema, a.hostname)
    except AccesoError as exc:
        print(exc)
        return 1
    print(f"Máquina registrada: {m['id']} ({m['nombre']}, {m['sistema']}).")
    return 0


def _token_crear(a: argparse.Namespace) -> int:
    try:
        token, id_ = get_acceso().crear_token_maquina(a.maquina)
    except AccesoError as exc:
        print(exc)
        return 1
    print(f"Token {id_} de la máquina {a.maquina}. Cópialo ahora: no se vuelve a mostrar.")
    print(token)
    return 0


def _tokens(_: argparse.Namespace) -> int:
    filas = get_acceso().tokens_maquina()
    if not filas:
        print("No hay tokens de máquina.")
    for t in filas:
        estado = f"revocado {t['revocado']}" if t["revocado"] else "activo"
        print(
            f"{t['id']}  máquina={t['machine_id']:<12} creado={t['creado']}"
            f"  último uso={t['ultimo_uso'] or '-'}  {estado}"
        )
    return 0


def _token_revocar(a: argparse.Namespace) -> int:
    ok = get_acceso().revocar_token_maquina(a.id)
    print("Token revocado." if ok else "No hay un token activo con ese id.")
    return 0 if ok else 1


def _sesiones(_: argparse.Namespace) -> int:
    filas = get_acceso().sesiones_activas()
    if not filas:
        print("No hay sesiones activas.")
    for s in filas:
        print(
            f"{s.id}  {s.tipo:<3}  {s.dispositivo or '-'}  ip={s.ip or '-'}"
            f"  último uso={s.ultimo_uso.isoformat()}  vence={s.expira.isoformat()}"
        )
    return 0


def _sesion_revocar(a: argparse.Namespace) -> int:
    ok = get_acceso().revocar_sesion(a.id)
    print("Sesión cerrada." if ok else "No hay una sesión activa con ese id.")
    return 0 if ok else 1


def _migrar(_: argparse.Namespace) -> int:
    from app.core.migracion_maquinas import migrar_esta_copia

    print(migrar_esta_copia())
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="acceso_cli", description="Acceso de la oficina de agentes")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("contrasena", help="fija o cambia la contraseña").set_defaults(f=_contrasena)
    sub.add_parser("maquinas", help="lista las máquinas").set_defaults(f=_maquinas)
    c = sub.add_parser("maquina-crear", help="registra una máquina")
    c.add_argument("--id", required=True)
    c.add_argument("--nombre", required=True)
    c.add_argument("--sistema", required=True, choices=["windows", "mac", "linux"])
    c.add_argument("--hostname")
    c.set_defaults(f=_maquina_crear)
    c = sub.add_parser("token-crear", help="crea un token para una máquina")
    c.add_argument("--maquina", required=True)
    c.set_defaults(f=_token_crear)
    sub.add_parser("tokens", help="lista los tokens de máquina").set_defaults(f=_tokens)
    c = sub.add_parser("token-revocar", help="revoca un token de máquina")
    c.add_argument("id")
    c.set_defaults(f=_token_revocar)
    sub.add_parser("sesiones", help="lista las sesiones activas").set_defaults(f=_sesiones)
    c = sub.add_parser("sesion-revocar", help="cierra una sesión")
    c.add_argument("id")
    c.set_defaults(f=_sesion_revocar)
    sub.add_parser("migrar", help="asigna los datos sin máquina a la local").set_defaults(f=_migrar)
    a = p.parse_args(argv)
    return int(a.f(a))


if __name__ == "__main__":
    sys.exit(main())

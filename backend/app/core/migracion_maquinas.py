"""Migration of stage 1.1: every existing record gets a machine.

The data of this copy (engine event log, classic database, permission log) was
written by this PC before machines existed. On start-up (once):

1. The local machine is registered (MAQUINA_LOCAL_ID, "Alienware", Windows,
   hostname of this PC). This step runs on every start and is harmless.
2. If the migration was not applied yet: each database is copied with the
   SQLite backup API to ``respaldos/AAAAMMDD-HHMMSS-antes-maquinas/``.
3. A ``machine_id`` column is added where missing and filled with the local
   machine for every row that has none.
4. The migration is marked as applied in ``acceso.db``: the next start does
   nothing (idempotent). Running it again by hand is harmless too.
"""

from __future__ import annotations

import logging
import socket
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.acceso import Acceso

logger = logging.getLogger(__name__)

NOMBRE = "2026-10-10-machine-id"

# (database key, table) that get the column.
TABLAS: tuple[tuple[str, str], ...] = (
    ("agent_events", "events"),
    ("visualizer", "sessions"),
    ("visualizer", "events"),
    ("permisos", "permisos"),
)


def _tablas_de(db: sqlite3.Connection) -> set[str]:
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _respaldar(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with (
        closing(sqlite3.connect(origen, timeout=30)) as src,
        closing(sqlite3.connect(destino)) as dst,
    ):
        src.backup(dst)


def migrar(
    acceso: Acceso,
    bases: dict[str, Path],
    dir_respaldos: Path,
    machine_id: str,
    nombre: str,
    sistema: str,
    hostname: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Assign the existing data to the local machine. Returns what it did."""
    clock = clock or (lambda: datetime.now(UTC))
    acceso.registrar_maquina(machine_id, nombre, sistema, hostname or socket.gethostname())
    if acceso.migracion_aplicada(NOMBRE):
        return {"aplicada": False, "motivo": "ya estaba aplicada"}

    existentes = {k: p for k, p in bases.items() if p.exists()}
    # Local time in the folder name (the time Washington sees on the PC).
    carpeta = dir_respaldos / f"{clock().astimezone():%Y%m%d-%H%M%S}-antes-maquinas"
    respaldos: list[str] = []
    for ruta in existentes.values():
        destino = carpeta / ruta.name
        _respaldar(ruta, destino)
        respaldos.append(str(destino))

    filas: dict[str, int] = {}
    for clave, tabla in TABLAS:
        ruta = existentes.get(clave)
        if ruta is None:
            continue
        with closing(sqlite3.connect(ruta, timeout=30)) as db, db:
            if tabla not in _tablas_de(db):
                continue
            columnas = {r[1] for r in db.execute(f"PRAGMA table_info({tabla})")}
            if "machine_id" not in columnas:
                db.execute(f"ALTER TABLE {tabla} ADD COLUMN machine_id TEXT")
            cur = db.execute(
                f"UPDATE {tabla} SET machine_id = ? WHERE machine_id IS NULL", (machine_id,)
            )
            filas[f"{ruta.name}:{tabla}"] = cur.rowcount

    detalle = f"máquina {machine_id}; filas {filas}; respaldos en {carpeta}"
    acceso.marcar_migracion(NOMBRE, detalle)
    logger.info("Migración %s aplicada: %s", NOMBRE, detalle)
    return {"aplicada": True, "filas": filas, "respaldos": respaldos, "carpeta": str(carpeta)}


def rutas_de_esta_copia() -> tuple[dict[str, Path], Path]:
    """Databases of this copy and the backup folder (from the settings)."""
    from app.config import get_settings

    s = get_settings()
    datos = Path(s.STATE_EVENT_LOG_PATH).parent
    bases: dict[str, Path] = {
        "agent_events": Path(s.STATE_EVENT_LOG_PATH),
        "permisos": datos / "permisos.db",
    }
    url = s.DATABASE_URL
    if url.startswith("sqlite") and ":///" in url:
        bases["visualizer"] = Path(url.split(":///", 1)[1])
    respaldos = Path(s.RESPALDOS_PATH) if s.RESPALDOS_PATH else datos / "respaldos"
    return bases, respaldos


def migrar_esta_copia() -> dict[str, Any]:
    from app.config import get_settings
    from app.core.acceso import get_acceso

    s = get_settings()
    bases, respaldos = rutas_de_esta_copia()
    return migrar(
        get_acceso(),
        bases,
        respaldos,
        s.MAQUINA_LOCAL_ID,
        s.MAQUINA_LOCAL_NOMBRE,
        s.MAQUINA_LOCAL_SISTEMA,
    )

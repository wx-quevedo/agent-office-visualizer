"""Borra sesiones de prueba de la copia de desarrollo.

Toda prueba que envía eventos al backend de desarrollo usa session_id con el
prefijo "prueba-" y al terminar los borra con este script:

    cd backend && uv run python ../scripts/borrar_sesiones_prueba.py            # prefijo prueba-
    cd backend && uv run python ../scripts/borrar_sesiones_prueba.py rafaga- reinicio-

Borra del registro propio del motor (backend/agent_events.db) y de la base de
la vista clásica de desarrollo (backend/visualizer.db). Nunca toca la oficina
diaria (la copia original de claude-office). Ejecutar con el backend de desarrollo detenido (o
reiniciarlo después): el motor conserva en memoria lo que ya cargó.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
DEFAULT_PREFIXES = ["prueba-"]
_MATCH = "substr(session_id, 1, length(?)) = ?"


def _delete(db: Path, table_sessions: str | None, prefixes: list[str]) -> dict[str, int]:
    if not db.exists():
        return {}
    deleted: dict[str, int] = {}
    conn = sqlite3.connect(db, timeout=30)
    try:
        with conn:
            for prefix in prefixes:
                for sid, n in conn.execute(
                    f"SELECT session_id, COUNT(*) FROM events WHERE {_MATCH} GROUP BY session_id",
                    (prefix, prefix),
                ).fetchall():
                    deleted[sid] = n
                conn.execute(f"DELETE FROM events WHERE {_MATCH}", (prefix, prefix))
                if table_sessions:
                    conn.execute(
                        f"DELETE FROM {table_sessions} WHERE substr(id, 1, length(?)) = ?",
                        (prefix, prefix),
                    )
    finally:
        conn.close()
    return deleted


def borrar(prefixes: list[str]) -> dict[str, dict[str, int]]:
    """Borra las sesiones cuyos ids empiezan con alguno de los prefijos."""
    prefixes = [p for p in prefixes if p]
    return {
        "registro_propio": _delete(BACKEND / "agent_events.db", None, prefixes),
        "base_clasica_desarrollo": _delete(BACKEND / "visualizer.db", "sessions", prefixes),
    }


if __name__ == "__main__":
    result = borrar(sys.argv[1:] or DEFAULT_PREFIXES)
    for name, sessions in result.items():
        total = sum(sessions.values())
        print(f"{name}: {len(sessions)} sesiones, {total} eventos borrados")
        for sid, n in sorted(sessions.items()):
            print(f"  {sid}: {n}")

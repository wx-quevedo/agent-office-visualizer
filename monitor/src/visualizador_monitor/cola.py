"""Cola persistente de envíos al servidor (SQLite).

Cada evento de un hook se guarda antes de responderle al hook, con un id
único (``evento_id``, el servidor lo usa para no contarlo dos veces). Se
envían en orden de llegada: si el primero falla, la cola espera (espera
progresiva: 1, 2, 4 ... hasta 60 s) y nada se adelanta. Sobrevive a reinicios
del monitor y de la PC.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ESPERA_MAXIMA = 60.0
# Tope de la cola (un corte muy largo o un token revocado no llenan el disco):
# se descartan los más viejos y se anota cuántos.
MAX_PENDIENTES = 50_000
MAX_DIAS = 7

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS cola (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id TEXT NOT NULL UNIQUE,
    ruta TEXT NOT NULL,
    cuerpo BLOB NOT NULL,
    creado TEXT NOT NULL,
    intentos INTEGER NOT NULL DEFAULT 0,
    proximo TEXT NOT NULL,
    ultimo_error TEXT
);
CREATE TABLE IF NOT EXISTS sesiones (
    session_id TEXT PRIMARY KEY,
    primer_evento TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS estado (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat()


@dataclass
class Envio:
    id: int
    evento_id: str
    ruta: str
    cuerpo: bytes
    intentos: int


class Cola:
    def __init__(self, ruta: Path, clock=None) -> None:  # type: ignore[no-untyped-def]
        self.ruta = ruta
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        with closing(self._conectar()) as db, db:
            db.executescript(_ESQUEMA)

    def _conectar(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.ruta, timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        return db

    def agregar(self, ruta: str, cuerpo: bytes, evento_id: str | None = None) -> str:
        """Guarda un envío; devuelve su id (idempotente por id)."""
        evento_id = evento_id or uuid.uuid4().hex
        ahora = _iso(self.clock())
        with self._lock, closing(self._conectar()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO cola (evento_id, ruta, cuerpo, creado, proximo) "
                "VALUES (?, ?, ?, ?, ?)",
                (evento_id, ruta, cuerpo, ahora, ahora),
            )
            self._recortar(db)
        return evento_id

    def _recortar(self, db: sqlite3.Connection) -> None:
        limite = _iso(self.clock() - timedelta(days=MAX_DIAS))
        viejos = db.execute("DELETE FROM cola WHERE creado < ?", (limite,)).rowcount
        n = int(db.execute("SELECT COUNT(*) FROM cola").fetchone()[0])
        if n > MAX_PENDIENTES:
            viejos += db.execute(
                "DELETE FROM cola WHERE id IN (SELECT id FROM cola ORDER BY id LIMIT ?)",
                (n - MAX_PENDIENTES,),
            ).rowcount
        if viejos:
            db.execute(
                "INSERT OR REPLACE INTO estado (clave, valor) VALUES ('ultimo_descarte', ?)",
                (f"{_iso(self.clock())} {viejos} descartados por el tope de la cola",),
            )

    def siguiente(self) -> Envio | None:
        """El más antiguo, si ya le toca (si no, None: la cola espera en orden)."""
        with self._lock, closing(self._conectar()) as db:
            fila = db.execute(
                "SELECT id, evento_id, ruta, cuerpo, intentos, proximo "
                "FROM cola ORDER BY id LIMIT 1"
            ).fetchone()
        if fila is None:
            return None
        if datetime.fromisoformat(fila[5]) > self.clock():
            return None
        return Envio(fila[0], fila[1], fila[2], bytes(fila[3]), fila[4])

    def enviado(self, envio: Envio) -> None:
        with self._lock, closing(self._conectar()) as db, db:
            db.execute("DELETE FROM cola WHERE id = ?", (envio.id,))
            db.execute(
                "INSERT OR REPLACE INTO estado (clave, valor) VALUES ('ultimo_envio', ?)",
                (_iso(self.clock()),),
            )

    def descartar(self, envio: Envio, motivo: str) -> None:
        """Rechazo definitivo del servidor (datos inválidos): no se reintenta."""
        with self._lock, closing(self._conectar()) as db, db:
            db.execute("DELETE FROM cola WHERE id = ?", (envio.id,))
            db.execute(
                "INSERT OR REPLACE INTO estado (clave, valor) VALUES ('ultimo_descarte', ?)",
                (f"{_iso(self.clock())} {motivo}"[:300],),
            )

    def posponer(self, envio: Envio, error: str, espera: float | None = None) -> float:
        """Falla de conexión o del servidor: espera progresiva. Devuelve la espera."""
        intentos = envio.intentos + 1
        if espera is None:
            espera = min(ESPERA_MAXIMA, 2 ** (intentos - 1))
        proximo = self.clock() + timedelta(seconds=espera)
        with self._lock, closing(self._conectar()) as db, db:
            db.execute(
                "UPDATE cola SET intentos = ?, proximo = ?, ultimo_error = ? WHERE id = ?",
                (intentos, _iso(proximo), error[:300], envio.id),
            )
        return espera

    def reintentar_ya(self) -> None:
        """El servidor volvió: todo lo pendiente vuelve a estar disponible."""
        ahora = _iso(self.clock())
        with self._lock, closing(self._conectar()) as db, db:
            db.execute("UPDATE cola SET proximo = ? WHERE proximo > ?", (ahora, ahora))

    def primer_evento(self, session_id: str, ts: datetime) -> datetime:
        """Primer evento visto de la sesión (sobrevive a reinicios: los tokens se
        cuentan desde ahí). Olvida las sesiones de más de 30 días."""
        limite = _iso(self.clock() - timedelta(days=30))
        with self._lock, closing(self._conectar()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO sesiones (session_id, primer_evento) VALUES (?, ?)",
                (session_id, _iso(ts)),
            )
            fila = db.execute(
                "SELECT primer_evento FROM sesiones WHERE session_id = ?", (session_id,)
            ).fetchone()
            db.execute("DELETE FROM sesiones WHERE primer_evento < ?", (limite,))
        return datetime.fromisoformat(fila[0])

    def pendientes(self) -> int:
        with closing(self._conectar()) as db:
            return int(db.execute("SELECT COUNT(*) FROM cola").fetchone()[0])

    def resumen(self) -> dict[str, object]:
        with closing(self._conectar()) as db:
            n, viejo, intentos, error = db.execute(
                "SELECT COUNT(*), MIN(creado), MAX(intentos), "
                "(SELECT ultimo_error FROM cola ORDER BY id LIMIT 1) FROM cola"
            ).fetchone()
            estado = dict(db.execute("SELECT clave, valor FROM estado").fetchall())
        return {
            "pendientes": int(n),
            "mas_antiguo": viejo,
            "intentos_del_primero": intentos or 0,
            "ultimo_error": error,
            "ultimo_envio": estado.get("ultimo_envio"),
            "ultimo_descarte": estado.get("ultimo_descarte"),
        }

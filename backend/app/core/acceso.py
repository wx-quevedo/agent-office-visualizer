"""Access: the single user (Washington), sessions, machines and machine tokens.

Everything lives in ``acceso.db`` (SQLite, next to the engine event log, or
ACCESO_DB_PATH):

- ``usuario``: one row, the argon2 hash of the password (set with the console
  command, never in code or repository files).
- ``sesiones``: web sessions (httpOnly cookie, 30 days) and app tokens (long
  lived, for the future iOS app), one per device, revocable. Only a keyed hash
  of each token is stored.
- ``maquinas`` and ``tokens_maquina``: the machines that send events (one
  monitor each) and their tokens, also stored as keyed hashes, revocable. A
  machine token can only use the ingest endpoints.
- ``migraciones``: one-time migrations already applied.

Tokens carry a prefix so their kind is visible: ``vas_`` web session,
``vap_`` app token, ``vam_`` machine token. Their hash is HMAC-SHA256 with
VISUALIZADOR_SECRETO (plain SHA-256 when it is empty, local mode): a copy of
the database alone is not enough to use them.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger(__name__)

DURACION_WEB = timedelta(days=30)
DURACION_APP = timedelta(days=365)
# Last-use updates are written at most this often (each request reads the session).
_TOQUE = timedelta(minutes=5)
MIN_CONTRASENA = 10
SISTEMAS = ("windows", "mac", "linux")
_ID_MAQUINA = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usuario (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    hash TEXT NOT NULL,
    cambiada TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sesiones (
    id TEXT PRIMARY KEY,
    hash TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL,
    dispositivo TEXT,
    ip TEXT,
    creada TEXT NOT NULL,
    ultimo_uso TEXT NOT NULL,
    expira TEXT NOT NULL,
    revocada TEXT
);
CREATE TABLE IF NOT EXISTS maquinas (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    sistema TEXT NOT NULL,
    hostname TEXT,
    version_monitor TEXT,
    ultima_conexion TEXT,
    creada TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens_maquina (
    id TEXT PRIMARY KEY,
    machine_id TEXT NOT NULL REFERENCES maquinas (id),
    hash TEXT NOT NULL UNIQUE,
    creado TEXT NOT NULL,
    ultimo_uso TEXT,
    revocado TEXT
);
CREATE TABLE IF NOT EXISTS migraciones (
    nombre TEXT PRIMARY KEY,
    aplicada TEXT NOT NULL,
    detalle TEXT
);
"""


def _iso(ts: datetime | None) -> str | None:
    return ts.astimezone(UTC).isoformat() if ts else None


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


@dataclass
class Sesion:
    id: str
    tipo: str  # "web" | "app"
    dispositivo: str | None
    ip: str | None
    creada: datetime
    ultimo_uso: datetime
    expira: datetime

    def vista(self, actual: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "dispositivo": self.dispositivo,
            "ip": self.ip,
            "creada": _iso(self.creada),
            "ultimo_uso": _iso(self.ultimo_uso),
            "expira": _iso(self.expira),
            "actual": actual,
        }


class AccesoError(Exception):
    """Invalid input for an access operation (shown to the user)."""


class Acceso:
    """Access database. Thread safe (one connection per call)."""

    def __init__(
        self,
        ruta: str | Path,
        secreto: str = "",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._secreto = secreto.encode("utf-8")
        self.clock = clock or (lambda: datetime.now(UTC))
        self._ph = PasswordHasher()
        self._lock = threading.Lock()
        with closing(self._conectar()) as db, db:
            db.executescript(_SCHEMA)

    def _conectar(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.ruta, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _hash_token(self, token: str) -> str:
        if self._secreto:
            return hmac.new(self._secreto, token.encode("utf-8"), hashlib.sha256).hexdigest()
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    # -- password ---------------------------------------------------------------

    def hay_contrasena(self) -> bool:
        with closing(self._conectar()) as db:
            return db.execute("SELECT 1 FROM usuario WHERE id = 1").fetchone() is not None

    def fijar_contrasena(self, contrasena: str) -> None:
        if len(contrasena) < MIN_CONTRASENA:
            raise AccesoError(f"La contraseña debe tener al menos {MIN_CONTRASENA} caracteres.")
        h = self._ph.hash(contrasena)
        with closing(self._conectar()) as db, db:
            db.execute(
                "INSERT INTO usuario (id, hash, cambiada) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET hash = excluded.hash, cambiada = excluded.cambiada",
                (h, _iso(self.clock())),
            )
            # A new password closes every session and app token.
            db.execute(
                "UPDATE sesiones SET revocada = ? WHERE revocada IS NULL",
                (_iso(self.clock()),),
            )

    def verificar_contrasena(self, contrasena: str) -> bool:
        with closing(self._conectar()) as db:
            fila = db.execute("SELECT hash FROM usuario WHERE id = 1").fetchone()
        if fila is None:
            # Same work as a real check, so the time does not tell there is no password.
            with contextlib.suppress(VerificationError, InvalidHashError):
                self._ph.verify(self._ph.hash("x" * MIN_CONTRASENA), contrasena + "\0")
            return False
        try:
            return self._ph.verify(fila["hash"], contrasena)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    # -- sessions ---------------------------------------------------------------

    def crear_sesion(
        self, tipo: str, dispositivo: str | None, ip: str | None
    ) -> tuple[str, Sesion]:
        """New web session or app token (after the password was checked)."""
        if tipo not in ("web", "app"):
            raise AccesoError("Tipo de sesión desconocido.")
        prefijo = "vas_" if tipo == "web" else "vap_"
        token = prefijo + secrets.token_urlsafe(32)
        ahora = self.clock()
        s = Sesion(
            id=secrets.token_hex(8),
            tipo=tipo,
            dispositivo=(dispositivo or "")[:120] or None,
            ip=(ip or "")[:64] or None,
            creada=ahora,
            ultimo_uso=ahora,
            expira=ahora + (DURACION_WEB if tipo == "web" else DURACION_APP),
        )
        with closing(self._conectar()) as db, db:
            db.execute(
                "INSERT INTO sesiones (id, hash, tipo, dispositivo, ip, creada, "
                "ultimo_uso, expira) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s.id,
                    self._hash_token(token),
                    s.tipo,
                    s.dispositivo,
                    s.ip,
                    _iso(s.creada),
                    _iso(s.ultimo_uso),
                    _iso(s.expira),
                ),
            )
        return token, s

    def validar_sesion(self, token: str | None, tipo: str | None = None) -> Sesion | None:
        """The live session of a token (web cookie or app token), or None."""
        if not token or not token.startswith(("vas_", "vap_")):
            return None
        with closing(self._conectar()) as db:
            fila = db.execute(
                "SELECT * FROM sesiones WHERE hash = ? AND revocada IS NULL",
                (self._hash_token(token),),
            ).fetchone()
        if fila is None:
            return None
        s = Sesion(
            id=fila["id"],
            tipo=fila["tipo"],
            dispositivo=fila["dispositivo"],
            ip=fila["ip"],
            creada=_dt(fila["creada"]),  # type: ignore[arg-type]
            ultimo_uso=_dt(fila["ultimo_uso"]),  # type: ignore[arg-type]
            expira=_dt(fila["expira"]),  # type: ignore[arg-type]
        )
        if tipo and s.tipo != tipo:
            return None
        ahora = self.clock()
        if ahora >= s.expira:
            return None
        if ahora - s.ultimo_uso > _TOQUE:
            with closing(self._conectar()) as db, db:
                db.execute("UPDATE sesiones SET ultimo_uso = ? WHERE id = ?", (_iso(ahora), s.id))
            s.ultimo_uso = ahora
        return s

    def revocar_sesion(self, id_: str) -> bool:
        with closing(self._conectar()) as db, db:
            cur = db.execute(
                "UPDATE sesiones SET revocada = ? WHERE id = ? AND revocada IS NULL",
                (_iso(self.clock()), id_),
            )
            return cur.rowcount > 0

    def sesiones_activas(self) -> list[Sesion]:
        ahora = _iso(self.clock())
        with closing(self._conectar()) as db:
            filas = db.execute(
                "SELECT * FROM sesiones WHERE revocada IS NULL AND expira > ? "
                "ORDER BY ultimo_uso DESC",
                (ahora,),
            ).fetchall()
        return [
            Sesion(
                id=f["id"],
                tipo=f["tipo"],
                dispositivo=f["dispositivo"],
                ip=f["ip"],
                creada=_dt(f["creada"]),  # type: ignore[arg-type]
                ultimo_uso=_dt(f["ultimo_uso"]),  # type: ignore[arg-type]
                expira=_dt(f["expira"]),  # type: ignore[arg-type]
            )
            for f in filas
        ]

    # -- machines ---------------------------------------------------------------

    def registrar_maquina(
        self, id_: str, nombre: str, sistema: str, hostname: str | None = None
    ) -> dict[str, Any]:
        """Create a machine, or update its name, system and hostname (idempotent)."""
        if not _ID_MAQUINA.match(id_):
            raise AccesoError(
                "El id de la máquina usa minúsculas, números y guiones (hasta 40 caracteres)."
            )
        if sistema not in SISTEMAS:
            raise AccesoError(f"Sistema desconocido: {sistema} (windows, mac o linux).")
        nombre = nombre.strip()[:80] or id_
        with closing(self._conectar()) as db, db:
            db.execute(
                "INSERT INTO maquinas (id, nombre, sistema, hostname, creada) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET nombre = excluded.nombre, "
                "sistema = excluded.sistema, hostname = COALESCE(excluded.hostname, hostname)",
                (id_, nombre, sistema, (hostname or None), _iso(self.clock())),
            )
        return self.maquina(id_)  # type: ignore[return-value]

    def maquina(self, id_: str) -> dict[str, Any] | None:
        with closing(self._conectar()) as db:
            fila = db.execute("SELECT * FROM maquinas WHERE id = ?", (id_,)).fetchone()
        return dict(fila) if fila else None

    def maquinas(self) -> list[dict[str, Any]]:
        with closing(self._conectar()) as db:
            return [dict(f) for f in db.execute("SELECT * FROM maquinas ORDER BY id").fetchall()]

    def latido_maquina(
        self, id_: str, version_monitor: str | None, hostname: str | None
    ) -> dict[str, Any] | None:
        with closing(self._conectar()) as db, db:
            db.execute(
                "UPDATE maquinas SET ultima_conexion = ?, "
                "version_monitor = COALESCE(?, version_monitor), hostname = COALESCE(?, hostname) "
                "WHERE id = ?",
                (
                    _iso(self.clock()),
                    (version_monitor or None) and version_monitor[:40],
                    (hostname or None) and hostname[:120],
                    id_,
                ),
            )
        return self.maquina(id_)

    # -- machine tokens -----------------------------------------------------------

    def crear_token_maquina(self, machine_id: str) -> tuple[str, str]:
        """New token of a machine: (token shown once, token id)."""
        if self.maquina(machine_id) is None:
            raise AccesoError(f"No existe la máquina {machine_id}.")
        token = "vam_" + secrets.token_urlsafe(32)
        id_ = secrets.token_hex(6)
        with closing(self._conectar()) as db, db:
            db.execute(
                "INSERT INTO tokens_maquina (id, machine_id, hash, creado) VALUES (?, ?, ?, ?)",
                (id_, machine_id, self._hash_token(token), _iso(self.clock())),
            )
        return token, id_

    def validar_token_maquina(self, token: str | None) -> str | None:
        """The machine id of a live machine token, or None."""
        if not token or not token.startswith("vam_"):
            return None
        with closing(self._conectar()) as db:
            fila = db.execute(
                "SELECT id, machine_id, ultimo_uso FROM tokens_maquina "
                "WHERE hash = ? AND revocado IS NULL",
                (self._hash_token(token),),
            ).fetchone()
        if fila is None:
            return None
        ahora = self.clock()
        ultimo = _dt(fila["ultimo_uso"])
        if ultimo is None or ahora - ultimo > _TOQUE:
            with closing(self._conectar()) as db, db:
                db.execute(
                    "UPDATE tokens_maquina SET ultimo_uso = ? WHERE id = ?",
                    (_iso(ahora), fila["id"]),
                )
        return str(fila["machine_id"])

    def tokens_maquina(self) -> list[dict[str, Any]]:
        with closing(self._conectar()) as db:
            return [
                dict(f)
                for f in db.execute(
                    "SELECT id, machine_id, creado, ultimo_uso, revocado FROM tokens_maquina "
                    "ORDER BY creado DESC"
                ).fetchall()
            ]

    def revocar_token_maquina(self, id_: str) -> bool:
        with closing(self._conectar()) as db, db:
            cur = db.execute(
                "UPDATE tokens_maquina SET revocado = ? WHERE id = ? AND revocado IS NULL",
                (_iso(self.clock()), id_),
            )
            return cur.rowcount > 0

    # -- migrations ---------------------------------------------------------------

    def migracion_aplicada(self, nombre: str) -> bool:
        with closing(self._conectar()) as db:
            return (
                db.execute("SELECT 1 FROM migraciones WHERE nombre = ?", (nombre,)).fetchone()
                is not None
            )

    def marcar_migracion(self, nombre: str, detalle: str) -> None:
        with closing(self._conectar()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO migraciones (nombre, aplicada, detalle) VALUES (?, ?, ?)",
                (nombre, _iso(self.clock()), detalle),
            )


class LimiteIntentos:
    """Failed sign-ins per IP with a progressive wait.

    The first 4 failures are free; from the 5th, each failure doubles the wait
    (5 s, 10 s, 20 s ... up to 15 min). A successful sign-in clears the IP.
    """

    LIBRES = 4
    BASE = 5.0
    MAXIMA = 900.0
    # All IPs together: more than this many failures in a minute closes sign-in
    # for a minute (many IPs, or forged ones, cannot guess without limit).
    GLOBAL_FALLOS = 30
    GLOBAL_ESPERA = 60.0

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(UTC))
        self._fallos: dict[str, tuple[int, datetime | None]] = {}
        self._recientes: list[datetime] = []
        self._global_hasta: datetime | None = None
        self._lock = threading.Lock()

    def espera_global(self) -> float:
        with self._lock:
            hasta = self._global_hasta
        if hasta is None:
            return 0.0
        return max(0.0, (hasta - self.clock()).total_seconds())

    def espera(self, ip: str) -> float:
        """Seconds the IP must still wait before trying again (0: it may try)."""
        with self._lock:
            _, hasta = self._fallos.get(ip, (0, None))
        if hasta is None:
            return 0.0
        return max(0.0, (hasta - self.clock()).total_seconds())

    def fallo(self, ip: str) -> float:
        """Record a failure; returns the wait it causes."""
        with self._lock:
            ahora = self.clock()
            self._recientes = [t for t in self._recientes if ahora - t < timedelta(minutes=1)]
            self._recientes.append(ahora)
            if len(self._recientes) > self.GLOBAL_FALLOS:
                self._global_hasta = ahora + timedelta(seconds=self.GLOBAL_ESPERA)
            n, _ = self._fallos.get(ip, (0, None))
            n += 1
            espera = 0.0
            if n > self.LIBRES:
                espera = min(self.MAXIMA, self.BASE * 2 ** (n - self.LIBRES - 1))
            self._fallos[ip] = (n, self.clock() + timedelta(seconds=espera) if espera else None)
            if len(self._fallos) > 5000:  # bound memory
                self._fallos.pop(next(iter(self._fallos)))
            return espera

    def exito(self, ip: str) -> None:
        with self._lock:
            self._fallos.pop(ip, None)


def exigir_secreto(settings: Any) -> None:
    """With sign-in on, refuse to start without a real VISUALIZADOR_SECRETO."""
    secreto = str(settings.VISUALIZADOR_SECRETO).strip()
    if settings.auth_activa and (len(secreto) < 32 or secreto == "COMPLETAR"):
        raise RuntimeError(
            "VISUALIZADOR_AUTH=activado necesita VISUALIZADOR_SECRETO de al menos 32 caracteres."
        )


_acceso: Acceso | None = None
_limite = LimiteIntentos()


def ruta_acceso() -> Path:
    from app.config import get_settings

    s = get_settings()
    if s.ACCESO_DB_PATH:
        return Path(s.ACCESO_DB_PATH)
    return Path(s.STATE_EVENT_LOG_PATH).parent / "acceso.db"


def get_acceso() -> Acceso:
    global _acceso
    if _acceso is None:
        from app.config import get_settings

        _acceso = Acceso(ruta_acceso(), get_settings().VISUALIZADOR_SECRETO)
    return _acceso


def set_acceso(a: Acceso | None) -> None:
    """For tests."""
    global _acceso
    _acceso = a


def get_limite() -> LimiteIntentos:
    return _limite


def set_limite(limite: LimiteIntentos) -> None:
    """For tests."""
    global _limite
    _limite = limite

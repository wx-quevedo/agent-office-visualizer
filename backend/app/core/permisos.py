"""Permission requests (state 13) answered from the office.

The hook registers each PermissionRequest of Claude Code here and, depending
on the policy and on where the user is, waits for a decision (long-poll):

- ``solo_fuera_de_la_pc`` (default): wait only when no PC page is open (no
  recent PC heartbeat; phone heartbeats only, or none).
- ``siempre``: always wait, up to the configured time.
- ``nunca``: only register (the request is shown, answered in VS Code).

A request can be decided once (approve, or reject with an optional short
reason that Claude receives). Expired requests and requests that are not
waiting reject decisions with a clear error. When Claude Code goes on (the
user answered in VS Code), the next event of the session marks the request as
resolved outside the office. Every request and decision is stored in an
SQLite log of its own (who: PC or phone, when, what).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

Politica = Literal["solo_fuera_de_la_pc", "siempre", "nunca"]
Estado = Literal["pendiente", "aprobada", "rechazada", "vencida", "resuelta_fuera"]

POLITICAS: tuple[Politica, ...] = ("solo_fuera_de_la_pc", "siempre", "nunca")
ESPERA_POR_DEFECTO = 90
ESPERA_MINIMA = 10
# Upper bound of the wait. The hook must be registered with a larger timeout
# (see PROJECT.md: the command for settings.json uses 600 s).
ESPERA_MAXIMA = 540
CONFIRMAR_POR_DEFECTO = [
    "rm",
    "rmdir",
    "del",
    "rd",
    "Remove-Item",
    "git push",
    "git reset --hard",
    "git clean",
    "deploy",
    "publish",
    "drop",
    "truncate",
    "format",
]
MAX_MOTIVO = 300
MAX_DETALLE = 4000
# Decided or expired requests stay in memory this long (the office shows them).
_RECIENTES = timedelta(minutes=10)
# Events of a session after the request that mean "Claude Code went on" (the
# user answered in VS Code): the end of the turn, or the tool itself running.
# Parallel tool calls also send PreToolUse/PostToolUse, so those only count
# for the same tool and input, or a PreToolUse that starts well after it.
EVENTOS_FIN = frozenset({"user_prompt_submit", "stop", "session_end"})
EVENTOS_HERRAMIENTA = frozenset({"post_tool_use", "post_tool_use_failure"})
_VENTANA_PARALELA = timedelta(seconds=3)


class PermisoError(Exception):
    """A decision that cannot be applied: HTTP status and message for the office."""

    def __init__(self, status: int, mensaje: str) -> None:
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


@dataclass
class Configuracion:
    politica: Politica = "solo_fuera_de_la_pc"
    espera_seg: int = ESPERA_POR_DEFECTO
    confirmar: list[str] = field(default_factory=lambda: list(CONFIRMAR_POR_DEFECTO))


@dataclass
class Solicitud:
    id: str
    session_id: str
    herramienta: str
    detalle: str
    entrada: dict[str, Any]
    cuenta: str | None
    proyecto: str | None
    creada: datetime
    esperando: bool
    vence: datetime | None
    estado: Estado = "pendiente"
    motivo: str | None = None
    dispositivo: str | None = None
    decidida: datetime | None = None

    def vista(self, now: datetime) -> dict[str, Any]:
        """JSON for the office and the hook."""
        espera_activa = self.estado == "pendiente" and self.esperando
        quedan = (
            max(0, math.ceil((self.vence - now).total_seconds()))
            if espera_activa and self.vence
            else 0
        )
        return {
            "id": self.id,
            "session_id": self.session_id,
            "herramienta": self.herramienta,
            "detalle": self.detalle,
            "cuenta": self.cuenta,
            "proyecto": self.proyecto,
            "creada": self.creada.isoformat(),
            "esperando": espera_activa,
            "vence": self.vence.isoformat() if self.vence else None,
            "segundos_restantes": quedan,
            "estado": self.estado,
            "motivo": self.motivo,
            "dispositivo": self.dispositivo,
            "decidida": self.decidida.isoformat() if self.decidida else None,
        }


def detalle_de(herramienta: str, entrada: dict[str, Any]) -> str:
    """What the request asks for, readable: the full command, the file, or the input."""
    for clave in ("command", "file_path", "notebook_path", "path", "url", "pattern"):
        valor = entrada.get(clave)
        if isinstance(valor, str) and valor.strip():
            texto = valor
            break
    else:
        texto = json.dumps(entrada, ensure_ascii=False) if entrada else herramienta
    return texto[:MAX_DETALLE]


def _iso(ts: datetime | None) -> str | None:
    return ts.isoformat() if ts else None


class RegistroPermisos:
    """Requests in memory plus their SQLite log; the configuration in a JSON file."""

    def __init__(self, carpeta: Path, clock: Any = None) -> None:
        self.ruta_db = carpeta / "permisos.db"
        self.ruta_config = carpeta / "permisos.json"
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._solicitudes: dict[str, Solicitud] = {}
        self._eventos: dict[str, asyncio.Event] = {}
        self._config = self._leer_config()
        carpeta.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.ruta_db) as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS permisos (
                    id TEXT PRIMARY KEY, session_id TEXT, herramienta TEXT,
                    detalle TEXT, cuenta TEXT, proyecto TEXT, creada TEXT,
                    esperando INTEGER, vence TEXT, politica TEXT, estado TEXT,
                    motivo TEXT, dispositivo TEXT, decidida TEXT)"""
            )

    # -- configuration -------------------------------------------------------

    def _leer_config(self) -> Configuracion:
        try:
            raw = json.loads(self.ruta_config.read_text(encoding="utf-8"))
            return validar_config(raw)
        except FileNotFoundError:
            return Configuracion()
        except Exception as exc:  # a broken file falls back to the defaults
            logger.warning("permisos.json no válido, se usan los valores por defecto: %s", exc)
            return Configuracion()

    @property
    def config(self) -> Configuracion:
        return self._config

    def guardar_config(self, config: Configuracion) -> Configuracion:
        self.ruta_config.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta_config.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.ruta_config)
        self._config = config
        return config

    # -- log -----------------------------------------------------------------

    def _guardar(self, s: Solicitud, politica: str | None = None) -> None:
        try:
            with sqlite3.connect(self.ruta_db) as db:
                db.execute(
                    """INSERT INTO permisos (id, session_id, herramienta, detalle, cuenta,
                        proyecto, creada, esperando, vence, politica, estado, motivo,
                        dispositivo, decidida)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET estado=excluded.estado,
                        motivo=excluded.motivo, dispositivo=excluded.dispositivo,
                        decidida=excluded.decidida""",
                    (
                        s.id,
                        s.session_id,
                        s.herramienta,
                        s.detalle,
                        s.cuenta,
                        s.proyecto,
                        _iso(s.creada),
                        int(s.esperando),
                        _iso(s.vence),
                        politica,
                        s.estado,
                        s.motivo,
                        s.dispositivo,
                        _iso(s.decidida),
                    ),
                )
        except Exception as exc:
            logger.warning("No se pudo guardar el permiso %s: %s", s.id, exc)

    def historial(self, limite: int = 50) -> list[dict[str, Any]]:
        with sqlite3.connect(self.ruta_db) as db:
            db.row_factory = sqlite3.Row
            filas = db.execute(
                "SELECT * FROM permisos ORDER BY creada DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(f) for f in filas]

    # -- requests ------------------------------------------------------------

    def _vencer(self, now: datetime) -> None:
        for s in list(self._solicitudes.values()):
            if s.estado == "pendiente" and s.esperando and s.vence and now >= s.vence:
                s.estado = "vencida"
                s.decidida = now
                self._guardar(s)
                self._avisar(s.id)
            ref = s.decidida or s.creada
            if s.estado != "pendiente" and now - ref > _RECIENTES:
                del self._solicitudes[s.id]
                self._eventos.pop(s.id, None)

    def crear(
        self,
        id_: str,
        session_id: str,
        herramienta: str,
        entrada: dict[str, Any],
        cuenta: str | None,
        proyecto: str | None,
        en_la_pc: bool,
    ) -> Solicitud:
        """Register a request; idempotent by id. Decides whether the hook waits."""
        now = self.clock()
        with self._lock:
            self._vencer(now)
            if id_ in self._solicitudes:
                return self._solicitudes[id_]
            cfg = self._config
            esperar = cfg.politica == "siempre" or (
                cfg.politica == "solo_fuera_de_la_pc" and not en_la_pc
            )
            # An older pending request of the same session is over: Claude asks again.
            for otra in self._solicitudes.values():
                if otra.session_id == session_id and otra.estado == "pendiente":
                    otra.estado = "resuelta_fuera"
                    otra.decidida = now
                    self._guardar(otra)
                    self._avisar(otra.id)
            s = Solicitud(
                id=id_,
                session_id=session_id,
                herramienta=herramienta,
                detalle=detalle_de(herramienta, entrada),
                entrada=entrada,
                cuenta=cuenta,
                proyecto=proyecto,
                creada=now,
                esperando=esperar,
                vence=now + timedelta(seconds=cfg.espera_seg) if esperar else None,
            )
            self._solicitudes[id_] = s
            self._guardar(s, cfg.politica)
            return s

    def obtener(self, id_: str) -> Solicitud | None:
        with self._lock:
            self._vencer(self.clock())
            return self._solicitudes.get(id_)

    def decidir(self, id_: str, aprobar: bool, motivo: str | None, dispositivo: str) -> Solicitud:
        """Apply the decision of the office (only once, only while it waits)."""
        now = self.clock()
        with self._lock:
            self._vencer(now)
            s = self._solicitudes.get(id_)
            if s is None:
                raise PermisoError(404, "La solicitud no existe o ya no está en la oficina.")
            if s.estado == "vencida":
                raise PermisoError(410, "Se agotó el tiempo de espera: responde en VS Code.")
            if s.estado == "resuelta_fuera":
                raise PermisoError(409, "Ya se respondió en VS Code.")
            if s.estado != "pendiente":
                raise PermisoError(409, "Esta solicitud ya fue decidida.")
            if not s.esperando:
                raise PermisoError(
                    409, "Esta solicitud no espera respuesta de la oficina: responde en VS Code."
                )
            s.estado = "aprobada" if aprobar else "rechazada"
            s.motivo = None if aprobar else ((motivo or "").strip()[:MAX_MOTIVO] or None)
            s.dispositivo = dispositivo
            s.decidida = now
            self._guardar(s)
            self._avisar(id_)
            logger.info(
                "Permiso %s %s desde %s (%s: %s)",
                id_,
                s.estado,
                dispositivo,
                s.herramienta,
                s.detalle[:120],
            )
            return s

    def resolver_sesion(
        self,
        session_id: str,
        tipo_evento: str,
        herramienta: str | None = None,
        entrada: dict[str, Any] | None = None,
    ) -> None:
        """Claude Code went on in this session: its pending request was answered in VS Code."""
        now = self.clock()
        with self._lock:
            for s in self._solicitudes.values():
                if s.session_id != session_id or s.estado != "pendiente":
                    continue
                misma = herramienta == s.herramienta and (
                    detalle_de(herramienta or "", entrada or {}) == s.detalle
                )
                if not (
                    tipo_evento in EVENTOS_FIN
                    or (tipo_evento in EVENTOS_HERRAMIENTA and misma)
                    or (tipo_evento == "pre_tool_use" and now - s.creada > _VENTANA_PARALELA)
                ):
                    continue
                s.estado = "resuelta_fuera"
                s.decidida = now
                self._guardar(s)
                self._avisar(s.id)

    def de_sesion(self, session_id: str) -> Solicitud | None:
        """The latest request of a session that the office still shows."""
        now = self.clock()
        with self._lock:
            self._vencer(now)
            lista = [s for s in self._solicitudes.values() if s.session_id == session_id]
        return max(lista, key=lambda s: s.creada) if lista else None

    def vistas_por_sesion(self) -> dict[str, dict[str, Any]]:
        """Pending (or just decided) request of each session, for /agents/state."""
        now = self.clock()
        with self._lock:
            self._vencer(now)
            ultimas: dict[str, Solicitud] = {}
            for s in self._solicitudes.values():
                if s.session_id not in ultimas or s.creada > ultimas[s.session_id].creada:
                    ultimas[s.session_id] = s
            return {sid: s.vista(now) for sid, s in ultimas.items()}

    # -- long-poll -------------------------------------------------------------

    def _avisar(self, id_: str) -> None:
        ev = self._eventos.get(id_)
        if ev is not None:
            ev.set()

    async def esperar(self, id_: str, segundos: float) -> Solicitud | None:
        """Wait up to *segundos* for a decision (or expiry) of a request."""
        s = self.obtener(id_)
        if s is None or s.estado != "pendiente" or not s.esperando:
            return s
        with self._lock:
            ev = self._eventos.setdefault(id_, asyncio.Event())
        restante = (s.vence - self.clock()).total_seconds() if s.vence else segundos
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(ev.wait(), timeout=max(0.0, min(segundos, restante)))
        return self.obtener(id_)


def validar_config(raw: Any) -> Configuracion:
    """Validated configuration (raises ValueError with a readable message)."""
    if not isinstance(raw, dict):
        raise ValueError("La configuración debe ser un objeto.")
    politica = raw.get("politica", "solo_fuera_de_la_pc")
    if politica not in POLITICAS:
        raise ValueError(f"Política desconocida: {politica}")
    espera = raw.get("espera_seg", ESPERA_POR_DEFECTO)
    if not isinstance(espera, int) or isinstance(espera, bool):
        raise ValueError("El tiempo de espera debe ser un número entero de segundos.")
    if not ESPERA_MINIMA <= espera <= ESPERA_MAXIMA:
        raise ValueError(
            f"El tiempo de espera debe estar entre {ESPERA_MINIMA} y {ESPERA_MAXIMA} s."
        )
    confirmar = raw.get("confirmar", CONFIRMAR_POR_DEFECTO)
    if not isinstance(confirmar, list) or not all(isinstance(c, str) for c in confirmar):
        raise ValueError("La lista de comandos debe ser una lista de textos.")
    limpia: list[str] = []
    for c in confirmar:
        c = c.strip()[:60]
        if c and c not in limpia:
            limpia.append(c)
    if len(limpia) > 50:
        raise ValueError("Como máximo 50 comandos que piden confirmación.")
    return Configuracion(politica=politica, espera_seg=espera, confirmar=limpia)


_registro: RegistroPermisos | None = None


def get_registro() -> RegistroPermisos:
    global _registro
    if _registro is None:
        from app.config import get_settings

        _registro = RegistroPermisos(Path(get_settings().STATE_EVENT_LOG_PATH).parent)
    return _registro


def set_registro(r: RegistroPermisos | None) -> None:
    """For tests."""
    global _registro
    _registro = r

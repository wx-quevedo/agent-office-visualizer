"""Proyectos con equipo (etapa 4, Prompt 37).

Desde la web o la app se crea un proyecto en una máquina: el servidor lo registra
con su equipo (un orquestador y uno o más agentes de código, cada uno con modelo,
esfuerzo, id de sesión y estado) y deja un encargo para el monitor de esa máquina.
El monitor crea la carpeta dentro de su ruta base, lanza las sesiones (claude -p
con stream-json) e informa el resultado. Pausar y reanudar también son encargos.

Estados del proyecto: creando, activo, pausando, pausado, reanudando, error.
Estados de un miembro: pendiente, activo, pausado, detenido, error.
Estados de un encargo: pendiente, en_curso, hecho, error.

Todo vive en ``proyectos.db`` junto a los demás datos del backend (el respaldo
copia cada ``.db``), con versión de esquema (``PRAGMA user_version``).
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

ESQUEMA = 1
# Nombre de un proyecto: la carpeta que se crea. Minúsculas, números y guiones,
# sin empezar ni terminar con guion, sin puntos ni barras (nunca una ruta).
NOMBRE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?$")
RESERVADOS = frozenset(
    {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(10)} | {f"lpt{i}" for i in range(10)}
)
CUENTAS = ("personal", "demo")
PLANTILLAS = ("web", "unity", "expo", "vacia")
ESFUERZOS = ("low", "medium", "high", "xhigh", "max")
MAX_AGENTES = 4
# Encargo tomado por un monitor que no informó: se vuelve a entregar.
REENTREGA = timedelta(minutes=3)
# Máquina encendida: latido del monitor en los últimos 90 s (sale cada 30 s).
ENCENDIDA = timedelta(seconds=90)
# Primera versión del monitor que sabe crear proyectos.
VERSION_MINIMA = (0, 4, 0)

EstadoProyecto = Literal["creando", "activo", "pausando", "pausado", "reanudando", "error"]

_MIGRACIONES: dict[int, list[str]] = {
    1: [
        """CREATE TABLE IF NOT EXISTS proyectos (
            id TEXT PRIMARY KEY, nombre TEXT NOT NULL, maquina TEXT NOT NULL,
            cuenta TEXT NOT NULL, ruta TEXT, plantilla TEXT NOT NULL,
            estado TEXT NOT NULL, auto_aprobar INTEGER NOT NULL DEFAULT 0,
            error TEXT, creado TEXT NOT NULL, actualizado TEXT NOT NULL,
            UNIQUE (maquina, nombre))""",
        """CREATE TABLE IF NOT EXISTS miembros (
            id TEXT PRIMARY KEY, proyecto_id TEXT NOT NULL REFERENCES proyectos (id),
            rol TEXT NOT NULL, nombre TEXT NOT NULL, modelo TEXT NOT NULL,
            esfuerzo TEXT NOT NULL, session_id TEXT, estado TEXT NOT NULL,
            orden INTEGER NOT NULL, actualizado TEXT NOT NULL,
            UNIQUE (proyecto_id, nombre))""",
        """CREATE TABLE IF NOT EXISTS encargos (
            id TEXT PRIMARY KEY, maquina TEXT NOT NULL, proyecto_id TEXT NOT NULL,
            tipo TEXT NOT NULL, datos TEXT NOT NULL, estado TEXT NOT NULL,
            creado TEXT NOT NULL, tomado TEXT, terminado TEXT, error TEXT)""",
        "CREATE INDEX IF NOT EXISTS encargos_maquina ON encargos (maquina, estado)",
        """CREATE TABLE IF NOT EXISTS maquinas_proyectos (
            maquina TEXT PRIMARY KEY, ruta_base TEXT, actualizado TEXT NOT NULL)""",
    ],
}


class ProyectoError(Exception):
    def __init__(self, status: int, mensaje: str) -> None:
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def validar_nombre(nombre: str) -> str:
    """El nombre tal cual o ProyectoError (422) con una explicación clara."""
    if not nombre:
        raise ProyectoError(422, "Escribe un nombre para el proyecto.")
    if len(nombre) > 50:
        raise ProyectoError(422, "El nombre puede tener hasta 50 caracteres.")
    if not NOMBRE.fullmatch(nombre):
        raise ProyectoError(
            422,
            "Usa solo minúsculas, números y guiones (sin espacios, puntos ni barras), "
            "y que no empiece ni termine con guion.",
        )
    if nombre in RESERVADOS:
        raise ProyectoError(422, "Ese nombre está reservado por Windows.")
    return nombre


def ruta_de(ruta_base: str, nombre: str) -> str:
    """La carpeta que se va a crear (solo para mostrar: la verifica el monitor)."""
    sep = "\\" if ("\\" in ruta_base or re.match(r"^[A-Za-z]:", ruta_base)) else "/"
    return ruta_base.rstrip("\\/") + sep + nombre


def version_tupla(v: str | None) -> tuple[int, ...]:
    if not v:
        return ()
    partes = re.findall(r"\d+", v)[:3]
    return tuple(int(p) for p in partes)


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat()


class ProyectosEquipo:
    def __init__(self, carpeta: Path, clock: Callable[[], datetime] | None = None) -> None:
        carpeta.mkdir(parents=True, exist_ok=True)
        self.ruta = carpeta / "proyectos.db"
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._migrar()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.ruta)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def _migrar(self) -> None:
        with self._lock, self._db() as db:
            version = int(db.execute("PRAGMA user_version").fetchone()[0])
            for v in range(version + 1, ESQUEMA + 1):
                for sql in _MIGRACIONES[v]:
                    db.execute(sql)
                db.execute(f"PRAGMA user_version = {v}")

    def version(self) -> int:
        with self._db() as db:
            return int(db.execute("PRAGMA user_version").fetchone()[0])

    # -- máquinas --------------------------------------------------------------------

    def anotar_ruta_base(self, maquina: str, ruta_base: str | None) -> None:
        if not ruta_base:
            return
        with self._lock, self._db() as db:
            db.execute(
                """INSERT INTO maquinas_proyectos (maquina, ruta_base, actualizado) VALUES (?,?,?)
                ON CONFLICT(maquina) DO UPDATE SET ruta_base = excluded.ruta_base,
                    actualizado = excluded.actualizado""",
                (maquina, ruta_base[:300], _iso(self.clock())),
            )

    def rutas_base(self) -> dict[str, str]:
        with self._db() as db:
            return {
                r["maquina"]: r["ruta_base"]
                for r in db.execute("SELECT maquina, ruta_base FROM maquinas_proyectos")
            }

    def vista_maquinas(self, maquinas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Las máquinas registradas con su ruta base, si están encendidas y si su
        monitor sabe crear proyectos."""
        rutas = self.rutas_base()
        ahora = self.clock()
        salida: list[dict[str, Any]] = []
        for m in maquinas:
            ultima = m.get("ultima_conexion")
            encendida = False
            if isinstance(ultima, str) and ultima:
                try:
                    encendida = ahora - datetime.fromisoformat(ultima) <= ENCENDIDA
                except ValueError:
                    encendida = False
            soporta = version_tupla(m.get("version_monitor")) >= VERSION_MINIMA
            ruta = rutas.get(m["id"])
            if not encendida:
                motivo = "Apagada o sin monitor"
            elif not soporta:
                motivo = "Su monitor no sabe crear proyectos: actualízalo"
            elif not ruta:
                motivo = "Su monitor todavía no informó la ruta base"
            else:
                motivo = None
            salida.append(
                {
                    "id": m["id"],
                    "nombre": m.get("nombre") or m["id"],
                    "sistema": m.get("sistema"),
                    "version_monitor": m.get("version_monitor"),
                    "ultima_conexion": ultima,
                    "encendida": encendida,
                    "ruta_base": ruta,
                    "disponible": motivo is None,
                    "motivo": motivo,
                }
            )
        return salida

    # -- proyectos ------------------------------------------------------------------------

    def _miembros(self, db: sqlite3.Connection, proyecto_id: str) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in db.execute(
                "SELECT * FROM miembros WHERE proyecto_id = ? ORDER BY orden", (proyecto_id,)
            )
        ]

    def proyecto(self, id_: str) -> dict[str, Any] | None:
        with self._db() as db:
            r = db.execute("SELECT * FROM proyectos WHERE id = ?", (id_,)).fetchone()
            if r is None:
                return None
            p = dict(r)
            p["auto_aprobar"] = bool(p["auto_aprobar"])
            p["equipo"] = self._miembros(db, id_)
            return p

    def proyectos(self) -> list[dict[str, Any]]:
        with self._db() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM proyectos ORDER BY creado DESC")]
        return [p for i in ids if (p := self.proyecto(i)) is not None]

    def crear(
        self,
        nombre: str,
        maquina: str,
        cuenta: str,
        plantilla: str,
        orquestador: dict[str, str],
        agentes: list[dict[str, str]],
        auto_aprobar: bool,
        ruta_base: str,
    ) -> dict[str, Any]:
        nombre = validar_nombre(nombre)
        if cuenta not in CUENTAS:
            raise ProyectoError(422, "La cuenta tiene que ser personal o demo.")
        if plantilla not in PLANTILLAS:
            raise ProyectoError(422, "Plantilla desconocida.")
        if not 1 <= len(agentes) <= MAX_AGENTES:
            raise ProyectoError(422, f"El equipo lleva de 1 a {MAX_AGENTES} agentes de código.")
        for m in [orquestador, *agentes]:
            if m.get("esfuerzo") not in ESFUERZOS:
                raise ProyectoError(422, "Esfuerzo desconocido.")
            if not re.fullmatch(r"[A-Za-z0-9.\-\[\]]{2,60}", m.get("modelo") or ""):
                raise ProyectoError(422, "Modelo desconocido.")
        ahora = _iso(self.clock())
        id_ = uuid.uuid4().hex
        ruta = ruta_de(ruta_base, nombre)
        miembros = [("orquestador", "orquestador", orquestador)] + [
            ("agente", "agente" if len(agentes) == 1 else f"agente-{i + 1}", a)
            for i, a in enumerate(agentes)
        ]
        with self._lock, self._db() as db:
            if db.execute(
                "SELECT 1 FROM proyectos WHERE maquina = ? AND nombre = ?", (maquina, nombre)
            ).fetchone():
                raise ProyectoError(409, "Ya hay un proyecto con ese nombre en esa máquina.")
            db.execute(
                """INSERT INTO proyectos (id, nombre, maquina, cuenta, ruta, plantilla, estado,
                    auto_aprobar, creado, actualizado) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    id_,
                    nombre,
                    maquina,
                    cuenta,
                    ruta,
                    plantilla,
                    "creando",
                    int(auto_aprobar),
                    ahora,
                    ahora,
                ),
            )
            for orden, (rol, nombre_m, m) in enumerate(miembros):
                db.execute(
                    """INSERT INTO miembros (id, proyecto_id, rol, nombre, modelo, esfuerzo,
                        session_id, estado, orden, actualizado) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        uuid.uuid4().hex,
                        id_,
                        rol,
                        nombre_m,
                        m["modelo"],
                        m["esfuerzo"],
                        str(uuid.uuid4()),  # el id de la sesión lo decide el servidor
                        "pendiente",
                        orden,
                        ahora,
                    ),
                )
            self._encargar(db, maquina, id_, "crear")
        p = self.proyecto(id_)
        assert p is not None
        return p

    def _datos_encargo(self, db: sqlite3.Connection, proyecto_id: str) -> dict[str, Any]:
        r = db.execute("SELECT * FROM proyectos WHERE id = ?", (proyecto_id,)).fetchone()
        return {
            "proyecto_id": proyecto_id,
            "nombre": r["nombre"],
            "cuenta": r["cuenta"],
            "plantilla": r["plantilla"],
            "equipo": [
                {k: m[k] for k in ("rol", "nombre", "modelo", "esfuerzo", "session_id")}
                for m in self._miembros(db, proyecto_id)
            ],
        }

    def _encargar(self, db: sqlite3.Connection, maquina: str, proyecto_id: str, tipo: str) -> str:
        id_ = uuid.uuid4().hex
        db.execute(
            """INSERT INTO encargos (id, maquina, proyecto_id, tipo, datos, estado, creado)
            VALUES (?,?,?,?,?,?,?)""",
            (
                id_,
                maquina,
                proyecto_id,
                tipo,
                json.dumps(self._datos_encargo(db, proyecto_id), ensure_ascii=False),
                "pendiente",
                _iso(self.clock()),
            ),
        )
        return id_

    def pausar(self, id_: str) -> dict[str, Any]:
        return self._cambiar(id_, "pausar", ("activo", "error"), "pausando")

    def reanudar(self, id_: str) -> dict[str, Any]:
        return self._cambiar(id_, "reanudar", ("pausado", "error"), "reanudando")

    def _cambiar(self, id_: str, tipo: str, desde: tuple[str, ...], nuevo: str) -> dict[str, Any]:
        with self._lock, self._db() as db:
            r = db.execute("SELECT * FROM proyectos WHERE id = ?", (id_,)).fetchone()
            if r is None:
                raise ProyectoError(404, "No existe ese proyecto.")
            if r["estado"] not in desde:
                raise ProyectoError(409, f"El equipo está {r['estado']}: no se puede {tipo} ahora.")
            # Un error de creación (sin carpeta) no se reanuda: se vuelve a crear.
            if tipo == "reanudar" and r["estado"] == "error" and not self._algun_lanzado(db, id_):
                raise ProyectoError(
                    409, "El proyecto no llegó a crearse: no hay equipo que reanudar."
                )
            db.execute(
                "UPDATE proyectos SET estado = ?, error = NULL, actualizado = ? WHERE id = ?",
                (nuevo, _iso(self.clock()), id_),
            )
            self._encargar(db, r["maquina"], id_, tipo)
        p = self.proyecto(id_)
        assert p is not None
        return p

    @staticmethod
    def _algun_lanzado(db: sqlite3.Connection, id_: str) -> bool:
        return (
            db.execute(
                "SELECT 1 FROM miembros WHERE proyecto_id = ? "
                "AND estado IN ('activo','pausado','detenido')",
                (id_,),
            ).fetchone()
            is not None
        )

    # -- el monitor -------------------------------------------------------------------------

    def encargos_pendientes(self, maquina: str) -> list[dict[str, Any]]:
        """Los encargos de la máquina por hacer (y los tomados hace rato sin respuesta),
        que quedan tomados."""
        ahora = self.clock()
        limite = _iso(ahora - REENTREGA)
        with self._lock, self._db() as db:
            filas = db.execute(
                """SELECT * FROM encargos WHERE maquina = ? AND (estado = 'pendiente'
                    OR (estado = 'en_curso' AND tomado < ?)) ORDER BY creado""",
                (maquina, limite),
            ).fetchall()
            for f in filas:
                db.execute(
                    "UPDATE encargos SET estado = 'en_curso', tomado = ? WHERE id = ?",
                    (_iso(ahora), f["id"]),
                )
        return [
            {
                "id": f["id"],
                "tipo": f["tipo"],
                "proyecto_id": f["proyecto_id"],
                **json.loads(f["datos"]),
            }
            for f in filas
        ]

    def informar_encargo(
        self,
        maquina: str,
        encargo_id: str,
        ok: bool,
        error: str | None,
        ruta: str | None,
        miembros: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ahora = _iso(self.clock())
        with self._lock, self._db() as db:
            e = db.execute("SELECT * FROM encargos WHERE id = ?", (encargo_id,)).fetchone()
            if e is None or e["maquina"] != maquina:
                raise ProyectoError(404, "No existe ese encargo para esta máquina.")
            if e["estado"] in ("hecho", "error"):
                return {"estado": e["estado"]}
            db.execute(
                "UPDATE encargos SET estado = ?, terminado = ?, error = ? WHERE id = ?",
                ("hecho" if ok else "error", ahora, (error or None) and error[:500], encargo_id),
            )
            final = {"crear": "activo", "reanudar": "activo", "pausar": "pausado"}[e["tipo"]]
            db.execute(
                """UPDATE proyectos SET estado = ?, error = ?, ruta = COALESCE(?, ruta),
                    actualizado = ? WHERE id = ?""",
                (
                    final if ok else "error",
                    None if ok else (error or "Falló")[:500],
                    ruta,
                    ahora,
                    e["proyecto_id"],
                ),
            )
            self._actualizar_miembros(db, e["proyecto_id"], miembros)
        return {"estado": "hecho" if ok else "error"}

    def informar_equipos(self, maquina: str, equipos: list[dict[str, Any]]) -> int:
        """Estado de las sesiones que el monitor tiene lanzadas (cada pocos segundos)."""
        n = 0
        with self._lock, self._db() as db:
            for eq in equipos:
                r = db.execute(
                    "SELECT maquina FROM proyectos WHERE id = ?", (str(eq.get("proyecto_id")),)
                ).fetchone()
                if r is None or r["maquina"] != maquina:
                    continue
                n += self._actualizar_miembros(db, str(eq["proyecto_id"]), eq.get("miembros") or [])
        return n

    def _actualizar_miembros(
        self, db: sqlite3.Connection, proyecto_id: str, miembros: list[dict[str, Any]]
    ) -> int:
        n = 0
        ahora = _iso(self.clock())
        for m in miembros:
            estado = m.get("estado")
            if estado not in ("pendiente", "activo", "pausado", "detenido", "error"):
                continue
            n += db.execute(
                "UPDATE miembros SET estado = ?, actualizado = ? "
                "WHERE proyecto_id = ? AND nombre = ?",
                (estado, ahora, proyecto_id, str(m.get("nombre"))),
            ).rowcount
        return n

    def sesiones_lanzadas(self) -> dict[str, dict[str, Any]]:
        """session_id -> modelo, esfuerzo, rol y proyecto (para la oficina)."""
        with self._db() as db:
            filas = db.execute(
                """SELECT m.session_id, m.modelo, m.esfuerzo, m.rol, m.nombre, m.estado,
                    m.actualizado, p.nombre AS proyecto, p.id AS proyecto_id
                FROM miembros m JOIN proyectos p ON p.id = m.proyecto_id
                WHERE m.session_id IS NOT NULL"""
            ).fetchall()
        return {f["session_id"]: dict(f) for f in filas}


# Estados de la oficina de una sesión que terminó (o se está yendo).
_TERMINADA = (12, 21)
EN_ESPERA = {"numero": 18, "nombre": "En espera"}


def vista_lanzada(a: dict[str, Any], lanzada: dict[str, Any] | None) -> dict[str, Any]:
    """La vista de la oficina de una sesión lanzada por un monitor: con su modelo,
    esfuerzo y rol (en -p la oficina no los recibe) y, si el monitor la tiene viva
    pero la oficina la vio terminar (se reanudó o el monitor se reinició y la retomó
    sin escribirle), "En espera" en vez de cerrada hasta que alguien le escriba."""
    if lanzada is None:
        return a
    salida = {
        **a,
        "agente": {
            **a["agente"],
            "modelo": a["agente"].get("modelo") or lanzada["modelo"],
            "esfuerzo": lanzada["esfuerzo"],
            "rol": lanzada["rol"],
            "proyecto_equipo": lanzada["proyecto_id"],
        },
    }
    if lanzada.get("estado") == "activo" and a["estado"]["numero"] in _TERMINADA:
        desde = max(str(a["estado"]["desde"]), str(lanzada.get("actualizado") or ""))
        salida["estado"] = {**EN_ESPERA, "desde": desde}
        salida["cierre"] = None
        salida["en_espera"] = True
    return salida


_registro: ProyectosEquipo | None = None


def get_proyectos_equipo() -> ProyectosEquipo:
    global _registro
    if _registro is None:
        from app.config import get_settings

        _registro = ProyectosEquipo(Path(get_settings().STATE_EVENT_LOG_PATH).parent)
    return _registro


def set_proyectos_equipo(instancia: ProyectosEquipo | None) -> None:
    global _registro
    _registro = instancia

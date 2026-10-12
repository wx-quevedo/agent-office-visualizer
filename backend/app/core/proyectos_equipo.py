"""Proyectos con equipo (etapa 4, Prompts 37 y 38).

Desde la web o la app se crea un proyecto en una máquina: el servidor lo registra
con su equipo (un orquestador y uno o más agentes de código, cada uno con modelo,
esfuerzo, id de sesión y estado) y deja un encargo para el monitor de esa máquina.
El monitor crea la carpeta dentro de su ruta base, lanza las sesiones (claude -p
con stream-json) e informa el resultado. Pausar, reanudar, detener y agregar un
agente también son encargos.

Prompt 38, chat y órdenes: los mensajes de Washington al orquestador viajan como
encargos ("mensaje"); el monitor manda las respuestas del orquestador y las órdenes
que propone. Una orden queda "por aprobar" hasta que Washington la aprueba (tal cual
o editada) o la rechaza con motivo; solo entonces sale un encargo "orden" (o
"rechazo") para el monitor, que la escribe al agente elegido del mismo proyecto. Con
la aprobación automática encendida en el proyecto, la orden sale aprobada sola. El
monitor nunca puede aprobar: solo informa en curso, terminada o fallida.

Estados del proyecto: creando, activo, pausando, pausado, reanudando, deteniendo,
detenido, error.
Estados de un miembro: pendiente, activo, pausado, detenido, error.
Estados de un encargo: pendiente, en_curso, hecho, error.
Estados de una orden: por_aprobar, aprobada, rechazada, en_curso, terminada, fallida.

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

ESQUEMA = 2
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

EstadoProyecto = Literal[
    "creando", "activo", "pausando", "pausado", "reanudando", "deteniendo", "detenido", "error"
]
EstadoOrden = Literal["por_aprobar", "aprobada", "rechazada", "en_curso", "terminada", "fallida"]
# Lo que el monitor puede informar de una orden, y desde qué estado (nunca aprobarla).
DESDE_MONITOR: dict[str, tuple[str, ...]] = {
    "en_curso": ("aprobada",),
    "terminada": ("aprobada", "en_curso"),
    "fallida": ("aprobada", "en_curso"),
}
MAX_MENSAJES = 200
# Estado final del proyecto cuando el monitor termina un encargo de equipo.
FINAL_ENCARGO = {
    "crear": "activo",
    "reanudar": "activo",
    "pausar": "pausado",
    "detener": "detenido",
}

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
    2: [
        """CREATE TABLE IF NOT EXISTS mensajes (
            id TEXT PRIMARY KEY, proyecto_id TEXT NOT NULL REFERENCES proyectos (id),
            autor TEXT NOT NULL, texto TEXT NOT NULL, creado TEXT NOT NULL,
            origen_id TEXT UNIQUE)""",
        "CREATE INDEX IF NOT EXISTS mensajes_proyecto ON mensajes (proyecto_id, creado)",
        """CREATE TABLE IF NOT EXISTS ordenes (
            id TEXT PRIMARY KEY, proyecto_id TEXT NOT NULL REFERENCES proyectos (id),
            numero INTEGER NOT NULL, agente TEXT NOT NULL, texto_propuesto TEXT NOT NULL,
            texto_final TEXT, estimado TEXT, dificultad TEXT, estado TEXT NOT NULL,
            motivo TEXT, decidido_por TEXT, decidido TEXT, resumen TEXT,
            creado TEXT NOT NULL, actualizado TEXT NOT NULL, origen_id TEXT UNIQUE,
            UNIQUE (proyecto_id, numero))""",
        "CREATE INDEX IF NOT EXISTS ordenes_estado ON ordenes (estado, creado)",
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

    def _encargar(
        self,
        db: sqlite3.Connection,
        maquina: str,
        proyecto_id: str,
        tipo: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        id_ = uuid.uuid4().hex
        db.execute(
            """INSERT INTO encargos (id, maquina, proyecto_id, tipo, datos, estado, creado)
            VALUES (?,?,?,?,?,?,?)""",
            (
                id_,
                maquina,
                proyecto_id,
                tipo,
                json.dumps(
                    {**self._datos_encargo(db, proyecto_id), **(extra or {})}, ensure_ascii=False
                ),
                "pendiente",
                _iso(self.clock()),
            ),
        )
        return id_

    def pausar(self, id_: str) -> dict[str, Any]:
        return self._cambiar(id_, "pausar", ("activo", "error"), "pausando")

    def reanudar(self, id_: str) -> dict[str, Any]:
        return self._cambiar(id_, "reanudar", ("pausado", "detenido", "error"), "reanudando")

    def detener(self, id_: str) -> dict[str, Any]:
        """Cierra las sesiones del equipo; la carpeta queda intacta y se puede reanudar."""
        return self._cambiar(id_, "detener", ("activo", "pausado", "error"), "deteniendo")

    def _cambiar(self, id_: str, tipo: str, desde: tuple[str, ...], nuevo: str) -> dict[str, Any]:
        with self._lock, self._db() as db:
            r = db.execute("SELECT * FROM proyectos WHERE id = ?", (id_,)).fetchone()
            if r is None:
                raise ProyectoError(404, "No existe ese proyecto.")
            if r["estado"] not in desde:
                raise ProyectoError(409, f"El equipo está {r['estado']}: no se puede {tipo} ahora.")
            # Un error de creación (sin carpeta) no se reanuda ni se detiene.
            if (
                tipo in ("reanudar", "detener")
                and r["estado"] == "error"
                and not self._algun_lanzado(db, id_)
            ):
                raise ProyectoError(
                    409, f"El proyecto no llegó a crearse: no hay equipo que {tipo}."
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
            final = FINAL_ENCARGO.get(e["tipo"])
            if final is not None:
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
            elif not ok and e["tipo"] == "orden":
                # El monitor no la encoló (agente fuera del proyecto, proyecto que no tiene).
                orden_id = json.loads(e["datos"]).get("orden_id")
                db.execute(
                    """UPDATE ordenes SET estado = 'fallida', motivo = ?, actualizado = ?
                    WHERE id = ? AND estado = 'aprobada'""",
                    ((error or "El monitor no pudo entregarla.")[:500], ahora, orden_id),
                )
            elif not ok and e["tipo"] == "agregar":
                db.execute(
                    "UPDATE proyectos SET error = ?, actualizado = ? WHERE id = ?",
                    ((error or "No se pudo agregar el agente.")[:500], ahora, e["proyecto_id"]),
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

    # -- equipo: interruptor y agentes nuevos (Prompt 38) ----------------------------------

    def _fila_proyecto(self, db: sqlite3.Connection, id_: str) -> sqlite3.Row:
        r = db.execute("SELECT * FROM proyectos WHERE id = ?", (id_,)).fetchone()
        if r is None:
            raise ProyectoError(404, "No existe ese proyecto.")
        return r

    def auto_aprobar(self, id_: str, activo: bool) -> dict[str, Any]:
        """Enciende o apaga la aprobación automática. Solo vale para las órdenes que
        lleguen después: las que ya esperan siguen esperando a Washington."""
        with self._lock, self._db() as db:
            self._fila_proyecto(db, id_)
            db.execute(
                "UPDATE proyectos SET auto_aprobar = ?, actualizado = ? WHERE id = ?",
                (int(activo), _iso(self.clock()), id_),
            )
        p = self.proyecto(id_)
        assert p is not None
        return p

    def agregar_agente(self, id_: str, modelo: str, esfuerzo: str) -> dict[str, Any]:
        if esfuerzo not in ESFUERZOS:
            raise ProyectoError(422, "Esfuerzo desconocido.")
        if not re.fullmatch(r"[A-Za-z0-9.\-\[\]]{2,60}", modelo):
            raise ProyectoError(422, "Modelo desconocido.")
        ahora = _iso(self.clock())
        with self._lock, self._db() as db:
            r = self._fila_proyecto(db, id_)
            if r["estado"] not in ("activo", "pausado", "detenido"):
                raise ProyectoError(
                    409, f"El equipo está {r['estado']}: espera a que termine para agregar."
                )
            miembros = self._miembros(db, id_)
            agentes = [m for m in miembros if m["rol"] == "agente"]
            if len(agentes) >= MAX_AGENTES:
                raise ProyectoError(409, f"El equipo ya tiene {MAX_AGENTES} agentes de código.")
            nombres = {m["nombre"] for m in miembros}
            n = len(agentes) + 1
            while f"agente-{n}" in nombres:
                n += 1
            nombre = f"agente-{n}"
            db.execute(
                """INSERT INTO miembros (id, proyecto_id, rol, nombre, modelo, esfuerzo,
                    session_id, estado, orden, actualizado) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    uuid.uuid4().hex,
                    id_,
                    "agente",
                    nombre,
                    modelo,
                    esfuerzo,
                    str(uuid.uuid4()),
                    "pendiente",
                    max(m["orden"] for m in miembros) + 1,
                    ahora,
                ),
            )
            db.execute(
                "UPDATE proyectos SET error = NULL, actualizado = ? WHERE id = ?", (ahora, id_)
            )
            self._encargar(db, r["maquina"], id_, "agregar", {"miembro": nombre})
        p = self.proyecto(id_)
        assert p is not None
        return p

    # -- chat -------------------------------------------------------------------------------

    def mensajes(self, proyecto_id: str, limite: int = MAX_MENSAJES) -> list[dict[str, Any]]:
        with self._db() as db:
            filas = db.execute(
                """SELECT id, autor, texto, creado FROM mensajes WHERE proyecto_id = ?
                ORDER BY creado DESC, rowid DESC LIMIT ?""",
                (proyecto_id, limite),
            ).fetchall()
        return [dict(f) for f in reversed(filas)]

    def escribir(self, proyecto_id: str, texto: str) -> dict[str, Any]:
        """Un mensaje de Washington al orquestador: queda en el chat y sale como encargo.
        Si el equipo está pausado o detenido, el monitor lo guarda hasta reanudar."""
        texto = texto.strip()
        if not texto:
            raise ProyectoError(422, "Escribe un mensaje.")
        ahora = _iso(self.clock())
        id_ = uuid.uuid4().hex
        with self._lock, self._db() as db:
            r = self._fila_proyecto(db, proyecto_id)
            if r["estado"] == "creando" or (
                r["estado"] == "error" and not self._algun_lanzado(db, proyecto_id)
            ):
                raise ProyectoError(409, "El proyecto todavía no tiene equipo.")
            db.execute(
                "INSERT INTO mensajes (id, proyecto_id, autor, texto, creado) VALUES (?,?,?,?,?)",
                (id_, proyecto_id, "washington", texto, ahora),
            )
            self._encargar(
                db, r["maquina"], proyecto_id, "mensaje", {"mensaje_id": id_, "texto": texto}
            )
        return {"id": id_, "autor": "washington", "texto": texto, "creado": ahora}

    def _de_mi_maquina(self, db: sqlite3.Connection, maquina: str, proyecto_id: str) -> sqlite3.Row:
        r = db.execute("SELECT * FROM proyectos WHERE id = ?", (proyecto_id,)).fetchone()
        if r is None or r["maquina"] != maquina:
            raise ProyectoError(404, "No existe ese proyecto para esta máquina.")
        return r

    def respuesta_orquestador(
        self, maquina: str, proyecto_id: str, origen_id: str, texto: str
    ) -> dict[str, Any]:
        """Lo que respondió el orquestador (lo manda el monitor; repetirlo no duplica)."""
        with self._lock, self._db() as db:
            self._de_mi_maquina(db, maquina, proyecto_id)
            previo = db.execute(
                "SELECT id FROM mensajes WHERE origen_id = ?", (origen_id,)
            ).fetchone()
            if previo is not None:
                return {"id": previo["id"], "repetido": True}
            id_ = uuid.uuid4().hex
            db.execute(
                """INSERT INTO mensajes (id, proyecto_id, autor, texto, creado, origen_id)
                VALUES (?,?,?,?,?,?)""",
                (id_, proyecto_id, "orquestador", texto, _iso(self.clock()), origen_id),
            )
        return {"id": id_, "repetido": False}

    # -- órdenes ------------------------------------------------------------------------------

    @staticmethod
    def _vista_orden(f: sqlite3.Row) -> dict[str, Any]:
        o = dict(f)
        o.pop("origen_id", None)
        o["texto"] = o["texto_final"] or o["texto_propuesto"]
        o["editada"] = o["texto_final"] is not None
        return o

    _SELECT_ORDEN = """SELECT o.*, p.nombre AS proyecto FROM ordenes o
        JOIN proyectos p ON p.id = o.proyecto_id"""

    def orden(self, id_: str) -> dict[str, Any] | None:
        with self._db() as db:
            f = db.execute(f"{self._SELECT_ORDEN} WHERE o.id = ?", (id_,)).fetchone()
        return self._vista_orden(f) if f is not None else None

    def ordenes(
        self, proyecto_id: str | None = None, estado: str | None = None, limite: int = 200
    ) -> list[dict[str, Any]]:
        """Las órdenes, las más nuevas primero (de un proyecto o de todos)."""
        donde: list[str] = []
        args: list[Any] = []
        if proyecto_id is not None:
            donde.append("o.proyecto_id = ?")
            args.append(proyecto_id)
        if estado is not None:
            donde.append("o.estado = ?")
            args.append(estado)
        sql = self._SELECT_ORDEN + (f" WHERE {' AND '.join(donde)}" if donde else "")
        with self._db() as db:
            filas = db.execute(
                f"{sql} ORDER BY o.creado DESC, o.numero DESC LIMIT ?", (*args, limite)
            ).fetchall()
        return [self._vista_orden(f) for f in filas]

    def por_aprobar(self) -> dict[str, int]:
        """proyecto_id -> cuántas órdenes esperan a Washington."""
        with self._db() as db:
            return {
                r[0]: int(r[1])
                for r in db.execute(
                    "SELECT proyecto_id, COUNT(*) FROM ordenes "
                    "WHERE estado = 'por_aprobar' GROUP BY proyecto_id"
                )
            }

    def proponer_orden(
        self,
        maquina: str,
        proyecto_id: str,
        origen_id: str,
        agente: str,
        texto: str,
        estimado: str | None = None,
        dificultad: str | None = None,
    ) -> dict[str, Any]:
        """Una orden que propuso el orquestador (la manda el monitor). Queda por aprobar,
        salvo con la aprobación automática encendida. Solo para un agente de código de
        ese mismo proyecto."""
        texto = texto.strip()
        if not texto:
            raise ProyectoError(422, "La orden está vacía.")
        ahora = _iso(self.clock())
        with self._lock, self._db() as db:
            r = self._de_mi_maquina(db, maquina, proyecto_id)
            previo = db.execute(
                "SELECT id FROM ordenes WHERE origen_id = ?", (origen_id,)
            ).fetchone()
            if previo is not None:
                o = db.execute(f"{self._SELECT_ORDEN} WHERE o.id = ?", (previo["id"],)).fetchone()
                return self._vista_orden(o)
            destino = db.execute(
                "SELECT 1 FROM miembros WHERE proyecto_id = ? AND nombre = ? AND rol = 'agente'",
                (proyecto_id, agente),
            ).fetchone()
            if destino is None:
                raise ProyectoError(422, f"{agente} no es un agente de código de este proyecto.")
            numero = int(
                db.execute(
                    "SELECT COALESCE(MAX(numero), 0) + 1 FROM ordenes WHERE proyecto_id = ?",
                    (proyecto_id,),
                ).fetchone()[0]
            )
            auto = bool(r["auto_aprobar"])
            id_ = uuid.uuid4().hex
            db.execute(
                """INSERT INTO ordenes (id, proyecto_id, numero, agente, texto_propuesto,
                    estimado, dificultad, estado, decidido_por, decidido, creado, actualizado,
                    origen_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    id_,
                    proyecto_id,
                    numero,
                    agente,
                    texto,
                    (estimado or None) and estimado[:60],
                    (dificultad or None) and dificultad[:60],
                    "aprobada" if auto else "por_aprobar",
                    "automatico" if auto else None,
                    ahora if auto else None,
                    ahora,
                    ahora,
                    origen_id,
                ),
            )
            if auto:
                self._encargar_orden(db, r["maquina"], id_)
            o = db.execute(f"{self._SELECT_ORDEN} WHERE o.id = ?", (id_,)).fetchone()
        return self._vista_orden(o)

    def _encargar_orden(self, db: sqlite3.Connection, maquina: str, orden_id: str) -> None:
        o = db.execute("SELECT * FROM ordenes WHERE id = ?", (orden_id,)).fetchone()
        self._encargar(
            db,
            maquina,
            o["proyecto_id"],
            "orden",
            {
                "orden_id": o["id"],
                "numero": o["numero"],
                "agente": o["agente"],
                "texto": o["texto_final"] or o["texto_propuesto"],
            },
        )

    def _por_decidir(self, db: sqlite3.Connection, id_: str) -> sqlite3.Row:
        o = db.execute("SELECT * FROM ordenes WHERE id = ?", (id_,)).fetchone()
        if o is None:
            raise ProyectoError(404, "No existe esa orden.")
        if o["estado"] != "por_aprobar":
            raise ProyectoError(409, "Esa orden ya se decidió.")
        return o

    def aprobar(self, id_: str, texto: str | None, dispositivo: str) -> dict[str, Any]:
        """Aprueba una orden, tal cual o con el texto editado, y sale para el monitor."""
        ahora = _iso(self.clock())
        with self._lock, self._db() as db:
            o = self._por_decidir(db, id_)
            final = texto.strip() if texto is not None else None
            if final is not None and not final:
                raise ProyectoError(422, "La orden editada quedó vacía.")
            if final == o["texto_propuesto"]:
                final = None
            db.execute(
                """UPDATE ordenes SET estado = 'aprobada', texto_final = ?, decidido_por = ?,
                    decidido = ?, actualizado = ? WHERE id = ?""",
                (final, dispositivo, ahora, ahora, id_),
            )
            r = self._fila_proyecto(db, o["proyecto_id"])
            self._encargar_orden(db, r["maquina"], id_)
        v = self.orden(id_)
        assert v is not None
        return v

    def rechazar(self, id_: str, motivo: str, dispositivo: str) -> dict[str, Any]:
        """Rechaza una orden con su motivo; el monitor se lo cuenta al orquestador."""
        motivo = motivo.strip()
        if not motivo:
            raise ProyectoError(422, "Escribe el motivo del rechazo.")
        ahora = _iso(self.clock())
        with self._lock, self._db() as db:
            o = self._por_decidir(db, id_)
            db.execute(
                """UPDATE ordenes SET estado = 'rechazada', motivo = ?, decidido_por = ?,
                    decidido = ?, actualizado = ? WHERE id = ?""",
                (motivo[:500], dispositivo, ahora, ahora, id_),
            )
            r = self._fila_proyecto(db, o["proyecto_id"])
            self._encargar(
                db,
                r["maquina"],
                o["proyecto_id"],
                "rechazo",
                {
                    "orden_id": id_,
                    "numero": o["numero"],
                    "agente": o["agente"],
                    "motivo": motivo[:500],
                },
            )
        v = self.orden(id_)
        assert v is not None
        return v

    def informar_orden(
        self, maquina: str, id_: str, estado: str, resumen: str | None
    ) -> dict[str, Any]:
        """El monitor informa que la orden está en curso, terminada o fallida."""
        if estado not in DESDE_MONITOR:
            raise ProyectoError(422, "Estado de orden no válido.")
        with self._lock, self._db() as db:
            o = db.execute("SELECT * FROM ordenes WHERE id = ?", (id_,)).fetchone()
            if o is None:
                raise ProyectoError(404, "No existe esa orden.")
            self._de_mi_maquina(db, maquina, o["proyecto_id"])
            if o["estado"] == estado:
                return {"estado": estado}
            if o["estado"] not in DESDE_MONITOR[estado]:
                raise ProyectoError(409, f"La orden está {o['estado']}: no pasa a {estado}.")
            db.execute(
                """UPDATE ordenes SET estado = ?, resumen = COALESCE(?, resumen),
                    actualizado = ? WHERE id = ?""",
                (estado, (resumen or None) and resumen[:4000], _iso(self.clock()), id_),
            )
        return {"estado": estado}

    def decisiones(self, ahora: datetime) -> list[dict[str, Any]]:
        """Las órdenes por aprobar como elementos de la bandeja de Decisiones."""
        with self._db() as db:
            filas = db.execute(
                f"""{self._SELECT_ORDEN} WHERE o.estado = 'por_aprobar'
                ORDER BY o.creado, o.numero"""
            ).fetchall()
            orquestadores = {
                r["proyecto_id"]: r["session_id"]
                for r in db.execute(
                    "SELECT proyecto_id, session_id FROM miembros WHERE rol = 'orquestador'"
                )
            }
            proyectos = {
                r["id"]: dict(r)
                for r in db.execute("SELECT id, ruta, cuenta, maquina FROM proyectos")
            }
        salida: list[dict[str, Any]] = []
        for f in filas:
            o = self._vista_orden(f)
            p = proyectos.get(o["proyecto_id"], {})
            creado = datetime.fromisoformat(o["creado"])
            primera = o["texto"].strip().splitlines()[0] if o["texto"].strip() else ""
            salida.append(
                {
                    "tipo": "orden",
                    "id": o["id"],
                    "session_id": orquestadores.get(o["proyecto_id"]) or "",
                    "proyecto": o["proyecto"],
                    "carpeta": p.get("ruta"),
                    "cuenta": p.get("cuenta"),
                    "maquina": p.get("maquina"),
                    "desde": o["creado"],
                    "hace_s": max(0, int((ahora - creado).total_seconds())),
                    "resumen": f"Orden {o['numero']} para {o['agente']}: {primera[:160]}",
                    "detalle": o["texto"],
                    "orden": o,
                }
            )
        return salida


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

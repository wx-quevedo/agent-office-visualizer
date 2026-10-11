"""Bandejas de Decisiones e Ideas (etapa 3, Prompt 33).

Decisiones: lo que espera a Washington, lo más urgente arriba (permisos, luego
preguntas, luego atascos; dentro de cada tipo, lo que espera hace más tiempo),
con la frase del agente auxiliar si existe y el detalle técnico. Más lo resuelto
hoy: quién, cómo y cuándo.

- Permisos: los del registro de permisos (se aprueban o rechazan con la ruta de
  siempre). Las resoluciones salen de su registro (``permisos.db``).
- Preguntas (AskUserQuestion o una pregunta al final del turno): solo lectura.
  Claude Code documenta cómo contestarlas desde un hook PreToolUse, pero en esta
  instalación no es confiable (ver PROJECT.md), así que se responden en la PC.
  Cuando una pregunta deja de estar pendiente se anota como respondida.
- Atascos: "Ya lo vi" los saca de la bandeja sin tocar al agente.

Ideas: texto, proyecto (o ninguno), origen (dictada o escrita), fecha y estado
(nueva, asignada, archivada).

Todo vive en ``bandejas.db`` junto a los demás datos del backend (el respaldo
copia cada ``.db``), con versión de esquema (``PRAGMA user_version``).
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

Tipo = Literal["permiso", "pregunta", "atasco"]
EstadoIdea = Literal["nueva", "asignada", "archivada"]
Origen = Literal["dictada", "escrita"]

ORDEN: dict[str, int] = {"permiso": 0, "pregunta": 1, "atasco": 2}
ESQUEMA = 1
MAX_TEXTO_IDEA = 2000
MAX_PROYECTO = 200
_PREGUNTAS = frozenset({"AskUserQuestion", "ExitPlanMode"})
DISPOSITIVOS = {"pc": "PC", "celular": "celular", "app": "app iOS"}

_MIGRACIONES: dict[int, list[str]] = {
    1: [
        """CREATE TABLE IF NOT EXISTS ideas (
            id TEXT PRIMARY KEY, texto TEXT NOT NULL, proyecto TEXT,
            origen TEXT NOT NULL, estado TEXT NOT NULL,
            creada TEXT NOT NULL, actualizada TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS ideas_creada ON ideas (creada)",
        """CREATE TABLE IF NOT EXISTS atascos_vistos (
            clave TEXT PRIMARY KEY, session_id TEXT, proyecto TEXT, cuenta TEXT,
            maquina TEXT, motivo TEXT, resumen TEXT, desde TEXT, visto TEXT NOT NULL,
            dispositivo TEXT)""",
        """CREATE TABLE IF NOT EXISTS preguntas (
            clave TEXT PRIMARY KEY, session_id TEXT, proyecto TEXT, cuenta TEXT,
            maquina TEXT, texto TEXT, resumen TEXT, creada TEXT NOT NULL,
            resuelta TEXT, como TEXT)""",
        "CREATE INDEX IF NOT EXISTS preguntas_resuelta ON preguntas (resuelta)",
    ],
}


def _d(valor: Any) -> dict[str, Any]:
    """Un dict tipado (o vacío) para leer campos opcionales de la vista del agente."""
    return cast(dict[str, Any], valor) if isinstance(valor, dict) else {}


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def nombre_proyecto(carpeta: str | None) -> str | None:
    if not carpeta:
        return None
    partes = [p for p in carpeta.replace("\\", "/").split("/") if p]
    return partes[-1] if partes else carpeta


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat()


def _fecha(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def clave_atasco(a: dict[str, Any]) -> str | None:
    at = _d(a.get("atasco"))
    if not at:
        return None
    return f"{a['agente']['session_id']}:atasco:{at.get('tipo')}:{at.get('desde')}"


def es_pregunta(a: dict[str, Any]) -> bool:
    """El agente espera tu respuesta a una pregunta (14, o un 13 de AskUserQuestion)."""
    numero = a["estado"]["numero"]
    if numero == 14:
        return True
    if numero != 13:
        return False
    ev = _d(_d(a.get("espera")).get("evidencia"))
    herramienta = _d(a.get("permiso")).get("herramienta") or ev.get("herramienta")
    return herramienta in _PREGUNTAS or bool(a.get("pregunta_opciones"))


def clave_pregunta(a: dict[str, Any]) -> str:
    texto = a.get("pregunta_pendiente") or a["estado"]["desde"]
    return f"{a['agente']['session_id']}:pregunta:{_huella(str(texto))}"


def _resumen(a: dict[str, Any], *tipos: str) -> str | None:
    res = _d(a.get("resumenes"))
    for t in tipos:
        r = _d(res.get(t))
        if r.get("estado") == "listo" and r.get("texto"):
            return str(r["texto"])
    return None


def _base(a: dict[str, Any], tipo: str, desde: datetime, ahora: datetime) -> dict[str, Any]:
    ag = a["agente"]
    return {
        "tipo": tipo,
        "session_id": ag["session_id"],
        "proyecto": nombre_proyecto(ag.get("proyecto")),
        "carpeta": ag.get("proyecto"),
        "cuenta": ag.get("cuenta"),
        "maquina": ag.get("maquina"),
        "desde": _iso(desde),
        "hace_s": max(0, int((ahora - desde).total_seconds())),
    }


def pendientes(
    agentes: list[dict[str, Any]], vistos: set[str], ahora: datetime
) -> list[dict[str, Any]]:
    """La bandeja de decisiones, lo más urgente arriba. Puro (para las pruebas)."""
    salida: list[dict[str, Any]] = []
    for a in agentes:
        numero = a["estado"]["numero"]
        desde_estado = _fecha(a["estado"].get("desde")) or ahora
        if es_pregunta(a):
            permiso = _d(a.get("permiso"))
            creada = _fecha(permiso.get("creada")) if numero == 13 else None
            item = _base(a, "pregunta", creada or desde_estado, ahora)
            item.update(
                {
                    "id": clave_pregunta(a),
                    "resumen": _resumen(a, "pregunta", "permiso"),
                    "detalle": a.get("pregunta_pendiente"),
                    "pregunta": {
                        "texto": a.get("pregunta_pendiente"),
                        "preguntas": a.get("pregunta_opciones") or [],
                        # Solo lectura: se responde en la PC (ver PROJECT.md).
                        "responder_en": "pc",
                    },
                }
            )
            salida.append(item)
        elif numero == 13:
            permiso = a.get("permiso")
            ev = _d(_d(a.get("espera")).get("evidencia"))
            p = _d(permiso)
            desde = _fecha(p.get("creada")) or desde_estado
            item = _base(a, "permiso", desde, ahora)
            item.update(
                {
                    "id": p.get("id")
                    or f"{a['agente']['session_id']}:permiso:{a['estado']['desde']}",
                    "resumen": _resumen(a, "permiso"),
                    "detalle": p.get("detalle") or ev.get("comando"),
                    "permiso": {
                        "id": p.get("id"),
                        "herramienta": p.get("herramienta") or ev.get("herramienta"),
                        # Solo con la solicitud esperando se decide desde aquí.
                        "esperando": bool(p.get("esperando")),
                        "segundos_restantes": int(p.get("segundos_restantes") or 0),
                        "estado": p.get("estado"),
                    },
                }
            )
            salida.append(item)
        clave = clave_atasco(a)
        if clave and clave not in vistos and numero != 21:
            at = _d(a["atasco"])
            intentos = cast(list[Any], at.get("ultimos_intentos") or [])
            item = _base(a, "atasco", _fecha(at.get("desde")) or desde_estado, ahora)
            item.update(
                {
                    "id": clave,
                    "resumen": _resumen(a, "atasco"),
                    "detalle": at.get("motivo"),
                    "atasco": {
                        "tipo": at.get("tipo"),
                        "motivo": at.get("motivo"),
                        "ultimo_intento": intentos[-1] if intentos else None,
                        "ultimo_error": at.get("ultimo_error"),
                    },
                }
            )
            salida.append(item)
    salida.sort(key=lambda i: (ORDEN[i["tipo"]], i["desde"], i["id"]))
    return salida


def _como_permiso(estado: str) -> str:
    return {
        "aprobada": "Aprobado",
        "rechazada": "Rechazado",
        "resuelta_fuera": "Respondido en la PC",
        "vencida": "Se venció; respondido en la PC",
    }.get(estado, estado)


class Bandejas:
    def __init__(
        self,
        carpeta: Path,
        clock: Callable[[], datetime] | None = None,
        zona: str = "America/Guayaquil",
    ) -> None:
        carpeta.mkdir(parents=True, exist_ok=True)
        self.ruta = carpeta / "bandejas.db"
        self.ruta_permisos = carpeta / "permisos.db"
        self.clock = clock or (lambda: datetime.now(UTC))
        self.zona = ZoneInfo(zona)
        self._lock = threading.Lock()
        self._migrar()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.ruta)
        db.row_factory = sqlite3.Row
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

    def inicio_de_hoy(self) -> datetime:
        hoy = self.clock().astimezone(self.zona).date()
        return datetime.combine(hoy, time.min, self.zona).astimezone(UTC)

    # -- atascos ------------------------------------------------------------------

    def vistos(self) -> set[str]:
        with self._db() as db:
            return {r[0] for r in db.execute("SELECT clave FROM atascos_vistos")}

    def marcar_visto(self, item: dict[str, Any], dispositivo: str) -> dict[str, Any]:
        ahora = self.clock()
        with self._lock, self._db() as db:
            db.execute(
                """INSERT OR IGNORE INTO atascos_vistos (clave, session_id, proyecto, cuenta,
                    maquina, motivo, resumen, desde, visto, dispositivo)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    item["id"],
                    item["session_id"],
                    item.get("proyecto"),
                    item.get("cuenta"),
                    item.get("maquina"),
                    item.get("detalle"),
                    item.get("resumen"),
                    item.get("desde"),
                    _iso(ahora),
                    dispositivo,
                ),
            )
        return {"id": item["id"], "visto": _iso(ahora)}

    # -- preguntas: se anotan pendientes y, al irse, como respondidas ---------------

    def sincronizar(self, items: list[dict[str, Any]], agentes: list[dict[str, Any]]) -> None:
        ahora = _iso(self.clock())
        actuales = {i["id"]: i for i in items if i["tipo"] == "pregunta"}
        cerradas = {a["agente"]["session_id"] for a in agentes if a["estado"]["numero"] in (12, 21)}
        with self._lock, self._db() as db:
            abiertas = {
                r["clave"]: r["session_id"]
                for r in db.execute(
                    "SELECT clave, session_id FROM preguntas WHERE resuelta IS NULL"
                )
            }
            for clave, i in actuales.items():
                if clave in abiertas:
                    if i.get("resumen"):
                        db.execute(
                            "UPDATE preguntas SET resumen = ? WHERE clave = ?",
                            (i["resumen"], clave),
                        )
                    continue
                db.execute(
                    """INSERT OR IGNORE INTO preguntas (clave, session_id, proyecto, cuenta,
                        maquina, texto, resumen, creada) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        clave,
                        i["session_id"],
                        i.get("proyecto"),
                        i.get("cuenta"),
                        i.get("maquina"),
                        i.get("detalle"),
                        i.get("resumen"),
                        i["desde"],
                    ),
                )
            for clave, sid in abiertas.items():
                if clave in actuales:
                    continue
                como = "La sesión se cerró" if sid in cerradas else "Respondida en la PC"
                db.execute(
                    "UPDATE preguntas SET resuelta = ?, como = ? WHERE clave = ?",
                    (ahora, como, clave),
                )

    # -- resueltas de hoy -----------------------------------------------------------------

    def resueltas_hoy(self) -> list[dict[str, Any]]:
        desde = _iso(self.inicio_de_hoy())
        salida: list[dict[str, Any]] = []
        with self._db() as db:
            for r in db.execute(
                "SELECT * FROM preguntas WHERE resuelta >= ? ORDER BY resuelta DESC", (desde,)
            ):
                salida.append(
                    {
                        "tipo": "pregunta",
                        "id": r["clave"],
                        "proyecto": r["proyecto"],
                        "cuenta": r["cuenta"],
                        "maquina": r["maquina"],
                        "texto": r["resumen"] or r["texto"],
                        "como": r["como"],
                        "quien": "PC",
                        "cuando": r["resuelta"],
                    }
                )
            for r in db.execute(
                "SELECT * FROM atascos_vistos WHERE visto >= ? ORDER BY visto DESC", (desde,)
            ):
                salida.append(
                    {
                        "tipo": "atasco",
                        "id": r["clave"],
                        "proyecto": r["proyecto"],
                        "cuenta": r["cuenta"],
                        "maquina": r["maquina"],
                        "texto": r["resumen"] or r["motivo"],
                        "como": "Ya lo vi",
                        "quien": DISPOSITIVOS.get(r["dispositivo"] or "", r["dispositivo"]),
                        "cuando": r["visto"],
                    }
                )
        if self.ruta_permisos.is_file():
            with sqlite3.connect(self.ruta_permisos) as db:
                db.row_factory = sqlite3.Row
                filas = db.execute(
                    """SELECT * FROM permisos WHERE decidida >= ? AND estado != 'pendiente'
                    ORDER BY decidida DESC""",
                    (desde,),
                ).fetchall()
            for r in filas:
                if r["herramienta"] in _PREGUNTAS:
                    continue  # una pregunta, no un permiso: ya está como pregunta
                dispositivo = r["dispositivo"]
                quien = (
                    DISPOSITIVOS.get(dispositivo, dispositivo)
                    if r["estado"] in ("aprobada", "rechazada") and dispositivo
                    else "PC"
                )
                salida.append(
                    {
                        "tipo": "permiso",
                        "id": r["id"],
                        "proyecto": r["proyecto"],
                        "cuenta": r["cuenta"],
                        "maquina": r["machine_id"],
                        "texto": f"{r['herramienta']}: {r['detalle']}"[:300],
                        "como": _como_permiso(r["estado"]),
                        "motivo": r["motivo"],
                        "quien": quien,
                        "cuando": r["decidida"],
                    }
                )
        salida.sort(key=lambda i: i["cuando"] or "", reverse=True)
        return salida

    # -- ideas -------------------------------------------------------------------------------

    @staticmethod
    def _idea(r: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": r["id"],
            "texto": r["texto"],
            "proyecto": r["proyecto"],
            "origen": r["origen"],
            "estado": r["estado"],
            "creada": r["creada"],
            "actualizada": r["actualizada"],
        }

    def ideas(self, archivadas: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM ideas"
        if not archivadas:
            sql += " WHERE estado != 'archivada'"
        with self._db() as db:
            return [self._idea(r) for r in db.execute(sql + " ORDER BY creada DESC")]

    def idea(self, id_: str) -> dict[str, Any] | None:
        with self._db() as db:
            r = db.execute("SELECT * FROM ideas WHERE id = ?", (id_,)).fetchone()
        return self._idea(r) if r else None

    def crear_idea(self, texto: str, proyecto: str | None, origen: str) -> dict[str, Any]:
        texto = texto.strip()[:MAX_TEXTO_IDEA]
        if not texto:
            raise ValueError("La idea no puede estar vacía.")
        proyecto = (proyecto or "").strip()[:MAX_PROYECTO] or None
        ahora = _iso(self.clock())
        id_ = uuid.uuid4().hex
        with self._lock, self._db() as db:
            db.execute(
                """INSERT INTO ideas (id, texto, proyecto, origen, estado, creada, actualizada)
                VALUES (?,?,?,?,?,?,?)""",
                (id_, texto, proyecto, origen, "asignada" if proyecto else "nueva", ahora, ahora),
            )
        idea = self.idea(id_)
        assert idea is not None
        return idea

    def cambiar_idea(
        self, id_: str, *, proyecto: str | None | Literal[False] = False, texto: str | None = None
    ) -> dict[str, Any] | None:
        """Cambia el proyecto (``None`` = sin proyecto) o el texto. Una idea archivada
        sigue archivada; las demás quedan asignada o nueva según su proyecto."""
        actual = self.idea(id_)
        if actual is None:
            return None
        nuevo_texto = actual["texto"] if texto is None else texto.strip()[:MAX_TEXTO_IDEA]
        if not nuevo_texto:
            raise ValueError("La idea no puede estar vacía.")
        nuevo_proyecto = (
            actual["proyecto"]
            if proyecto is False
            else ((proyecto or "").strip()[:MAX_PROYECTO] or None)
        )
        estado = actual["estado"]
        if estado != "archivada":
            estado = "asignada" if nuevo_proyecto else "nueva"
        with self._lock, self._db() as db:
            db.execute(
                """UPDATE ideas SET texto = ?, proyecto = ?, estado = ?, actualizada = ?
                WHERE id = ?""",
                (nuevo_texto, nuevo_proyecto, estado, _iso(self.clock()), id_),
            )
        return self.idea(id_)

    def archivar_idea(self, id_: str, archivar: bool = True) -> dict[str, Any] | None:
        actual = self.idea(id_)
        if actual is None:
            return None
        estado = "archivada" if archivar else ("asignada" if actual["proyecto"] else "nueva")
        with self._lock, self._db() as db:
            db.execute(
                "UPDATE ideas SET estado = ?, actualizada = ? WHERE id = ?",
                (estado, _iso(self.clock()), id_),
            )
        return self.idea(id_)


_bandejas: Bandejas | None = None


def get_bandejas() -> Bandejas:
    global _bandejas
    if _bandejas is None:
        from app.config import get_settings

        s = get_settings()
        _bandejas = Bandejas(Path(s.STATE_EVENT_LOG_PATH).parent, zona=s.ZONA_HORARIA)
    return _bandejas


def set_bandejas(instancia: Bandejas | None) -> None:
    global _bandejas
    _bandejas = instancia

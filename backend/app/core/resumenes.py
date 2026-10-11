"""Avisos resumidos (etapa 2.4).

El monitor de cada máquina resume cada aviso con un agente auxiliar (Claude Code
con Haiku, aislado) y manda la frase. Aquí:

- ``avisos_del_agente``: los avisos vigentes de un agente (permiso pendiente,
  pregunta, tarea terminada, atasco), cada uno con una clave estable y los datos
  que necesita el auxiliar. Puro.
- ``Resumenes``: las frases recibidas por clave, el interruptor de los resúmenes
  (encendido por defecto) y el consumo del auxiliar (tokens y tiempo por cuenta),
  separado del de los agentes.
- ``es_auxiliar``: un evento que viene de la carpeta del auxiliar no entra a la
  oficina (el auxiliar corre sin hooks; esto es la segunda barrera).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from app.core.secretos import enmascarar

logger = logging.getLogger(__name__)

CARPETA_AUXILIAR = "/.visualizador-monitor/auxiliar"
TIPOS = ("permiso", "pregunta", "termino", "atasco")
# Herramientas que esperan tu respuesta, no tu permiso.
_PREGUNTAS = frozenset({"AskUserQuestion", "ExitPlanMode"})
# Una tarea terminada se resume solo si es reciente (no al reiniciar el monitor).
TERMINO_RECIENTE = timedelta(minutes=3)
_MAX_RESUMENES = 2000
_MAX_TEXTO = 400


def es_auxiliar(*rutas: str | None) -> bool:
    """Alguna de las rutas (carpeta, cwd, transcripción) es la del auxiliar."""
    for r in rutas:
        if isinstance(r, str) and r:
            norm = r.replace("\\", "/").lower().rstrip("/") + "/"
            if CARPETA_AUXILIAR + "/" in norm:
                return True
    return False


def _corto(texto: Any, largo: int = _MAX_TEXTO) -> str | None:
    """Una línea recortada y sin secretos (lo que sale hacia el monitor)."""
    if not isinstance(texto, str):
        return None
    t = enmascarar(" ".join(texto.split()))
    return (t[: largo - 1] + "…") if len(t) > largo else (t or None)


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def nombre_proyecto(carpeta: str | None) -> str:
    if not carpeta:
        return "Sin proyecto"
    partes = [p for p in carpeta.replace("\\", "/").split("/") if p]
    return partes[-1] if partes else carpeta


def avisos_del_agente(
    a: dict[str, Any],
    permiso: dict[str, Any] | None = None,
    ultimo_turno: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Los avisos vigentes del agente, con su clave y los datos para resumirlos."""
    sid = str(a["agente"]["session_id"])
    estado = a["estado"]
    numero = int(estado["numero"])
    salida: list[dict[str, Any]] = []

    def aviso(tipo: str, clave: str, datos: dict[str, Any], como: str | None = None) -> None:
        salida.append(
            {
                "tipo": tipo,
                "clave": f"{sid}:{tipo}:{clave}",
                "datos": {k: v for k, v in datos.items() if v},
                **({"como": como} if como else {}),
            }
        )

    if numero == 13:
        espera = cast(dict[str, Any], a.get("espera") or {})
        ev = cast(dict[str, Any], espera.get("evidencia") or {})
        herramienta = (permiso or {}).get("herramienta") or ev.get("herramienta")
        detalle = (permiso or {}).get("detalle") or ev.get("comando")
        clave = (permiso or {}).get("id") or estado["desde"]
        if herramienta in _PREGUNTAS:
            # Espera tu respuesta a una pregunta (AskUserQuestion): para la oficina
            # es un 13, pero el auxiliar la resume como pregunta.
            texto = a.get("pregunta_pendiente") or detalle
            aviso("permiso", str(clave), {"pregunta": _corto(texto)}, como="pregunta")
        else:
            aviso(
                "permiso",
                str(clave),
                {"herramienta": _corto(herramienta, 80), "detalle": _corto(detalle)},
            )
    pregunta = a.get("pregunta_pendiente")
    if isinstance(pregunta, str) and pregunta.strip() and numero in (14, 21):
        aviso("pregunta", _huella(pregunta), {"pregunta": _corto(pregunta)})
    if numero == 11 and not pregunta:
        t = ultimo_turno or {}
        aviso(
            "termino",
            str(estado["desde"]),
            {
                "pedido": _corto(t.get("pedido"), 200),
                "archivos_editados": len(t.get("archivos_editados") or []) or None,
                "commits": len(t.get("commits") or []) or None,
            },
        )
    atasco = cast(dict[str, Any] | None, a.get("atasco"))
    if isinstance(atasco, dict) and atasco.get("motivo"):
        intentos = cast(list[Any], atasco.get("ultimos_intentos") or [])
        aviso(
            "atasco",
            f"{atasco.get('tipo')}:{atasco.get('desde')}",
            {
                "motivo": _corto(atasco.get("motivo")),
                "ultimo_error": _corto(atasco.get("ultimo_error"), 200),
                "ultimo_intento": _corto(intentos[-1] if intentos else None, 120),
            },
        )
    return salida


class Resumenes:
    """Frases por clave, interruptor y consumo del auxiliar (persistidos en ``carpeta``)."""

    def __init__(self, carpeta: Path | None) -> None:
        self.carpeta = carpeta
        self._lock = threading.Lock()
        self._frases: dict[str, dict[str, Any]] = {}
        self.activos = True
        if carpeta is not None:
            try:
                c = json.loads((carpeta / "avisos.json").read_text(encoding="utf-8"))
                self.activos = bool(c.get("resumenes", True))
            except (OSError, ValueError, AttributeError):
                pass

    # -- interruptor ---------------------------------------------------------------

    def config(self) -> dict[str, Any]:
        return {"resumenes": self.activos}

    def cambiar(self, activos: bool) -> dict[str, Any]:
        with self._lock:
            self.activos = activos
            if self.carpeta is not None:
                try:
                    self.carpeta.mkdir(parents=True, exist_ok=True)
                    (self.carpeta / "avisos.json").write_text(
                        json.dumps({"resumenes": activos}), encoding="utf-8"
                    )
                except OSError:
                    logger.exception("No se pudo guardar la configuración de avisos")
        return self.config()

    # -- frases ----------------------------------------------------------------------

    def registrar(
        self,
        clave: str,
        texto: str | None,
        maquina: str,
        metricas: dict[str, Any],
        ahora: datetime | None = None,
    ) -> dict[str, Any]:
        ahora = ahora or datetime.now(UTC)
        previa = self.obtener(clave)
        if previa is not None and previa["estado"] == "listo":
            return previa  # una frase lista no se reemplaza
        limpio = _corto(texto, 300)
        if limpio is not None and limpio != " ".join((texto or "").split())[:300]:
            limpio = None  # la frase traía algo con forma de secreto
        fila = {
            "clave": clave,
            "texto": limpio,
            "estado": "listo" if limpio else "fallo",
            "motivo": _corto(metricas.get("motivo"), 80),
            "recibido": ahora.isoformat(),
        }
        with self._lock:
            self._frases[clave] = fila
            if len(self._frases) > _MAX_RESUMENES:
                for k in list(self._frases)[: len(self._frases) - _MAX_RESUMENES]:
                    del self._frases[k]
        if metricas.get("llamo"):
            self._anotar_consumo(ahora, maquina, metricas, fila["estado"] == "listo")
        return fila

    def obtener(self, clave: str) -> dict[str, Any] | None:
        with self._lock:
            return self._frases.get(clave)

    def vista(self, avisos: list[dict[str, Any]]) -> dict[str, Any]:
        """Para cada tipo de aviso vigente: su clave, estado y frase."""
        salida: dict[str, Any] = {}
        for av in avisos:
            fila = self.obtener(av["clave"])
            if not self.activos:
                estado, texto = "apagado", None
            elif fila is None:
                estado, texto = "pendiente", None
            else:
                estado, texto = fila["estado"], fila["texto"]
            salida[av["tipo"]] = {"clave": av["clave"], "estado": estado, "texto": texto}
        return salida

    # -- consumo ---------------------------------------------------------------------

    def _anotar_consumo(self, ahora: datetime, maquina: str, m: dict[str, Any], ok: bool) -> None:
        def entero(v: Any) -> int:
            return int(v) if isinstance(v, (int, float)) and v >= 0 else 0

        fila = {
            "ts": ahora.isoformat(),
            "maquina": maquina,
            "cuenta": str(m.get("cuenta") or "desconocida")[:40],
            "modelo": str(m.get("modelo") or "")[:60] or None,
            "tokens_entrada": entero(m.get("tokens_entrada")),
            "tokens_salida": entero(m.get("tokens_salida")),
            "segundos": round(float(m.get("segundos") or 0), 2),
            "costo_usd": round(float(m.get("costo_usd") or 0), 6),
            "ok": ok,
        }
        if self.carpeta is None:
            return
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            with (self.carpeta / "auxiliar.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("No se pudo anotar el consumo del auxiliar")

    def consumo(self, desde: datetime, hasta: datetime) -> dict[str, Any]:
        """Tokens y tiempo del auxiliar entre dos horas, total y por cuenta."""
        filas: list[dict[str, Any]] = []
        if self.carpeta is not None:
            try:
                with (self.carpeta / "auxiliar.jsonl").open(encoding="utf-8") as f:
                    for linea in f:
                        try:
                            fila = json.loads(linea)
                            ts = datetime.fromisoformat(fila["ts"])
                        except (ValueError, KeyError, TypeError):
                            continue
                        if desde <= ts < hasta:
                            filas.append(fila)
            except OSError:
                pass

        def suma(grupo: list[dict[str, Any]]) -> dict[str, Any]:
            return {
                "llamadas": len(grupo),
                "fallos": sum(1 for f in grupo if not f.get("ok")),
                "tokens_entrada": sum(int(f.get("tokens_entrada") or 0) for f in grupo),
                "tokens_salida": sum(int(f.get("tokens_salida") or 0) for f in grupo),
                "segundos": round(sum(float(f.get("segundos") or 0) for f in grupo), 1),
                "costo_usd": round(sum(float(f.get("costo_usd") or 0) for f in grupo), 6),
            }

        cuentas = sorted({str(f.get("cuenta")) for f in filas})
        return {
            "etiqueta": "auxiliar",
            "total": suma(filas),
            "por_cuenta": [
                {"cuenta": c, **suma([f for f in filas if str(f.get("cuenta")) == c])}
                for c in cuentas
            ],
        }


_resumenes: Resumenes | None = None


def get_resumenes() -> Resumenes:
    global _resumenes
    if _resumenes is None:
        from app.config import get_settings

        _resumenes = Resumenes(Path(get_settings().STATE_EVENT_LOG_PATH).parent)
    return _resumenes


def set_resumenes(instancia: Resumenes | None) -> None:
    global _resumenes
    _resumenes = instancia

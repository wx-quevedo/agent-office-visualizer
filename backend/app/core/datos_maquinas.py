"""Lo que cada monitor manda además de los eventos (etapa 2.1).

- **Límites** de la suscripción por cuenta: los ``rate_limits`` que Claude Code
  entrega a la barra de estado (porcentaje usado y hora de reinicio de las
  ventanas de 5 h y semanal). Son "lo último visto": valen hasta su
  ``resets_at`` y solo existen para Pro/Max después de la primera respuesta.
- **Proyectos** ("Dónde quedamos"): el resumen del PROJECT.md de cada carpeta
  donde trabajó un agente (plan, posición, siguiente paso, decisiones) y su
  último commit.

En memoria y en dos archivos JSON junto al registro del motor, para que un
reinicio del backend no los borre.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


def cuenta_de_carpeta(carpeta: str | None) -> str:
    """personal (``.claude``), demo (``.claude-demo``) o el nombre de la carpeta."""
    if not carpeta:
        return "desconocida"
    nombre = carpeta.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()
    if nombre == ".claude":
        return "personal"
    if nombre.startswith(".claude-"):
        return nombre.removeprefix(".claude-")
    return nombre or "desconocida"


class DatosMaquinas:
    def __init__(self, carpeta: Path | None) -> None:
        self.carpeta = carpeta
        self._lock = threading.Lock()
        self.limites: dict[str, dict[str, Any]] = self._leer("limites.json")
        self.proyectos: dict[str, dict[str, Any]] = self._leer("proyectos.json")

    def _leer(self, nombre: str) -> dict[str, dict[str, Any]]:
        if self.carpeta is None:
            return {}
        try:
            datos: object = json.loads((self.carpeta / nombre).read_text(encoding="utf-8"))
            return cast(dict[str, dict[str, Any]], datos) if isinstance(datos, dict) else {}
        except (OSError, ValueError):
            return {}

    def _guardar(self, nombre: str, datos: dict[str, Any]) -> None:
        if self.carpeta is None:
            return
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            tmp = self.carpeta / f"{nombre}.tmp"
            tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.carpeta / nombre)
        except OSError:
            logger.exception("No se pudo guardar %s", nombre)

    # -- límites -----------------------------------------------------------------

    def registrar_limites(self, maquina: str, cuenta_dir: str | None, datos: dict[str, Any]) -> str:
        cuenta = cuenta_de_carpeta(cuenta_dir)
        clave = f"{maquina}|{cuenta}"
        with self._lock:
            self.limites[clave] = {
                "maquina": maquina,
                "cuenta": cuenta,
                **datos,
                "recibido": datetime.now(UTC).isoformat(),
            }
            self._guardar("limites.json", self.limites)
        return cuenta

    def vista_limites(self, ahora: datetime | None = None) -> list[dict[str, Any]]:
        """Cada cuenta con sus ventanas; una ventana cuyo reinicio ya pasó se marca vencida."""
        ahora = ahora or datetime.now(UTC)
        out: list[dict[str, Any]] = []
        with self._lock:
            filas = [dict(v) for v in self.limites.values()]
        for fila in filas:
            for ventana in ("cinco_horas", "semanal"):
                crudo: object = fila.get(ventana)
                if not isinstance(crudo, dict):
                    continue
                v = cast(dict[str, Any], crudo)
                if v.get("reinicia"):
                    try:
                        reinicia = datetime.fromisoformat(str(v["reinicia"]))
                        fila[ventana] = {**v, "vencida": reinicia <= ahora}
                    except ValueError:
                        fila[ventana] = {**v, "vencida": None}
            out.append(fila)
        return sorted(out, key=lambda f: (f["maquina"], f["cuenta"]))

    # -- proyectos ----------------------------------------------------------------

    def registrar_proyectos(self, maquina: str, proyectos: list[dict[str, Any]]) -> int:
        with self._lock:
            for p in proyectos:
                carpeta = str(p.get("carpeta") or "")
                if not carpeta:
                    continue
                self.proyectos[f"{maquina}|{carpeta}"] = {
                    **p,
                    "maquina": maquina,
                    "recibido": datetime.now(UTC).isoformat(),
                }
            self._guardar("proyectos.json", self.proyectos)
        return len(proyectos)

    def vista_proyectos(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self.proyectos.values()]


_datos: DatosMaquinas | None = None


def get_datos_maquinas() -> DatosMaquinas:
    global _datos
    if _datos is None:
        from app.config import get_settings

        _datos = DatosMaquinas(Path(get_settings().STATE_EVENT_LOG_PATH).parent)
    return _datos


def set_datos_maquinas(instancia: DatosMaquinas | None) -> None:
    global _datos
    _datos = instancia

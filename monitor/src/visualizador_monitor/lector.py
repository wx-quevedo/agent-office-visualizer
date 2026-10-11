"""Lo que el monitor lee de esta máquina y manda al servidor (etapa 1.2).

Sesiones que pasaron por el monitor (los hooks mandan session_id, ruta de la
transcripción y PID + hora de creación del proceso de Claude Code). Cada
``intervalo_lectura`` segundos, por sesión activa en las últimas 24 h:
proceso vivo, contexto y modelo, tokens de salida acumulados (y de entrada
nueva), textos del turno, turno terminado, primer y último momento. Va a
``POST /api/v1/maquinas/observaciones`` (no se encola: el siguiente ciclo
manda el estado actual). El latido de la máquina sale cada ``intervalo_latido``.

Solo se leen transcripciones dentro de las carpetas de cuentas configuradas.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from visualizador_monitor import VERSION
from visualizador_monitor.cliente import Servidor, SinConexion
from visualizador_monitor.procesos import proceso_vivo
from visualizador_monitor.proyecto_md import leer_resumen
from visualizador_monitor.registro import logger
from visualizador_monitor.transcripcion import Totales, resumen_cola

_ACTIVA_S = 24 * 3600


def sistema() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


@dataclass
class SesionVista:
    session_id: str
    transcript: str | None = None
    pid: int | None = None
    creado: float | None = None
    primer_evento: datetime | None = None
    ultimo_evento: float = field(default_factory=time.time)
    totales: Totales | None = None
    # Etapa 2.1: carpeta del proyecto (project_dir o cwd del hook).
    carpeta: str | None = None


class Primeros(Protocol):
    def primer_evento(self, session_id: str, ts: datetime) -> datetime: ...


def _ts_evento(payload: dict[str, Any]) -> datetime:
    raw = payload.get("timestamp")
    if isinstance(raw, str):
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


class Lector:
    def __init__(
        self, servidor: Servidor, cuentas: list[str], primeros: Primeros | None = None
    ) -> None:
        self.servidor = servidor
        self.primeros = primeros
        self.cuentas = [Path(c).resolve() for c in cuentas]
        self.sesiones: dict[str, SesionVista] = {}
        self._lock = threading.Lock()
        self.ultimo_envio: str | None = None
        # Etapa 2.1: resúmenes de PROJECT.md ya enviados (carpeta -> (huella, hora)).
        self._proyectos_enviados: dict[str, tuple[str, float]] = {}
        # Límites de cada cuenta (barra de estado de Claude Code) por enviar.
        self.limites: dict[str, dict[str, Any]] = {}
        self._limites_pendientes = False
        self.ultimo_envio_proyectos: str | None = None

    # -- desde los hooks --------------------------------------------------------

    def vio_evento(self, payload: dict[str, Any]) -> None:
        sid = payload.get("session_id")
        if not isinstance(sid, str) or not sid:
            return
        crudo = payload.get("data")
        data: dict[str, Any] = crudo if isinstance(crudo, dict) else {}
        ts = _ts_evento(payload)
        with self._lock:
            s = self.sesiones.get(sid)
            if s is None:
                if self.primeros is not None:
                    ts = self.primeros.primer_evento(sid, ts)
                s = self.sesiones[sid] = SesionVista(sid, primer_evento=ts)
            s.ultimo_evento = time.time()
            tp = data.get("transcript_path")
            if isinstance(tp, str) and tp:
                s.transcript = tp
            carpeta = data.get("project_dir") or data.get("working_dir")
            if isinstance(carpeta, str) and carpeta:
                s.carpeta = carpeta
            pid = data.get("claude_pid")
            if isinstance(pid, int) and pid > 0:
                s.pid = pid
                creado = data.get("claude_pid_created")
                s.creado = float(creado) if isinstance(creado, (int, float)) else None

    # -- lectura -------------------------------------------------------------

    def _permitida(self, ruta: str) -> Path | None:
        """La transcripción, solo si está dentro de una cuenta configurada y existe.

        Primero sin tocar el disco: nada de rutas de red (``\\\\host\\...``) ni de
        dispositivo, que harían que Windows se autentique ante otro equipo; y la
        ruta tiene que quedar dentro de una cuenta. Recién entonces se resuelve
        (enlaces) y se vuelve a comprobar."""
        if not ruta or ruta.startswith(("\\\\", "//")) or "\x00" in ruta:
            return None
        try:
            plana = Path(os.path.normpath(os.path.abspath(os.path.expanduser(ruta))))
            if plana.suffix != ".jsonl" or not any(plana.is_relative_to(c) for c in self.cuentas):
                return None
            p = plana.resolve()
        except (OSError, ValueError):
            return None
        if not any(p.is_relative_to(c) for c in self.cuentas):
            return None
        return p if p.is_file() else None

    def observar(self, s: SesionVista) -> dict[str, Any]:
        obs: dict[str, Any] = {"session_id": s.session_id}
        if s.pid:
            obs["pid"] = s.pid
            vivo = proceso_vivo(s.pid, s.creado)
            if vivo is not None:
                obs["proceso_vivo"] = vivo
        ruta = self._permitida(s.transcript) if s.transcript else None
        if ruta is not None:
            try:
                obs.update(resumen_cola(ruta))
                if s.totales is None or s.totales.path != ruta:
                    s.totales = Totales(ruta, desde=s.primer_evento)
                obs["tokens_salida_total"] = s.totales.leer()
                obs["tamano_transcripcion"] = ruta.stat().st_size
            except OSError as e:
                logger.warning("No se pudo leer una transcripción: %s", type(e).__name__)
        return obs

    def ciclo(self) -> int:
        """Observa las sesiones activas y las manda; devuelve cuántas mandó."""
        ahora = time.time()
        with self._lock:
            for sid in [k for k, s in self.sesiones.items() if ahora - s.ultimo_evento > _ACTIVA_S]:
                del self.sesiones[sid]
            activas = list(self.sesiones.values())
        if not activas:
            return 0
        observaciones = [self.observar(s) for s in activas]
        for i in range(0, len(observaciones), 200):
            lote = observaciones[i : i + 200]
            try:
                r = self.servidor.post_json(
                    "/api/v1/maquinas/observaciones", {"sesiones": lote}, timeout=10.0
                )
            except SinConexion:
                return 0
            if r.status >= 300:
                logger.warning("El servidor no aceptó las observaciones (HTTP %s)", r.status)
                return 0
        self.ultimo_envio = datetime.now(UTC).isoformat()
        return len(observaciones)

    # -- "Dónde quedamos" ----------------------------------------------------------

    def proyectos(self, forzar_cada: float = 600.0) -> int:
        """Resumen del PROJECT.md (y último commit) de cada carpeta con sesiones
        activas; se manda si cambió o cada ``forzar_cada`` segundos."""
        with self._lock:
            carpetas = sorted({s.carpeta for s in self.sesiones.values() if s.carpeta})
        lote: list[dict[str, Any]] = []
        huellas: dict[str, str] = {}
        ahora = time.time()
        for carpeta in carpetas[:50]:
            try:
                resumen = leer_resumen(Path(carpeta))
            except Exception:
                logger.exception("No se pudo leer el PROJECT.md de un proyecto")
                continue
            datos = {"carpeta": carpeta, **resumen}
            huella = hashlib.sha256(
                json.dumps(datos, sort_keys=True, default=str).encode()
            ).hexdigest()
            previo = self._proyectos_enviados.get(carpeta)
            if previo and previo[0] == huella and ahora - previo[1] < forzar_cada:
                continue
            lote.append(datos)
            huellas[carpeta] = huella
        if not lote:
            return 0
        try:
            r = self.servidor.post_json(
                "/api/v1/maquinas/proyectos", {"proyectos": lote}, timeout=10.0
            )
        except SinConexion:
            return 0
        if r.status >= 300:
            logger.warning("El servidor no aceptó los proyectos (HTTP %s)", r.status)
            return 0
        for carpeta, huella in huellas.items():
            self._proyectos_enviados[carpeta] = (huella, ahora)
        self.ultimo_envio_proyectos = datetime.now(UTC).isoformat()
        return len(lote)

    # -- límites de la suscripción --------------------------------------------------

    def recibir_limites(self, datos: dict[str, Any]) -> None:
        """Lo que mandó la barra de estado de una cuenta (lo último gana)."""
        cuenta = str(datos.get("cuenta_dir") or "desconocida")
        with self._lock:
            self.limites[cuenta] = datos
            self._limites_pendientes = True

    def enviar_limites(self) -> bool:
        with self._lock:
            if not self._limites_pendientes:
                return False
            cuentas = list(self.limites.values())
            self._limites_pendientes = False
        try:
            r = self.servidor.post_json(
                "/api/v1/maquinas/limites", {"cuentas": cuentas}, timeout=5.0
            )
        except SinConexion:
            with self._lock:
                self._limites_pendientes = True
            return False
        if r.status >= 300:
            logger.warning("El servidor no aceptó los límites (HTTP %s)", r.status)
            return False
        return True

    def latido(self) -> bool:
        try:
            r = self.servidor.post_json(
                "/api/v1/maquinas/latido",
                {
                    "version_monitor": VERSION,
                    "hostname": socket.gethostname(),
                    "sistema": sistema(),
                },
                timeout=5.0,
            )
        except SinConexion:
            return False
        return 200 <= r.status < 300


def descripcion_maquina() -> str:
    return f"{socket.gethostname()} ({platform.system()} {platform.release()})"

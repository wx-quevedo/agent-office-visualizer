"""Hilo de los avisos resumidos (etapa 2.4).

Cada ``cada`` segundos, mientras hay sesiones activas en esta máquina, pide al
servidor los avisos de sus sesiones que todavía no tienen resumen, los resume con
el auxiliar (dos a la vez como máximo) y manda cada frase con su consumo. Si el
auxiliar falla, igual avisa al servidor ("fallo"), y la oficina usa el texto de
siempre sin esperar más.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from visualizador_monitor.auxiliar import Auxiliar, Resultado, detener_todos
from visualizador_monitor.cliente import Servidor, SinConexion
from visualizador_monitor.registro import logger

_MAX_ENVIADOS = 500


class Resumidor(threading.Thread):
    def __init__(
        self,
        servidor: Servidor,
        auxiliar: Auxiliar,
        hay_sesiones: Callable[[], bool],
        cada: float = 1.5,
    ) -> None:
        super().__init__(name="resumidor", daemon=True)
        self.servidor = servidor
        self.auxiliar = auxiliar
        self.hay_sesiones = hay_sesiones
        self.cada = cada
        self.parar = threading.Event()
        self.hay_nuevo = threading.Event()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="auxiliar")
        self._en_curso: set[str] = set()
        self._enviados: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()
        self.ultimo: dict[str, Any] | None = None

    def run(self) -> None:
        while not self.parar.is_set():
            self.hay_nuevo.wait(self.cada)
            self.hay_nuevo.clear()
            if self.parar.is_set():
                break
            try:
                if self.hay_sesiones():
                    self.ronda()
            except Exception:
                logger.exception("Error en los avisos resumidos")
        self._pool.shutdown(wait=False, cancel_futures=True)
        detener_todos()  # ningún auxiliar queda corriendo sin su tope

    def ronda(self) -> int:
        """Pide los avisos por resumir y lanza los nuevos; devuelve cuántos lanzó."""
        try:
            r = self.servidor.pedir("GET", "/api/v1/maquinas/avisos", timeout=5.0)
        except SinConexion:
            return 0
        if r.status >= 300 or not isinstance(r.cuerpo, dict):
            return 0
        avisos = r.cuerpo.get("avisos")
        if not isinstance(avisos, list):
            return 0
        lanzados = 0
        for aviso in avisos:
            if not isinstance(aviso, dict):
                continue
            clave = aviso.get("clave")
            if not isinstance(clave, str) or not clave:
                continue
            with self._lock:
                if clave in self._en_curso or clave in self._enviados:
                    continue
                self._en_curso.add(clave)
            self._pool.submit(self._resumir_y_enviar, clave, aviso)
            lanzados += 1
        return lanzados

    def _resumir_y_enviar(self, clave: str, aviso: dict[str, Any]) -> None:
        try:
            resultado = self.auxiliar.resumir(aviso)
            if self.enviar(clave, resultado):
                with self._lock:
                    self._enviados[clave] = None
                    while len(self._enviados) > _MAX_ENVIADOS:
                        self._enviados.popitem(last=False)
            self.ultimo = {
                "tipo": aviso.get("tipo"),
                "ok": resultado.texto is not None,
                "motivo": resultado.motivo,
                "segundos": resultado.segundos,
            }
        except Exception:
            logger.exception("No se pudo resumir un aviso")
        finally:
            with self._lock:
                self._en_curso.discard(clave)

    def enviar(self, clave: str, r: Resultado) -> bool:
        if r.motivo == "limite_por_minuto":
            return False  # se reintenta en la próxima ronda
        try:
            resp = self.servidor.post_json(
                "/api/v1/maquinas/resumenes",
                {"clave": clave, "texto": r.texto, "metricas": r.metricas()},
                timeout=5.0,
            )
        except SinConexion:
            return False
        return resp.status < 300

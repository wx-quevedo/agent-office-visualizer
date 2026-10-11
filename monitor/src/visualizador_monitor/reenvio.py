"""Hilo que vacía la cola hacia el servidor, en orden.

- 2xx (o "duplicado"): enviado, se borra.
- 400, 409, 422: rechazo definitivo de la aplicación (datos inválidos, sesión
  de otra máquina): se descarta y se anota; no frena a los demás.
- 401/403 (token inválido o revocado): espera de 60 s; se anota.
- Sin conexión, 3xx, 404, 405, 413, 429 o 5xx (también errores del proxy, como
  una dirección mal escrita o nginx en pleno despliegue): espera progresiva del
  primero; nada se adelanta y nada se pierde.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from visualizador_monitor.cliente import Servidor, SinConexion
from visualizador_monitor.cola import Cola
from visualizador_monitor.registro import logger

_DEFINITIVOS = {400, 409, 422}


class EstadoConexion:
    def __init__(self) -> None:
        self.conectado: bool | None = None
        self.ultimo_ok: str | None = None
        self.ultimo_error: str | None = None
        self._lock = threading.Lock()

    def ok(self) -> bool:
        """Registra un éxito; True si antes no había conexión."""
        with self._lock:
            volvio = self.conectado is False
            self.conectado = True
            self.ultimo_ok = datetime.now(UTC).isoformat()
            return volvio

    def fallo(self, motivo: str) -> None:
        with self._lock:
            self.conectado = False
            self.ultimo_error = f"{datetime.now(UTC).isoformat()} {motivo}"

    def vista(self) -> dict[str, object]:
        return {
            "conectado": self.conectado,
            "ultimo_ok": self.ultimo_ok,
            "ultimo_error": self.ultimo_error,
        }


def enviar_uno(cola: Cola, servidor: Servidor, estado: EstadoConexion) -> bool | None:
    """Intenta el primero de la cola: True enviado/descartado, False falló, None no hay."""
    envio = cola.siguiente()
    if envio is None:
        return None
    try:
        r = servidor.pedir(
            "POST",
            envio.ruta,
            envio.cuerpo,
            timeout=10.0,
            cabeceras={"X-Evento-Id": envio.evento_id},
        )
    except SinConexion as e:
        espera = cola.posponer(envio, f"sin conexión ({e})")
        estado.fallo(f"sin conexión ({e})")
        logger.warning("Servidor sin respuesta; reintento en %.0f s", espera)
        return False
    if 200 <= r.status < 300:
        cola.enviado(envio)
        if estado.ok():
            cola.reintentar_ya()
            logger.info("Conexión con el servidor recuperada")
        return True
    if r.status in _DEFINITIVOS:
        cola.descartar(envio, f"HTTP {r.status}")
        estado.ok()
        # Sin el cuerpo de la respuesta: un 422 repite los datos (comandos, textos).
        logger.error("El servidor rechazó un envío (HTTP %s)", r.status)
        return True
    if r.status in (401, 403):
        cola.posponer(envio, f"HTTP {r.status}: token inválido o revocado", espera=60.0)
        estado.fallo(f"HTTP {r.status}: token inválido o revocado")
        logger.error("El servidor no acepta el token de esta máquina (HTTP %s)", r.status)
        return False
    espera = cola.posponer(envio, f"HTTP {r.status}")
    estado.fallo(f"HTTP {r.status}")
    logger.warning("El servidor respondió HTTP %s; reintento en %.0f s", r.status, espera)
    return False


class Reenviador(threading.Thread):
    def __init__(self, cola: Cola, servidor: Servidor, estado: EstadoConexion) -> None:
        super().__init__(name="reenvio", daemon=True)
        self.cola = cola
        self.servidor = servidor
        self.estado = estado
        self.hay_nuevo = threading.Event()
        self.parar = threading.Event()

    def run(self) -> None:
        while not self.parar.is_set():
            try:
                r = enviar_uno(self.cola, self.servidor, self.estado)
            except Exception:
                logger.exception("Error inesperado al reenviar")
                r = False
            if r is True:
                continue  # el siguiente, sin esperar
            self.hay_nuevo.wait(0.5 if r is None else 1.0)
            self.hay_nuevo.clear()

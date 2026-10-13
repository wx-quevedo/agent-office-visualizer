"""El monitor en marcha: API local, cola con reenvío, lecturas y latido."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from visualizador_monitor import VERSION, config
from visualizador_monitor.auxiliar import Auxiliar, es_de_auxiliar
from visualizador_monitor.cliente import Servidor
from visualizador_monitor.cola import Cola
from visualizador_monitor.config import Configuracion
from visualizador_monitor.equipos import Equipos, HiloEncargos, HiloEnVivo
from visualizador_monitor.lector import Lector
from visualizador_monitor.reenvio import EstadoConexion, Reenviador
from visualizador_monitor.registro import logger
from visualizador_monitor.resumidor import Resumidor
from visualizador_monitor.servidor_local import arrancar, esperar_permiso, reenviar_permiso
from visualizador_monitor.sesiones import LanzadorNoDisponible


class Monitor:
    def __init__(self, cfg: Configuracion, base: Path) -> None:
        self.cfg = cfg
        self.base = base
        self.servidor = Servidor(cfg.url_servidor, cfg.token)
        self.clave = config.clave_local(base)
        self.cola = Cola(base / "cola.db")
        self.conexion = EstadoConexion()
        self.lector = Lector(self.servidor, cfg.cuentas, self.cola)
        self.reenviador = Reenviador(self.cola, self.servidor, self.conexion)
        self.lanzador = LanzadorNoDisponible()  # etapa 4
        # Etapa 2.4: avisos resumidos por el auxiliar (solo con sesiones activas).
        self.resumidor = Resumidor(
            self.servidor, Auxiliar(cfg.cuentas, base), lambda: bool(self.lector.sesiones)
        )
        # Etapa 4: proyectos con equipo (encargos del servidor: crear, pausar, reanudar).
        ruta_proyectos = config.ruta_proyectos(cfg)
        self.lector.ruta_proyectos = str(ruta_proyectos)
        self.equipos = Equipos(base, ruta_proyectos, cfg.cuentas)
        self.encargos = HiloEncargos(self.servidor, self.equipos)
        # Prompt 45: leído, respondiendo y el texto parcial de los orquestadores.
        self.en_vivo = HiloEnVivo(self.servidor, self.equipos)
        self.inicio = datetime.now(UTC).isoformat()
        self.parar = threading.Event()
        self.http: Any = None

    # -- API local (llamado desde servidor_local) ---------------------------------

    def recibir_evento(self, payload: dict[str, Any], cuerpo: bytes) -> dict[str, Any]:
        if es_de_auxiliar(payload, self.resumidor.auxiliar.carpeta):
            # El auxiliar corre sin hooks; si igual llegara algo suyo, no entra a la oficina.
            return {"status": "ignored", "event_id": None, "visual_action": "none"}
        evento_id = self.cola.agregar("/api/v1/events", cuerpo)
        try:
            self.lector.vio_evento(payload)
        except Exception:
            logger.exception("No se pudo anotar la sesión del evento")
        self.reenviador.hay_nuevo.set()
        self.resumidor.hay_nuevo.set()
        return {"status": "accepted", "event_id": evento_id, "visual_action": "queued"}

    def registrar_permiso(self, cuerpo: bytes) -> dict[str, Any]:
        try:
            datos = json.loads(cuerpo)
        except ValueError:
            datos = None
        if isinstance(datos, dict) and es_de_auxiliar(datos, self.resumidor.auxiliar.carpeta):
            # El auxiliar no tiene herramientas; si igual pidiera permiso, no va a la oficina.
            return {"esperar": False, "segundos_restantes": 0, "estado": "ignorado"}
        # Los eventos anteriores de la sesión llegan primero: si no, el servidor
        # cerraría la solicitud nueva con un evento viejo. Si la cola no se vacía
        # en 1 s, el hook sigue sin decisión (el diálogo de VS Code).
        fin = time.monotonic() + 1.0
        while self.cola.pendientes() > 0:
            if time.monotonic() >= fin:
                return {"esperar": False, "segundos_restantes": 0, "estado": "cola_pendiente"}
            self.reenviador.hay_nuevo.set()
            time.sleep(0.05)
        return reenviar_permiso(self.servidor, cuerpo)

    def esperar_permiso(self, id_: str, espera: float) -> dict[str, Any]:
        return esperar_permiso(self.servidor, id_, espera)

    def recibir_limites(self, datos: dict[str, Any]) -> dict[str, Any]:
        self.lector.recibir_limites(datos)
        return {"estado": "recibido"}

    def estado(self) -> dict[str, Any]:
        """Para el comando estado: nunca incluye el token."""
        return {
            "version": VERSION,
            "pid": os.getpid(),
            "maquina": socket.gethostname(),
            "servidor": self.cfg.url_servidor,
            "puerto": self.cfg.puerto,
            "inicio": self.inicio,
            "conexion": self.conexion.vista(),
            "cola": self.cola.resumen(),
            "ultimo_envio_observaciones": self.lector.ultimo_envio,
            "sesiones_vistas": len(self.lector.sesiones),
            "ultimo_envio_proyectos": self.lector.ultimo_envio_proyectos,
            "limites": self.lector.limites,
            "cuentas": self.cfg.cuentas,
            "ultimo_resumen": self.resumidor.ultimo,
            "ruta_proyectos": self.lector.ruta_proyectos,
            "equipos": self.equipos.estado_equipos(),
        }

    # -- en marcha -------------------------------------------------------------

    def iniciar(self) -> None:
        """Abre el puerto local (falla si otro monitor ya lo usa) y arranca los hilos."""
        self.http, _ = arrancar(self, self.cfg.puerto)
        self.reenviador.start()
        self.resumidor.start()
        self.encargos.start()
        self.en_vivo.start()
        (self.base / "monitor.pid").write_text(str(os.getpid()), encoding="ascii")
        logger.info(
            "Monitor %s escuchando en 127.0.0.1:%s; servidor %s; cuentas %s",
            VERSION,
            self.cfg.puerto,
            self.cfg.url_servidor,
            ", ".join(self.cfg.cuentas) or "(ninguna)",
        )

    def bucle(self) -> None:
        proximo_latido = 0.0
        proxima_lectura = 0.0
        while not self.parar.is_set():
            ahora = time.monotonic()
            if ahora >= proximo_latido:
                proximo_latido = ahora + self.cfg.intervalo_latido
                try:
                    if self.lector.latido() and self.conexion.ok():
                        self.cola.reintentar_ya()
                        self.reenviador.hay_nuevo.set()
                except Exception:
                    logger.exception("Error en el latido")
            if ahora >= proxima_lectura:
                proxima_lectura = ahora + self.cfg.intervalo_lectura
                try:
                    self.lector.ciclo()
                except Exception:
                    logger.exception("Error leyendo transcripciones y procesos")
                try:
                    self.lector.proyectos()
                except Exception:
                    logger.exception("Error leyendo los PROJECT.md")
            try:
                self.lector.enviar_limites()
            except Exception:
                logger.exception("Error enviando los límites")
            self.parar.wait(1.0)

    def detener(self) -> None:
        self.parar.set()
        self.reenviador.parar.set()
        self.resumidor.parar.set()
        self.encargos.parar.set()
        self.en_vivo.parar.set()
        self.resumidor.hay_nuevo.set()
        self.reenviador.hay_nuevo.set()
        if self.http is not None:
            self.http.shutdown()
            self.http.server_close()
        # Cierra las sesiones de proyectos que lanzó (al volver, las retoma).
        self.equipos.detener_todo()

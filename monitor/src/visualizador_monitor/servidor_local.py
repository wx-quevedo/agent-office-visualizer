"""API local del monitor (solo 127.0.0.1): la misma ingesta que usan los hooks.

- ``POST /api/v1/events``: se guarda en la cola (con un id único) y se responde
  de inmediato; el envío al servidor va en segundo plano y en orden.
- ``POST /api/v1/permisos/solicitudes``: se reenvía al servidor (1,2 s, menos
  que los 2 s del hook: el servidor no queda esperando a un hook que ya se fue). Si no
  responde: ``{"esperar": false}`` y el hook sigue sin decisión (diálogo de VS Code).
- ``GET /api/v1/permisos/solicitudes/{id}?espera=N``: espera larga reenviada al
  servidor. Si no responde: ``{"estado": "sin_conexion"}`` (sin decisión).
- ``GET /estado``: estado del monitor (para el comando ``estado``).

Solo atiende a quien trae la clave local (``X-API-Key``, archivo
``clave-local.txt`` de la carpeta de datos, que leen los hooks): ni una página
web (CSRF, DNS rebinding) ni otro usuario de la PC pueden usarla. Además exige
``Host`` 127.0.0.1/localhost, rechaza pedidos de navegador (``Origin``,
``Sec-Fetch-Site``) y, en los POST, ``Content-Type: application/json``.

Sin asyncio (``ThreadingHTTPServer``): no le afecta el problema del bucle
Proactor de Windows que cerraba el puerto del backend de la diaria.
"""

from __future__ import annotations

import hmac
import json
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from visualizador_monitor.cliente import Servidor, SinConexion
from visualizador_monitor.registro import logger

MAX_CUERPO = 2_000_000
_ID = re.compile(r"^/api/v1/permisos/solicitudes/([A-Za-z0-9_-]{1,64})$")
ESPERA_MAXIMA_LARGA = 25.0


class MonitorHTTP(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # en Windows permitiría dos monitores en el mismo puerto

    def __init__(self, puerto: int, app: Any) -> None:
        self.app = app
        self.puerto = puerto
        super().__init__(("127.0.0.1", puerto), _Manejador)

    def server_bind(self) -> None:
        # En Windows, sin esto otro proceso podría abrir el mismo puerto encima.
        exclusivo = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusivo is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, exclusivo, 1)
        super().server_bind()


class _Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 10  # un cliente que no termina de mandar el cuerpo no deja hilos colgados

    def _app(self) -> Any:
        return cast(MonitorHTTP, self.server).app

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # nada de accesos en el registro (podrían traer datos de los comandos)

    def _responder(self, status: int, cuerpo: Any) -> None:
        datos = json.dumps(cuerpo).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(datos)

    def _permitido(self, post: bool) -> bool:
        """Clave local, Host local y nada de navegadores; si no, 403."""
        srv = cast(MonitorHTTP, self.server)
        host = (self.headers.get("Host") or "").strip().lower()
        hosts = {f"127.0.0.1:{srv.puerto}", f"localhost:{srv.puerto}"}
        clave = self.headers.get("X-API-Key") or ""
        motivo = None
        if host not in hosts:
            motivo = "Host"
        elif self.headers.get("Origin") is not None or self.headers.get(
            "Sec-Fetch-Site", "none"
        ) not in ("none", ""):
            motivo = "navegador"
        elif not hmac.compare_digest(clave.encode(), str(srv.app.clave).encode()):
            motivo = "clave"
        elif post and not (self.headers.get("Content-Type") or "").startswith("application/json"):
            motivo = "tipo"
        elif self.headers.get("Transfer-Encoding") is not None:
            motivo = "chunked"
        if motivo is None:
            return True
        self._responder(403, {"detail": "No autorizado"})
        return False

    def _leer(self) -> bytes | None:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n < 0 or n > MAX_CUERPO:
            return None
        return self.rfile.read(n) if n else b""

    def do_GET(self) -> None:  # noqa: N802
        if not self._permitido(post=False):
            return
        url = urlparse(self.path)
        app = self._app()
        if url.path in ("/estado", "/health"):
            self._responder(200, app.estado())
            return
        m = _ID.match(url.path)
        if m:
            q = parse_qs(url.query)
            try:
                espera = min(float((q.get("espera") or ["0"])[0]), ESPERA_MAXIMA_LARGA)
            except ValueError:
                espera = 0.0
            self._responder(200, app.esperar_permiso(m.group(1), max(0.0, espera)))
            return
        self._responder(404, {"detail": "No existe"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._permitido(post=True):
            return
        url = urlparse(self.path)
        cuerpo = self._leer()
        if cuerpo is None:
            self._responder(413, {"detail": "Cuerpo demasiado grande"})
            return
        app = self._app()
        if url.path == "/api/v1/events":
            try:
                payload = json.loads(cuerpo.decode("utf-8"))
            except ValueError:
                self._responder(422, {"detail": "JSON inválido"})
                return
            if not isinstance(payload, dict):
                self._responder(422, {"detail": "JSON inválido"})
                return
            self._responder(200, app.recibir_evento(payload, cuerpo))
            return
        if url.path == "/api/v1/permisos/solicitudes":
            self._responder(200, app.registrar_permiso(cuerpo))
            return
        self._responder(404, {"detail": "No existe"})


def reenviar_permiso(servidor: Servidor, cuerpo: bytes) -> dict[str, Any]:
    """Registro de un permiso en el servidor; sin respuesta: el hook sigue sin decisión."""
    try:
        r = servidor.pedir("POST", "/api/v1/permisos/solicitudes", cuerpo, timeout=1.2)
    except SinConexion as e:
        logger.warning("Permiso sin servidor (%s): sigue el diálogo de VS Code", e)
        return {"esperar": False, "segundos_restantes": 0, "estado": "sin_conexion"}
    if r.status >= 300 or not isinstance(r.cuerpo, dict):
        return {"esperar": False, "segundos_restantes": 0, "estado": f"http_{r.status}"}
    return r.cuerpo


def esperar_permiso(servidor: Servidor, id_: str, espera: float) -> dict[str, Any]:
    try:
        r = servidor.pedir(
            "GET",
            f"/api/v1/permisos/solicitudes/{id_}?espera={espera:.1f}",
            timeout=espera + 3.0,
        )
    except SinConexion:
        return {"estado": "sin_conexion", "esperando": False}
    if r.status >= 300 or not isinstance(r.cuerpo, dict):
        return {"estado": f"http_{r.status}", "esperando": False}
    return r.cuerpo


def arrancar(app: Any, puerto: int) -> tuple[MonitorHTTP, threading.Thread]:
    http = MonitorHTTP(puerto, app)
    hilo = threading.Thread(target=http.serve_forever, name="api-local", daemon=True)
    hilo.start()
    return http, hilo

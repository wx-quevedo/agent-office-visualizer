"""Servidor falso (lo que sería el backend) para probar el monitor sin red."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

TOKEN = "vam_prueba_token_secreto_1234567890"


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class Pedido:
    metodo: str
    ruta: str
    cabeceras: dict[str, str]
    cuerpo: bytes

    def json(self) -> Any:
        return json.loads(self.cuerpo.decode("utf-8")) if self.cuerpo else None


@dataclass
class ServidorFalso:
    puerto: int
    pedidos: list[Pedido] = field(default_factory=lambda: [])
    # ruta -> (status, cuerpo) para forzar respuestas
    respuestas: dict[str, tuple[int, Any]] = field(default_factory=lambda: {})
    ids_vistos: set[str] = field(default_factory=lambda: set())
    permisos: dict[str, str] = field(default_factory=lambda: {})
    _http: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.puerto}"

    def eventos(self) -> list[dict[str, Any]]:
        return [p.json() for p in self.pedidos if p.ruta == "/api/v1/events"]

    def arrancar(self) -> None:
        falso = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a: Any) -> None:
                pass

            def _manejar(self, metodo: str) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                cuerpo = self.rfile.read(n) if n else b""
                ruta = self.path.split("?")[0]
                falso.pedidos.append(Pedido(metodo, self.path, dict(self.headers), cuerpo))
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    self._enviar(401, {"detail": "token"})
                    return
                if ruta in falso.respuestas:
                    self._enviar(*falso.respuestas[ruta])
                    return
                if ruta == "/api/v1/events":
                    eid = self.headers.get("X-Evento-Id") or ""
                    if eid in falso.ids_vistos:
                        self._enviar(200, {"status": "duplicado"})
                        return
                    falso.ids_vistos.add(eid)
                    self._enviar(200, {"status": "accepted"})
                    return
                if ruta == "/api/v1/permisos/solicitudes":
                    datos = json.loads(cuerpo)
                    falso.permisos.setdefault(datos["id"], "pendiente")
                    self._enviar(200, {"esperar": True, "segundos_restantes": 30})
                    return
                if ruta.startswith("/api/v1/permisos/solicitudes/"):
                    id_ = ruta.rsplit("/", 1)[1]
                    self._enviar(200, {"estado": falso.permisos.get(id_, "pendiente")})
                    return
                self._enviar(200, {"ok": True})

            def _enviar(self, status: int, cuerpo: Any) -> None:
                datos = json.dumps(cuerpo).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(datos)))
                if 300 <= status < 400 and isinstance(cuerpo, dict) and "Location" in cuerpo:
                    self.send_header("Location", str(cuerpo["Location"]))
                self.end_headers()
                self.wfile.write(datos)

            def do_GET(self) -> None:  # noqa: N802
                self._manejar("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._manejar("POST")

        ThreadingHTTPServer.allow_reuse_address = True
        self._http = ThreadingHTTPServer(("127.0.0.1", self.puerto), H)
        self._http.daemon_threads = True
        threading.Thread(target=self._http.serve_forever, daemon=True).start()

    def detener(self) -> None:
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
            self._http = None


@pytest.fixture
def servidor() -> Iterator[ServidorFalso]:
    s = ServidorFalso(puerto_libre())
    s.arrancar()
    yield s
    s.detener()


@pytest.fixture
def base(tmp_path: Path) -> Path:
    d = tmp_path / "datos-monitor"
    d.mkdir()
    return d

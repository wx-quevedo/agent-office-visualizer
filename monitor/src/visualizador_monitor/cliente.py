"""Llamadas HTTP al servidor con el token de máquina (``Authorization: Bearer``).

Sin redirecciones: una respuesta 3xx vuelve como tal (el envío se reintenta).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class SinConexion(Exception):
    """El servidor no respondió (red, DNS, tiempo agotado, servidor apagado)."""


@dataclass
class Respuesta:
    status: int
    cuerpo: Any


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    """Una redirección no se sigue: urllib copiaría el token a otro destino y
    convertiría el POST en GET sin cuerpo (el evento se perdería)."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_ABRIR = urllib.request.build_opener(_SinRedirecciones()).open


class Servidor:
    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self._token = token

    def _cabeceras(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {"Content-Type": "application/json", "User-Agent": "visualizador-monitor"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        h.update(extra or {})
        return h

    def pedir(
        self,
        metodo: str,
        ruta: str,
        cuerpo: bytes | None = None,
        timeout: float = 5.0,
        cabeceras: dict[str, str] | None = None,
    ) -> Respuesta:
        """Respuesta del servidor (también 4xx/5xx); SinConexion si no hubo respuesta."""
        req = urllib.request.Request(
            self.url + ruta, data=cuerpo, method=metodo, headers=self._cabeceras(cabeceras)
        )
        try:
            with _ABRIR(req, timeout=timeout) as r:
                return Respuesta(r.status, _json(r.read()))
        except urllib.error.HTTPError as e:
            try:
                datos = e.read()
            except Exception:
                datos = b""
            return Respuesta(e.code, _json(datos))
        except Exception as e:  # URLError, timeout, ConnectionError, ssl...
            raise SinConexion(type(e).__name__) from None

    def post_json(self, ruta: str, datos: dict[str, Any], timeout: float = 5.0) -> Respuesta:
        return self.pedir("POST", ruta, json.dumps(datos).encode("utf-8"), timeout)


def _json(datos: bytes) -> Any:
    if not datos:
        return None
    try:
        return json.loads(datos.decode("utf-8"))
    except ValueError:
        return None

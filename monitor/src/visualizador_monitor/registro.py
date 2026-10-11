"""Registro de errores del monitor con rotación y sin tokens.

``~/.visualizador-monitor/logs/monitor.log`` (1 MB, 5 copias). El formato quita
cualquier token de cada línea (también de las trazas) antes de escribirla.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from visualizador_monitor.config import mascara

logger = logging.getLogger("visualizador_monitor")


class _SinTokens(logging.Formatter):
    """Enmascara los tokens en la línea ya armada (mensaje, traza y pila)."""

    def __init__(self, token: str, fmt: str | None = None) -> None:
        super().__init__(fmt)
        self.token = token

    def format(self, record: logging.LogRecord) -> str:
        return mascara(super().format(record), self.token)


def ruta_registro(base: Path) -> Path:
    return base / "logs" / "monitor.log"


def configurar(base: Path, token: str = "", consola: bool = False) -> Path:
    ruta = ruta_registro(base)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    archivo = RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    archivo.setFormatter(_SinTokens(token, "%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(archivo)
    if consola:
        salida = logging.StreamHandler()
        salida.setFormatter(_SinTokens(token))
        logger.addHandler(salida)
    logger.setLevel(logging.INFO)
    return ruta

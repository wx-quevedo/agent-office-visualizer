"""Etapa 4 (sin implementar): el servidor pide al monitor lanzar sesiones de Claude Code.

Queda definida la interfaz para que el orquestador del servidor pueda pedir,
en una carpeta de esta máquina, una sesión nueva o la continuación de una:

    claude -p "<encargo>" --output-format stream-json --verbose
           [--resume <session_id>] [--model <modelo>] [--permission-mode default]

El monitor corre como el usuario (no SYSTEM) justamente para esto: usa su
login de Claude Code y sus carpetas de cuentas (CLAUDE_CONFIG_DIR para elegir
personal o Demo Org). Flujo previsto:

1. El monitor pregunta por órdenes pendientes (``GET /api/v1/maquinas/ordenes``,
   con su token) o las recibe por un WebSocket de máquina.
2. Valida la orden (carpeta dentro de la ruta base permitida de la máquina,
   por ejemplo ``E:\\Agents`` en la Alienware; cuenta conocida).
3. Lanza el proceso y reenvía cada línea de stream-json al servidor
   (``POST /api/v1/maquinas/ordenes/{id}/salida``), con la misma cola sin conexión.
4. Al terminar manda el código de salida y el session_id para seguir con --resume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Esfuerzo = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass
class OrdenSesion:
    """Orden del servidor para lanzar o continuar una sesión."""

    id: str
    carpeta: str
    encargo: str
    cuenta: str  # "personal" | "demo" (carpeta .claude o .claude-demo)
    resume_session_id: str | None = None
    modelo: str | None = None
    esfuerzo: Esfuerzo | None = None
    herramientas_permitidas: list[str] = field(default_factory=lambda: [])


@dataclass
class ResultadoSesion:
    orden_id: str
    session_id: str | None
    codigo_salida: int | None
    error: str | None = None


class LanzadorSesiones(Protocol):
    """Lo que el monitor implementará en la etapa 4."""

    def lanzar(self, orden: OrdenSesion) -> ResultadoSesion: ...

    def cancelar(self, orden_id: str) -> bool: ...


class LanzadorNoDisponible:
    """Hasta la etapa 4 el monitor no lanza sesiones."""

    def lanzar(self, orden: OrdenSesion) -> ResultadoSesion:
        raise NotImplementedError("Lanzar sesiones llega en la etapa 4.")

    def cancelar(self, orden_id: str) -> bool:
        raise NotImplementedError("Lanzar sesiones llega en la etapa 4.")

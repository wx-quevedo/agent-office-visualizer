"""Monitor de máquina de la oficina de agentes (etapa 1.2).

Corre como proceso del usuario en cada máquina. Recibe en 127.0.0.1 los
eventos y permisos de los hooks de Claude Code, lee transcripciones y
procesos de esa máquina, y envía todo al servidor con el token de máquina.
Es el único que conoce el token y la dirección del servidor.
"""

try:
    from importlib.metadata import version as _version

    VERSION = _version("visualizador-monitor")
except Exception:  # empaquetado sin metadatos
    VERSION = "0.5.0"

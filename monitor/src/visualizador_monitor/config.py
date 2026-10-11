"""Configuración del monitor: un archivo JSON del usuario.

``~/.visualizador-monitor/config.json`` (o VISUALIZADOR_MONITOR_DIR): dirección
del servidor, token de máquina, puerto local, carpetas de las cuentas de Claude
Code. El token solo vive en ese archivo: nunca se escribe en el registro ni en
la salida de los comandos (``mascara``).
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PUERTO_POR_DEFECTO = 8765
_TOKEN = re.compile(r"\b(va[msp])_[A-Za-z0-9_-]{4,}")


def directorio() -> Path:
    """Carpeta de datos del monitor (configuración, cola, registro, lista de peligrosos)."""
    raw = os.environ.get("VISUALIZADOR_MONITOR_DIR", "").strip()
    return Path(raw) if raw else Path.home() / ".visualizador-monitor"


def cuentas_detectadas(inicio: Path | None = None) -> list[str]:
    """Carpetas de cuentas de Claude Code que existen (.claude y .claude-*)."""
    base = inicio or Path.home()
    encontradas: list[str] = []
    try:
        for p in sorted(base.iterdir()):
            es_cuenta = p.name == ".claude" or p.name.startswith(".claude-")
            if (
                es_cuenta
                and p.is_dir()
                and ((p / "projects").is_dir() or (p / "settings.json").is_file())
            ):
                encontradas.append(str(p))
    except OSError:
        pass
    return encontradas


@dataclass
class Configuracion:
    servidor: str = ""
    token: str = ""
    puerto: int = PUERTO_POR_DEFECTO
    cuentas: list[str] = field(default_factory=lambda: [])
    # Segundos entre lecturas de transcripciones y procesos, y entre latidos.
    intervalo_lectura: float = 15.0
    intervalo_latido: float = 30.0
    # Etapa 4: carpeta donde se crean los proyectos ("" = la de siempre, ver ruta_proyectos).
    ruta_proyectos: str = ""

    @property
    def url_servidor(self) -> str:
        return self.servidor.rstrip("/")

    def vista(self) -> dict[str, Any]:
        """Para mostrar: el token enmascarado."""
        d = asdict(self)
        d["token"] = mascara_token(self.token)
        return d


def mascara_token(token: str) -> str:
    if not token:
        return "(sin token)"
    return token[:4] + "…" + token[-2:] if len(token) > 12 else "…"


def mascara(texto: str, token: str = "") -> str:
    """Quita cualquier token del texto (registro y salida de comandos)."""
    if token:
        texto = texto.replace(token, mascara_token(token))
    return _TOKEN.sub(lambda m: f"{m.group(1)}_…", texto)


def ruta_proyectos(cfg: Configuracion) -> Path:
    """Carpeta base de los proyectos: la configurada o, si no hay, E:/Agents en Windows
    cuando existe la unidad E: (la Alienware) y ~/Agents en los demás casos."""
    if cfg.ruta_proyectos.strip():
        return Path(cfg.ruta_proyectos.strip())
    if os.name == "nt" and Path("E:\\").is_dir():
        return Path("E:\\Agents")
    return Path.home() / "Agents"


def ruta_config(base: Path | None = None) -> Path:
    return (base or directorio()) / "config.json"


def cargar(base: Path | None = None) -> Configuracion:
    ruta = ruta_config(base)
    if not ruta.is_file():
        return Configuracion(cuentas=cuentas_detectadas())
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    conocidos = {k: v for k, v in datos.items() if k in Configuracion.__dataclass_fields__}
    cfg = Configuracion(**conocidos)
    if not cfg.cuentas:
        cfg.cuentas = cuentas_detectadas()
    return cfg


def _escribir_privado(ruta: Path, texto: str) -> None:
    """Escritura atómica; en Mac y Linux solo la lee el usuario (0600). En Windows,
    dentro del perfil, el permiso heredado ya es solo del usuario."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, ruta)


def guardar(cfg: Configuracion, base: Path | None = None) -> Path:
    ruta = ruta_config(base)
    _escribir_privado(ruta, json.dumps(asdict(cfg), ensure_ascii=False, indent=2))
    return ruta


def validar_servidor(url: str) -> str:
    """https, o http solo hacia la misma PC (pruebas): el token nunca viaja sin cifrar."""
    url = url.strip().rstrip("/")
    partes = urlsplit(url)
    if partes.scheme == "https" and partes.hostname:
        return url
    if partes.scheme == "http" and partes.hostname in ("127.0.0.1", "localhost", "::1"):
        return url
    raise ValueError(
        "La dirección del servidor debe empezar con https:// (http:// solo en la misma PC)."
    )


def clave_local(base: Path | None = None) -> str:
    """Clave entre los hooks y el monitor (X-API-Key): ninguna página web ni otro
    usuario de la PC puede usar la API local sin ella. Se crea la primera vez."""
    ruta = (base or directorio()) / "clave-local.txt"
    try:
        clave = ruta.read_text(encoding="utf-8").strip()
        if clave:
            return clave
    except OSError:
        pass
    clave = secrets.token_urlsafe(32)
    _escribir_privado(ruta, clave)
    return clave

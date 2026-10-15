"""Agente auxiliar de los avisos (etapa 2.4).

Resume cada aviso (permiso pendiente, pregunta, tarea terminada, atasco) en una
frase clara para escucharla: "SkyNest quiere borrar una carpeta de compilación
de Unity y necesita tu permiso". Lo lanza el monitor con ``claude -p`` y Haiku,
con la cuenta del agente que generó el aviso, y totalmente aislado:

- carpeta propia y vacía (``~/.visualizador-monitor/auxiliar``);
- ``--safe-mode``: sin CLAUDE.md, hooks, plugins, skills, MCP ni memoria, pero con
  la sesión de la suscripción (``--bare`` solo acepta una clave de API);
- ``--setting-sources ""`` y ``--settings {"disableAllHooks": true}``: ningún
  archivo de configuración ni hook;
- ``--tools ""``, ``--disallowedTools "mcp__*"``, ``--strict-mcp-config``: ninguna
  herramienta; ``--disable-slash-commands``; ``--max-turns 1``;
- ``--no-session-persistence`` y ``CLAUDE_CODE_SKIP_PROMPT_HISTORY=1``: no guarda la
  sesión ni aparece en el historial; nunca ``--resume`` ni ``--continue``;
- entorno limpio: sin ninguna variable ``CLAUDE*`` o ``ANTHROPIC*`` heredada; la
  cuenta Demo Org lleva ``CLAUDE_CONFIG_DIR``; la personal, la carpeta por defecto;
- la entrada va por la entrada estándar (no en la línea de comandos), con los
  secretos enmascarados y recortada.

Tope de ``TOPE_S`` segundos y ``POR_MINUTO`` llamadas por minuto. Si falla, tarda
o no hay cuenta, no hay frase y la oficina usa el texto de siempre.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from visualizador_monitor.config import directorio
from visualizador_monitor.secretos import enmascarar, palabras_raras, parece_dato

TOPE_S = 8.0
POR_MINUTO = 6
MAX_PALABRAS = 25
MAX_CAMPO = 300
MAX_ENTRADA = 900
MAX_CACHE = 300
MODELO = "haiku"
CARPETA = "auxiliar"
_RUTA_AUXILIAR = "/.visualizador-monitor/auxiliar"
MARCA_AUXILIAR = "VISUALIZADOR_AUXILIAR"

TIPOS = {
    "permiso": "permiso pendiente",
    "pregunta": "pregunta del agente",
    "termino": "tarea terminada",
    "atasco": "el agente parece atascado",
}
_CAMPOS = (
    ("herramienta", "Herramienta"),
    ("detalle", "Comando o detalle"),
    ("pregunta", "Pregunta"),
    ("pedido", "Lo que se le pidió"),
    ("archivos_editados", "Archivos editados"),
    ("commits", "Commits"),
    ("motivo", "Motivo"),
    ("ultimo_intento", "Último intento"),
    ("ultimo_error", "Último error"),
)

_PROSA = frozenset({"pregunta", "pedido", "motivo", "ultimo_error"})

SISTEMA = """Resumes avisos de agentes de programación para que Washington los escuche en voz alta.
Responde con una sola frase en español latino neutro, de máximo 25 palabras.
La frase empieza por el nombre del proyecto, dice qué pasa y qué necesita de Washington.
Nunca incluyas rutas, nombres de archivos, comandos, código, comillas, URL ni datos enmascarados.
Describe la acción en lenguaje sencillo (por ejemplo "borrar una carpeta de compilación de Unity").
Ejemplos:
SkyNest quiere borrar una carpeta de compilación de Unity y necesita tu permiso.
vive-demo te pregunta si publica la versión nueva; espera tu respuesta.
mi-proyecto terminó de corregir el inicio de sesión y está listo para lo siguiente.
buscapez parece atascado: repite el mismo error al compilar; revisa qué intentó."""

# -- entrada ---------------------------------------------------------------------------


def _limpio(valor: Any, largo: int = MAX_CAMPO) -> str | None:
    if isinstance(valor, bool) or valor is None:
        return None
    t = " ".join(str(valor).split())
    if not t:
        return None
    t = enmascarar(t)
    return t if len(t) <= largo else t[: largo - 1] + "…"


def armar_entrada(aviso: Mapping[str, Any]) -> str:
    """El texto que recibe el auxiliar: proyecto, tipo y los datos del aviso."""
    tipo = str(aviso.get("tipo") or "")
    como = str(aviso.get("como") or "")  # un 13 que en realidad es una pregunta
    lineas = [
        f"Proyecto: {_limpio(aviso.get('proyecto'), 80) or 'sin nombre'}",
        f"Tipo de aviso: {TIPOS.get(como, TIPOS.get(tipo, tipo or 'aviso'))}",
    ]
    datos = aviso.get("datos")
    if isinstance(datos, Mapping):
        for clave, nombre in _CAMPOS:
            v = _limpio(datos.get(clave))  # type: ignore[union-attr]
            if v and clave in _PROSA:
                v = acortar_rutas(v)
            if v:
                lineas.append(f"{nombre}: {v}")
    entrada = "\n".join(lineas)
    return entrada if len(entrada) <= MAX_ENTRADA else entrada[: MAX_ENTRADA - 1] + "…"


# -- cuenta y aislamiento -------------------------------------------------------------


def _normal(ruta: str) -> str:
    with contextlib.suppress(OSError, ValueError):
        ruta = os.path.realpath(ruta)  # nombres cortos 8.3, enlaces
    return os.path.normcase(ruta).replace("\\", "/").rstrip("/") + "/"


def es_de_auxiliar(payload: Mapping[str, Any], carpeta: Path | None = None) -> bool:
    """Un evento o solicitud que viene del auxiliar (nunca va a la oficina): por su
    carpeta (la fija o la real, ``carpeta``) o por la marca de entorno del hook."""
    crudo = payload.get("data")
    datos: Mapping[str, Any] = crudo if isinstance(crudo, Mapping) else {}  # type: ignore[assignment]
    if datos.get("auxiliar") is True or payload.get("auxiliar") is True:
        return True
    propia = _normal(str(carpeta)) if carpeta is not None else None
    for clave in ("project_dir", "working_dir", "transcript_path", "cwd"):
        for fuente in (datos, payload):
            v = fuente.get(clave)
            if not isinstance(v, str) or not v:
                continue
            if _RUTA_AUXILIAR + "/" in v.replace("\\", "/").lower() + "/":
                return True
            if propia is not None and _normal(v).startswith(propia):
                return True
    return False


def cuenta_para(transcript: str | None, cuenta: str | None, cuentas: list[Path]) -> Path | None:
    """La carpeta de la cuenta del agente: la que contiene su transcripción o, sin
    ella, la que corresponde a "personal" (.claude) o "demo" (.claude-demo). Nunca
    otra: un aviso de Demo Org no pasa por la cuenta personal ni al revés."""
    if transcript and transcript.startswith(("\\\\", "//")):
        return None  # una ruta de red nunca elige cuenta
    if transcript:
        try:
            ruta = Path(os.path.normpath(os.path.abspath(os.path.expanduser(transcript))))
        except (OSError, ValueError):
            ruta = None
        if ruta is not None:
            dentro = [c for c in cuentas if ruta.is_relative_to(c)]
            if dentro:
                return max(dentro, key=lambda c: len(c.parts))
            return None
    nombres = {"personal": ".claude", "demo": ".claude-demo"}
    buscado = nombres.get(cuenta or "")
    if buscado is None:
        return None
    for c in cuentas:
        if c.name.lower() == buscado:
            return c
    return None


def nombre_cuenta(carpeta: Path) -> str:
    n = carpeta.name.lower()
    if n == ".claude":
        return "personal"
    return n.removeprefix(".claude-") or n


def entorno(cuenta: Path, base: Mapping[str, str], home: Path | None = None) -> dict[str, str]:
    """El entorno del auxiliar: sin variables CLAUDE*/ANTHROPIC* heredadas (ni de
    una sesión de Claude Code ni una clave de API) y con la cuenta elegida."""
    env = {
        k: v
        for k, v in base.items()
        if not k.upper().startswith(("CLAUDE", "ANTHROPIC", "OTEL_"))
        and k.upper() not in ("NODE_OPTIONS",)
    }
    por_defecto = (home or Path.home()) / ".claude"
    if os.path.normcase(str(cuenta)) != os.path.normcase(str(por_defecto)):
        env["CLAUDE_CONFIG_DIR"] = str(cuenta)
    env.update(
        {
            "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1",
            "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
            # Tercera barrera: si algún hook corriera igual, el hook lo ve y no manda nada.
            MARCA_AUXILIAR: "1",
        }
    )
    return env


def comando(claude: str) -> list[str]:
    """La llamada aislada (opciones verificadas en code.claude.com/docs, CLI 2.1.296)."""
    return [
        claude,
        "-p",
        "--model",
        MODELO,
        "--effort",
        "low",
        "--safe-mode",
        "--setting-sources",
        "",
        "--settings",
        json.dumps({"disableAllHooks": True}),
        "--strict-mcp-config",
        "--tools",
        "",
        "--disallowedTools",
        "mcp__*",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--max-turns",
        "1",
        "--system-prompt",
        SISTEMA,
        "--output-format",
        "json",
    ]


def buscar_claude(home: Path | None = None) -> str | None:
    h = home or Path.home()
    candidatos = [
        shutil.which("claude.exe") if os.name == "nt" else shutil.which("claude"),
        str(h / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")),
    ]
    for candidato in candidatos:
        if not candidato or not Path(candidato).is_file():
            continue
        # En Windows solo un ejecutable: un .cmd pasaría por cmd.exe con el prompt
        # de varias líneas, y el script de npm sin extensión no se puede lanzar.
        if os.name == "nt" and not candidato.lower().endswith(".exe"):
            continue
        return candidato
    return None


# -- salida ------------------------------------------------------------------------------

# Rutas (C:\x\y, a/b/c.py, ./x): quedan solo con su último nombre.
_RUTA_LARGA = re.compile(r"(?<![\w:/])(?:[A-Za-z]:)?(?:[\\/]?[\w.~-]+)?(?:[\\/][\w.~-]+)+[\\/]?")
# Lo que no se arregla: código, URL o datos enmascarados.
_PROHIBIDO = re.compile(r"`|https?://|www\.|\[secreto\]")


def acortar_rutas(texto: str) -> str:
    """Cada ruta queda con su último nombre: "src/components/avisos" -> "avisos"."""

    def ultimo(m: re.Match[str]) -> str:
        crudo = m.group(0)
        partes = [x for x in re.split(r"[\\/]", crudo) if x and not x.endswith(":")]
        if not partes:
            return crudo
        es_ruta = (
            "\\" in crudo
            or crudo[:1] in "/.~"
            or re.match(r"[A-Za-z]:", crudo) is not None
            or len(partes) >= 3
            or re.search(r"\.[A-Za-z][\w]{0,5}$", partes[-1]) is not None
        )
        return partes[-1] if es_ruta else crudo  # "y/o", "5/10" no son rutas

    return _RUTA_LARGA.sub(ultimo, texto)


_SUELTAS = frozenset(
    [
        "y",
        "o",
        "u",
        "e",
        "ni",
        "de",
        "del",
        "a",
        "al",
        "en",
        "que",
        "con",
        "para",
        "por",
        "sin",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "su",
        "sus",
        "se",
        "lo",
    ]
)


def _recortar_frase(palabras: list[str]) -> str:
    """Cierra una frase cortada en la última pausa natural (coma, punto y coma) de la
    segunda mitad o, si no hay, sin palabras sueltas al final ("…y.")."""
    for i in range(len(palabras) - 1, len(palabras) // 2, -1):
        if palabras[i].endswith((",", ";", ":")):
            return " ".join(palabras[: i + 1]).rstrip(",;:") + "."
    while len(palabras) > 1 and palabras[-1].lower().strip(",;:") in _SUELTAS:
        palabras = palabras[:-1]
    return " ".join(palabras).rstrip(",;:") + "."


def limpiar_salida(texto: str | None, proyecto: str, entrada: str = "") -> str | None:
    """Una frase de hasta 25 palabras que empieza por el proyecto, sin rutas (quedan
    con su último nombre), o None si no sirve (vacía, con código, URL o datos
    enmascarados)."""
    if not texto:
        return None
    linea = next((x.strip() for x in texto.splitlines() if x.strip()), "")
    linea = linea.strip("\"'“”«»*_ ").replace("**", "")
    linea = " ".join(linea.split())
    if not linea or enmascarar(linea) != linea:
        return None  # la frase trae algo con forma de secreto
    if any(parece_dato(w) for w in re.split(r"[\s/\\]+", linea)):
        return None  # o algo con forma de clave o identificador
    linea = acortar_rutas(linea)
    if not linea or _PROHIBIDO.search(linea) or enmascarar(linea) != linea:
        return None
    # Copia un dato raro de la entrada (algo con letras y números o símbolos)?
    raras = palabras_raras(entrada) - palabras_raras(proyecto)
    if any(w in r or r in w for w in palabras_raras(linea) for r in raras):
        return None
    palabras = linea.split(" ")
    if len(palabras) > MAX_PALABRAS:
        linea = _recortar_frase(palabras[:MAX_PALABRAS])
    if proyecto and linea.lower().startswith(proyecto.lower()):
        linea = proyecto + linea[len(proyecto) :]  # el nombre tal cual ("mi-proyecto")
    elif proyecto:
        # "El agente de SkyNest..." también empieza por el proyecto.
        inicio = linea.lower()[: len(proyecto) + 20]
        if proyecto.lower() not in inicio:
            linea = f"{proyecto}: {linea[0].lower()}{linea[1:]}"
    return linea


# -- llamada ------------------------------------------------------------------------------


@dataclass
class Resultado:
    texto: str | None
    motivo: str | None = None
    segundos: float = 0.0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    costo_usd: float = 0.0
    modelo: str | None = None
    cuenta: str | None = None
    llamo: bool = False
    desde_cache: bool = False

    def metricas(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("texto")
        d.pop("desde_cache")
        return d


class TiempoAgotado(Exception):
    pass


# Procesos del auxiliar en marcha: el monitor los detiene al cerrarse.
_ACTIVOS: set[subprocess.Popen[bytes]] = set()
_ACTIVOS_LOCK = threading.Lock()


def _matar(p: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, check=False
        )
    with contextlib.suppress(OSError):
        p.kill()


def detener_todos() -> int:
    """Detiene los auxiliares que siguen corriendo; devuelve cuántos."""
    with _ACTIVOS_LOCK:
        activos = list(_ACTIVOS)
    for p in activos:
        _matar(p)
    return len(activos)


Ejecutor = Callable[[list[str], bytes, Path, dict[str, str], float], tuple[int, bytes]]


def ejecutar(
    cmd: list[str], entrada: bytes, cwd: Path, env: dict[str, str], tope: float
) -> tuple[int, bytes]:
    """Corre el auxiliar; con el tope cumplido lo detiene (con sus hijos) y avisa."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=cwd,
        env=env,
        creationflags=flags,
    )
    with _ACTIVOS_LOCK:
        _ACTIVOS.add(p)
    try:
        salida, _ = p.communicate(entrada, timeout=tope)
    except subprocess.TimeoutExpired:
        _matar(p)
        with contextlib.suppress(Exception):
            p.communicate(timeout=2)
        raise TiempoAgotado from None
    finally:
        with _ACTIVOS_LOCK:
            _ACTIVOS.discard(p)
    return p.returncode, salida


def _entero(v: Any) -> int:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else 0


class Auxiliar:
    def __init__(
        self,
        cuentas: list[str],
        base: Path | None = None,
        ejecutor: Ejecutor = ejecutar,
        claude: str | None = None,
        reloj: Callable[[], float] = time.monotonic,
        tope: float = TOPE_S,
        por_minuto: int = POR_MINUTO,
        entorno_base: Mapping[str, str] | None = None,
    ) -> None:
        self.cuentas = [Path(os.path.normpath(os.path.abspath(c))) for c in cuentas]
        self.carpeta = (base or directorio()) / CARPETA
        self.ejecutor = ejecutor
        self._claude = claude
        self.reloj = reloj
        self.tope = tope
        self.por_minuto = por_minuto
        self.entorno_base = entorno_base
        self._llamadas: deque[float] = deque()
        self._cache: OrderedDict[str, Resultado] = OrderedDict()
        self._lock = threading.Lock()

    def _guardar(self, clave: str, r: Resultado) -> None:
        with self._lock:
            self._cache[clave] = r
            self._cache.move_to_end(clave)
            while len(self._cache) > MAX_CACHE:
                self._cache.popitem(last=False)

    def _en_cache(self, *claves: str) -> Resultado | None:
        with self._lock:
            for c in claves:
                r = self._cache.get(c)
                if r is not None:
                    return Resultado(**{**asdict(r), "llamo": False, "desde_cache": True})
        return None

    def _turno(self) -> bool:
        """Límite por minuto: True si hay lugar para una llamada más."""
        ahora = self.reloj()
        with self._lock:
            while self._llamadas and ahora - self._llamadas[0] >= 60:
                self._llamadas.popleft()
            if len(self._llamadas) >= self.por_minuto:
                return False
            self._llamadas.append(ahora)
            return True

    def resumir(self, aviso: Mapping[str, Any]) -> Resultado:
        clave = str(aviso.get("clave") or "")
        entrada = armar_entrada(aviso)
        cuenta = cuenta_para(
            aviso.get("transcript") if isinstance(aviso.get("transcript"), str) else None,
            aviso.get("cuenta") if isinstance(aviso.get("cuenta"), str) else None,
            self.cuentas,
        )
        if cuenta is None:
            return Resultado(None, "sin_cuenta")
        # Mismo texto y misma cuenta: la misma frase (recordatorios, reintentos).
        huella = hashlib.sha256(f"{cuenta}\n{entrada}".encode()).hexdigest()
        previo = self._en_cache(clave, huella)
        if previo is not None:
            return previo
        claude = self._claude or buscar_claude()
        if claude is None:
            return Resultado(None, "sin_claude", cuenta=nombre_cuenta(cuenta))
        if not self._turno():
            return Resultado(None, "limite_por_minuto", cuenta=nombre_cuenta(cuenta))
        r = self._llamar(claude, entrada, cuenta, str(aviso.get("proyecto") or ""))
        self._guardar(huella, r)
        if clave:
            self._guardar(clave, r)
        return r

    def _llamar(self, claude: str, entrada: str, cuenta: Path, proyecto: str) -> Resultado:
        nombre = nombre_cuenta(cuenta)
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
        except OSError:
            return Resultado(None, "sin_carpeta", cuenta=nombre)
        env = entorno(cuenta, self.entorno_base if self.entorno_base is not None else os.environ)
        inicio = self.reloj()
        try:
            codigo, salida = self.ejecutor(
                comando(claude), entrada.encode("utf-8"), self.carpeta, env, self.tope
            )
        except TiempoAgotado:
            return Resultado(
                None, "tiempo_agotado", round(self.reloj() - inicio, 2), cuenta=nombre, llamo=True
            )
        except Exception as e:
            return Resultado(
                None,
                f"error_{type(e).__name__}"[:40],
                round(self.reloj() - inicio, 2),
                cuenta=nombre,
            )
        segundos = round(self.reloj() - inicio, 2)
        try:
            datos = json.loads(salida.decode("utf-8", errors="replace"))
        except ValueError:
            datos = None
        if not isinstance(datos, dict):
            return Resultado(None, "salida_ilegible", segundos, cuenta=nombre, llamo=True)
        crudo_uso = datos.get("usage")
        uso: dict[str, Any] = crudo_uso if isinstance(crudo_uso, dict) else {}
        crudo_modelos = datos.get("modelUsage")
        modelos: dict[str, Any] = crudo_modelos if isinstance(crudo_modelos, dict) else {}
        costo = datos.get("total_cost_usd")
        r = Resultado(
            None,
            None,
            segundos,
            tokens_entrada=_entero(uso.get("input_tokens"))
            + _entero(uso.get("cache_creation_input_tokens"))
            + _entero(uso.get("cache_read_input_tokens")),
            tokens_salida=_entero(uso.get("output_tokens")),
            costo_usd=float(costo) if isinstance(costo, (int, float)) else 0.0,
            modelo=next(iter(modelos), None),
            cuenta=nombre,
            llamo=True,
        )
        if codigo != 0 or datos.get("is_error"):
            r.motivo = "error_del_auxiliar"
            return r
        resultado = datos.get("result")
        r.texto = limpiar_salida(
            resultado if isinstance(resultado, str) else None, proyecto, entrada
        )
        if r.texto is None:
            r.motivo = "salida_invalida"
        return r

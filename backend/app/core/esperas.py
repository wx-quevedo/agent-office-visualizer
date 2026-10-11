"""Esperas específicas (etapa 2.1): qué está haciendo o esperando un agente,
en una frase corta con el tiempo transcurrido.

A partir de la herramienta en curso se arma un "sujeto" y se compara con una
tabla de reglas (patrón, texto, minutos razonables):

- Bash / PowerShell: el comando, sin los mensajes de commit ni los cuerpos de
  heredoc (así "push" o "pytest" dentro de un mensaje no confunden).
- MCP: ``mcp:<servidor>:<herramienta>`` (de ``mcp__servidor__herramienta``; los
  servidores de plugins ``plugin_<plugin>_<servidor>`` quedan como ``<servidor>``).
- Subagente (Task / Agent): ``subagente:<descripción>``.
- Otras herramientas: ``herramienta:<nombre>:<detalle>``.

Las reglas de comandos solo coinciden donde empieza un comando (inicio, o
después de ``&&``, ``;``, ``|``, ``(``), aceptando prefijos como ``npx``,
``uv run``, ``python -m``, ``sudo``, variables de entorno o la ruta del
ejecutable: ``grep pytest docs/`` no es "corriendo pruebas".

La primera regla que coincide da el texto (``{1}``, ``{2}``... son los grupos
del patrón). Sin regla: el ejecutable (o la herramienta) y el tiempo. Los
minutos son el tiempo razonable para ese tipo de tarea: pasado ese tiempo el
detector de atascos la marca (sin minutos: nunca, como un servidor).

La tabla se puede ampliar con un archivo de texto (``esperas.txt`` junto al
registro del motor, o ``ESPERAS_PATH``): una regla por línea,
``patrón ## texto ## minutos`` (minutos opcionales), ``#`` es comentario. Sus
reglas van antes que las de fábrica (ganan); una línea inválida se ignora.
"""

from __future__ import annotations

import re
import shlex
import time
from dataclasses import dataclass
from pathlib import Path

# Minutos razonables para lo que no tiene regla.
LIMITE_POR_DEFECTO_MIN = 10.0
_LARGO_GRUPO = 60


@dataclass(frozen=True)
class Regla:
    patron: re.Pattern[str]
    texto: str
    limite_min: float | None


# Inicio de un comando y sus prefijos habituales; luego el ejecutable con o sin ruta.
C = (
    r"(?:^|[;&|(\n]\s*)(?:[\w.-]+=\S*\s+|sudo\s+|npx\s+|bunx\s+|pnpm\s+dlx\s+|uvx\s+"
    r"|uv\s+run\s+(?:--?\S+\s+)*|python3?\s+-m\s+|py\s+-m\s+|timeout\s+\d+\s+|time\s+|&\s*)*"
    r"(?:\"[^\"\n]*[\\/]|'[^'\n]*[\\/]|[^\"'\s;&|]*[\\/])?"
)
_MCP = r"^mcp:(?:plugin_[^:]*_)?"

# (patrón, texto, minutos razonables). El orden importa: gana la primera.
PREDETERMINADAS: list[tuple[str, str, float | None]] = [
    # -- Unity -----------------------------------------------------------------
    (_MCP + r"unity[^:]*:[^:]*(?:compile|recompile|refresh)", "Unity: compilando scripts", 15),
    (_MCP + r"unity[^:]*:[^:]*test", "Unity: corriendo pruebas", 30),
    (_MCP + r"unity[^:]*:[^:]*build", "Unity: compilando el proyecto", 60),
    (_MCP + r"unity[^:]*:(.+)", "Unity: {1}", 10),
    (C + r"unity(?:\.exe)?[\"']?\s.*-runtests", "Unity: corriendo pruebas", 30),
    (
        C + r"unity(?:\.exe)?[\"']?\s.*(?:-buildtarget|-executemethod|-build\w*player)",
        "Unity: compilando el proyecto",
        60,
    ),
    (C + r"unity(?:\.exe)?[\"']?\s.*-batchmode", "Unity: compilando scripts", 15),
    # -- Blender ---------------------------------------------------------------
    (_MCP + r"blender[^:]*:[^:]*render", "Blender: render", 60),
    (_MCP + r"blender[^:]*:(.+)", "Blender: {1}", 10),
    (
        C + r"blender(?:\.exe)?[\"']?\s.*\s(?:-f|-a|--render-frame|--render-anim)\b",
        "Blender: render",
        60,
    ),
    (C + r"blender(?:\.exe)?[\"']?(?:\s|$)", "Blender: ejecutando un script", 15),
    # -- Servidores y procesos que siguen corriendo (sin límite) ----------------------
    (
        C + r"(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:dev|start|serve|preview)\b"
        r"|" + C + r"(?:next\s+(?:dev|start)|vite(?:\s|$)|uvicorn|flask\s+run|http\.server)"
        r"|" + C + r"php\s+artisan\s+serve",
        "Servidor de desarrollo",
        None,
    ),
    (
        C + r"(?:tail\s+-[a-z]*f|gh\s+run\s+watch|docker\s+(?:compose\s+)?logs\s+-[a-z]*f)",
        "Siguiendo un registro",
        None,
    ),
    # -- Dependencias ------------------------------------------------------------
    (C + r"(npm|pnpm|yarn|bun)\s+(?:install|i|ci|add)\b", "Instalando dependencias ({1})", 15),
    (
        C + r"(?:uv\s+(?:sync|add|pip\s+install)|pip3?\s+install|poetry\s+install)\b",
        "Instalando dependencias (Python)",
        15,
    ),
    (C + r"composer\s+(?:install|update|require)\b", "Instalando dependencias (Composer)", 15),
    (C + r"(?:dotnet|nuget)\s+restore\b", "Instalando dependencias (.NET)", 15),
    (C + r"playwright\s+install\b", "Descargando navegadores (Playwright)", 15),
    (
        C + r"(?:apt(?:-get)?\s+install|winget\s+(?:install|upgrade)|choco\s+install)\b",
        "Instalando programas",
        20,
    ),
    # -- Pruebas -----------------------------------------------------------------
    (C + r"pytest\b", "Corriendo pruebas (pytest)", 20),
    (
        C + r"(vitest|jest|mocha)\b|" + C + r"(playwright)\s+test\b",
        "Corriendo pruebas ({1}{2})",
        20,
    ),
    (C + r"(npm|pnpm|yarn|bun|deno)\s+(?:run\s+)?test\b", "Corriendo pruebas ({1})", 20),
    (C + r"dotnet\s+test\b", "Corriendo pruebas (.NET)", 20),
    (C + r"cargo\s+test\b", "Corriendo pruebas (cargo)", 20),
    (C + r"go\s+test\b", "Corriendo pruebas (go)", 20),
    (C + r"(?:phpunit|php\s+artisan\s+test|pest)(?:\s|$)", "Corriendo pruebas (PHP)", 20),
    (C + r"make\s+(?:test|checkall|check)\b", "Corriendo pruebas (make)", 25),
    # -- Revisión y compilación ----------------------------------------------------
    (C + r"tsc\b[^;&|]*--noemit", "Revisando tipos (tsc)", 10),
    (C + r"(pyright|mypy)\b", "Revisando tipos ({1})", 10),
    (C + r"(eslint|ruff|prettier|black)\b", "Revisando el estilo ({1})", 10),
    (
        C + r"(npm|pnpm|yarn|bun)\s+run\s+(?:lint|typecheck|check|format)\b",
        "Revisando el código ({1})",
        10,
    ),
    (
        C + r"(?:(?:next|vite|webpack|turbo)\s+build|(?:npm|pnpm|yarn|bun)\s+run\s+build)\b",
        "Compilando el frontend",
        15,
    ),
    (C + r"(?:dotnet\s+(?:build|publish|run)|msbuild)\b", "Compilando (.NET)", 20),
    (C + r"cargo\s+(?:build|check|clippy|run)\b", "Compilando (cargo)", 20),
    (C + r"go\s+(?:build|vet|run)\b", "Compilando (go)", 15),
    (C + r"(?:cmake\s+--build|ninja)\b", "Compilando (CMake)", 30),
    (C + r"gradlew?(?:\.bat)?(?:\s|$)", "Compilando (Gradle)", 30),
    (C + r"pyinstaller\b|empaquetar\.py", "Empaquetando el instalador", 15),
    (C + r"docker\s+(?:compose\s+)?build\b", "Construyendo la imagen (Docker)", 30),
    (C + r"docker\s+(?:compose\s+up|run)\b", "Levantando contenedores (Docker)", 15),
    # -- Git y red -----------------------------------------------------------------
    (C + r"git\s+(?:-\S+\s+\S+\s+)*push\b", "Subiendo cambios (git push)", 10),
    (C + r"git\s+(?:-\S+\s+\S+\s+)*(pull|fetch|clone)\b", "Descargando de git (git {1})", 10),
    (C + r"git\s+(?:-\S+\s+\S+\s+)*commit\b", "Haciendo commit", 10),
    (r"desplegar\.sh", "Desplegando al servidor", 15),
    (C + r"(?:ssh|scp|rsync)(?:\.exe)?(?:\s|$)", "Trabajando en un servidor remoto", 15),
    (
        C + r"(?:curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm)\b",
        "Descargando de la red",
        15,
    ),
    (C + r"(?:expand-archive|unzip|7z|tar\s+-?[a-z]*x)\b", "Descomprimiendo", 10),
    (C + r"(?:robocopy|copy-item\b.*-recurse|xcopy)\b", "Copiando archivos", 15),
    # -- Otros ---------------------------------------------------------------------
    (C + r"ffmpeg\b", "Procesando audio o video (ffmpeg)", 30),
    (C + r"claude(?:\.exe)?\s[^;&|]*(?:\s-p\b|--print\b)", "Agente auxiliar (claude -p)", 15),
    (C + r"sleep\s+(\d+(?:\.\d+)?)\s*([smhd]?)\b", "Esperando (sleep {1}{2})", None),
    (C + r"start-sleep\s+(?:-s(?:econds)?\s+)?(\d+(?:\.\d+)?)(?:\s|$)", "Esperando ({1} s)", None),
    (C + r"start-sleep\s+-m(?:illiseconds)?\s+(\d+)", "Esperando ({1} ms)", None),
    # -- Herramientas de Claude Code -------------------------------------------------
    (r"^subagente:\s*$", "Subagente", 60),
    (r"^subagente:(.+)", "Subagente: {1}", 60),
    (r"^herramienta:webfetch\b", "Leyendo una página web", 5),
    (r"^herramienta:websearch\b", "Buscando en la web", 5),
    (r"^herramienta:(?:read|grep|glob|ls)\b", "Leyendo archivos", 5),
    (r"^herramienta:(?:edit|write|multiedit|notebookedit)\b", "Editando archivos", 5),
    (_MCP + r"claude-in-chrome:(.+)", "Navegador: {1}", 10),
    (r"^mcp:([^:]+):(.+)", "{1}: {2}", 10),
]

ENCABEZADO = """# Esperas específicas propias: qué hace o espera un agente, en una frase.
# Una regla por línea:  patrón ## texto ## minutos razonables (opcional)
# El patrón es una expresión regular (sin distinguir mayúsculas) contra el "sujeto":
#   Bash/PowerShell: el comando;  MCP: mcp:servidor:herramienta;
#   subagente: subagente:descripción;  otras: herramienta:nombre:detalle.
# {1}, {2}... en el texto son los grupos del patrón. Estas reglas van antes que
# las de fábrica (ganan). Sin minutos: nunca se marca como atasco.
# Ejemplos:
# generar_informe\\.py ## Generando el informe mensual ## 20
# ^mcp:figma:(.+) ## Figma: {1} ## 5
"""


def texto_predeterminado() -> str:
    """La tabla de fábrica escrita como archivo (referencia y pruebas)."""
    lineas = [ENCABEZADO]
    for patron, texto, minutos in PREDETERMINADAS:
        sufijo = f" ## {minutos:g}" if minutos is not None else ""
        lineas.append(f"{patron} ## {texto}{sufijo}")
    return "\n".join(lineas) + "\n"


def leer_reglas(texto: str) -> list[Regla]:
    """Reglas de un archivo; una línea inválida se ignora."""
    reglas: list[Regla] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = [p.strip() for p in linea.split(" ## ")]
        if len(partes) < 2 or not partes[0] or not partes[1]:
            continue
        limite: float | None = None
        if len(partes) >= 3 and partes[2]:
            try:
                limite = float(partes[2])
            except ValueError:
                continue
        try:
            reglas.append(Regla(re.compile(partes[0], re.IGNORECASE), partes[1], limite))
        except re.error:
            continue
    return reglas


_PREDETERMINADAS = [Regla(re.compile(p, re.IGNORECASE), t, m) for p, t, m in PREDETERMINADAS]
_cache: dict[str, tuple[float, float, list[Regla]]] = {}
_TTL_S = 5.0


def cargar_reglas(ruta: Path | None) -> list[Regla]:
    """Las reglas propias del archivo (si hay) seguidas de las de fábrica.

    El archivo se relee si cambió (como mucho cada 5 s)."""
    if ruta is None:
        return _PREDETERMINADAS
    ahora = time.monotonic()
    guardadas = _cache.get(str(ruta))
    if guardadas and ahora - guardadas[1] < _TTL_S:
        return guardadas[2]
    try:
        mtime = ruta.stat().st_mtime
    except OSError:
        _cache[str(ruta)] = (-1.0, ahora, _PREDETERMINADAS)
        return _PREDETERMINADAS
    if guardadas and guardadas[0] == mtime:
        _cache[str(ruta)] = (mtime, ahora, guardadas[2])
        return guardadas[2]
    try:
        propias = leer_reglas(ruta.read_text(encoding="utf-8-sig"))
    except OSError:
        propias = []
    reglas = propias + _PREDETERMINADAS
    _cache[str(ruta)] = (mtime, ahora, reglas)
    return reglas


def crear_archivo(ruta: Path) -> None:
    """El archivo de reglas propias con su explicación, si no existe."""
    if not ruta.exists():
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(ENCABEZADO, encoding="utf-8")
        except OSError:
            pass


def duracion(segundos: float) -> str:
    """40 s, 2 min, 1 h 5 min."""
    s = max(0, int(segundos))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    h, m = divmod(s // 60, 60)
    return f"{h} h {m} min" if m else f"{h} h"


_ENV = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PREFIJOS = {
    "sudo",
    "env",
    "time",
    "nohup",
    "npx",
    "bunx",
    "uvx",
    "call",
    "exec",
    "&",
    ".",
    "timeout",
}
_NAVEGACION = {"cd", "pushd", "popd", "set-location", "sl", "source", "export", "set"}
_INTERPRETES = {
    "python",
    "python3",
    "py",
    "node",
    "deno",
    "bun",
    "uv",
    "php",
    "ruby",
    "pwsh",
    "powershell",
}


def _nombre(p: str) -> str:
    nombre = re.split(r"[\\/]", p.strip("\"'"))[-1]
    return re.sub(r"\.(exe|cmd|bat|ps1|sh)$", "", nombre, flags=re.IGNORECASE) or p


def ejecutable(comando: str) -> str:
    """El programa de un comando: salta cd/export, variables y prefijos; para un
    intérprete agrega el script (``python informe.py``)."""
    for segmento in re.split(r"&&|\|\||[;|\n]", comando.strip()):
        try:
            partes = shlex.split(segmento, posix=False)
        except ValueError:
            partes = segmento.split()
        partes = [p for p in partes if p]
        i = 0
        while i < len(partes) and (_ENV.match(partes[i]) or partes[i].lower() in _PREFIJOS):
            i += 1
            if i < len(partes) and partes[i - 1].lower() == "timeout" and partes[i].isdigit():
                i += 1
        # "uv run [opciones] programa" es un prefijo más.
        if i + 1 < len(partes) and partes[i].lower() == "uv" and partes[i + 1].lower() == "run":
            i += 2
            while i < len(partes) and partes[i].startswith("-"):
                i += 1
        if i >= len(partes):
            continue
        prog = _nombre(partes[i])
        if prog.lower() in _NAVEGACION:
            continue
        if prog.lower() in _INTERPRETES:
            resto = [
                p
                for p in partes[i + 1 :]
                if not p.startswith("-") and p.lower() not in ("run", "-m")
            ]
            if resto:
                return f"{prog} {_nombre(resto[0])}"
        return prog
    return comando.strip()[:40] or "un comando"


_HERRAMIENTAS_TERMINAL = {"bash", "powershell"}
_HERRAMIENTAS_SUBAGENTE = {"task", "agent"}
_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", re.DOTALL)
_MENSAJE = re.compile(r"""(\s(?:-\w*m|--message|-F)(?:\s+|=))(?:"(?:[^"\\]|\\.)*"|'[^']*'|\S+)""")


_SEPARADOR = re.compile(r"(&&|\|\||[;|\n])")
_GIT_COMMIT = re.compile(r"\bgit\b.*\bcommit\b", re.IGNORECASE | re.DOTALL)


def limpiar_comando(comando: str) -> str:
    """Sin cuerpos de heredoc ni mensajes de commit (para comparar con las reglas)."""
    sin_heredoc = _HEREDOC.sub("<<heredoc", comando)
    partes = _SEPARADOR.split(sin_heredoc)
    return "".join(_MENSAJE.sub(r"\1<mensaje>", p) if _GIT_COMMIT.search(p) else p for p in partes)


def sujeto(tool_name: str | None, command: str | None, descripcion: str | None) -> str:
    nombre = (tool_name or "").strip()
    bajo = nombre.lower()
    if bajo in _HERRAMIENTAS_TERMINAL:
        return limpiar_comando(command or "").strip()
    if bajo.startswith("mcp__"):
        partes = nombre.split("__")
        servidor = partes[1] if len(partes) > 1 else ""
        # Servidores de plugins: "plugin_<plugin>_<servidor>" -> "<servidor>".
        if servidor.startswith("plugin_") and servidor.count("_") >= 2:
            servidor = servidor.split("_", 2)[2]
        herramienta = "__".join(partes[2:]) if len(partes) > 2 else ""
        return f"mcp:{servidor}:{herramienta}"
    if bajo in _HERRAMIENTAS_SUBAGENTE:
        return f"subagente:{descripcion or command or ''}"
    return f"herramienta:{bajo}:{command or ''}"


def _aplicar(texto: str, m: re.Match[str], mcp: bool) -> str:
    def grupo(g: re.Match[str]) -> str:
        i = int(g.group(1))
        try:
            valor = (m.group(i) or "").strip()
        except IndexError:
            return ""
        if mcp:
            valor = re.sub(r"_+", " ", valor)
        return valor if len(valor) <= _LARGO_GRUPO else valor[: _LARGO_GRUPO - 1] + "…"

    return re.sub(r"\{(\d+)\}", grupo, texto)


def describir(
    tool_name: str | None,
    command: str | None,
    descripcion: str | None,
    segundos: float,
    reglas: list[Regla],
) -> dict[str, object]:
    """La frase de la tarea en curso: texto, tiempo y minutos razonables."""
    suj = sujeto(tool_name, command, descripcion)
    for regla in reglas:
        m = regla.patron.search(suj)
        if m:
            base = _aplicar(regla.texto, m, suj.startswith("mcp:"))
            return {
                "texto": f"{base}, {duracion(segundos)}",
                "base": base,
                "segundos": int(segundos),
                "limite_min": regla.limite_min,
                "regla": regla.patron.pattern[:200],
                "sujeto": suj[:200],
            }
    bajo = (tool_name or "").lower()
    if bajo in _HERRAMIENTAS_TERMINAL and command and command.strip():
        base = f"Ejecutando {ejecutable(command)}"
    else:
        base = tool_name or "Trabajando"
    return {
        "texto": f"{base}, {duracion(segundos)}",
        "base": base,
        "segundos": int(segundos),
        "limite_min": LIMITE_POR_DEFECTO_MIN,
        "regla": None,
        "sujeto": suj[:200],
    }


def espera_fija(texto: str, segundos: float) -> dict[str, object]:
    """Esperas que no dependen de una herramienta (permiso, respuesta)."""
    return {
        "texto": f"{texto}, {duracion(segundos)}",
        "base": texto,
        "segundos": int(segundos),
        "limite_min": None,
        "regla": None,
        "sujeto": None,
    }

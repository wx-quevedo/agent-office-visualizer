"""Equipos de proyectos (etapa 4, Prompts 37 y 38).

El servidor deja encargos para esta máquina y el monitor:

- **Crear**: arma la carpeta del proyecto solo dentro de su ruta base (comprobada
  con la ruta real, sin enlaces que la saquen de ahí), hace ``git init``, deja un
  PROJECT.md mínimo y aplica la plantilla. Después lanza el equipo.
- **Lanzar**: una sesión ``claude -p`` con entrada y salida stream-json por miembro
  (orquestador y agentes de código), en la carpeta del proyecto, con la cuenta del
  proyecto (``CLAUDE_CONFIG_DIR`` solo para Demo Org), ``--model``, ``--effort``, un
  ``--append-system-prompt`` con su rol y el id de sesión que decidió el servidor.
  Los hooks del visualizador las siguen viendo: cargan la configuración del usuario.
- **Pausar y detener**: cierra la entrada de los procesos que lanzó este monitor y,
  si no terminan, los detiene. Nunca toca otros procesos. Detener deja el equipo
  "detenido" (la carpeta queda intacta); los dos se reanudan con ``--resume <id>``.
- **Reinicio del monitor**: retoma los equipos que estaban activos. Si un proceso
  suyo anterior sigue vivo (mismo PID y misma hora de creación), lo detiene antes.

Chat y órdenes (Prompt 38), con el monitor de intermediario:

- Nadie más les escribe a estas sesiones: el orquestador arranca sin ``SendMessage``,
  ``ListAgents``, ``Bash`` ni ``PowerShell`` y los agentes rechazan los mensajes de
  otras sesiones (``crossSessionInbound: refuse``). Solo el monitor escribe, por la
  entrada estándar de cada proceso que lanzó.
- Los mensajes de Washington ("mensaje") van al orquestador; lo que responde en cada
  turno va al chat. Cuando su respuesta trae un bloque ``<orden agente="...">...</orden>``
  para un agente de código de su proyecto, el monitor lo registra en el servidor, que
  lo deja por aprobar; si el destino no es un agente de ese proyecto, no sale a ningún
  lado y se le avisa al orquestador.
- Una orden aprobada llega como encargo "orden" y se escribe solo al agente elegido de
  ese mismo proyecto. Si está ocupado, espera en la cola de ese agente. Al terminar
  el turno, el monitor informa el resumen y se lo pasa al orquestador. Un rechazo
  ("rechazo") le llega al orquestador con su motivo.
- Las colas, lo que está en curso y lo que falta mandar al servidor se guardan en
  ``equipos.json``: pausar, reanudar o reiniciar el monitor no pierden nada. Una orden
  que estaba en curso cuando se cortó la sesión se informa fallida (no se repite sola:
  pudo quedar a medias) y el orquestador se entera.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from visualizador_monitor.auxiliar import buscar_claude, cuenta_para
from visualizador_monitor.cliente import Servidor, SinConexion
from visualizador_monitor.procesos import hora_creacion, proceso_vivo
from visualizador_monitor.registro import logger

NOMBRE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?$")
RESERVADOS = frozenset(
    {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(10)} | {f"lpt{i}" for i in range(10)}
)
ESFUERZOS = frozenset({"low", "medium", "high", "xhigh", "max"})
MODELO = re.compile(r"^[A-Za-z0-9.\-\[\]]{2,60}$")
SESION = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ID_SERVIDOR = re.compile(r"^[0-9a-f]{32}$")
ESPERA_CIERRE = 20.0  # segundos para que una sesión termine sola al pausar
ARRANQUE = 3.0  # segundos que una sesión recién lanzada debe seguir viva
MAX_CHAT = 20000  # caracteres de una respuesta del orquestador al chat
MAX_RESUMEN = 3000  # caracteres del resumen del resultado de una orden
MAX_VISTOS = 500  # ids de encargos ya encolados que se recuerdan (reentregas)
# Lo que el orquestador no puede usar: mensajes a otras sesiones y la terminal (con la
# terminal podría lanzar o retomar otra sesión por su cuenta).
BLOQUEADAS_ORQUESTADOR = "SendMessage,ListAgents,Bash,PowerShell"

PLANTILLAS: dict[str, tuple[str, str | None]] = {
    "vacia": ("Vacía", None),
    "web": (
        "Web",
        "node_modules/\n.next/\nout/\ndist/\nbuild/\n.env\n.env.*\n!.env.example\n"
        "*.log\n.DS_Store\nThumbs.db\n.vercel/\ncoverage/\n",
    ),
    "unity": (
        "Unity",
        "[Ll]ibrary/\n[Tt]emp/\n[Oo]bj/\n[Bb]uild/\n[Bb]uilds/\n[Ll]ogs/\n[Uu]ser[Ss]ettings/\n"
        "[Mm]emoryCaptures/\n*.csproj\n*.unityproj\n*.sln\n*.suo\n*.user\n*.pidb\n*.booproj\n"
        "*.apk\n*.aab\n*.unitypackage\n.vs/\n.idea/\n.DS_Store\nThumbs.db\n",
    ),
    "expo": (
        "App Expo",
        "node_modules/\n.expo/\ndist/\nweb-build/\nexpo-env.d.ts\nios/\nandroid/\n*.jks\n*.p8\n"
        "*.p12\n*.key\n*.mobileprovision\n*.orig.*\n.env\n.env.*\n!.env.example\n*.log\n"
        ".DS_Store\nThumbs.db\n",
    ),
}

ROL_ORQUESTADOR = (
    "Eres el orquestador del proyecto {nombre}. Diseñas y planificas con Washington: "
    "conversas, propones y ordenas el trabajo en etapas. Los agentes de código de este "
    "proyecto son: {agentes}. Para darle una orden a uno de ellos, escribe en tu respuesta "
    "un bloque con este formato exacto, un bloque por orden:\n"
    '<orden agente="NOMBRE" estimado="10 min" dificultad="baja">\n'
    "La instrucción completa, clara y autocontenida.\n"
    "</orden>\n"
    "estimado y dificultad (baja, media o alta) son opcionales. Washington aprueba, edita "
    "o rechaza cada orden antes de que llegue al agente; después recibirás el resultado o "
    "el motivo del rechazo. No tienes otra forma de escribirles a otras sesiones. "
    "Responde en español latino neutro."
)
ROL_AGENTE = (
    "Eres {miembro}, agente de código del proyecto {nombre}. Recibes órdenes del "
    "orquestador de este proyecto aprobadas por Washington y no empiezas trabajo por tu "
    "cuenta. Al terminar cada orden, responde con un resumen breve de lo que hiciste y "
    "del resultado. Responde en español latino neutro."
)
SALUDO = {
    "orquestador": (
        "Se creó el proyecto {nombre}. Preséntate en una sola frase y espera "
        "a que Washington te escriba."
    ),
    "agente": "Se creó el proyecto {nombre}. Responde solo: listo, esperando órdenes.",
}
ORDEN_AL_AGENTE = "Orden {numero} del orquestador, aprobada por Washington:\n\n{texto}"
RESULTADO = "Resultado de la orden {numero} para {agente} ({estado}):\n{resumen}"
EDITADA = (
    "Washington editó esta orden antes de aprobarla. El agente recibió este texto:\n{texto}\n\n"
)
RECHAZO = "Washington rechazó la orden {numero} para {agente}. Motivo: {motivo}"
INTERRUMPIDA = (
    "La orden {numero} para {agente} se interrumpió: {motivo}. Puede haber quedado a medias; "
    "revisa antes de proponerla de nuevo."
)
DESTINO_INVALIDO = (
    'La orden para "{agente}" no se registró: no es un agente de código de este proyecto. '
    "Los agentes son: {agentes}."
)
NO_REGISTRADA = "La orden para {agente} no se registró en el servidor: {detalle}"
ORDEN_VACIA = "La orden para {agente} no se registró: venía sin una instrucción concreta."
AGREGADO = "Se agregó al equipo el agente de código {miembro}. Ya puedes darle órdenes."
# Una sesión retomada conserva el --append-system-prompt con el que nació (Claude Code
# ignora uno nuevo al usar --resume): si su rol cambió, se le escribe una vez.
ROL_ACTUALIZADO = (
    "Actualización de tus instrucciones, hecha por Washington a través del monitor. "
    "Desde ahora reemplazan por completo a las de tu sistema donde se contradigan:\n\n{rol}"
)

_BLOQUE = re.compile(r"<orden\b([^>]*)>(.*?)</orden\s*>", re.S | re.I)
# Código en línea (`...` dentro de una frase): un bloque citado así no es una orden.
_CODIGO_EN_LINEA = re.compile(r"(?<!`)`(?!`)[^`\n]+`(?!`)")
_ATRIBUTO = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


class EquipoError(Exception):
    pass


# -- carpeta ----------------------------------------------------------------------------


def validar_nombre(nombre: Any) -> str:
    if not isinstance(nombre, str) or not NOMBRE.fullmatch(nombre) or nombre in RESERVADOS:
        raise EquipoError("Nombre de proyecto no válido.")
    return nombre


def carpeta_segura(base: Path, nombre: str) -> Path:
    """La carpeta del proyecto, solo si queda justo dentro de la ruta base real y
    todavía no existe. Crea la ruta base si falta."""
    validar_nombre(nombre)
    if str(base).startswith(("\\\\", "//")):
        raise EquipoError("La ruta base no puede ser una ruta de red.")
    if not base.is_absolute():
        raise EquipoError("La ruta base tiene que ser absoluta.")
    try:
        base.mkdir(parents=True, exist_ok=True)
        base_real = base.resolve(strict=True)
    except OSError as e:
        raise EquipoError(f"No se pudo usar la ruta base ({type(e).__name__}).") from None
    carpeta = base_real / nombre
    if os.path.lexists(carpeta):
        raise EquipoError("Ya existe una carpeta con ese nombre en la ruta base.")
    real = carpeta.resolve(strict=False)
    if os.path.normcase(str(real.parent)) != os.path.normcase(str(base_real)):
        raise EquipoError("La carpeta quedaría fuera de la ruta base.")
    return carpeta


def preparar_carpeta(
    carpeta: Path,
    nombre: str,
    plantilla: str,
    hoy: str,
    git: Callable[[Path], None] | None = None,
) -> None:
    """Crea la carpeta, ``git init``, un PROJECT.md mínimo y la plantilla."""
    if plantilla not in PLANTILLAS:
        raise EquipoError("Plantilla desconocida.")
    titulo, gitignore = PLANTILLAS[plantilla]
    carpeta.mkdir(parents=False, exist_ok=False)
    (git or git_init)(carpeta)
    lineas = [
        f"# {nombre}",
        "",
        f"Proyecto creado el {hoy} desde la oficina de agentes.",
    ]
    if gitignore is not None:
        lineas.append(f"Plantilla: {titulo} (con un .gitignore para {titulo}).")
        (carpeta / ".gitignore").write_text(gitignore, encoding="utf-8")
    (carpeta / "PROJECT.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def git_init(carpeta: Path) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        r = subprocess.run(
            ["git", "init", "-q"],
            cwd=carpeta,
            capture_output=True,
            timeout=30,
            creationflags=flags,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise EquipoError(f"No se pudo ejecutar git init ({type(e).__name__}).") from None
    if r.returncode != 0:
        raise EquipoError("git init falló.")


# -- órdenes en la respuesta del orquestador ------------------------------------------------


def extraer_ordenes(texto: str) -> tuple[list[dict[str, str | None]], str]:
    """Las órdenes que trae una respuesta del orquestador y el texto sin los bloques.
    Cada orden: agente, texto, estimado y dificultad (estos dos, si los dio)."""
    citas = [c.span() for c in _CODIGO_EN_LINEA.finditer(texto)]
    ordenes: list[dict[str, str | None]] = []
    partes: list[str] = []
    previo = 0
    for bloque in _BLOQUE.finditer(texto):
        if any(a <= bloque.start() < b for a, b in citas):
            continue  # lo menciona entre comillas invertidas: es texto, no una orden
        attrs = {k.lower(): v.strip() for k, v in _ATRIBUTO.findall(bloque.group(1))}
        cuerpo = bloque.group(2).strip()
        ordenes.append(
            {
                "agente": attrs.get("agente", ""),
                # Un relleno ("...") no es una instrucción.
                "texto": cuerpo if cuerpo.strip(". \u2026") else "",
                "estimado": attrs.get("estimado") or None,
                "dificultad": attrs.get("dificultad") or None,
            }
        )
        partes.append(texto[previo : bloque.start()])
        previo = bloque.end()
    partes.append(texto[previo:])
    sin_cercas = re.sub(r"```[A-Za-z]*\s*```", "", "".join(partes))  # la que envolvía la orden
    limpio = re.sub(r"\n{3,}", "\n\n", sin_cercas).strip()
    return ordenes, limpio


# -- sesiones -----------------------------------------------------------------------------


@dataclass
class Miembro:
    rol: str
    nombre: str
    modelo: str
    esfuerzo: str
    session_id: str
    lanzado: bool = False
    pid: int | None = None
    creado: float | None = None
    # Huella del rol con el que nació o con el que se actualizó (ver ROL_ACTUALIZADO).
    rol_huella: str | None = None


@dataclass
class Proyecto:
    id: str
    nombre: str
    carpeta: str
    cuenta: str
    activo: bool = False
    miembros: list[Miembro] = field(default_factory=lambda: [])
    detenido: bool = False
    # Por miembro: lo que espera su turno y lo que se le escribió y todavía no termina.
    colas: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: {})
    en_curso: dict[str, dict[str, Any]] = field(default_factory=lambda: {})
    # Mensajes, órdenes y rechazos ya encolados (el servidor puede reentregarlos).
    vistos: list[str] = field(default_factory=lambda: [])

    def orquestador(self) -> Miembro | None:
        return next((m for m in self.miembros if m.rol == "orquestador"), None)

    def agente(self, nombre: str) -> Miembro | None:
        """Solo un agente de código de este proyecto (nunca el orquestador ni otro)."""
        return next((m for m in self.miembros if m.rol == "agente" and m.nombre == nombre), None)

    def agentes(self) -> list[str]:
        return [m.nombre for m in self.miembros if m.rol == "agente"]


def miembros_de(equipo: Any) -> list[Miembro]:
    if not isinstance(equipo, list) or not equipo:
        raise EquipoError("El encargo no trae el equipo.")
    salida: list[Miembro] = []
    for m in equipo:
        if not isinstance(m, dict):
            raise EquipoError("Miembro no válido.")
        rol, nombre = m.get("rol"), m.get("nombre")
        modelo, esfuerzo, sid = m.get("modelo"), m.get("esfuerzo"), m.get("session_id")
        if (
            rol not in ("orquestador", "agente")
            or not isinstance(nombre, str)
            or not re.fullmatch(r"[a-z0-9-]{1,40}", nombre)
            or not isinstance(modelo, str)
            or not MODELO.fullmatch(modelo)
            or esfuerzo not in ESFUERZOS
            or not isinstance(sid, str)
            or not SESION.fullmatch(sid)
        ):
            raise EquipoError("Miembro no válido.")
        salida.append(Miembro(rol, nombre, modelo, esfuerzo, sid))
    return salida


def texto_rol(proyecto: Proyecto, m: Miembro) -> str:
    if m.rol == "orquestador":
        return ROL_ORQUESTADOR.format(
            nombre=proyecto.nombre, agentes=", ".join(proyecto.agentes()) or "ninguno"
        )
    return ROL_AGENTE.format(nombre=proyecto.nombre, miembro=m.nombre)


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def comando_sesion(claude: list[str], proyecto: Proyecto, m: Miembro, reanudar: bool) -> list[str]:
    rol = texto_rol(proyecto, m)
    cmd = [
        *claude,
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        m.modelo,
        "--effort",
        m.esfuerzo,
        "--permission-mode",
        # El agente solo trabaja con órdenes aprobadas: edita archivos de su carpeta sin
        # pedir permiso; la terminal sigue pidiéndolo. El orquestador, como siempre.
        "acceptEdits" if m.rol == "agente" else "default",
        "--name",
        f"{proyecto.nombre}-{m.nombre}",
        "--append-system-prompt",
        rol,
    ]
    cmd += ["--resume", m.session_id] if reanudar else ["--session-id", m.session_id]
    if m.rol == "orquestador":
        # Sus órdenes salen solo por el monitor (bloque <orden>), con la aprobación de Washington.
        cmd += ["--disallowedTools", BLOQUEADAS_ORQUESTADOR]
    else:
        # Solo el monitor le escribe (por su entrada): ninguna otra sesión de la máquina.
        cmd += ["--settings", json.dumps({"crossSessionInbound": "refuse"})]
    return cmd


def entorno_sesion(cuenta_dir: Path | None, base: dict[str, str], home: Path) -> dict[str, str]:
    """Entorno de una sesión lanzada: sin las variables de otra sesión de Claude Code y,
    para Demo Org, con su carpeta de configuración. Los hooks del usuario siguen activos."""
    env = {k: v for k, v in base.items() if not k.upper().startswith(("CLAUDE", "ANTHROPIC"))}
    por_defecto = home / ".claude"
    if cuenta_dir is not None and os.path.normcase(str(cuenta_dir)) != os.path.normcase(
        str(por_defecto)
    ):
        env["CLAUDE_CONFIG_DIR"] = str(cuenta_dir)
    return env


def mensaje(texto: str) -> bytes:
    linea = {"type": "user", "message": {"role": "user", "content": texto}}
    return (json.dumps(linea, ensure_ascii=False) + "\n").encode("utf-8")


class Sesion:
    """Un proceso ``claude -p`` lanzado por este monitor. Junta el texto de cada turno
    (lo que escribió la sesión principal, no sus subagentes) hasta su ``result``."""

    def __init__(self, cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.proceso = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        self.ultimo: dict[str, Any] | None = None
        self.resultados = 0
        self.enviados = 0
        self._textos: list[str] = []
        self._turnos: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._lector = threading.Thread(target=self._leer, daemon=True)
        self._lector.start()

    @property
    def pid(self) -> int:
        return self.proceso.pid

    def viva(self) -> bool:
        return self.proceso.poll() is None

    def ocupada(self) -> bool:
        """Tiene un mensaje escrito cuyo turno todavía no terminó."""
        with self._lock:
            return self.enviados > self.resultados

    def tomar_turnos(self) -> list[dict[str, Any]]:
        """Los turnos terminados desde la última vez (texto, resultado, es_error)."""
        with self._lock:
            turnos, self._turnos = self._turnos, []
        return turnos

    def _leer(self) -> None:
        assert self.proceso.stdout is not None
        for linea in self.proceso.stdout:
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            tipo = d.get("type")
            if tipo == "assistant" and not d.get("parent_tool_use_id"):
                contenido = (d.get("message") or {}).get("content") or []
                for b in contenido if isinstance(contenido, list) else []:
                    if isinstance(b, dict) and b.get("type") == "text":
                        with self._lock:
                            self._textos.append(str(b.get("text") or ""))
            elif tipo == "result":
                resultado = str(d.get("result") or "")
                es_error = bool(d.get("is_error"))
                with self._lock:
                    texto = "\n\n".join(t.strip() for t in self._textos if t.strip())
                    self._textos = []
                    self.resultados += 1
                    self.ultimo = {"texto": resultado[:2000], "es_error": es_error}
                    self._turnos.append(
                        {"texto": texto or resultado, "resultado": resultado, "es_error": es_error}
                    )

    def enviar(self, texto: str) -> None:
        if self.proceso.stdin is None or not self.viva():
            raise EquipoError("La sesión no está corriendo.")
        with self._lock:
            self.enviados += 1
        try:
            self.proceso.stdin.write(mensaje(texto))
            self.proceso.stdin.flush()
        except OSError:
            with self._lock:
                self.enviados -= 1
            raise

    def cerrar(self, espera: float = ESPERA_CIERRE) -> None:
        """Cierra la entrada (la sesión termina sola) y, si no termina, la detiene."""
        if self.proceso.stdin is not None:
            with contextlib.suppress(OSError):
                self.proceso.stdin.close()
        try:
            self.proceso.wait(timeout=espera)
        except subprocess.TimeoutExpired:
            detener_pid(self.proceso.pid)
            try:
                self.proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proceso.kill()
        # Lo que alcanzó a escribir antes de terminar (el último turno) se lee entero.
        self._lector.join(timeout=5)


def detener_pid(pid: int) -> None:
    """Detiene un proceso y sus hijos. Solo se llama con PIDs lanzados por este monitor."""
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
            creationflags=flags,
        )
    else:
        with contextlib.suppress(OSError):
            os.kill(pid, 15)


# -- el gestor ------------------------------------------------------------------------------


class Equipos:
    def __init__(
        self,
        base: Path,
        ruta_proyectos: Path,
        cuentas: list[str],
        claude: list[str] | None = None,
        entorno_base: dict[str, str] | None = None,
        home: Path | None = None,
        git: Callable[[Path], None] | None = None,
        arranque: float = ARRANQUE,
        espera_cierre: float = ESPERA_CIERRE,
    ) -> None:
        self.archivo = base / "equipos.json"
        self.ruta_proyectos = ruta_proyectos
        self.cuentas = [Path(os.path.normpath(os.path.abspath(c))) for c in cuentas]
        self._claude = claude
        self.entorno_base = entorno_base if entorno_base is not None else dict(os.environ)
        self.home = home or Path.home()
        self.git = git
        self.arranque = arranque
        self.espera_cierre = espera_cierre
        self.proyectos: dict[str, Proyecto] = {}
        self.sesiones: dict[str, Sesion] = {}  # session_id -> proceso lanzado aquí
        # Lo que falta mandar al servidor (respuestas, órdenes propuestas, avances).
        self.salida: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._cargar()

    # -- estado guardado ----------------------------------------------------------------

    def _cargar(self) -> None:
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for pid_, p in (datos.get("proyectos") or {}).items():
            try:
                self.proyectos[pid_] = Proyecto(
                    id=pid_,
                    nombre=p["nombre"],
                    carpeta=p["carpeta"],
                    cuenta=p["cuenta"],
                    activo=bool(p.get("activo")),
                    miembros=[Miembro(**m) for m in p.get("miembros") or []],
                    detenido=bool(p.get("detenido")),
                    colas={k: list(v) for k, v in (p.get("colas") or {}).items()},
                    en_curso=dict(p.get("en_curso") or {}),
                    vistos=list(p.get("vistos") or []),
                )
            except (KeyError, TypeError, AttributeError):
                logger.warning("equipos.json: se ignoró un proyecto ilegible")
        salida = datos.get("salida")
        if isinstance(salida, list):
            self.salida = [s for s in salida if isinstance(s, dict)]

    def _guardar(self) -> None:
        datos = {
            "proyectos": {k: asdict(v) for k, v in self.proyectos.items()},
            "salida": self.salida,
        }
        tmp = self.archivo.with_name(self.archivo.name + ".tmp")
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.archivo)

    # -- encargos ------------------------------------------------------------------------

    def procesar(self, encargo: dict[str, Any]) -> dict[str, Any]:
        """Hace un encargo; devuelve el resultado para el servidor."""
        tipo = encargo.get("tipo")
        pid_ = str(encargo.get("proyecto_id") or "")
        try:
            with self._lock:
                if tipo == "crear":
                    p = self.crear(encargo)
                elif tipo == "pausar":
                    p = self.pausar(pid_)
                elif tipo == "detener":
                    p = self.pausar(pid_, detener=True)
                elif tipo == "reanudar":
                    p = self.reanudar(pid_)
                elif tipo == "agregar":
                    p = self.agregar(encargo)
                elif tipo == "mensaje":
                    p = self.recibir_mensaje(encargo)
                elif tipo == "orden":
                    p = self.recibir_orden(encargo)
                elif tipo == "rechazo":
                    p = self.recibir_rechazo(encargo)
                else:
                    raise EquipoError("Encargo desconocido.")
            return {"ok": True, "ruta": p.carpeta, "miembros": self.estado_miembros(p)}
        except EquipoError as e:
            p = self.proyectos.get(pid_)
            return {"ok": False, "error": str(e), "miembros": self.estado_miembros(p) if p else []}
        except Exception as e:  # nunca tumba el hilo de encargos
            logger.exception("Falló un encargo de proyecto")
            return {"ok": False, "error": f"Error inesperado ({type(e).__name__}).", "miembros": []}

    def _proyecto(self, pid_: str) -> Proyecto:
        p = self.proyectos.get(pid_)
        if p is None:
            raise EquipoError("Este monitor no tiene ese proyecto.")
        return p

    def crear(self, e: dict[str, Any]) -> Proyecto:
        pid_ = str(e.get("proyecto_id") or "")
        if not ID_SERVIDOR.fullmatch(pid_):
            raise EquipoError("Encargo sin proyecto.")
        if pid_ in self.proyectos:
            return self.proyectos[pid_]  # encargo repetido (reentrega): ya está hecho
        nombre = validar_nombre(e.get("nombre"))
        cuenta = e.get("cuenta")
        if cuenta not in ("personal", "demo"):
            raise EquipoError("Cuenta desconocida.")
        if cuenta_para(None, cuenta, self.cuentas) is None:
            raise EquipoError(f"Esta máquina no tiene configurada la cuenta {cuenta}.")
        miembros = miembros_de(e.get("equipo"))
        carpeta = carpeta_segura(self.ruta_proyectos, nombre)
        preparar_carpeta(
            carpeta,
            nombre,
            str(e.get("plantilla") or "vacia"),
            datetime.now().strftime("%Y-%m-%d"),
            self.git,
        )
        p = Proyecto(pid_, nombre, str(carpeta), cuenta, activo=True, miembros=miembros)
        self.proyectos[pid_] = p
        self._guardar()
        self._lanzar_equipo(p, reanudar=False)
        return p

    def pausar(self, pid_: str, detener: bool = False) -> Proyecto:
        """Cierra las sesiones del equipo. Lo encolado se queda para cuando se reanude."""
        p = self._proyecto(pid_)
        for m in p.miembros:
            s = self.sesiones.pop(m.session_id, None)
            if s is not None:
                s.cerrar(self.espera_cierre)
                # Un turno que alcanzó a terminar al cerrar se atiende como siempre.
                for t in s.tomar_turnos():
                    self._fin_de_turno(p, m, t)
            m.pid = None
            m.creado = None
        motivo = "se detuvo el equipo" if detener else "se pausó el equipo"
        for nombre in list(p.en_curso):
            self._interrumpir(p, nombre, motivo)
        p.activo = False
        p.detenido = detener
        self._guardar()
        return p

    def reanudar(self, pid_: str) -> Proyecto:
        p = self._proyecto(pid_)
        p.activo = True
        p.detenido = False
        self._guardar()
        # Sin saludo: la oficina las muestra "En espera" hasta que alguien les escriba.
        self._lanzar_equipo(p, reanudar=True, saludo=False)
        return p

    def agregar(self, e: dict[str, Any]) -> Proyecto:
        """Un agente de código nuevo en un equipo existente: se lanza si el equipo está
        activo y el orquestador se entera."""
        p = self._proyecto(str(e.get("proyecto_id") or ""))
        actuales = {m.nombre for m in p.miembros}
        nuevos = [m for m in miembros_de(e.get("equipo")) if m.nombre not in actuales]
        if any(m.rol != "agente" for m in nuevos):
            raise EquipoError("Solo se agregan agentes de código.")
        if not nuevos:
            return p  # reentrega: ya está
        p.miembros.extend(nuevos)
        for m in nuevos:
            self._avisar_orquestador(p, AGREGADO.format(miembro=m.nombre))
        self._guardar()
        if p.activo:
            self._lanzar_equipo(p, reanudar=True, saludo=False)
        return p

    def _ya_visto(self, p: Proyecto, clave: str) -> bool:
        if clave in p.vistos:
            return True
        p.vistos = [*p.vistos, clave][-MAX_VISTOS:]
        return False

    def recibir_mensaje(self, e: dict[str, Any]) -> Proyecto:
        """Un mensaje de Washington para el orquestador del proyecto."""
        p = self._proyecto(str(e.get("proyecto_id") or ""))
        texto = e.get("texto")
        mid = str(e.get("mensaje_id") or "")
        if not isinstance(texto, str) or not texto.strip() or not ID_SERVIDOR.fullmatch(mid):
            raise EquipoError("Mensaje no válido.")
        orq = p.orquestador()
        if orq is None:
            raise EquipoError("El proyecto no tiene orquestador.")
        if not self._ya_visto(p, f"mensaje:{mid}"):
            p.colas.setdefault(orq.nombre, []).append({"tipo": "mensaje", "texto": texto})
            self._guardar()
        return p

    def recibir_orden(self, e: dict[str, Any]) -> Proyecto:
        """Una orden aprobada: va a la cola del agente elegido, solo si es un agente de
        código de este mismo proyecto."""
        p = self._proyecto(str(e.get("proyecto_id") or ""))
        oid = str(e.get("orden_id") or "")
        texto = e.get("texto")
        numero = e.get("numero")
        if not ID_SERVIDOR.fullmatch(oid) or not isinstance(texto, str) or not texto.strip():
            raise EquipoError("Orden no válida.")
        destino = p.agente(str(e.get("agente") or ""))
        if destino is None:
            raise EquipoError(f"{e.get('agente')} no es un agente de código de este proyecto.")
        if not self._ya_visto(p, f"orden:{oid}"):
            p.colas.setdefault(destino.nombre, []).append(
                {
                    "tipo": "orden",
                    "orden_id": oid,
                    "numero": numero,
                    "texto": texto,
                    "editada": e.get("editada") is True,
                }
            )
            self._guardar()
        return p

    def recibir_rechazo(self, e: dict[str, Any]) -> Proyecto:
        p = self._proyecto(str(e.get("proyecto_id") or ""))
        oid = str(e.get("orden_id") or "")
        if not ID_SERVIDOR.fullmatch(oid):
            raise EquipoError("Rechazo no válido.")
        if not self._ya_visto(p, f"rechazo:{oid}"):
            self._avisar_orquestador(
                p,
                RECHAZO.format(
                    numero=e.get("numero"),
                    agente=e.get("agente"),
                    motivo=str(e.get("motivo") or "sin motivo"),
                ),
            )
            self._guardar()
        return p

    def retomar(self) -> int:
        """Al arrancar el monitor: relanza los equipos que estaban activos."""
        n = 0
        with self._lock:
            for p in self.proyectos.values():
                # Lo que estaba en curso murió con el monitor anterior.
                for nombre in list(p.en_curso):
                    self._interrumpir(p, nombre, "el monitor se reinició")
                if not p.activo:
                    continue
                for m in p.miembros:
                    # Un proceso anterior de este monitor (mismo PID y misma hora de
                    # creación) que siguiera vivo: se detiene antes de relanzar.
                    if m.pid and m.creado and proceso_vivo(m.pid, m.creado) is True:
                        detener_pid(m.pid)
                try:
                    self._lanzar_equipo(p, reanudar=True, saludo=False)
                    n += 1
                except EquipoError as e:
                    logger.warning("No se pudo retomar el equipo de %s: %s", p.nombre, e)
            self._guardar()
        return n

    def detener_todo(self) -> None:
        """Al cerrar el monitor: cierra las sesiones que lanzó (siguen activas para retomarlas)."""
        with self._lock:
            for p in self.proyectos.values():
                for m in p.miembros:
                    s = self.sesiones.pop(m.session_id, None)
                    if s is None:
                        continue
                    s.cerrar(5.0)
                    for t in s.tomar_turnos():
                        self._fin_de_turno(p, m, t)
            for s in self.sesiones.values():
                s.cerrar(5.0)
            self.sesiones.clear()
            self._guardar()

    # -- chat y órdenes -------------------------------------------------------------------------

    def _avisar_orquestador(self, p: Proyecto, texto: str, clase: str = "") -> None:
        orq = p.orquestador()
        if orq is not None:
            p.colas.setdefault(orq.nombre, []).append(
                {"tipo": "aviso", "texto": texto, "clase": clase}
            )

    def _al_servidor(self, tipo: str, ruta: str, datos: dict[str, Any], p: Proyecto) -> None:
        self.salida.append({"tipo": tipo, "ruta": ruta, "datos": datos, "proyecto_id": p.id})

    def _interrumpir(self, p: Proyecto, nombre: str, motivo: str) -> None:
        """Lo que se le escribió a una sesión que se cortó antes de terminar el turno."""
        item = p.en_curso.pop(nombre, None)
        if item is None:
            return
        if item.get("tipo") == "orden":
            self._al_servidor(
                "avance",
                f"/api/v1/maquinas/ordenes/{item['orden_id']}",
                {"estado": "fallida", "resumen": f"Se interrumpió: {motivo}."},
                p,
            )
            self._avisar_orquestador(
                p, INTERRUMPIDA.format(numero=item.get("numero"), agente=nombre, motivo=motivo)
            )
        else:
            # Un mensaje o aviso al orquestador: se vuelve a escribir al reanudar.
            p.colas.setdefault(nombre, []).insert(0, item)

    def _fin_de_turno(self, p: Proyecto, m: Miembro, turno: dict[str, Any]) -> None:
        item = p.en_curso.pop(m.nombre, None)
        if m.rol == "orquestador":
            # Si insiste con un destino inválido justo después del aviso, no se le vuelve
            # a avisar (evita un ida y vuelta sin fin entre el monitor y el orquestador).
            insiste = bool(item and item.get("clase") == "destino")
            self._respuesta_orquestador(p, str(turno.get("texto") or ""), avisar=not insiste)
            return
        if item is None or item.get("tipo") != "orden":
            return  # el saludo al arrancar
        estado = "fallida" if turno.get("es_error") else "terminada"
        resumen = (
            str(turno.get("resultado") or turno.get("texto") or "").strip() or "(sin texto)"
        )[:MAX_RESUMEN]
        self._al_servidor(
            "avance",
            f"/api/v1/maquinas/ordenes/{item['orden_id']}",
            {"estado": estado, "resumen": resumen},
            p,
        )
        aviso = RESULTADO.format(
            numero=item.get("numero"), agente=m.nombre, estado=estado, resumen=resumen
        )
        if item.get("editada"):
            aviso = EDITADA.format(texto=item.get("texto") or "") + aviso
        self._avisar_orquestador(p, aviso)

    def _respuesta_orquestador(self, p: Proyecto, texto: str, avisar: bool = True) -> None:
        ordenes, limpio = extraer_ordenes(texto)
        if limpio:
            self._al_servidor(
                "chat",
                "/api/v1/maquinas/chat",
                {"proyecto_id": p.id, "origen_id": uuid.uuid4().hex, "texto": limpio[:MAX_CHAT]},
                p,
            )
        for o in ordenes:
            agente = str(o["agente"] or "")
            if p.agente(agente) is None or not o["texto"]:
                # Nunca sale a ningún lado: ni al servidor ni a otra sesión.
                logger.warning("%s: orden sin destino válido o sin instrucción", p.nombre)
                if avisar:
                    plantilla = ORDEN_VACIA if p.agente(agente) is not None else DESTINO_INVALIDO
                    self._avisar_orquestador(
                        p,
                        plantilla.format(
                            agente=agente, agentes=", ".join(p.agentes()) or "ninguno"
                        ),
                        "destino",
                    )
                continue
            self._al_servidor(
                "orden",
                "/api/v1/maquinas/ordenes",
                {
                    "proyecto_id": p.id,
                    "origen_id": uuid.uuid4().hex,
                    "agente": agente,
                    "texto": str(o["texto"])[:MAX_CHAT],
                    "estimado": (o["estimado"] or None) and str(o["estimado"])[:60],
                    "dificultad": (o["dificultad"] or None) and str(o["dificultad"])[:60],
                },
                p,
            )

    def _entregar(self, p: Proyecto, m: Miembro, s: Sesion, item: dict[str, Any]) -> None:
        if item.get("tipo") == "orden":
            texto = ORDEN_AL_AGENTE.format(numero=item.get("numero"), texto=item["texto"])
        else:
            texto = str(item.get("texto") or "")
        s.enviar(texto)
        p.en_curso[m.nombre] = item
        if item.get("tipo") == "orden":
            self._al_servidor(
                "avance",
                f"/api/v1/maquinas/ordenes/{item['orden_id']}",
                {"estado": "en_curso"},
                p,
            )

    def atender(self) -> int:
        """Atiende los turnos terminados y escribe lo encolado a cada sesión libre.
        Devuelve cuántas cosas hizo."""
        hechas = 0
        with self._lock:
            for p in self.proyectos.values():
                for m in p.miembros:
                    s = self.sesiones.get(m.session_id)
                    if s is None:
                        continue
                    for t in s.tomar_turnos():
                        self._fin_de_turno(p, m, t)
                        hechas += 1
                if not p.activo:
                    continue
                for m in p.miembros:
                    cola = p.colas.get(m.nombre)
                    s = self.sesiones.get(m.session_id)
                    if not cola or s is None or m.nombre in p.en_curso:
                        continue
                    if not s.viva() or s.ocupada():
                        continue
                    item = cola[0]
                    try:
                        self._entregar(p, m, s, item)
                    except (OSError, EquipoError):
                        logger.warning("No se pudo escribir a %s-%s", p.nombre, m.nombre)
                        continue
                    cola.pop(0)
                    hechas += 1
            if hechas:
                self._guardar()
        return hechas

    def vaciar_salida(self, servidor: Servidor) -> int:
        """Manda al servidor lo pendiente, en orden. Sin conexión o con un error del
        servidor (5xx) se reintenta después; un rechazo (4xx) se descarta."""
        enviados = 0
        while True:
            with self._lock:
                if not self.salida:
                    break
                item = self.salida[0]
            try:
                r = servidor.post_json(item["ruta"], item["datos"], timeout=10.0)
            except SinConexion:
                break
            if r.status >= 500:
                break
            with self._lock:
                if self.salida and self.salida[0] is item:
                    self.salida.pop(0)
                if r.status >= 400:
                    logger.warning("El servidor rechazó %s (%s)", item.get("ruta"), r.status)
                    p = self.proyectos.get(str(item.get("proyecto_id")))
                    if item.get("tipo") == "orden" and p is not None:
                        detalle = r.cuerpo.get("detail") if isinstance(r.cuerpo, dict) else None
                        self._avisar_orquestador(
                            p,
                            NO_REGISTRADA.format(
                                agente=item["datos"].get("agente"),
                                detalle=detalle or f"error {r.status}",
                            ),
                        )
                self._guardar()
            enviados += 1
        return enviados

    # -- lanzar -------------------------------------------------------------------------------

    def _claude_cmd(self) -> list[str]:
        if self._claude is not None:
            return self._claude
        c = buscar_claude(self.home)
        if c is None:
            raise EquipoError("No se encontró claude.exe en esta máquina.")
        return [c]

    def _lanzar_equipo(self, p: Proyecto, reanudar: bool, saludo: bool = True) -> None:
        cuenta_dir = cuenta_para(None, p.cuenta, self.cuentas)
        if cuenta_dir is None:
            raise EquipoError(f"Esta máquina no tiene configurada la cuenta {p.cuenta}.")
        env = entorno_sesion(cuenta_dir, self.entorno_base, self.home)
        claude = self._claude_cmd()
        for m in p.miembros:
            actual = self.sesiones.get(m.session_id)
            if actual is not None and actual.viva():
                continue
            # Una sesión que nunca arrancó se lanza de nuevo con su id, no se retoma.
            retomar = reanudar and m.lanzado
            s = Sesion(comando_sesion(claude, p, m, retomar), Path(p.carpeta), env)
            self.sesiones[m.session_id] = s
            m.lanzado = True
            m.pid = s.pid
            m.creado = hora_creacion(s.pid)
            rol = texto_rol(p, m)
            if not retomar:
                m.rol_huella = huella(rol)
            elif m.rol_huella != huella(rol):
                # Retomada con su rol de nacimiento: se le cuenta el nuevo antes que nada.
                p.colas.setdefault(m.nombre, []).insert(
                    0, {"tipo": "aviso", "texto": ROL_ACTUALIZADO.format(rol=rol), "clase": "rol"}
                )
                m.rol_huella = huella(rol)
            # Saludo solo al nacer (o si se pide): retomada, queda "En espera".
            if saludo or not retomar:
                with contextlib.suppress(OSError, EquipoError):
                    s.enviar(SALUDO[m.rol].format(nombre=p.nombre))
        self._guardar()
        # Unos segundos para ver que no se cayeron al arrancar (cuenta, modelo, opciones).
        fin = time.monotonic() + self.arranque
        while time.monotonic() < fin:
            if any(not self.sesiones[m.session_id].viva() for m in p.miembros):
                break
            time.sleep(0.2)
        caidas = [m.nombre for m in p.miembros if not self.sesiones[m.session_id].viva()]
        if caidas:
            raise EquipoError(f"No arrancó: {', '.join(caidas)}.")

    # -- estado para el servidor ---------------------------------------------------------------

    def estado_miembros(self, p: Proyecto) -> list[dict[str, str]]:
        salida: list[dict[str, str]] = []
        for m in p.miembros:
            s = self.sesiones.get(m.session_id)
            if not p.activo:
                estado = "detenido" if p.detenido else "pausado" if m.lanzado else "pendiente"
            elif s is not None and s.viva():
                estado = "activo"
            elif m.lanzado:
                estado = "detenido"
            else:
                estado = "pendiente"
            salida.append({"nombre": m.nombre, "estado": estado})
        return salida

    def estado_equipos(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"proyecto_id": p.id, "miembros": self.estado_miembros(p)}
                for p in self.proyectos.values()
            ]


class HiloEncargos(threading.Thread):
    """Cada segundo atiende los turnos y las colas de los equipos y manda lo pendiente
    al servidor; cada pocos segundos pide los encargos de esta máquina, los hace e
    informa; y manda el estado de los equipos."""

    def __init__(
        self,
        servidor: Servidor,
        equipos: Equipos,
        cada: float = 3.0,
        informe: float = 15.0,
        pulso: float = 1.0,
    ) -> None:
        super().__init__(name="encargos", daemon=True)
        self.servidor = servidor
        self.equipos = equipos
        self.cada = cada
        self.informe = informe
        self.pulso = pulso
        self.parar = threading.Event()
        self._proximo_informe = 0.0
        self._proxima_consulta = 0.0

    def run(self) -> None:
        try:
            self.equipos.retomar()
        except Exception:
            logger.exception("No se pudieron retomar los equipos")
        while not self.parar.is_set():
            try:
                self.ronda()
            except Exception:
                logger.exception("Error en los encargos de proyectos")
            self.parar.wait(self.pulso)
        self.equipos.detener_todo()
        with contextlib.suppress(Exception):
            self.equipos.vaciar_salida(self.servidor)

    def ronda(self) -> int:
        hechos = 0
        ahora = time.monotonic()
        if ahora >= self._proxima_consulta:
            self._proxima_consulta = ahora + self.cada
            hechos = self._encargos()
        self.equipos.atender()
        self.equipos.vaciar_salida(self.servidor)
        ahora = time.monotonic()
        if hechos or ahora >= self._proximo_informe:
            self._proximo_informe = ahora + self.informe
            equipos = self.equipos.estado_equipos()
            if equipos:
                with contextlib.suppress(SinConexion):
                    self.servidor.post_json(
                        "/api/v1/maquinas/equipos", {"equipos": equipos}, timeout=10.0
                    )
        return hechos

    def _encargos(self) -> int:
        hechos = 0
        try:
            r = self.servidor.pedir("GET", "/api/v1/maquinas/encargos", timeout=10.0)
        except SinConexion:
            return 0
        if r.status < 300 and isinstance(r.cuerpo, dict):
            for e in r.cuerpo.get("encargos") or []:
                if not isinstance(e, dict) or not isinstance(e.get("id"), str):
                    continue
                resultado = self.equipos.procesar(e)
                # Sin conexión: el servidor lo vuelve a entregar y todo es idempotente.
                with contextlib.suppress(SinConexion):
                    self.servidor.post_json(
                        f"/api/v1/maquinas/encargos/{e['id']}", resultado, timeout=10.0
                    )
                hechos += 1
        return hechos

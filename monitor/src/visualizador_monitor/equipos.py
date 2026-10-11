"""Equipos de proyectos (etapa 4, Prompt 37).

El servidor deja encargos para esta máquina (crear, pausar, reanudar) y el monitor:

- **Crear**: arma la carpeta del proyecto solo dentro de su ruta base (comprobada
  con la ruta real, sin enlaces que la saquen de ahí), hace ``git init``, deja un
  PROJECT.md mínimo y aplica la plantilla. Después lanza el equipo.
- **Lanzar**: una sesión ``claude -p`` con entrada y salida stream-json por miembro
  (orquestador y agentes de código), en la carpeta del proyecto, con la cuenta del
  proyecto (``CLAUDE_CONFIG_DIR`` solo para Demo Org), ``--model``, ``--effort``, un
  ``--append-system-prompt`` con su rol y el id de sesión que decidió el servidor.
  El orquestador arranca con ``SendMessage`` y ``ListAgents`` bloqueados (el Prompt 38
  pondrá el hook que limita a quién le escribe); los agentes aceptan mensajes de
  otras sesiones (``crossSessionInbound: accept``). Los hooks del visualizador las
  siguen viendo: cargan la configuración del usuario como cualquier sesión.
- **Pausar**: cierra la entrada de los procesos que lanzó este monitor y, si no
  terminan, los detiene. Nunca toca otros procesos.
- **Reanudar**: vuelve a lanzar cada sesión con ``--resume <id>``.
- **Reinicio del monitor**: retoma los equipos que estaban activos. Si un proceso
  suyo anterior sigue vivo (mismo PID y misma hora de creación), lo detiene antes.

El estado de los equipos vive en ``equipos.json`` (en la carpeta del monitor).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import threading
import time
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
ESPERA_CIERRE = 20.0  # segundos para que una sesión termine sola al pausar
ARRANQUE = 3.0  # segundos que una sesión recién lanzada debe seguir viva

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
    "conversas con él, propones y ordenas el trabajo en etapas. Todavía no das órdenes "
    "a los agentes de código: esa función llega más adelante. Responde en español latino neutro."
)
ROL_AGENTE = (
    "Eres el agente de código del proyecto {nombre}. Esperas las órdenes del orquestador "
    "de este proyecto o de Washington y no empiezas trabajo por tu cuenta. "
    "Responde en español latino neutro."
)
SALUDO = {
    "orquestador": (
        "Se creó el proyecto {nombre}. Preséntate en una sola frase y espera "
        "a que Washington te escriba."
    ),
    "agente": "Se creó el proyecto {nombre}. Responde solo: listo, esperando órdenes.",
}
REANUDADO = "Se reanudó el equipo del proyecto {nombre}. Responde solo: listo."


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


@dataclass
class Proyecto:
    id: str
    nombre: str
    carpeta: str
    cuenta: str
    activo: bool = False
    miembros: list[Miembro] = field(default_factory=lambda: [])


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


def comando_sesion(claude: list[str], proyecto: Proyecto, m: Miembro, reanudar: bool) -> list[str]:
    rol = (ROL_ORQUESTADOR if m.rol == "orquestador" else ROL_AGENTE).format(nombre=proyecto.nombre)
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
        "default",
        "--name",
        f"{proyecto.nombre}-{m.nombre}",
        "--append-system-prompt",
        rol,
    ]
    cmd += ["--resume", m.session_id] if reanudar else ["--session-id", m.session_id]
    if m.rol == "orquestador":
        # Hasta el Prompt 38 (hook que limita a quién le escribe): sin mensajes a otras sesiones.
        cmd += ["--disallowedTools", "SendMessage,ListAgents"]
    else:
        cmd += ["--settings", json.dumps({"crossSessionInbound": "accept"})]
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
    """Un proceso ``claude -p`` lanzado por este monitor."""

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
        self._lock = threading.Lock()
        threading.Thread(target=self._leer, daemon=True).start()

    @property
    def pid(self) -> int:
        return self.proceso.pid

    def viva(self) -> bool:
        return self.proceso.poll() is None

    def _leer(self) -> None:
        assert self.proceso.stdout is not None
        for linea in self.proceso.stdout:
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("type") == "result":
                with self._lock:
                    self.resultados += 1
                    self.ultimo = {
                        "texto": str(d.get("result") or "")[:2000],
                        "es_error": bool(d.get("is_error")),
                    }

    def enviar(self, texto: str) -> None:
        if self.proceso.stdin is None or not self.viva():
            raise EquipoError("La sesión no está corriendo.")
        self.proceso.stdin.write(mensaje(texto))
        self.proceso.stdin.flush()

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
                )
            except (KeyError, TypeError):
                logger.warning("equipos.json: se ignoró un proyecto ilegible")

    def _guardar(self) -> None:
        datos = {"proyectos": {k: asdict(v) for k, v in self.proyectos.items()}}
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
                elif tipo == "reanudar":
                    p = self.reanudar(pid_)
                else:
                    raise EquipoError("Encargo desconocido.")
            return {"ok": True, "ruta": p.carpeta, "miembros": self.estado_miembros(p)}
        except EquipoError as e:
            p = self.proyectos.get(pid_)
            return {"ok": False, "error": str(e), "miembros": self.estado_miembros(p) if p else []}
        except Exception as e:  # nunca tumba el hilo de encargos
            logger.exception("Falló un encargo de proyecto")
            return {"ok": False, "error": f"Error inesperado ({type(e).__name__}).", "miembros": []}

    def crear(self, e: dict[str, Any]) -> Proyecto:
        pid_ = str(e.get("proyecto_id") or "")
        if not re.fullmatch(r"[0-9a-f]{32}", pid_):
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

    def pausar(self, pid_: str) -> Proyecto:
        p = self.proyectos.get(pid_)
        if p is None:
            raise EquipoError("Este monitor no tiene ese proyecto.")
        for m in p.miembros:
            s = self.sesiones.pop(m.session_id, None)
            if s is not None:
                s.cerrar(self.espera_cierre)
            m.pid = None
            m.creado = None
        p.activo = False
        self._guardar()
        return p

    def reanudar(self, pid_: str) -> Proyecto:
        p = self.proyectos.get(pid_)
        if p is None:
            raise EquipoError("Este monitor no tiene ese proyecto.")
        p.activo = True
        self._guardar()
        self._lanzar_equipo(p, reanudar=True)
        return p

    def retomar(self) -> int:
        """Al arrancar el monitor: relanza los equipos que estaban activos."""
        n = 0
        with self._lock:
            for p in self.proyectos.values():
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
        return n

    def detener_todo(self) -> None:
        """Al cerrar el monitor: cierra las sesiones que lanzó (siguen activas para retomarlas)."""
        with self._lock:
            for sid, s in list(self.sesiones.items()):
                s.cerrar(5.0)
                self.sesiones.pop(sid, None)

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
            texto = REANUDADO if retomar else SALUDO[m.rol]
            if saludo or not retomar:
                with contextlib.suppress(OSError, EquipoError):
                    s.enviar(texto.format(nombre=p.nombre))
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
                estado = "pausado" if m.lanzado else "pendiente"
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
    """Pide los encargos de esta máquina cada pocos segundos, los hace e informa;
    y manda el estado de los equipos."""

    def __init__(
        self, servidor: Servidor, equipos: Equipos, cada: float = 3.0, informe: float = 15.0
    ) -> None:
        super().__init__(name="encargos", daemon=True)
        self.servidor = servidor
        self.equipos = equipos
        self.cada = cada
        self.informe = informe
        self.parar = threading.Event()
        self._proximo_informe = 0.0

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
            self.parar.wait(self.cada)
        self.equipos.detener_todo()

    def ronda(self) -> int:
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
                # Sin conexión: el servidor lo vuelve a entregar y crear es idempotente.
                with contextlib.suppress(SinConexion):
                    self.servidor.post_json(
                        f"/api/v1/maquinas/encargos/{e['id']}", resultado, timeout=10.0
                    )
                hechos += 1
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

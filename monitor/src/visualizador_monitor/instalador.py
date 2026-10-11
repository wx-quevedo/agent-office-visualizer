"""Instalación y desinstalación del monitor en Windows (lo usa el instalador .exe).

Instalar:
1. Detiene el monitor que corra y copia el empaquetado a una carpeta nueva por
   instalación dentro de ``destino`` (por defecto
   ``%LOCALAPPDATA%\\VisualizadorMonitor\\v<versión>-<fecha>``): una
   actualización no choca con los hooks que tienen abierto el anterior.
2. Escribe la configuración del usuario (servidor, token, puerto, cuentas) y la
   lista de comandos peligrosos si no existe.
3. En cada cuenta de Claude Code detectada (``.claude``, ``.claude-*``) respalda
   ``settings.json`` y cambia SOLO las entradas de ``claude-office-hook`` para
   que llamen al monitor (``"<monitor>" hook <evento>``), con 600 s en el permiso.
4. Escribe ``arranque.ps1`` (bucle que rearranca el monitor si se cae) y
   registra la tarea programada oculta al iniciar sesión (usuario, sin
   administrador) que lo corre; la arranca.
5. Guarda un manifiesto (``instalacion.json``) con todo lo que cambió.

Desinstalar deja todo como estaba: revierte cada entrada cambiada a su texto
original, quita la tarea, detiene el monitor y borra sus archivos.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from visualizador_monitor import VERSION, config
from visualizador_monitor.cli import NOMBRE_TAREA

MARCA = "claude-office-hook"
EVENTO_PERMISO = "permission_request"
TIMEOUT_PERMISO = 600


def destino_por_defecto() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "VisualizadorMonitor"


def comando_hook(exe: Path, evento: str) -> str:
    # Barras normales: los hooks corren en Git Bash o en cmd y los dos las aceptan.
    return f'"{exe.as_posix()}" hook {evento}'


def _evento_de(comando: str) -> str | None:
    """El evento de una entrada nuestra: claude-office-hook <evento> o, de una
    instalación anterior, "<...>/visualizador-monitor.exe" hook <evento>."""
    partes = comando.split()
    for n, crudo in enumerate(partes):
        p = crudo.strip("\"'").removesuffix(".exe").removesuffix(".EXE")
        if p.endswith(MARCA) and n + 1 < len(partes):
            return partes[n + 1]
        if p.endswith("visualizador-monitor") and n + 2 < len(partes) and partes[n + 1] == "hook":
            return partes[n + 2]
    return None


def _encadenar(previos: list[dict[str, Any]], nuevos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Une los cambios de dos instalaciones: el original sigue siendo el de la primera."""
    resultado = [dict(c) for c in previos]
    for c in nuevos:
        base = next((r for r in resultado if r["despues"] == c["antes"]), None)
        if base is None:
            resultado.append(c)
        else:
            base["despues"] = c["despues"]
            base["timeout_despues"] = c["timeout_despues"]
    return resultado


def cambiar_hooks(settings: dict[str, Any], exe: Path) -> list[dict[str, Any]]:
    """Cambia en memoria las entradas de claude-office-hook; devuelve los cambios."""
    cambios: list[dict[str, Any]] = []
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return cambios
    for tipo, grupos in hooks.items():
        if not isinstance(grupos, list):
            continue
        for grupo in grupos:
            if not isinstance(grupo, dict) or not isinstance(grupo.get("hooks"), list):
                continue
            for h in grupo["hooks"]:
                if not isinstance(h, dict):
                    continue
                antes = str(h.get("command", ""))
                evento = _evento_de(antes)
                if evento is None:
                    continue
                despues = comando_hook(exe, evento)
                if despues == antes and (
                    evento != EVENTO_PERMISO or h.get("timeout") == TIMEOUT_PERMISO
                ):
                    continue
                timeout_antes = h.get("timeout")
                h["command"] = despues
                if evento == EVENTO_PERMISO:
                    h["timeout"] = TIMEOUT_PERMISO
                cambios.append(
                    {
                        "tipo": tipo,
                        "evento": evento,
                        "antes": antes,
                        "despues": despues,
                        "timeout_antes": timeout_antes,
                        "timeout_despues": h.get("timeout"),
                    }
                )
    return cambios


def revertir_hooks(settings: dict[str, Any], cambios: list[dict[str, Any]]) -> int:
    """Vuelve cada entrada cambiada a su texto y timeout originales."""
    n = 0
    pendientes = list(cambios)
    for grupos in (settings.get("hooks") or {}).values():
        if not isinstance(grupos, list):
            continue
        for grupo in grupos:
            for h in grupo.get("hooks", []) if isinstance(grupo, dict) else []:
                if not isinstance(h, dict):
                    continue
                c = next((c for c in pendientes if c["despues"] == h.get("command")), None)
                if c is None:
                    continue
                pendientes.remove(c)
                h["command"] = c["antes"]
                if c["timeout_antes"] is None:
                    h.pop("timeout", None)
                else:
                    h["timeout"] = c["timeout_antes"]
                n += 1
    return n


def _escribir_json(ruta: Path, datos: dict[str, Any]) -> None:
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, ruta)


def _huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _matar(pid_archivo: Path) -> None:
    if not pid_archivo.is_file():
        return
    try:
        pid = int(pid_archivo.read_text(encoding="ascii").strip())
    except (ValueError, OSError):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    pid_archivo.unlink(missing_ok=True)


def _detener_monitor(dir_datos: Path, nombre_tarea: str | None = None) -> None:
    """Detiene el bucle de arranque y el monitor (el bucle primero: si no, lo rearranca)."""
    detener = dir_datos / "detener"
    if dir_datos.is_dir():
        detener.write_text("", encoding="ascii")
    if os.name == "nt" and nombre_tarea:
        detener_tarea(nombre_tarea)
    _matar(dir_datos / "arranque.pid")
    _matar(dir_datos / "monitor.pid")
    time.sleep(0.5)
    detener.unlink(missing_ok=True)


def _powershell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _ps(texto: str) -> str:
    return "'" + texto.replace("'", "''") + "'"


def guion_arranque(exe: Path, dir_datos: Path) -> str:
    """arranque.ps1: corre el monitor y lo vuelve a arrancar si se cae. Termina
    si existe el archivo ``detener`` (instalador) o si el monitor ya no está."""
    datos = _ps(str(dir_datos))
    return (
        "# Arranque del monitor de la oficina de agentes (lo escribe el instalador).\n"
        f"$env:VISUALIZADOR_MONITOR_DIR = {datos}\n"
        f"$exe = {_ps(str(exe))}\n"
        f"Set-Content -LiteralPath (Join-Path {datos} 'arranque.pid') -Value $PID -Encoding ascii\n"
        "while ($true) {\n"
        f"    if (Test-Path -LiteralPath (Join-Path {datos} 'detener')) {{ break }}\n"
        "    if (-not (Test-Path -LiteralPath $exe)) { break }\n"
        "    & $exe servir\n"
        "    # 2: falta configurar; 3: el puerto ya está ocupado (otro monitor)\n"
        "    if ($LASTEXITCODE -in 2, 3) { Start-Sleep -Seconds 30 } else { Start-Sleep -Seconds 3 }\n"
        "}\n"
    )


def registrar_tarea(guion: Path, nombre: str = NOMBRE_TAREA) -> tuple[bool, str]:
    """Como el arranque de la diaria: tarea del usuario al iniciar sesión, sin
    administrador ni límite de tiempo; si Windows no la deja crear, un acceso
    directo en Inicio. Devuelve (registrada, "tarea" o "acceso directo: ...")."""
    argumentos = f'-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{guion}"'
    script = f"""
$ErrorActionPreference = 'Stop'
$usuario = "$env:USERDOMAIN\\$env:USERNAME"
$argumentos = {_ps(argumentos)}
try {{
    $accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argumentos
    $disparo = New-ScheduledTaskTrigger -AtLogOn -User $usuario
    $principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
    $ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName {_ps(nombre)} -Action $accion -Trigger $disparo -Principal $principal -Settings $ajustes -Description 'Monitor de máquina de la oficina de agentes' -Force | Out-Null
    Start-ScheduledTask -TaskName {_ps(nombre)}
    Write-Output 'tarea'
}} catch {{
    $acceso = Join-Path ([Environment]::GetFolderPath('Startup')) ({_ps(nombre)} + '.lnk')
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($acceso)
    $lnk.TargetPath = 'powershell.exe'
    $lnk.Arguments = $argumentos
    $lnk.WindowStyle = 7
    $lnk.Save()
    Start-Process powershell.exe -ArgumentList $argumentos -WindowStyle Hidden
    Write-Output "acceso directo: $acceso"
}}
"""
    r = _powershell(script)
    salida = (r.stdout or "").strip()
    return r.returncode == 0, salida or (r.stderr or "").strip()


def detener_tarea(nombre: str = NOMBRE_TAREA) -> None:
    _powershell(f"Stop-ScheduledTask -TaskName {_ps(nombre)} -ErrorAction SilentlyContinue")


def quitar_tarea(nombre: str = NOMBRE_TAREA) -> None:
    _powershell(
        f"Stop-ScheduledTask -TaskName {_ps(nombre)} -ErrorAction SilentlyContinue; "
        f"Unregister-ScheduledTask -TaskName {_ps(nombre)} -Confirm:$false -ErrorAction SilentlyContinue; "
        f"Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Startup')) ({_ps(nombre)} + '.lnk')) -ErrorAction SilentlyContinue"
    )


def _leer_settings(cuentas: list[str]) -> dict[Path, dict[str, Any]]:
    """Todos los settings.json, antes de tocar nada: uno ilegible (por ejemplo con
    comentarios) detiene la instalación sin haber cambiado ningún archivo."""
    leidos: dict[Path, dict[str, Any]] = {}
    for cuenta in cuentas:
        ruta = Path(cuenta) / "settings.json"
        if not ruta.is_file():
            continue
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError) as e:
            raise ValueError(
                f"No se pudo leer {ruta} ({type(e).__name__}); no se cambió nada."
            ) from None
        if not isinstance(datos, dict):
            raise ValueError(f"{ruta} no tiene el formato esperado; no se cambió nada.")
        leidos[ruta] = datos
    return leidos


def _borrar_versiones_viejas(destino: Path, actual: Path) -> None:
    """Las versiones anteriores, si ningún hook en curso las tiene abiertas."""
    for d in destino.glob("v*"):
        if d.is_dir() and d != actual:
            shutil.rmtree(d, ignore_errors=True)


def instalar(
    *,
    servidor: str,
    token: str,
    origen: Path,
    destino: Path | None = None,
    inicio: Path | None = None,
    puerto: int = config.PUERTO_POR_DEFECTO,
    tarea: bool = True,
    nombre_tarea: str = NOMBRE_TAREA,
    exe_nombre: str = "visualizador-monitor.exe",
) -> dict[str, Any]:
    """Instala el monitor; devuelve el manifiesto (sin el token)."""
    from claude_office_hooks.peligrosos import texto_predeterminado

    servidor = config.validar_servidor(servidor)
    if not token.startswith("vam_"):
        raise ValueError("El token de máquina empieza con vam_.")
    destino = destino or destino_por_defecto()
    inicio = inicio or Path.home()
    dir_datos = inicio / ".visualizador-monitor"
    cuentas = config.cuentas_detectadas(inicio)
    leidos = _leer_settings(cuentas)  # antes de cambiar nada

    # Una reinstalación conserva lo que cambió la primera (para poder desinstalar).
    previos: dict[str, dict[str, Any]] = {}
    manifiesto_previo = dir_datos / "instalacion.json"
    if manifiesto_previo.is_file():
        anterior = json.loads(manifiesto_previo.read_text(encoding="utf-8"))
        previos = {a["ruta"]: a for a in anterior.get("settings", [])}

    # 1. archivos del monitor: cada instalación en su propia carpeta (v<versión>-<fecha>),
    # así una actualización no choca con los hooks que tienen abierta la anterior.
    _detener_monitor(dir_datos, nombre_tarea)
    ahora = datetime.now()
    carpeta = destino / f"v{VERSION}-{ahora.strftime('%Y%m%d-%H%M%S-%f')}"
    shutil.copytree(origen, carpeta)
    exe = carpeta / exe_nombre

    # 2. configuración del usuario y clave local de los hooks
    cfg = config.Configuracion(servidor=servidor, token=token, puerto=puerto, cuentas=cuentas)
    config.guardar(cfg, dir_datos)
    config.clave_local(dir_datos)
    lista = dir_datos / "comandos-peligrosos.txt"
    if not lista.is_file():
        lista.write_text(texto_predeterminado(), encoding="utf-8")

    manifiesto: dict[str, Any] = {
        "instalado": ahora.isoformat(timespec="seconds"),
        "version": VERSION,
        "destino": str(destino),
        "exe": str(exe),
        "datos": str(dir_datos),
        "servidor": servidor,
        "puerto": puerto,
        "cuentas": cuentas,
        "settings": list(previos.values()),
        "tarea": False,
        "nombre_tarea": nombre_tarea,
        "tarea_detalle": "",
    }

    def guardar_manifiesto() -> None:
        _escribir_json(dir_datos / "instalacion.json", manifiesto)

    # 3. hooks de cada cuenta (respaldo antes de tocar; el manifiesto se guarda
    # después de cada archivo, así la desinstalación siempre sabe qué revertir)
    guardar_manifiesto()
    sello = ahora.strftime("%Y%m%d-%H%M%S-%f")
    for ruta, datos in leidos.items():
        cambios = cambiar_hooks(datos, exe)
        if not cambios:
            continue
        previo = previos.get(str(ruta))
        huella_antes = _huella(ruta)
        # Nunca se pisa un respaldo anterior: el de la primera instalación es el original.
        respaldo = ruta.with_name(f"settings.json.respaldo-visualizador-{sello}")
        n = 1
        while respaldo.exists():
            respaldo = ruta.with_name(f"settings.json.respaldo-visualizador-{sello}-{n}")
            n += 1
        shutil.copy2(ruta, respaldo)
        _escribir_json(ruta, datos)
        # Si alguien cambió el archivo entre dos instalaciones, el respaldo original ya
        # no sirve entero: al desinstalar se revierten solo nuestras entradas.
        intacto = previo is None or huella_antes == previo.get("huella")
        ajuste = {
            "ruta": str(ruta),
            "respaldo": previo["respaldo"] if previo else str(respaldo),
            "huella": _huella(ruta) if intacto else None,
            "cambios": _encadenar(previo["cambios"], cambios) if previo else cambios,
        }
        manifiesto["settings"] = [a for a in manifiesto["settings"] if a["ruta"] != str(ruta)]
        manifiesto["settings"].append(ajuste)
        guardar_manifiesto()

    # 4. arranque automático
    guion = destino / "arranque.ps1"
    guion.write_text(guion_arranque(exe, dir_datos), encoding="utf-8-sig")
    if tarea:
        manifiesto["tarea"], manifiesto["tarea_detalle"] = registrar_tarea(guion, nombre_tarea)
    else:
        manifiesto["tarea_detalle"] = "sin tarea (prueba)"
    guardar_manifiesto()
    _borrar_versiones_viejas(destino, carpeta)
    return manifiesto


def desinstalar(
    *, destino: Path | None = None, inicio: Path | None = None, conservar_datos: bool = False
) -> dict[str, Any]:
    """Deja todo como estaba antes de instalar."""
    inicio = inicio or Path.home()
    dir_datos = inicio / ".visualizador-monitor"
    manifiesto_ruta = dir_datos / "instalacion.json"
    if not manifiesto_ruta.is_file():
        # Sin manifiesto no se sabe qué hooks revertir: no se borra el monitor
        # (los hooks seguirían apuntando a un programa que ya no existe).
        return {"revertidos": [], "destino_borrado": False, "sin_manifiesto": True}
    manifiesto: dict[str, Any] = json.loads(manifiesto_ruta.read_text(encoding="utf-8"))
    destino = destino or Path(manifiesto.get("destino") or destino_por_defecto())
    nombre_tarea = manifiesto.get("nombre_tarea") or NOMBRE_TAREA

    _detener_monitor(dir_datos, nombre_tarea)
    if os.name == "nt":
        quitar_tarea(nombre_tarea)
    pendientes = 0
    if (dir_datos / "cola.db").is_file():
        from visualizador_monitor.cola import Cola

        pendientes = Cola(dir_datos / "cola.db").pendientes()
    revertidos: list[dict[str, Any]] = []
    for ajuste in manifiesto.get("settings", []):
        ruta = Path(ajuste["ruta"])
        if not ruta.is_file():
            continue
        respaldo = Path(ajuste["respaldo"])
        if respaldo.is_file() and ajuste.get("huella") and _huella(ruta) == ajuste["huella"]:
            # Nadie lo tocó desde la instalación: vuelve el archivo original, byte a byte.
            shutil.copy2(respaldo, ruta)
            revertidos.append({"ruta": str(ruta), "entradas": len(ajuste["cambios"])})
            continue
        # Cambió después (otro programa o a mano): solo se revierten nuestras entradas.
        datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
        n = revertir_hooks(datos, ajuste["cambios"])
        if n:
            _escribir_json(ruta, datos)
        revertidos.append({"ruta": str(ruta), "entradas": n})
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    if not conservar_datos and dir_datos.exists():
        shutil.rmtree(dir_datos, ignore_errors=True)
    return {
        "revertidos": revertidos,
        "destino_borrado": not destino.exists(),
        "pendientes_sin_enviar": pendientes,
    }

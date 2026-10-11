"""Detector de atascos (etapa 2.1).

Un agente queda "atascado" cuando, en el turno en curso:

1. **Una herramienta excede su tiempo razonable**: el de la regla de esperas
   que le corresponde (pruebas, compilación, Unity...). No cuentan las que van
   en segundo plano, las rápidas (Read, Edit...: si llevan minutos es un evento
   perdido, no un atasco) ni la espera de tu permiso o tu respuesta.
2. **Repite el mismo error**: la última herramienta falló y ese mismo error
   (misma herramienta y ejecutable; mensaje sin "Exit code N", números, rutas
   ni ids) aparece ``errores_repetidos`` veces entre los últimos
   ``ventana_errores`` resultados. Las interrupciones no cuentan.
3. **Trabaja mucho sin avances**: lleva ``sin_avance_min`` minutos usando
   herramientas sin editar archivos (Edit/Write, escrituras desde la terminal,
   ediciones por MCP de Unity o Blender) ni hacer commits. La ventana empieza
   después de la última herramienta larga; si casi todo es leer o buscar en la
   web (investigación), el umbral es 1,5 veces mayor.

El turno en curso empieza con el último pedido, o después del último ``Stop`` si
el agente siguió trabajando sin pedido nuevo (una tarea de fondo que terminó).
Devuelve el motivo y un resumen de lo último que intentó.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.esperas import duracion, ejecutable
from app.core.historial import COMMIT, EDICION, una_linea
from app.models.events import EventType

# Herramientas que esperan al usuario (nunca son "una herramienta larga").
_PREGUNTAS = frozenset({"AskUserQuestion", "ExitPlanMode"})
# Herramientas que tardan segundos: si una sigue "en curso" es un evento perdido.
_RAPIDAS = frozenset(
    {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit", "NotebookEdit", "TodoWrite"}
)
_LECTURA = frozenset({"Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch", "TodoWrite"})
_TERMINAL = frozenset({"Bash", "PowerShell"})
# Escrituras desde la terminal y ediciones por MCP.
_ESCRITURA_TERMINAL = re.compile(
    r"\b(?:set-content|out-file|add-content|new-item|copy-item|move-item|remove-item)\b"
    r"|\bsed\s+-i\b|\btee\b|(?:^|[^<>=&|])>>?\s*[\w./\\\"'~$-]|\bgit\s+apply\b"
    r"|(?:^|[;&|(\s])(?:mv|cp|rm|mkdir|touch)\s",
    re.IGNORECASE,
)
_EDICION_MCP = re.compile(
    r"manage_(?:script|gameobject|scene|asset|prefab|material|shader)|execute_blender_code"
    r"|create_|update_|write_|edit_|delete_|apply_",
    re.IGNORECASE,
)
_HERRAMIENTA_LARGA_S = 120


@dataclass(frozen=True)
class Umbrales:
    errores_repetidos: int = 3
    ventana_errores: int = 8
    sin_avance_min: float = 30.0


_EXIT = re.compile(r"^\s*exit code[:\s]+-?\d+\s*$", re.IGNORECASE)
_RUTA = re.compile(r"(?:[A-Za-z]:)?[\\/][^\s'\"]+")
_HEX = re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]{8,}\b", re.IGNORECASE)
_NUM = re.compile(r"\d+")


def linea_util(texto: str | None) -> str | None:
    """La primera línea que dice algo (no "Exit code N")."""
    if not texto:
        return None
    for linea in texto.splitlines():
        if linea.strip() and not _EXIT.match(linea):
            return una_linea(linea, 200)
    return una_linea(texto, 200)


def clave_error(rec: Any) -> str:
    """La misma falla aunque cambien números, rutas o ids."""
    t = (linea_util(rec.text) or "").lower()
    t = _RUTA.sub("<ruta>", t)
    t = _HEX.sub("<id>", t)
    t = _NUM.sub("#", t)
    programa = ejecutable(rec.command) if rec.tool_name in _TERMINAL and rec.command else ""
    return f"{rec.tool_name or '?'}|{programa.lower()}|{t[:160]}"


def _intento(rec: Any) -> str:
    detalle = una_linea(rec.descripcion or rec.command, 80)
    return f"{rec.tool_name}: {detalle}" if detalle else str(rec.tool_name)


def _es_avance(rec: Any) -> bool:
    if rec.event_type != EventType.POST_TOOL_USE or rec.success is False:
        return False
    nombre = rec.tool_name or ""
    if nombre in EDICION:
        return True
    if nombre in _TERMINAL and rec.command:
        return bool(COMMIT.search(rec.command) or _ESCRITURA_TERMINAL.search(rec.command))
    return nombre.startswith("mcp__") and bool(_EDICION_MCP.search(nombre))


def turno_en_curso(records: Sequence[Any]) -> list[Any] | None:
    """Los records del turno abierto, o None si el último turno ya terminó."""
    for i in range(len(records) - 1, -1, -1):
        r = records[i]
        if not r.is_main:
            continue
        if r.event_type == EventType.USER_PROMPT_SUBMIT:
            return list(records[i:])
        if r.event_type == EventType.STOP:
            despues = list(records[i + 1 :])
            sigue = any(x.event_type == EventType.PRE_TOOL_USE and x.is_main for x in despues)
            return despues if sigue else None
    return list(records) or None


def detectar(
    records: Sequence[Any],
    pendientes: Sequence[Any],
    ahora: datetime,
    esperando_usuario: bool,
    limite_de: Callable[[Any], tuple[float | None, str]],
    umbrales: Umbrales,
) -> dict[str, Any] | None:
    """El atasco del turno en curso, o None.

    ``records``: los de la sesión en orden. ``pendientes``: herramientas en curso.
    ``limite_de(rec)``: (minutos razonables o None, texto de la espera).
    """
    if esperando_usuario:
        return None  # esperar tu permiso o tu respuesta no es estar atascado
    turno = turno_en_curso(records)
    if not turno:
        return None
    intentos = [r for r in turno if r.event_type == EventType.PRE_TOOL_USE]
    resumen = [_intento(r) for r in intentos[-3:]]
    fallas = [
        r for r in turno if r.event_type == EventType.POST_TOOL_USE_FAILURE and not r.is_interrupt
    ]
    ultimo_error = linea_util(fallas[-1].text) if fallas else None

    def atasco(tipo: str, motivo: str, desde: datetime) -> dict[str, Any]:
        return {
            "tipo": tipo,
            "motivo": motivo,
            "desde": desde.isoformat(),
            "ultimos_intentos": resumen,
            "ultimo_error": ultimo_error,
        }

    # 1. Una herramienta pasada de su tiempo razonable.
    largas: list[Any] = []
    for rec in pendientes:
        if rec.run_in_background or rec.tool_name in _PREGUNTAS or rec.tool_name in _RAPIDAS:
            continue
        segundos = (ahora - rec.ts).total_seconds()
        if segundos >= _HERRAMIENTA_LARGA_S:
            largas.append(rec)
        limite, texto = limite_de(rec)
        if limite is not None and segundos > limite * 60:
            return atasco(
                "herramienta_larga",
                f"{texto}: lleva {duracion(segundos)} (lo razonable es {limite:g} min)",
                rec.ts,
            )

    # 2. El mismo error repetido (y la última herramienta sigue fallando).
    resultados = [
        r
        for r in turno
        if r.event_type in (EventType.POST_TOOL_USE, EventType.POST_TOOL_USE_FAILURE)
        and not r.is_interrupt
    ][-max(1, umbrales.ventana_errores) :]
    if resultados and resultados[-1].event_type == EventType.POST_TOOL_USE_FAILURE:
        clave = clave_error(resultados[-1])
        repetidas = [
            r
            for r in resultados
            if r.event_type == EventType.POST_TOOL_USE_FAILURE and clave_error(r) == clave
        ]
        if len(repetidas) >= umbrales.errores_repetidos:
            herramienta = resultados[-1].tool_name
            detalle = f": {ultimo_error}" if ultimo_error else ""
            return atasco(
                "error_repetido",
                f"Repite el mismo error {len(repetidas)} veces ({herramienta}){detalle}",
                repetidas[0].ts,
            )

    # 3. Mucho tiempo trabajando sin cambios en archivos ni commits.
    if largas:
        return None  # una herramienta larga en curso: la mide la regla 1
    inicio = turno[0].ts
    # Después de la última herramienta larga que ya terminó (pruebas, compilación...).
    previas = {
        r.tool_use_id: r.ts
        for r in turno
        if r.event_type == EventType.PRE_TOOL_USE and r.tool_use_id
    }
    for r in turno:
        if (
            r.event_type in (EventType.POST_TOOL_USE, EventType.POST_TOOL_USE_FAILURE)
            and r.tool_use_id in previas
            and (r.ts - previas[r.tool_use_id]).total_seconds() >= _HERRAMIENTA_LARGA_S
        ):
            inicio = max(inicio, r.ts)
    recientes = [r for r in turno if r.ts >= inicio]
    usos = [r for r in recientes if r.event_type == EventType.PRE_TOOL_USE]
    if not usos:
        return None  # sin actividad: eso es inactividad, no atasco
    lectura = sum(1 for r in usos if r.tool_name in _LECTURA) / len(usos)
    ventana = umbrales.sin_avance_min * 60 * (1.5 if lectura >= 0.8 else 1.0)
    if (ahora - inicio).total_seconds() < ventana:
        return None
    ultimo_avance = max((r.ts for r in recientes if _es_avance(r)), default=None)
    if ultimo_avance is not None and (ahora - ultimo_avance).total_seconds() < ventana:
        return None
    desde = ultimo_avance or inicio
    return atasco(
        "sin_avances",
        f"Lleva {duracion((ahora - desde).total_seconds())} trabajando ({len(usos)} herramientas) "
        "sin editar archivos ni hacer commits",
        desde,
    )

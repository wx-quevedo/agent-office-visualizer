"""Historial por agente (etapa 2.1): la línea de tiempo de una sesión por turno.

Un turno empieza con lo que pide Washington (``UserPromptSubmit``) y termina con
el ``Stop`` de Claude o con el siguiente pedido. Por turno: el pedido en una
línea, las herramientas usadas, los archivos editados, los commits detectados,
la duración, los tokens de salida y cómo terminó:

- ``completado``: terminó con su ``Stop``.
- ``esperando``: terminó preguntando algo, o sigue abierto esperando permiso o respuesta.
- ``interrumpido``: llegó otro pedido o se cerró la sesión sin ``Stop``, o la
  última herramienta se cortó por una interrupción.
- ``error``: sin ``Stop`` y la última herramienta falló.
- ``en_curso``: el turno abierto mientras trabaja.

Puro: recibe los records de la sesión y las muestras de tokens.
"""

from __future__ import annotations

import bisect
import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.models.events import EventType

EDICION = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
# git commit al inicio de un segmento del comando (no dentro de un echo, un grep
# o el código de un heredoc).
_SEGMENTO_COMMIT = re.compile(r"^\s*\(?\s*git\s+(?:-\S+\s+\S+\s+)*commit\b", re.IGNORECASE)
_ENTRE_COMILLAS = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", re.DOTALL)
_SEPARADORES = re.compile(r"&&|\|\||[;|\n]")
# Hasta su línea de cierre, o hasta el final si el comando guardado quedó recortado.
_CUERPO_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?(?:\n\s*\1\b|\Z)", re.DOTALL)


class _Commit:
    """``COMMIT.search(comando)``: un ``git commit`` real en el comando."""

    @staticmethod
    def search(comando: str) -> bool:
        sin_heredoc = _CUERPO_HEREDOC.sub("", comando)
        # Lo que va entre comillas (mensajes, código de python -c) no cuenta.
        sin_textos = _ENTRE_COMILLAS.sub('""', sin_heredoc)
        return any(_SEGMENTO_COMMIT.match(s) for s in _SEPARADORES.split(sin_textos))


COMMIT = _Commit()
_MENSAJE = re.compile(r"""\s(?:-\w*m|--message)(?:\s+|=)(?:"([^"]*)"|'([^']*)'|(\S+))""")
_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\s*\1\b", re.DOTALL)
_LARGO_PEDIDO = 140


def una_linea(texto: str | None, largo: int = _LARGO_PEDIDO) -> str | None:
    """Primera línea con contenido, espacios colapsados, recortada."""
    if not texto:
        return None
    for linea in texto.splitlines():
        linea = " ".join(linea.split())
        if linea:
            return linea if len(linea) <= largo else linea[: largo - 1].rstrip() + "…"
    return None


def resumir_pedido(texto: str | None) -> str | None:
    """El pedido en una línea; los mensajes que traen otros agentes se nombran así."""
    if not texto:
        return None
    limpio = texto.lstrip()
    if limpio.startswith("<agent-message"):
        return "(mensaje de un subagente)"
    if limpio.startswith("<task-notification") or limpio.startswith("<system-reminder"):
        return "(aviso del sistema)"
    return una_linea(texto)


def mensaje_commit(comando: str) -> str | None:
    """El mensaje de un ``git commit`` (heredoc, -m, -am o --message), en una línea.

    Se busca desde el ``git commit`` (antes puede haber otro heredoc, de un script)."""
    inicio = re.search(r"\bgit\b[^\n]*?\bcommit\b", comando, re.IGNORECASE)
    if inicio:
        comando = comando[inicio.start() :]
    h = _HEREDOC.search(comando)
    if h:
        return una_linea(h.group(2), 100)
    m = _MENSAJE.search(comando)
    if m:
        return una_linea(next(g for g in m.groups() if g is not None), 100)
    return None


def tokens_en(
    muestras: Sequence[tuple[datetime, int]],
    ts: datetime,
    horas: Sequence[datetime] | None = None,
) -> int | None:
    """Tokens acumulados a esa hora: la última muestra anterior (o la primera).

    ``horas``: las horas de las muestras ya listas (evita armarlas en cada llamada)."""
    if not muestras:
        return None
    i = bisect.bisect_right(horas if horas is not None else [m[0] for m in muestras], ts)
    return muestras[i - 1][1] if i > 0 else muestras[0][1]


def _delta(
    muestras: Sequence[tuple[datetime, int]],
    ini: datetime,
    fin: datetime,
    horas: Sequence[datetime],
) -> int | None:
    a, b = tokens_en(muestras, ini, horas), tokens_en(muestras, fin, horas)
    if a is None or b is None:
        return None
    return max(0, b - a)


class _Turno:
    def __init__(self, inicio: datetime, pedido: str | None) -> None:
        self.inicio = inicio
        self.pedido = pedido
        self.fin: datetime | None = None
        self.resultado = "en_curso"
        self.herramientas: Counter[str] = Counter()
        self.archivos: list[str] = []
        self.commits: list[dict[str, Any]] = []
        self.errores = 0
        self.ultima_falla = False
        self.interrumpida = False
        self.pregunta: str | None = None
        self.ultimo_ts = inicio


def turnos(
    records: Sequence[Any],
    muestras: Sequence[tuple[datetime, int]],
    ahora: datetime,
    esperando: bool = False,
) -> list[dict[str, Any]]:
    """Turnos de la sesión, del más antiguo al más reciente.

    ``esperando``: el turno abierto espera permiso o respuesta ahora mismo.
    """
    lista: list[_Turno] = []
    actual: _Turno | None = None

    def cerrar(t: _Turno, ts: datetime, resultado: str) -> None:
        t.fin = ts
        t.resultado = resultado

    for rec in records:
        tipo = rec.event_type
        principal = rec.is_main
        if tipo == EventType.USER_PROMPT_SUBMIT and principal:
            if actual is not None and actual.fin is None:
                cerrar(actual, rec.ts, "interrumpido")
            actual = _Turno(rec.ts, resumir_pedido(rec.text))
            lista.append(actual)
            continue
        if actual is None:
            if tipo not in (EventType.PRE_TOOL_USE, EventType.POST_TOOL_USE):
                continue
            # Trabajo sin pedido visible (sesión retomada, pedido perdido).
            actual = _Turno(rec.ts, None)
            lista.append(actual)
        if actual.fin is not None:
            if tipo in (EventType.PRE_TOOL_USE, EventType.POST_TOOL_USE):
                # Trabajo después del Stop sin pedido nuevo: otro turno.
                actual = _Turno(rec.ts, None)
                lista.append(actual)
            else:
                continue
        actual.ultimo_ts = rec.ts
        if tipo == EventType.PRE_TOOL_USE and rec.tool_name:
            actual.herramientas[rec.tool_name] += 1
            if rec.tool_name in EDICION and rec.command and rec.command not in actual.archivos:
                actual.archivos.append(rec.command)
        elif tipo == EventType.POST_TOOL_USE:
            actual.ultima_falla = False
            if (
                rec.tool_name in ("Bash", "PowerShell")
                and rec.command
                and COMMIT.search(rec.command)
                and rec.success is not False
            ):
                actual.commits.append(
                    {"hora": rec.ts.isoformat(), "mensaje": mensaje_commit(rec.command)}
                )
        elif tipo == EventType.POST_TOOL_USE_FAILURE:
            actual.errores += 1
            actual.ultima_falla = True
            actual.interrumpida = bool(rec.is_interrupt)
        elif tipo == EventType.STOP and principal:
            actual.pregunta = rec.question_text if rec.question else None
            cerrar(actual, rec.ts, "esperando" if rec.question else "completado")
        elif tipo == EventType.SESSION_END and principal:
            cerrar(actual, rec.ts, "interrumpido")

    horas = [m[0] for m in muestras]
    salida: list[dict[str, Any]] = []
    for i, t in enumerate(lista):
        if t.fin is None:
            if t.interrumpida:
                t.resultado = "interrumpido"
            elif t.ultima_falla and i < len(lista) - 1:
                t.resultado = "error"
            elif esperando and i == len(lista) - 1:
                t.resultado = "esperando"
        if t.resultado == "interrumpido" and t.ultima_falla and not t.interrumpida:
            t.resultado = "error"
        fin = t.fin or (ahora if i == len(lista) - 1 else t.ultimo_ts)
        salida.append(
            {
                "numero": i + 1,
                "inicio": t.inicio.isoformat(),
                "fin": t.fin.isoformat() if t.fin else None,
                "duracion_s": max(0, int((fin - t.inicio).total_seconds())),
                "pedido": t.pedido,
                "herramientas": dict(t.herramientas.most_common()),
                "total_herramientas": sum(t.herramientas.values()),
                "archivos_editados": t.archivos,
                "commits": t.commits,
                "errores": t.errores,
                "tokens_salida": _delta(muestras, t.inicio, fin, horas),
                "resultado": t.resultado,
                "pregunta": t.pregunta,
            }
        )
    return salida


def pagina(lista: list[dict[str, Any]], numero: int, por_pagina: int) -> dict[str, Any]:
    """Página de turnos, del más reciente al más antiguo."""
    por_pagina = max(1, min(100, por_pagina))
    numero = max(1, numero)
    recientes = list(reversed(lista))
    inicio = (numero - 1) * por_pagina
    return {
        "pagina": numero,
        "por_pagina": por_pagina,
        "total": len(lista),
        "paginas": max(1, -(-len(lista) // por_pagina)),
        "turnos": recientes[inicio : inicio + por_pagina],
    }

"""Tokens y tiempo (etapa 2.1): por turno, por sesión y por día.

- **Tokens**: de salida, acumulados por sesión (las muestras que manda cada
  monitor o que lee el backend local), contados dentro del día.
- **Tiempo de trabajo**: la suma de los turnos (del pedido al ``Stop``) dentro
  del día. **Continuo**: el tramo actual de turnos seguidos (pausas de hasta
  ``PAUSA_CONTINUO_S``) si el agente sigue trabajando.
- Separado por cuenta (personal y Demo Org, por la carpeta de la transcripción) y
  por modelo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any

from app.core.historial import tokens_en, turnos

PAUSA_CONTINUO_S = 300


def tokens_entre(
    muestras: Sequence[tuple[datetime, int]], desde: datetime, hasta: datetime
) -> int | None:
    """Tokens producidos entre dos horas. Antes de la primera muestra: 0 (la
    cuenta de cada sesión empieza en su primer evento)."""
    if not muestras:
        return None
    previas = [m for m in muestras if m[0] <= desde]
    base = previas[-1][1] if previas else 0
    fin = tokens_en(muestras, hasta)
    if fin is None or muestras[0][0] > hasta:
        return 0
    return max(0, fin - base)


def _intervalos(
    turnos_sesion: list[dict[str, Any]], ahora: datetime
) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for t in turnos_sesion:
        ini = datetime.fromisoformat(t["inicio"])
        fin = ini + timedelta(seconds=t["duracion_s"])
        out.append((ini, min(fin, ahora)))
    return out


def _recortar(iv: list[tuple[datetime, datetime]], desde: datetime, hasta: datetime) -> float:
    return sum(max(0.0, (min(b, hasta) - max(a, desde)).total_seconds()) for a, b in iv)


def continuo(turnos_sesion: list[dict[str, Any]], ahora: datetime) -> int:
    """Segundos del tramo de trabajo actual (0 si el último turno ya terminó)."""
    if not turnos_sesion or turnos_sesion[-1]["fin"] is not None:
        return 0
    iv = _intervalos(turnos_sesion, ahora)
    inicio = iv[-1][0]
    for a, b in reversed(iv[:-1]):
        if (inicio - b).total_seconds() <= PAUSA_CONTINUO_S:
            inicio = a
        else:
            break
    return int((ahora - inicio).total_seconds())


def _union(iv: Iterable[tuple[datetime, datetime]]) -> float:
    total = 0.0
    fin_actual: datetime | None = None
    ini_actual: datetime | None = None
    for a, b in sorted(iv):
        if fin_actual is None or a > fin_actual:
            if fin_actual is not None and ini_actual is not None:
                total += (fin_actual - ini_actual).total_seconds()
            ini_actual, fin_actual = a, b
        else:
            fin_actual = max(fin_actual, b)
    if fin_actual is not None and ini_actual is not None:
        total += (fin_actual - ini_actual).total_seconds()
    return total


def del_dia(
    sesiones: Sequence[dict[str, Any]],
    desde: datetime,
    hasta: datetime,
    ahora: datetime,
) -> dict[str, Any]:
    """Consumo de un día.

    ``sesiones``: dicts con ``session_id``, ``proyecto``, ``cuenta``, ``modelo``,
    ``maquina``, ``records``, ``muestras`` y ``esperando``.
    """
    por_sesion: list[dict[str, Any]] = []
    todos: list[tuple[datetime, datetime]] = []
    for s in sesiones:
        lista = turnos(s["records"], s["muestras"], ahora, s.get("esperando", False))
        iv = _intervalos(lista, ahora)
        segundos = _recortar(iv, desde, hasta)
        tokens = tokens_entre(s["muestras"], desde, hasta)
        turnos_dia = [t for t, (a, b) in zip(lista, iv, strict=True) if b >= desde and a <= hasta]
        if not turnos_dia and not tokens:
            continue
        todos.extend((max(a, desde), min(b, hasta)) for a, b in iv if b >= desde and a <= hasta)
        por_sesion.append(
            {
                "session_id": s["session_id"],
                "proyecto": s.get("proyecto"),
                "cuenta": s.get("cuenta") or "desconocida",
                "modelo": s.get("modelo") or "desconocido",
                "maquina": s.get("maquina"),
                "turnos": len(turnos_dia),
                "tokens_salida": tokens or 0,
                "segundos_trabajo": int(segundos),
                "continuo_s": continuo(lista, ahora)
                if hasta >= ahora - timedelta(minutes=1)
                else 0,
            }
        )

    def agrupar(clave: str) -> list[dict[str, Any]]:
        grupos: dict[str, dict[str, Any]] = {}
        for s in por_sesion:
            g = grupos.setdefault(
                s[clave],
                {clave: s[clave], "sesiones": 0, "tokens_salida": 0, "segundos_trabajo": 0},
            )
            g["sesiones"] += 1
            g["tokens_salida"] += s["tokens_salida"]
            g["segundos_trabajo"] += s["segundos_trabajo"]
        return sorted(grupos.values(), key=lambda g: -g["tokens_salida"])

    por_sesion.sort(key=lambda s: -s["segundos_trabajo"])
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "total": {
            "sesiones": len(por_sesion),
            "tokens_salida": sum(s["tokens_salida"] for s in por_sesion),
            "segundos_trabajo": sum(s["segundos_trabajo"] for s in por_sesion),
            # Tiempo con al menos un agente trabajando (sin sumar dos veces).
            "segundos_con_agentes": int(_union(todos)),
        },
        "por_cuenta": agrupar("cuenta"),
        "por_modelo": agrupar("modelo"),
        "por_sesion": por_sesion,
    }

"""Etapa 2.1, ver bien: historial, consumo, límites y "Dónde quedamos".

- GET  /agents/{session_id}/historial?pagina=1&por_pagina=20: turnos (del más reciente).
- GET  /consumo?dia=AAAA-MM-DD: tokens y tiempo de un día (hoy por defecto), por
  sesión, cuenta y modelo.
- GET  /limites: límites de 5 h y semanal por cuenta (lo último que vio cada monitor).
- GET  /proyectos: "Dónde quedamos" por proyecto, con lo último que hizo un agente ahí
  y los prompts que corrieron sus agentes ("Prompt N · ...", con tiempo y commits).
- POST /maquinas/limites y /maquinas/proyectos: los manda cada monitor (token de máquina).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.agent_state_engine import get_state_engine
from app.core.datos_maquinas import get_datos_maquinas
from app.core.historial import una_linea
from app.core.resumenes import get_resumenes

router = APIRouter(tags=["ver bien"])


@router.get("/agents/{session_id}/historial")
async def historial(
    session_id: str,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    if not session_id or len(session_id) > 128:
        raise HTTPException(status_code=404, detail="No existe esa sesión.")
    datos = get_state_engine().historial(session_id, pagina, por_pagina)
    if datos is None:
        raise HTTPException(status_code=404, detail="No existe esa sesión.")
    return datos


def _zona() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().ZONA_HORARIA)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


@router.get("/consumo")
async def consumo(dia: date | None = None) -> dict[str, Any]:
    zona = _zona()
    hoy = datetime.now(zona).date()
    dia = dia or hoy
    if dia > hoy or (hoy - dia).days > 31:
        raise HTTPException(status_code=422, detail="Día fuera de rango (hasta 31 días atrás).")
    desde = datetime.combine(dia, time.min, zona).astimezone(UTC)
    hasta = min(desde + timedelta(days=1), datetime.now(UTC))
    datos = get_state_engine().consumo(desde, hasta)
    # El auxiliar de los avisos, aparte: no se mezcla con los agentes.
    auxiliar = get_resumenes().consumo(desde, hasta)
    return {"dia": dia.isoformat(), "zona": str(zona), **datos, "auxiliar": auxiliar}


@router.get("/limites")
async def limites() -> dict[str, Any]:
    return {
        "fuente": "barra de estado de Claude Code (rate_limits; solo Pro y Max)",
        "cuentas": get_datos_maquinas().vista_limites(),
    }


def _misma_carpeta(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return a.replace("\\", "/").rstrip("/").lower() == b.replace("\\", "/").rstrip("/").lower()


# "Prompt 28 · Etapa 2.3, ficha..." al inicio del pedido.
_PROMPT = re.compile(r"^\s*prompt\s+(\d{1,4})\b\s*[·:.\-–—]?\s*(.*)$", re.IGNORECASE)
_MAX_PROMPTS = 40


def prompts_de_turnos(sesiones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Los prompts que corrieron los agentes de un proyecto.

    ``sesiones``: historiales (turnos del más reciente al más antiguo). Un prompt
    empieza con un pedido "Prompt N" y sigue con los pedidos siguientes de la misma
    sesión (respuestas, resultados de comandos) hasta el próximo "Prompt M": su
    tiempo y sus commits se suman. El resultado es el del último turno.
    """
    vistos: dict[int, dict[str, Any]] = {}
    for hist in sesiones:
        actual: dict[str, Any] | None = None
        for turno in reversed(hist.get("turnos") or []):
            m = _PROMPT.match(turno.get("pedido") or "")
            if m:
                numero = int(m.group(1))
                actual = vistos.get(numero)
                if actual is None:
                    actual = {
                        "numero": numero,
                        "nombre": una_linea(m.group(2), 100),
                        "inicio": turno["inicio"],
                        "duracion_s": 0,
                        "commits": [],
                        "resultado": turno["resultado"],
                        "session_id": hist.get("session_id"),
                    }
                    vistos[numero] = actual
            if actual is None:
                continue
            actual["duracion_s"] += int(turno.get("duracion_s") or 0)
            actual["commits"].extend(turno.get("commits") or [])
            actual["resultado"] = turno["resultado"]
    return sorted(vistos.values(), key=lambda p: p["numero"])[-_MAX_PROMPTS:]


@router.get("/proyectos")
async def proyectos() -> dict[str, Any]:
    motor = get_state_engine()
    vista = motor.snapshot()
    out: list[dict[str, Any]] = []
    for p in get_datos_maquinas().vista_proyectos():
        agentes = [
            a
            for a in vista["agentes"]
            if _misma_carpeta(a["agente"]["proyecto"], p.get("carpeta"))
            and a["agente"].get("maquina") in (None, p.get("maquina"))
        ]
        ultimo = max(agentes, key=lambda a: a["ultimo_evento"]["hora"] or "", default=None)
        historiales = [
            h
            for a in agentes
            if (h := motor.historial(a["agente"]["session_id"], 1, 100)) is not None
        ]
        actividad: dict[str, Any] | None = None
        if ultimo is not None:
            sid = ultimo["agente"]["session_id"]
            hist = motor.historial(sid, 1, 1)
            turno = hist["turnos"][0] if hist and hist["turnos"] else None
            actividad = {
                "session_id": sid,
                "estado": ultimo["estado"]["nombre"],
                "espera": (cast(dict[str, Any], ultimo.get("espera_detalle") or {})).get("texto"),
                "ultimo_evento": ultimo["ultimo_evento"]["hora"],
                "ultimo_turno": turno,
            }
        out.append(
            {
                **p,
                "ultima_actividad": actividad,
                "prompts_turnos": prompts_de_turnos(historiales),
            }
        )
    out.sort(key=lambda p: str(p.get("recibido") or ""), reverse=True)
    return {"proyectos": out}


# -- ingesta de los monitores ------------------------------------------------------


class Ventana(BaseModel):
    usado_pct: float | None = Field(default=None, ge=0, le=100)
    reinicia: datetime | None = None


class LimitesCuenta(BaseModel):
    cuenta_dir: str | None = Field(default=None, max_length=300)
    cinco_horas: Ventana | None = None
    semanal: Ventana | None = None
    visto: datetime | None = None
    modelo: str | None = Field(default=None, max_length=100)


class Limites(BaseModel):
    cuentas: list[LimitesCuenta] = Field(max_length=20)


def _maquina(request: Request) -> str:
    return getattr(request.state, "maquina", None) or get_settings().MAQUINA_LOCAL_ID


@router.post("/maquinas/limites")
async def recibir_limites(request: Request, body: Limites) -> dict[str, Any]:
    maquina = _maquina(request)
    datos = get_datos_maquinas()
    cuentas = [
        datos.registrar_limites(
            maquina, c.cuenta_dir, c.model_dump(mode="json", exclude={"cuenta_dir"})
        )
        for c in body.cuentas
    ]
    return {"recibidas": len(cuentas), "cuentas": cuentas}


class ItemPlan(BaseModel):
    nombre: str = Field(max_length=200)
    estado: str = Field(max_length=20)


class PromptPlan(BaseModel):
    numero: int = Field(ge=0, le=9999)
    nombre: str = Field(max_length=200)
    estado: str = Field(max_length=20)
    fecha: str | None = Field(default=None, max_length=40)
    commits: list[str] = Field(default_factory=lambda: [], max_length=10)


class Commit(BaseModel):
    hash: str = Field(max_length=64)
    mensaje: str | None = Field(default=None, max_length=300)
    fecha: str | None = Field(default=None, max_length=40)


class Proyecto(BaseModel):
    carpeta: str = Field(min_length=1, max_length=500)
    tiene_project_md: bool = False
    titulo: str | None = Field(default=None, max_length=300)
    plan: list[ItemPlan] = Field(default_factory=lambda: [], max_length=60)
    posicion: str | None = Field(default=None, max_length=200)
    siguiente_paso: str | None = Field(default=None, max_length=400)
    espera_decision: list[str] = Field(default_factory=lambda: [], max_length=10)
    ultimo_commit: Commit | None = None
    prompts: list[PromptPlan] = Field(default_factory=lambda: [], max_length=40)
    modificado: str | None = Field(default=None, max_length=40)
    error: str | None = Field(default=None, max_length=200)


class Proyectos(BaseModel):
    proyectos: list[Proyecto] = Field(max_length=100)


@router.post("/maquinas/proyectos")
async def recibir_proyectos(request: Request, body: Proyectos) -> dict[str, Any]:
    n = get_datos_maquinas().registrar_proyectos(
        _maquina(request), [p.model_dump(mode="json") for p in body.proyectos]
    )
    return {"recibidos": n}

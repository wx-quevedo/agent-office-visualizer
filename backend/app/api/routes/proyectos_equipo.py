"""Proyectos con equipo (etapa 4, Prompt 37).

Usuario:
- GET  /proyectos-creados: proyectos con su equipo y lo que está haciendo cada miembro.
- GET  /proyectos-creados/maquinas: máquinas con su ruta base y si se pueden elegir.
- POST /proyectos-creados: crea uno (deja un encargo para el monitor de la máquina).
- GET  /proyectos-creados/{id}: un proyecto con su equipo.
- POST /proyectos-creados/{id}/pausar y /reanudar.

Máquina (token de máquina):
- GET  /maquinas/encargos: sus encargos pendientes (quedan tomados).
- POST /maquinas/encargos/{id}: resultado de un encargo.
- POST /maquinas/equipos: estado de las sesiones que tiene lanzadas.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.acceso import get_acceso
from app.core.agent_state_engine import get_state_engine
from app.core.proyectos_equipo import (
    ESFUERZOS,
    MAX_AGENTES,
    ProyectoError,
    get_proyectos_equipo,
    vista_lanzada,
)

router = APIRouter(tags=["proyectos con equipo"])

Esfuerzo = Literal["low", "medium", "high", "xhigh", "max"]
assert set(ESFUERZOS) == {"low", "medium", "high", "xhigh", "max"}


def _error(e: ProyectoError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.mensaje)


def _maquina(request: Request) -> str:
    return getattr(request.state, "maquina", None) or get_settings().MAQUINA_LOCAL_ID


def maquinas_vista() -> list[dict[str, Any]]:
    return get_proyectos_equipo().vista_maquinas(get_acceso().maquinas())


def con_estado(p: dict[str, Any]) -> dict[str, Any]:
    """El proyecto con lo que muestra la oficina de cada miembro (estado y espera)."""
    lanzadas = get_proyectos_equipo().sesiones_lanzadas()
    agentes = {
        a["agente"]["session_id"]: vista_lanzada(a, lanzadas.get(a["agente"]["session_id"]))
        for a in get_state_engine().snapshot()["agentes"]
    }
    haciendo: str | None = None
    equipo: list[dict[str, Any]] = []
    for m in p["equipo"]:
        a = agentes.get(m.get("session_id") or "")
        oficina = None
        if a is not None:
            detalle = a.get("espera_detalle")
            espera = (
                cast(dict[str, Any], detalle).get("texto") if isinstance(detalle, dict) else None
            )
            oficina = {
                "numero": a["estado"]["numero"],
                "nombre": a["estado"]["nombre"],
                "desde": a["estado"]["desde"],
                "espera": espera,
            }
            if haciendo is None and a["estado"]["numero"] not in (11, 12, 18, 19, 20, 21):
                haciendo = f"{m['nombre']}: {espera or a['estado']['nombre']}"
        equipo.append({**m, "oficina": oficina})
    return {
        **p,
        "equipo": equipo,
        "haciendo": haciendo,
        # Llegan con el Prompt 38 (órdenes del orquestador al agente).
        "ordenes_por_aprobar": 0,
    }


@router.get("/proyectos-creados")
async def listar() -> dict[str, Any]:
    return {"proyectos": [con_estado(p) for p in get_proyectos_equipo().proyectos()]}


@router.get("/proyectos-creados/maquinas")
async def maquinas() -> dict[str, Any]:
    return {"maquinas": maquinas_vista()}


class Miembro(BaseModel):
    modelo: str = Field(min_length=2, max_length=60)
    esfuerzo: Esfuerzo


class NuevoProyecto(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    maquina: str = Field(min_length=1, max_length=64)
    cuenta: Literal["personal", "demo"]
    plantilla: Literal["web", "unity", "expo", "vacia"] = "vacia"
    orquestador: Miembro
    agentes: list[Miembro] = Field(min_length=1, max_length=MAX_AGENTES)
    auto_aprobar: bool = False


@router.post("/proyectos-creados", status_code=201)
async def crear(body: NuevoProyecto) -> dict[str, Any]:
    maquina = next((m for m in maquinas_vista() if m["id"] == body.maquina), None)
    if maquina is None:
        raise HTTPException(status_code=404, detail="No existe esa máquina.")
    if not maquina["disponible"]:
        raise HTTPException(
            status_code=409, detail=f"No se puede usar esa máquina: {maquina['motivo']}."
        )
    try:
        p = get_proyectos_equipo().crear(
            body.nombre,
            body.maquina,
            body.cuenta,
            body.plantilla,
            body.orquestador.model_dump(),
            [a.model_dump() for a in body.agentes],
            body.auto_aprobar,
            maquina["ruta_base"],
        )
    except ProyectoError as e:
        raise _error(e) from None
    return con_estado(p)


@router.get("/proyectos-creados/{id_}")
async def ver(id_: str) -> dict[str, Any]:
    p = get_proyectos_equipo().proyecto(id_)
    if p is None:
        raise HTTPException(status_code=404, detail="No existe ese proyecto.")
    return con_estado(p)


@router.post("/proyectos-creados/{id_}/pausar")
async def pausar(id_: str) -> dict[str, Any]:
    try:
        return con_estado(get_proyectos_equipo().pausar(id_))
    except ProyectoError as e:
        raise _error(e) from None


@router.post("/proyectos-creados/{id_}/reanudar")
async def reanudar(id_: str) -> dict[str, Any]:
    try:
        return con_estado(get_proyectos_equipo().reanudar(id_))
    except ProyectoError as e:
        raise _error(e) from None


# -- el monitor -------------------------------------------------------------------------


@router.get("/maquinas/encargos")
async def encargos(request: Request) -> dict[str, Any]:
    return {"encargos": get_proyectos_equipo().encargos_pendientes(_maquina(request))}


class EstadoMiembro(BaseModel):
    nombre: str = Field(min_length=1, max_length=40)
    estado: Literal["pendiente", "activo", "pausado", "detenido", "error"]


class ResultadoEncargo(BaseModel):
    ok: bool
    error: str | None = Field(default=None, max_length=500)
    ruta: str | None = Field(default=None, max_length=400)
    miembros: list[EstadoMiembro] = Field(default_factory=lambda: [], max_length=10)


@router.post("/maquinas/encargos/{id_}")
async def resultado_encargo(request: Request, id_: str, body: ResultadoEncargo) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().informar_encargo(
            _maquina(request),
            id_,
            body.ok,
            body.error,
            body.ruta,
            [m.model_dump() for m in body.miembros],
        )
    except ProyectoError as e:
        raise _error(e) from None


class Equipo(BaseModel):
    proyecto_id: str = Field(min_length=1, max_length=64)
    miembros: list[EstadoMiembro] = Field(max_length=10)


class Equipos(BaseModel):
    equipos: list[Equipo] = Field(max_length=50)


@router.post("/maquinas/equipos")
async def equipos(request: Request, body: Equipos) -> dict[str, Any]:
    n = get_proyectos_equipo().informar_equipos(
        _maquina(request), [e.model_dump() for e in body.equipos]
    )
    return {"actualizados": n}

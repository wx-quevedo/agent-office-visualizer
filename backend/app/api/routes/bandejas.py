"""Bandejas de Decisiones e Ideas (etapa 3, Prompt 33).

- GET  /decisiones: pendientes (permisos, preguntas, atascos; lo más urgente arriba)
  y resueltas de hoy. Los permisos se deciden con POST /permisos/solicitudes/{id}/decision.
- POST /decisiones/atascos/visto: "Ya lo vi" (lo saca de la bandeja, no toca al agente).
- GET  /ideas, POST /ideas, PATCH /ideas/{id}, POST /ideas/{id}/archivar.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.routes.agents_state import agentes_con_extras
from app.core.agent_state_engine import get_state_engine
from app.core.bandejas import (
    MAX_PROYECTO,
    MAX_TEXTO_IDEA,
    get_bandejas,
    nombre_proyecto,
    pendientes,
)
from app.core.datos_maquinas import get_datos_maquinas

router = APIRouter(tags=["bandejas"])


def bandeja_actual() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(agentes, pendientes) con las preguntas ya anotadas."""
    agentes = agentes_con_extras()
    b = get_bandejas()
    items = pendientes(agentes, b.vistos(), get_state_engine().clock())
    b.sincronizar(items, agentes)
    return agentes, items


@router.get("/decisiones")
async def decisiones() -> dict[str, Any]:
    _, items = bandeja_actual()
    conteo = {t: sum(1 for i in items if i["tipo"] == t) for t in ("permiso", "pregunta", "atasco")}
    return {
        "pendientes": items,
        "conteo": {**conteo, "total": len(items)},
        "resueltas_hoy": get_bandejas().resueltas_hoy(carpeta_de_sesion, carpetas_conocidas()),
    }


class Visto(BaseModel):
    id: str = Field(min_length=1, max_length=300)
    dispositivo: Literal["pc", "celular", "app"] = "app"


@router.post("/decisiones/atascos/visto")
async def atasco_visto(body: Visto) -> dict[str, Any]:
    _, items = bandeja_actual()
    item = next((i for i in items if i["tipo"] == "atasco" and i["id"] == body.id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Ese atasco ya no está en la bandeja.")
    return get_bandejas().marcar_visto(item, body.dispositivo)


def carpeta_de_sesion(session_id: str | None) -> str | None:
    log = get_state_engine().sessions.get(session_id or "")
    return log.project if log is not None else None


def carpetas_conocidas() -> list[str]:
    """Carpetas de proyectos: las que manda el monitor y las de las sesiones."""
    carpetas = [str(p.get("carpeta") or "") for p in get_datos_maquinas().vista_proyectos()]
    carpetas += [log.project or "" for log in get_state_engine().sessions.values()]
    return [c for c in carpetas if c]


# -- ideas ------------------------------------------------------------------------------


def proyectos_conocidos(ideas: list[dict[str, Any]]) -> list[str]:
    """Los proyectos que conoce el backend: los del monitor, los de los agentes y los
    que ya usan las ideas."""
    nombres: set[str] = set()
    for p in get_datos_maquinas().vista_proyectos():
        n = nombre_proyecto(p.get("carpeta"))
        if n:
            nombres.add(n)
    for a in get_state_engine().snapshot()["agentes"]:
        n = nombre_proyecto(a["agente"].get("proyecto"))
        if n:
            nombres.add(n)
    nombres.update(i["proyecto"] for i in ideas if i.get("proyecto"))
    return sorted(nombres, key=str.lower)


@router.get("/ideas")
async def listar_ideas(archivadas: bool = Query(default=False)) -> dict[str, Any]:
    ideas = get_bandejas().ideas(archivadas)
    return {"ideas": ideas, "proyectos": proyectos_conocidos(get_bandejas().ideas(True))}


class NuevaIdea(BaseModel):
    texto: str = Field(min_length=1, max_length=MAX_TEXTO_IDEA)
    proyecto: str | None = Field(default=None, max_length=MAX_PROYECTO)
    origen: Literal["dictada", "escrita"] = "escrita"


@router.post("/ideas", status_code=201)
async def crear_idea(body: NuevaIdea) -> dict[str, Any]:
    try:
        return get_bandejas().crear_idea(body.texto, body.proyecto, body.origen)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


class CambioIdea(BaseModel):
    # Ausente: no cambia. null: sin proyecto.
    proyecto: str | None = Field(default=None, max_length=MAX_PROYECTO)
    texto: str | None = Field(default=None, max_length=MAX_TEXTO_IDEA)


@router.patch("/ideas/{id_}")
async def cambiar_idea(id_: str, body: CambioIdea) -> dict[str, Any]:
    campos = body.model_fields_set
    try:
        idea = get_bandejas().cambiar_idea(
            id_,
            proyecto=body.proyecto if "proyecto" in campos else False,
            texto=body.texto if "texto" in campos else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    if idea is None:
        raise HTTPException(status_code=404, detail="No existe esa idea.")
    return idea


class Archivar(BaseModel):
    archivar: bool = True


@router.post("/ideas/{id_}/archivar")
async def archivar_idea(id_: str, body: Archivar | None = None) -> dict[str, Any]:
    idea = get_bandejas().archivar_idea(id_, body.archivar if body else True)
    if idea is None:
        raise HTTPException(status_code=404, detail="No existe esa idea.")
    return idea

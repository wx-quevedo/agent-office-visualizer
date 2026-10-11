"""Read-only catalog state of every active agent (new canvas data source)."""

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.agent_state_engine import get_state_engine
from app.core.bandejas import get_bandejas, pendientes
from app.core.permisos import get_registro
from app.core.proyectos_equipo import get_proyectos_equipo, vista_lanzada
from app.core.resumenes import avisos_del_agente, get_resumenes

router = APIRouter(prefix="/agents", tags=["agents"])


def agentes_con_extras(snap: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The agents of the snapshot with their permission request and summaries."""
    snap = snap if snap is not None else get_state_engine().snapshot()
    permisos = get_registro().vistas_por_sesion()
    resumenes = get_resumenes()
    # Etapa 4: en -p la oficina no recibe el modelo ni el esfuerzo; los pone el registro
    # de proyectos con equipo para las sesiones que lanzó un monitor.
    lanzadas = get_proyectos_equipo().sesiones_lanzadas()
    agentes: list[dict[str, Any]] = []
    for a in snap["agentes"]:
        permiso = permisos.get(a["agente"]["session_id"])
        a = vista_lanzada(a, lanzadas.get(a["agente"]["session_id"]))
        agentes.append(
            {
                **a,
                "permiso": permiso,
                "resumenes": resumenes.vista(avisos_del_agente(a, permiso)),
            }
        )
    return agentes


@router.get("/state")
async def get_agents_state() -> dict[str, Any]:
    """Return each active agent's catalog state, wait, indicators and recent
    raw events, plus the user's global presence. Recomputed at request time.
    Each agent carries its permission request of the office (``permiso``:
    pending, or just decided/expired), or null, and the one-sentence summaries
    of its current alerts (``resumenes``, stage 2.4). ``decisiones_pendientes``:
    how many items the Decisions inbox has (stage 3, the app's tab badge).
    """
    engine = get_state_engine()
    snap = engine.snapshot()
    agentes = agentes_con_extras(snap)
    bandejas = get_bandejas()
    reloj = getattr(engine, "clock", None)
    leido = reloj() if callable(reloj) else None
    ahora = leido if isinstance(leido, datetime) else datetime.now(UTC)
    items = pendientes(agentes, bandejas.vistos(), ahora)
    bandejas.sincronizar(items, agentes)
    return {**snap, "agentes": agentes, "decisiones_pendientes": len(items)}


class Heartbeat(BaseModel):
    cliente: str = Field(min_length=1, max_length=64)
    dispositivo: Literal["pc", "celular"] = "pc"


@router.post("/presence")
async def post_presence(beat: Heartbeat) -> dict[str, str]:
    """Heartbeat of an open /oficina page (every 30 s). Counts as a connected
    browser for the user's presence, like the WebSocket. /datos does not send it.
    """
    get_state_engine().heartbeat(beat.cliente, beat.dispositivo)
    return {"estado": "ok"}

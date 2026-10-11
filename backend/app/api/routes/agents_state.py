"""Read-only catalog state of every active agent (new canvas data source)."""

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.agent_state_engine import get_state_engine
from app.core.permisos import get_registro
from app.core.resumenes import avisos_del_agente, get_resumenes

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/state")
async def get_agents_state() -> dict[str, Any]:
    """Return each active agent's catalog state, wait, indicators and recent
    raw events, plus the user's global presence. Recomputed at request time.
    Each agent carries its permission request of the office (``permiso``:
    pending, or just decided/expired), or null, and the one-sentence summaries
    of its current alerts (``resumenes``, stage 2.4).
    """
    snap = get_state_engine().snapshot()
    permisos = get_registro().vistas_por_sesion()
    resumenes = get_resumenes()
    agentes: list[dict[str, Any]] = []
    for a in snap["agentes"]:
        permiso = permisos.get(a["agente"]["session_id"])
        agentes.append(
            {
                **a,
                "permiso": permiso,
                "resumenes": resumenes.vista(avisos_del_agente(a, permiso)),
            }
        )
    return {**snap, "agentes": agentes}


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

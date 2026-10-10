"""Read-only catalog state of every active agent (new canvas data source)."""

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.agent_state_engine import get_state_engine

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/state")
async def get_agents_state() -> dict[str, Any]:
    """Return each active agent's catalog state, wait, indicators and recent
    raw events, plus the user's global presence. Recomputed at request time.
    """
    return get_state_engine().snapshot()


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

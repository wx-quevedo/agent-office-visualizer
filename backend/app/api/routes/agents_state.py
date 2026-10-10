"""Read-only catalog state of every active agent (new canvas data source)."""

from typing import Any

from fastapi import APIRouter

from app.core.agent_state_engine import get_state_engine

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/state")
async def get_agents_state() -> dict[str, Any]:
    """Return each active agent's catalog state, wait, indicators and recent
    raw events, plus the user's global presence. Recomputed at request time.
    """
    return get_state_engine().snapshot()

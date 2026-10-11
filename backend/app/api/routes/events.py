import logging
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.core.agent_state_engine import get_state_engine
from app.core.permisos import get_registro
from app.models.events import AnyEvent

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Per-session in-memory rate limiter for event ingestion (ARC-016)
# ---------------------------------------------------------------------------
# Keyed by session_id (not a single global bucket) so that one busy Claude
# Code session can never starve another. Event.session_id is regex-validated
# upstream to [a-zA-Z0-9_-]{1,128}, so it is a safe, bounded-length dict key.
_WINDOW = 60.0  # sliding window length in seconds

# Hard cap on simultaneously tracked session buckets. Internal safety valve
# against unbounded memory if many distinct session_ids appear within one
# window; realistic localhost deployments see a handful of concurrent
# sessions, so this only trips under bugs/abuse. Not operator-tunable.
_MAX_TRACKED_SESSIONS = 4096

# Fallback bucket key when the parsed session_id is unexpectedly empty.
# Event.session_id is a required Pydantic field, so this is defensive only;
# such requests share a single global bucket rather than a per-session one.
_FALLBACK_KEY = "__global__"

# session_id -> deque of monotonic timestamps within the current window.
_request_times: dict[str, deque[float]] = {}


def reset_rate_limiter() -> None:
    """Clear the rate limiter state.  Intended for use between test runs."""
    _request_times.clear()


def _prune_stale_buckets(exclude: str, cutoff: float) -> None:
    """Drop buckets whose newest entry has aged out of the window.

    A bucket that is empty, or whose freshest entry (``dq[-1]``) is older
    than ``cutoff``, is dead: the owning session has been idle for at least
    one full window. Removing these on every ingestion is what keeps the
    dict bounded under normal operation. ``exclude`` (the current session)
    is skipped because the caller manages it directly.

    Subsumes the "drop empty buckets" cleanup: a one-shot session that
    fires a few events and never returns leaves a non-empty but fully aged
    bucket behind, which would otherwise leak (the previous global limiter
    only ever drained the *current* session's deque).
    """
    for sid in [
        s for s, dq in _request_times.items() if s != exclude and (not dq or dq[-1] < cutoff)
    ]:
        del _request_times[sid]


def _check_rate_limit(session_id: str) -> None:
    """Raise HTTP 429 if this session's request rate exceeds the limit.

    Sliding-window counter keyed per session_id. Memory is bounded two ways:
    stale buckets are pruned on every call (see ``_prune_stale_buckets``),
    and a hard cap (``_MAX_TRACKED_SESSIONS``) guards the pathological case
    where many distinct sessions are all live within one window.

    Args:
        session_id: The event's session_id, used as the limiter key. Falls
            back to ``_FALLBACK_KEY`` if somehow empty.
    """
    key = session_id or _FALLBACK_KEY
    now = time.monotonic()
    cutoff = now - _WINDOW

    times = _request_times.get(key)
    if times is None:
        # New session — prune dead buckets first, then enforce the hard cap.
        _prune_stale_buckets(exclude=key, cutoff=cutoff)
        if len(_request_times) >= _MAX_TRACKED_SESSIONS:
            # All existing buckets are live; drop the oldest-inserted.
            _request_times.pop(next(iter(_request_times)))
        times = deque[float]()
        _request_times[key] = times
    else:
        # Drop this session's aged entries, then prune others opportunistically.
        while times and times[0] < cutoff:
            times.popleft()
        _prune_stale_buckets(exclude=key, cutoff=cutoff)

    if len(times) >= get_settings().EVENT_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
        )

    times.append(now)


@router.post("/events")
async def receive_event(
    request: Request,
    event: AnyEvent,
) -> dict[str, str]:
    """Receive a Claude Code hook event (from a hook or a machine monitor).

    The state engine takes it in arrival order (its own append-only log) and
    the response is immediate, so hooks never block.
    Subject to a per-session rate limit (default 1000 events per 60 seconds
    per session_id, configurable via the EVENT_RATE_LIMIT setting/env var).

    Args:
        request: The incoming HTTP request.
        event: The event payload from Claude Code hooks. ``event.session_id``
            keys the rate-limit bucket so concurrent sessions don't starve
            each other.

    Returns:
        A status payload with event_id and processing state.
    """
    _check_rate_limit(event.session_id)
    # The machine comes from its token (or the local one): never from the client.
    event.machine_id = getattr(request.state, "maquina", None) or get_settings().MAQUINA_LOCAL_ID
    # A monitor resends when an answer was lost: the event id makes it idempotent.
    # Keyed by machine: one machine cannot suppress the events of another.
    crudo = request.headers.get("x-evento-id", "")[:64]
    evento_id = f"{event.machine_id}:{crudo}" if crudo else None
    if evento_id and get_state_engine().ya_recibido(evento_id):
        return {"status": "duplicado", "event_id": crudo, "visual_action": "none"}
    # A session belongs to the machine that started it: another machine cannot
    # add events to it or take it over.
    duena = get_state_engine().maquina_de(event.session_id)
    if duena is not None and duena != event.machine_id:
        raise HTTPException(status_code=409, detail="Esa sesión es de otra máquina.")
    # Catalog state engine, in arrival order (its own append-only log).
    get_state_engine().accept(event, origin="hook")
    # Recorded only once accepted (no await in between: no other request runs here).
    get_state_engine().marcar_recibido(evento_id)
    # A pending permission of the office ends when Claude Code goes on.
    get_registro().resolver_sesion(
        event.session_id,
        str(event.event_type),
        getattr(event.data, "tool_name", None),
        getattr(event.data, "tool_input", None),
    )
    return {
        "status": "accepted",
        "event_id": str(event.timestamp),
        "visual_action": "processing",  # Simplified
    }

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_receive_event():
    response = client.post(
        "/api/v1/events",
        json={
            "event_type": "session_start",
            "session_id": "test_session",
            "timestamp": "2026-01-15T10:00:00",
            "data": {},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_event_rate_limiter_is_per_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARC-016: ingestion rate limit keys by session_id, not globally.

    One busy session hitting its limit must not throttle a different,
    concurrent session. The previous single global deque throttled the
    wrong dimension and silently dropped events from unrelated sessions
    (hooks do not retry on 429).
    """
    from app.api.routes import events
    from app.config import Settings

    limit = 3
    test_settings = Settings(EVENT_RATE_LIMIT=limit)
    monkeypatch.setattr(events, "get_settings", lambda: test_settings)
    events.reset_rate_limiter()

    def post(session_id: str) -> int:
        return client.post(
            "/api/v1/events",
            json={
                "event_type": "session_start",
                "session_id": session_id,
                "data": {},
            },
        ).status_code

    # Session A fills its own bucket up to the limit.
    for _ in range(limit):
        assert post("sess-a") == 200
    # Session A is now throttled at its own bucket.
    assert post("sess-a") == 429
    # Session B has a separate bucket and is unaffected — the core
    # per-session property the fix restores.
    assert post("sess-b") == 200

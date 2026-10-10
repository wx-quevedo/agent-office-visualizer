"""Engine-owned event log: order, no loss, retention, first-start import, 1 h no-PID close."""

import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.agent_event_store import AgentEventStore
from app.core.agent_state_engine import AgentStateEngine, Thresholds, bootstrap
from app.db.database import AsyncSessionLocal
from app.db.models import EventRecord, SessionRecord
from app.models.events import AnyEvent, EventAdapter

NOW = datetime.now(UTC)


def ev(session_id: str, event_type: str, seconds_ago: float, **data: Any) -> AnyEvent:
    return EventAdapter.validate_python(
        {
            "event_type": event_type,
            "session_id": session_id,
            "timestamp": NOW - timedelta(seconds=seconds_ago),
            "data": data,
        }
    )


def rows(store: AgentEventStore) -> list[tuple[int, str, str, str]]:
    with sqlite3.connect(store.path) as conn:
        return conn.execute(
            "SELECT id, session_id, event_type, payload FROM events ORDER BY id"
        ).fetchall()


@pytest.fixture
def store(tmp_path: Path):
    s = AgentEventStore(tmp_path / "agent_events.db")
    s.start()
    yield s
    s.close()


def test_appends_in_arrival_order_without_loss(store: AgentEventStore) -> None:
    sent = []
    for i in range(1200):
        e = ev(f"s{i % 3}", "pre_tool_use", 0, tool_name="Read", tool_use_id=f"t{i}")
        store.append(e)
        sent.append(f"t{i}")
    store.flush()
    saved = rows(store)
    assert len(saved) == 1200
    assert [r[0] for r in saved] == sorted(r[0] for r in saved)
    assert [EventAdapter.validate_json(r[3]).data.tool_use_id for r in saved] == sent  # type: ignore[union-attr]


def test_concurrent_writers_keep_per_session_order(store: AgentEventStore) -> None:
    def producer(sid: str) -> None:
        for i in range(250):
            store.append(ev(sid, "pre_tool_use", 0, tool_name="Read", tool_use_id=f"{sid}-{i}"))

    threads = [threading.Thread(target=producer, args=(f"s{n}",)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    store.flush()
    saved = rows(store)
    assert len(saved) == 2000
    ids = [EventAdapter.validate_json(r[3]).data.tool_use_id for r in saved]  # type: ignore[union-attr]
    assert len(set(ids)) == 2000
    for n in range(8):
        mine = [x for x in ids if x.startswith(f"s{n}-")]
        assert mine == [f"s{n}-{i}" for i in range(250)]


def test_retention_drops_old_events(store: AgentEventStore) -> None:
    store.append(ev("s1", "session_start", 0))
    store.append(ev("s1", "stop", 0))
    store.flush()
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE events SET received_ts = ? WHERE event_type = 'session_start'",
            ((NOW - timedelta(days=8)).isoformat(),),
        )
    assert store.delete_older_than(NOW - timedelta(days=7)) == 1
    assert [r[2] for r in rows(store)] == ["stop"]


def test_iter_recent_returns_whole_active_sessions(store: AgentEventStore) -> None:
    store.append(ev("old", "session_start", 30 * 3600))
    store.append(ev("live", "session_start", 30 * 3600))  # old start, recent activity
    store.append(ev("live", "user_prompt_submit", 60, prompt="x"))
    store.flush()
    loaded = list(store.iter_recent(NOW - timedelta(hours=24)))
    assert [(p["session_id"], p["event_type"]) for p in loaded] == [
        ("live", "session_start"),
        ("live", "user_prompt_submit"),
    ]


def test_failed_save_is_logged_and_engine_keeps_working(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class BrokenStore(AgentEventStore):
        def append(self, event: AnyEvent, origin: str = "hook") -> None:
            raise OSError("disk full")

    engine = AgentStateEngine(Thresholds(), store=BrokenStore(tmp_path / "x.db"))
    engine.accept(ev("s1", "session_start", 0))
    assert "s1" in engine.sessions
    assert "could not queue" in caplog.text


async def test_first_start_imports_last_24h_from_classic_db(tmp_path: Path) -> None:
    async with AsyncSessionLocal() as db:
        for sid in ("imp-live", "imp-old"):
            db.add(SessionRecord(id=sid, status="active"))
        rows_to_add = [
            ("imp-live", "session_start", 2 * 3600),
            ("imp-live", "stop", 3600),
            ("imp-old", "session_start", 50 * 3600),
        ]
        for sid, et, ago in rows_to_add:
            db.add(
                EventRecord(
                    session_id=sid,
                    timestamp=NOW - timedelta(seconds=ago),
                    event_type=et,
                    data={"last_assistant_message": "Listo."} if et == "stop" else {},
                )
            )
        await db.commit()

    store = AgentEventStore(tmp_path / "first.db")
    store.start()
    engine = AgentStateEngine(Thresholds(), store=store)
    result = await bootstrap(engine)
    assert result["importados"] == 2
    assert "imp-live" in engine.sessions and "imp-old" not in engine.sessions
    assert store.count() == 2

    # Second start: the log is not empty, so it loads from the log only.
    engine2 = AgentStateEngine(Thresholds(), store=store)
    result2 = await bootstrap(engine2)
    assert result2["importados"] == 0
    assert result2["cargados"] == 2
    assert [r.event_type for r in engine2.sessions["imp-live"].records] == [
        "session_start",
        "stop",
    ]
    store.close()


def test_no_pid_sessions_close_after_one_hour() -> None:
    from app.config import get_settings

    assert get_settings().STATE_NO_PID_CLOSE_HOURS == 1
    assert Thresholds.from_settings().no_pid_close == 3600
    clock_now = [NOW]
    engine = AgentStateEngine(Thresholds(), clock=lambda: clock_now[0])
    engine.ingest(ev("s1", "stop", 0, last_assistant_message="¿Lo borro también?"))
    clock_now[0] = NOW + timedelta(minutes=59)
    assert engine.state_for("s1").number == 14
    clock_now[0] = NOW + timedelta(minutes=61)
    st = engine.state_for("s1")
    assert st.number == 21
    agent = engine.tick()["agentes"][0]
    assert agent["cierre"]["motivo"] == "sin_pid_antiguo"
    assert agent["pregunta_pendiente"] == "¿Lo borro también?"

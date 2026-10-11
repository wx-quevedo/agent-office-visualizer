"""Append-only event log of the agent state engine.

Independent of the classic office database (``visualizer.db``), which loses
some events under bursts (race in ``EventProcessor._persist_event``) and stays
only for the classic view. Every event the engine receives is appended here in
arrival order by a single writer thread (SQLite in WAL mode), and on start-up
the engine rebuilds its state from this log.

Writes never block the request path: ``append`` puts the row on a queue and
the writer thread commits in batches. A failed write is logged (with the
event) and the engine keeps working in memory.
"""

from __future__ import annotations

import json
import logging
import queue
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.models.events import AnyEvent

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_ts TEXT NOT NULL,
    received_ts TEXT NOT NULL,
    origin TEXT NOT NULL,
    payload TEXT NOT NULL,
    machine_id TEXT
);
CREATE INDEX IF NOT EXISTS events_session ON events (session_id, id);
CREATE INDEX IF NOT EXISTS events_event_ts ON events (event_ts);
"""

_BATCH = 500
_STOP = object()


def _iso(ts: datetime) -> str:
    return (ts if ts.tzinfo else ts.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


class AgentEventStore:
    """SQLite append-only log with a single writer thread."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[object] = queue.Queue()
        self._writer: threading.Thread | None = None
        self.write_errors = 0
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            # Logs created before stage 1.1: the migration fills it for old rows.
            columnas = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
            if "machine_id" not in columnas:
                with conn:
                    conn.execute("ALTER TABLE events ADD COLUMN machine_id TEXT")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    # -- writing -------------------------------------------------------------

    def start(self) -> None:
        if self._writer is None or not self._writer.is_alive():
            self._writer = threading.Thread(target=self._run, name="agent-event-store", daemon=True)
            self._writer.start()

    def append(self, event: AnyEvent, origin: str = "hook") -> None:
        """Queue one event for writing (arrival order is preserved)."""
        row = (
            event.session_id,
            str(event.event_type),
            _iso(event.timestamp),
            datetime.now(UTC).isoformat(),
            origin,
            event.model_dump_json(),
            event.machine_id,
        )
        self._queue.put(row)
        if self._writer is None:
            self.start()

    def flush(self, timeout: float = 10.0) -> None:
        """Wait until every queued event has been written."""
        done = threading.Event()
        self._queue.put(done)
        done.wait(timeout)

    def close(self) -> None:
        if self._writer is not None and self._writer.is_alive():
            self._queue.put(_STOP)
            self._writer.join(10)
        self._writer = None

    def _run(self) -> None:
        conn = self._connect()
        try:
            while True:
                item = self._queue.get()
                batch: list[tuple[str | None, ...]] = []
                markers: list[threading.Event] = []
                stop = False
                while True:
                    if item is _STOP:
                        stop = True
                    elif isinstance(item, threading.Event):
                        markers.append(item)
                    else:
                        batch.append(item)  # type: ignore[arg-type]
                    if stop or len(batch) >= _BATCH:
                        break
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                if batch:
                    self._write(conn, batch)
                for m in markers:
                    m.set()
                if stop:
                    return
        finally:
            conn.close()

    def _write(self, conn: sqlite3.Connection, batch: list[tuple[str | None, ...]]) -> None:
        try:
            with conn:
                conn.executemany(
                    "INSERT INTO events (session_id, event_type, event_ts, received_ts, "
                    "origin, payload, machine_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
        except sqlite3.Error:
            # Retry one by one so a single bad row does not drop the batch.
            for row in batch:
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO events (session_id, event_type, event_ts, "
                            "received_ts, origin, payload, machine_id) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            row,
                        )
                except sqlite3.Error:
                    self.write_errors += 1
                    logger.exception(
                        "Agent event log: could not save %s for session %s", row[1], row[0]
                    )

    # -- reading / maintenance ----------------------------------------------

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def iter_recent(self, since: datetime) -> Iterator[tuple[dict[str, Any], str]]:
        """Payloads of every event of the sessions active since ``since``.

        Whole sessions are returned (not only their recent events) so state
        that depends on older events, such as SessionStart, is rebuilt too.
        Rows come in arrival order, as ``(payload, origin)``.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload, origin, machine_id FROM events WHERE session_id IN ("
                " SELECT session_id FROM events GROUP BY session_id"
                " HAVING MAX(event_ts) >= ?) ORDER BY id",
                (_iso(since),),
            )
            for payload, origin, machine_id in rows:
                datos = json.loads(payload)
                # Events saved before stage 1.1 have it only in the column.
                if machine_id and not datos.get("machine_id"):
                    datos["machine_id"] = machine_id
                yield datos, origin

    def delete_sessions(self, prefixes: list[str]) -> dict[str, int]:
        """Delete every event of the sessions whose id starts with a prefix.

        Used to remove test sessions. Returns ``{session_id: deleted_events}``.
        """
        deleted: dict[str, int] = {}
        with closing(self._connect()) as conn, conn:
            for prefix in prefixes:
                if not prefix:
                    continue
                match = "substr(session_id, 1, length(?)) = ?"
                for sid, n in conn.execute(
                    f"SELECT session_id, COUNT(*) FROM events WHERE {match} GROUP BY session_id",
                    (prefix, prefix),
                ).fetchall():
                    deleted[sid] = n
                conn.execute(f"DELETE FROM events WHERE {match}", (prefix, prefix))
        return deleted

    def delete_older_than(self, cutoff: datetime) -> int:
        """Retention: drop events received before ``cutoff``."""
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM events WHERE received_ts < ?", (_iso(cutoff),))
            return cur.rowcount


def default_store_path() -> Path:
    from app.config import get_settings

    return Path(get_settings().STATE_EVENT_LOG_PATH)


def retention_cutoff(now: datetime, days: float) -> datetime:
    return now - timedelta(days=days)

"""Agent state engine: catalog states computed from raw hook events.

Specification: ``docs/proyecto/catalogo-estados.md`` (20 states, "a quién
espera", presence and effort indicators). This module is independent of the
classic office ``StateMachine``: it keeps its own ordered log of compact event
records per session and derives the state from that log, the user's presence
and the current time. Time-based states (program wait, idle, rest, short-lived
states) are recomputed by :meth:`AgentStateEngine.tick`, which the app calls
every second, not only when an event arrives.

Output field names are in Spanish because they are the project's vocabulary
(see the catalog); code identifiers follow the rest of the backend.
"""

from __future__ import annotations

import bisect
import logging
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from app.core import atascos as _atascos
from app.core import consumo as _consumo
from app.core import esperas as _esperas
from app.core import historial as _historial
from app.core import resumenes as _resumenes
from app.core import token_tracker as _token_tracker
from app.core.agent_event_store import AgentEventStore
from app.core.transcript_tail import (
    TranscriptTotals,
    asks_question,
    clean_prompt,
    last_assistant_text,
    last_usage,
    resolve_transcript,
    tail_first_ts,
    turn_progress,
    user_text_near,
)
from app.models.events import AnyEvent, EventAdapter, EventType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

STATE_NAMES: dict[int, str] = {
    1: "Llega",
    2: "Recibe encargo",
    3: "Pensando",
    4: "Leyendo",
    5: "Escribiendo código",
    6: "En la terminal",
    7: "Investigando en la web",
    8: "Usando una app externa",
    9: "Planificando",
    10: "Compactando memoria",
    11: "Terminó el turno",
    12: "Se va",
    13: "Te espera: permiso",
    14: "Te espera: respuesta",
    15: "Espera un programa",
    16: "Espera una subida o descarga",
    17: "Espera a otros agentes",
    18: "Inactivo contigo presente",
    19: "Descansando sin ti",
    20: "Regresa al trabajo",
    21: "Cerrado",
}

# States where the agent is working (the stuck detector runs only in these).
_ESTADOS_DE_TRABAJO = frozenset({2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 20})

# Waiting kind for each waiting state.
WAIT_BY_STATE: dict[int, str] = {
    13: "tu_permiso",
    14: "tu_respuesta",
    15: "programa",
    16: "subida",
    17: "agentes",
}

# Tool name -> working state. mcp__* tools map to 8; tools not listed here fall
# back to 3 ("Pensando") and keep their name in ``herramienta_actual``.
READ_TOOLS = frozenset({"Read", "Grep", "Glob", "LS", "NotebookRead", "ToolSearch", "Skill"})
WRITE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
SHELL_TOOLS = frozenset({"Bash", "PowerShell"})
TERMINAL_TOOLS = SHELL_TOOLS | frozenset(
    {"BashOutput", "KillShell", "KillBash", "TaskOutput", "TaskStop", "Monitor"}
)
WEB_TOOLS = frozenset({"WebSearch", "WebFetch"})
PLAN_TOOLS = frozenset(
    {"TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "EnterPlanMode"}
)
# Tools that block on the user's answer while they run.
ASK_USER_TOOLS = frozenset({"AskUserQuestion", "ExitPlanMode"})

# Shell commands that move data over the network ("espera una subida o
# descarga"). Each pattern stops at a shell separator so `git status && ls`
# does not match `git ... push` across commands. Documented in PROJECT.md.
_SEG = r"[^|;&\n]*?"
NETWORK_COMMAND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("git push/pull/fetch/clone", re.compile(rf"\bgit\b{_SEG}\s(push|pull|fetch|clone)\b")),
    ("scp", re.compile(r"(^|[\s;&|(])scp\s")),
    ("rsync", re.compile(r"(^|[\s;&|(])rsync\s")),
    ("sftp", re.compile(r"(^|[\s;&|(])sftp\s")),
    ("docker/podman push/pull", re.compile(rf"\b(docker|podman)\b{_SEG}\s(push|pull)\b")),
    ("eas submit/build/update", re.compile(rf"\beas\b{_SEG}\s(submit|build|update)\b")),
    ("npm/pnpm/yarn publish", re.compile(rf"\b(npm|pnpm|yarn)\b{_SEG}\spublish\b")),
    ("gh release upload/download", re.compile(rf"\bgh\b{_SEG}\srelease\s+(upload|download)\b")),
    ("curl -T/--upload-file", re.compile(rf"\bcurl\b{_SEG}\s(-T|--upload-file)\b")),
    ("curl -o/-O (descarga)", re.compile(rf"\bcurl\b{_SEG}\s(-o|-O|--output|--remote-name)\b")),
    ("wget", re.compile(r"(^|[\s;&|(])wget\s")),
    ("aws s3 cp/sync/mv", re.compile(r"\baws\s+s3\s+(cp|sync|mv)\b")),
    ("gsutil cp/rsync", re.compile(rf"\bgsutil\b{_SEG}\s(cp|rsync)\b")),
    ("rclone copy/sync/move", re.compile(rf"\brclone\b{_SEG}\s(copy|sync|move)\b")),
    ("huggingface upload/download", re.compile(r"\b(huggingface-cli|hf)\s+(upload|download)\b")),
    (
        "firebase/vercel/netlify deploy",
        re.compile(rf"\b(firebase|vercel|netlify)\b{_SEG}\sdeploy\b"),
    ),
]


def network_command_match(command: str | None) -> str | None:
    """Return the label of the network pattern ``command`` matches, if any."""
    if not command:
        return None
    for label, pattern in NETWORK_COMMAND_PATTERNS:
        if pattern.search(command):
            return label
    return None


def tool_state(tool_name: str | None) -> int:
    """Catalog working state for a running tool (shell handled by the caller)."""
    if not tool_name:
        return 3
    if tool_name in READ_TOOLS:
        return 4
    if tool_name in WRITE_TOOLS:
        return 5
    if tool_name in TERMINAL_TOOLS:
        return 6
    if tool_name in WEB_TOOLS:
        return 7
    if tool_name.startswith("mcp__"):
        return 8
    if tool_name in PLAN_TOOLS:
        return 9
    return 3


def account_for_transcript(path: str | None) -> str | None:
    """'personal' for ~/.claude transcripts, 'demo' for ~/.claude-demo."""
    if not path:
        return None
    norm = path.replace("\\", "/").lower()
    if "/.claude-demo/" in norm:
        return "demo"
    if "/.claude/" in norm:
        return "personal"
    return None


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Thresholds:
    """Time thresholds in seconds (configurable via Settings / backend .env)."""

    program_wait: float = 30
    idle: float = 300
    presence_window: float = 600
    rest_after_disconnect: float = 600
    prompt: float = 3
    return_: float = 5
    reconcile_after: float = 120
    process_check: float = 30
    no_pid_close: float = 3600
    exit_visible: float = 120
    session_max_age: float = 24 * 3600

    @classmethod
    def from_settings(cls) -> Thresholds:
        from app.config import get_settings

        s = get_settings()
        return cls(
            program_wait=s.STATE_PROGRAM_WAIT_SECONDS,
            idle=s.STATE_IDLE_SECONDS,
            presence_window=s.STATE_PRESENCE_WINDOW_SECONDS,
            rest_after_disconnect=s.STATE_REST_AFTER_DISCONNECT_SECONDS,
            prompt=s.STATE_PROMPT_SECONDS,
            return_=s.STATE_RETURN_SECONDS,
            reconcile_after=s.STATE_RECONCILE_AFTER_SECONDS,
            process_check=s.STATE_PROCESS_CHECK_SECONDS,
            no_pid_close=s.STATE_NO_PID_CLOSE_HOURS * 3600,
            exit_visible=s.STATE_EXIT_VISIBLE_SECONDS,
            session_max_age=s.STATE_SESSION_MAX_AGE_HOURS * 3600,
        )


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

_MAX_RECORDS_PER_SESSION = 20_000
_RECENT_EVENTS = 15
_TOOL_RATE_WINDOW = 300.0  # tools/min and tokens/min window (5 min)
_SUMMARY_LEN = 80

_MAIN_IDS = frozenset({"", "main"})

# Claude Code only issues new tool calls after it has every result of the
# previous ones, so a main-agent PreToolUse that starts this long after a
# still-pending call means that call already ended (for producers that do not
# send PostToolUseFailure). Calls of one message start together.
_PARALLEL_TOOL_WINDOW = timedelta(seconds=2)
# Retries (one per second, from tick) to read a text from the transcript.
_TEXT_ATTEMPTS = 30
# A /oficina page that sent a heartbeat within this many seconds is "open".
_HEARTBEAT_TTL = 75


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _short(text: str | None, limit: int = _SUMMARY_LEN) -> str | None:
    if not text:
        return None
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class Record:
    """Compact, immutable view of one hook event."""

    ts: datetime
    seq: int
    event_type: str
    agent_id: str | None = None
    native_agent_id: str | None = None
    tool_name: str | None = None
    tool_use_id: str | None = None
    command: str | None = None
    text: str | None = None
    notification_type: str | None = None
    success: bool | None = None
    run_in_background: bool = False
    # Subagent that called the tool (hook ``tool_agent_id``), if any.
    tool_agent_id: str | None = None
    is_interrupt: bool | None = None
    reports_failures: bool = False
    # Stop: whether Claude's last message asks the user something.
    question: bool | None = None
    question_text: str | None = None
    # Where the event came from: hook, poller (classic transcript poller),
    # importacion (first-start import) or conciliacion (never stored).
    origin: str = "hook"
    # UserPromptSubmit whose text was only injected blocks (old hook
    # truncation): resolved later from the transcript.
    prompt_pending: bool = False
    text_attempts: int = 0
    # Claude Code process that owns the session (hook >= this project).
    claude_pid: int | None = None
    claude_pid_created: float | None = None
    # Stage 2.1: what the tool is for (Bash description, subagent task) and the
    # tool result error text (to detect the same error repeated).
    descripcion: str | None = None

    @property
    def is_main(self) -> bool:
        return (self.agent_id or "") in _MAIN_IDS and not self.tool_agent_id

    def sort_key(self) -> tuple[datetime, int]:
        return (self.ts, self.seq)


def record_from_event(event: AnyEvent, seq: int) -> Record:
    """Build a compact record from a parsed hook event."""
    d = event.data
    raw_input: object = getattr(d, "tool_input", None)
    tool_input: dict[str, Any] = (
        cast(dict[str, Any], raw_input) if isinstance(raw_input, dict) else {}
    )
    command = None
    if tool_input:
        raw_cmd = tool_input.get("command")
        if raw_cmd:
            command = str(raw_cmd)
        elif tool_input.get("file_path"):
            command = str(tool_input.get("file_path"))
        elif tool_input.get("pattern"):
            command = str(tool_input.get("pattern"))
        elif tool_input.get("url") or tool_input.get("query"):
            command = str(tool_input.get("url") or tool_input.get("query"))
        elif isinstance(tool_input.get("questions"), list):
            # AskUserQuestion: keep the first question's text.
            questions = cast(list[Any], tool_input.get("questions"))
            first: object = questions[0] if questions else None
            if isinstance(first, dict):
                command = str(cast(dict[str, Any], first).get("question") or "") or None
    raw_prompt: str | None = getattr(d, "prompt", None)
    prompt = clean_prompt(raw_prompt)
    text = (
        prompt
        if raw_prompt
        else getattr(d, "error", None)
        or getattr(d, "message", None)
        or getattr(d, "task_description", None)
        or getattr(d, "summary", None)
        or getattr(d, "reason", None)
    )
    return Record(
        ts=_aware(event.timestamp),
        seq=seq,
        event_type=str(event.event_type),
        agent_id=d.agent_id,
        native_agent_id=d.native_agent_id,
        tool_name=getattr(d, "tool_name", None),
        tool_use_id=getattr(d, "tool_use_id", None),
        command=command,
        text=str(text) if text else None,
        notification_type=getattr(d, "notification_type", None),
        success=getattr(d, "success", None),
        run_in_background=bool(tool_input.get("run_in_background")),
        tool_agent_id=getattr(d, "tool_agent_id", None),
        is_interrupt=getattr(d, "is_interrupt", None),
        reports_failures=bool(d.reports_tool_failures),
        claude_pid=d.claude_pid,
        claude_pid_created=d.claude_pid_created,
        prompt_pending=bool(raw_prompt) and prompt is None,
        descripcion=_descripcion(tool_input),
    )


def _descripcion(tool_input: dict[str, Any]) -> str | None:
    """Short purpose of a tool call: Bash "description" or the subagent's task."""
    for clave in ("description", "subagent_type"):
        valor = tool_input.get(clave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()[:200]
    return None


# ---------------------------------------------------------------------------
# Per-session data
# ---------------------------------------------------------------------------


def _is_permission_notification(rec: Record) -> bool:
    if rec.event_type != EventType.NOTIFICATION:
        return False
    if rec.notification_type:
        return "permission" in rec.notification_type
    return bool(rec.text and "permission" in rec.text.lower())


def _times_by_key() -> dict[str, datetime]:
    return {}


def _asks_user(rec: Record) -> bool:
    """Permission prompt that is really a question (AskUserQuestion, ExitPlanMode)."""
    if rec.tool_name in ASK_USER_TOOLS:
        return True
    return bool(rec.text and any(tool in rec.text for tool in ASK_USER_TOOLS))


@dataclass
class Reconciliation:
    """What the transcript says when events were lost (never stored as events)."""

    at: datetime
    evidence_ts: datetime | None
    tool_ids: frozenset[str]
    turn_end: datetime | None = None
    text: str | None = None
    question: bool = False

    def summary(self) -> str:
        parts: list[str] = []
        if self.tool_ids:
            parts.append(f"herramientas terminadas según la transcripción: {len(self.tool_ids)}")
        if self.turn_end:
            parts.append(f"turno terminado a las {self.turn_end.isoformat()}")
        return "; ".join(parts) or "sin cambios"


def _records_by_key() -> dict[str, Record]:
    return {}


def _times() -> list[datetime]:
    return []


def _records() -> list[Record]:
    return []


def _samples() -> list[tuple[datetime, int]]:
    return []


@dataclass
class _Derived:
    """Event-only facts (independent of the clock), rebuilt when the log changes."""

    first_ts: datetime | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    last_ts: datetime | None = None
    last_record: Record | None = None
    last_main: Record | None = None
    pending_tools: dict[str, Record] = field(default_factory=_records_by_key)
    pending_permission: Record | None = None
    active_subagents: dict[str, Record] = field(default_factory=_records_by_key)
    # Last event attributed to each active subagent (for the expiry).
    subagent_activity: dict[str, datetime] = field(default_factory=_times_by_key)
    tool_times: list[datetime] = field(default_factory=_times)
    active_minutes: int = 0
    consecutive_errors: int = 0
    saw_error_signal: bool = False
    last_prompt_ts: datetime | None = None
    # Latest Claude Code process seen for the session: (pid, creation time).
    process: tuple[int, float | None] | None = None
    # Explicit question still unanswered: a Stop that ends in "?" or an
    # AskUserQuestion/ExitPlanMode cut short by an end/restart of the session.
    question: Record | None = None


# Main-agent events that close a pending permission request.
_RESOLVES_PERMISSION = frozenset(
    {
        EventType.PRE_TOOL_USE,
        EventType.POST_TOOL_USE,
        EventType.POST_TOOL_USE_FAILURE,
        EventType.USER_PROMPT_SUBMIT,
        EventType.STOP,
        EventType.SESSION_END,
        EventType.SUBAGENT_START,
    }
)
_TOOL_DONE = frozenset({EventType.POST_TOOL_USE, EventType.POST_TOOL_USE_FAILURE})
# Main-agent events after which no tool can still be running in the foreground.
_CLEARS_PENDING = frozenset(
    {EventType.USER_PROMPT_SUBMIT, EventType.STOP, EventType.SESSION_END, EventType.SESSION_START}
)


def derive(records: Iterable[Record], recon: Reconciliation | None = None) -> _Derived:
    """Fold an ordered record log into clock-independent session facts."""
    dv = _Derived()
    native_to_start: dict[str, str] = {}
    minutes: set[int] = set()
    for rec in records:
        et = rec.event_type
        dv.last_record = rec
        # Synthetic stops from the classic transcript poller (zombie timeout)
        # do not end a subagent: only its SubagentStop, the main agent's Stop
        # or the death of the process do.
        if rec.origin == "poller" and et in (EventType.SUBAGENT_STOP, EventType.CLEANUP):
            continue
        # CLEANUP is synthesized by the backend (stamped when it runs), not
        # agent activity: it closes subagents but must not reset idle timers.
        if et != EventType.CLEANUP:
            dv.first_ts = dv.first_ts or rec.ts
            dv.last_ts = rec.ts
            minutes.add(int(rec.ts.timestamp() // 60))

        if et == EventType.SESSION_START:
            dv.start_ts = dv.start_ts or rec.ts
            dv.end_ts = None
        elif et == EventType.SESSION_END:
            dv.end_ts = rec.ts
        elif dv.end_ts is not None:
            dv.end_ts = None  # session resumed after an end

        if et == EventType.USER_PROMPT_SUBMIT:
            dv.last_prompt_ts = rec.ts
            dv.question = None
        elif et == EventType.STOP:
            dv.question = rec if rec.question else None
            dv.active_subagents.clear()  # the main agent's Stop ends its subagents
        if rec.claude_pid:
            dv.process = (rec.claude_pid, rec.claude_pid_created)

        # Subagents: SubagentStart without its SubagentStop.
        if et == EventType.SUBAGENT_START and rec.agent_id:
            dv.active_subagents[rec.agent_id] = rec
            dv.subagent_activity[rec.agent_id] = rec.ts
            dv.tool_times.append(rec.ts)  # the Task/Agent tool call itself
        elif et == EventType.SUBAGENT_INFO and rec.native_agent_id:
            if rec.native_agent_id not in native_to_start:
                linked = set(native_to_start.values())
                for aid in dv.active_subagents:
                    if aid not in linked:
                        native_to_start[rec.native_agent_id] = aid
                        break
        elif et in (EventType.SUBAGENT_STOP, EventType.CLEANUP):
            if rec.agent_id and rec.agent_id in dv.active_subagents:
                del dv.active_subagents[rec.agent_id]
            elif rec.native_agent_id and rec.native_agent_id in native_to_start:
                dv.active_subagents.pop(native_to_start[rec.native_agent_id], None)
        elif (
            et == EventType.POST_TOOL_USE_FAILURE
            and rec.is_main
            and rec.tool_name in ("Task", "Agent")
        ):
            # A Task/Agent call that fails never produces its SubagentStop.
            dv.active_subagents.pop(f"subagent_{rec.tool_use_id}", None)

        # Activity of a subagent: its own tool calls (native id or start id).
        owner = rec.tool_agent_id or rec.native_agent_id or (None if rec.is_main else rec.agent_id)
        if owner:
            start_id = native_to_start.get(owner, owner)
            if start_id in dv.active_subagents:
                dv.subagent_activity[start_id] = rec.ts

        # Errors: PostToolUseFailure in a row (user interrupts do not count).
        if rec.reports_failures:
            dv.saw_error_signal = True
        failed = (et == EventType.POST_TOOL_USE_FAILURE and not rec.is_interrupt) or (
            et == EventType.POST_TOOL_USE and rec.success is False
        )
        if failed or et == EventType.ERROR:
            dv.consecutive_errors += 1
            dv.saw_error_signal = True
        elif et == EventType.POST_TOOL_USE:
            dv.consecutive_errors = 0

        if not rec.is_main and et not in (EventType.SUBAGENT_START, EventType.SUBAGENT_STOP):
            # Subagent activity counts as an event and a tool, not as main state.
            if et == EventType.PRE_TOOL_USE:
                dv.tool_times.append(rec.ts)
            continue
        # Notifications (idle reminders, etc.) do not change what the agent
        # does; a permission notification is handled below.
        is_notification = et == EventType.NOTIFICATION

        if et == EventType.PRE_TOOL_USE:
            dv.tool_times.append(rec.ts)
            for key in [
                k
                for k, r in dv.pending_tools.items()
                if rec.ts - r.ts > _PARALLEL_TOOL_WINDOW and not r.run_in_background
            ]:
                del dv.pending_tools[key]
            key = rec.tool_use_id or f"{rec.tool_name}:{rec.seq}"
            dv.pending_tools[key] = rec
        elif et in _TOOL_DONE:
            if rec.tool_use_id and rec.tool_use_id in dv.pending_tools:
                del dv.pending_tools[rec.tool_use_id]
            else:
                # No tool_use_id: close the most recent pending call of that tool.
                for key in reversed(list(dv.pending_tools)):
                    if dv.pending_tools[key].tool_name == rec.tool_name:
                        del dv.pending_tools[key]
                        break
        if et in _CLEARS_PENDING:
            if et in (EventType.SESSION_START, EventType.SESSION_END):
                for pending in dv.pending_tools.values():
                    if pending.tool_name in ASK_USER_TOOLS:
                        dv.question = pending
            dv.pending_tools.clear()

        if et == EventType.PERMISSION_REQUEST or _is_permission_notification(rec):
            # AskUserQuestion/ExitPlanMode show up as a permission prompt but
            # they are questions: their pending tool call gives state 14.
            if not _asks_user(rec):
                dv.pending_permission = rec
        elif et in _RESOLVES_PERMISSION:
            dv.pending_permission = None

        # A subagent's result returns to the main agent (it resumes thinking),
        # unless the turn already ended: a background subagent finishing after
        # Stop does not wake the agent. Its start is the main agent waiting,
        # handled by active_subagents.
        if et == EventType.SUBAGENT_START or is_notification:
            continue
        if (
            et == EventType.SUBAGENT_STOP
            and dv.last_main is not None
            and dv.last_main.event_type == EventType.STOP
        ):
            continue
        dv.last_main = rec

    if recon is not None:
        _apply_reconciliation(dv, recon)
    dv.active_minutes = len(minutes)
    return dv


def _apply_reconciliation(dv: _Derived, recon: Reconciliation) -> None:
    """Close what the transcript shows finished; no event is invented or stored."""
    for key in [k for k, r in dv.pending_tools.items() if r.tool_use_id in recon.tool_ids]:
        del dv.pending_tools[key]
    if recon.turn_end is not None and (dv.last_main is None or recon.turn_end >= dv.last_main.ts):
        stop = Record(
            ts=recon.turn_end,
            seq=-1,
            event_type=str(EventType.STOP),
            text=recon.text,
            question=recon.question,
            question_text=recon.text[-200:] if recon.text else None,
            origin="conciliacion",
        )
        dv.last_main = stop
        dv.pending_tools.clear()
        dv.pending_permission = None
        dv.active_subagents.clear()
        dv.question = stop if recon.question else None
        if dv.last_ts is None or recon.turn_end > dv.last_ts:
            dv.last_ts = recon.turn_end


@dataclass
class SessionLog:
    """All engine-side data for one session."""

    session_id: str
    records: list[Record] = field(default_factory=_records)
    project: str | None = None
    # Machine that sends the events of this session (stage 1.1).
    machine_id: str | None = None
    # Stage 1.2: last observation of its monitor (process, tokens, texts).
    observacion: dict[str, Any] | None = None
    proceso_observado: bool | None = None
    transcript_path: str | None = None
    token_samples: list[tuple[datetime, int]] = field(default_factory=_samples)
    token_problem: str | None = None
    context_tokens: int | None = None
    context_window: int = 200_000
    # Stage 2.1: model of the session (from its monitor or the local transcript).
    modelo: str | None = None
    token_file_size: int = -1
    # Set when the registered Claude Code process is found gone.
    closed_process_at: datetime | None = None
    closed_pid: int | None = None
    # The process was seen alive by this run of the engine. When it was not
    # (found already gone right after a backend restart), the closure time is
    # unknown: the last event of the session is used, so a restart does not
    # move the closure to "now" (and the 1 h of a closed desk does not restart).
    process_seen_alive: bool = False
    # Reconciliation with the transcript (annotation only).
    recon: Reconciliation | None = None
    # Accumulated tokens of the transcript (read incrementally, in background).
    totals: TranscriptTotals | None = None
    totals_samples: list[tuple[datetime, int]] = field(default_factory=_samples)
    _derived: _Derived | None = None
    # Memory for state 20 ("regresa al trabajo").
    prev_state: int | None = None
    resting_since: datetime | None = None
    return_since: datetime | None = None
    return_until: datetime | None = None

    def add(self, rec: Record) -> None:
        if self.records and rec.sort_key() < self.records[-1].sort_key():
            bisect.insort(self.records, rec, key=Record.sort_key)
        else:
            self.records.append(rec)
        if len(self.records) > _MAX_RECORDS_PER_SESSION:
            del self.records[: len(self.records) - _MAX_RECORDS_PER_SESSION]
        self._derived = None

    def invalidate(self) -> None:
        self._derived = None

    @property
    def derived(self) -> _Derived:
        if self._derived is None:
            self._derived = derive(self.records, self.recon)
        return self._derived


# ---------------------------------------------------------------------------
# State computation
# ---------------------------------------------------------------------------


@dataclass
class Presence:
    connected: bool
    reason: str
    browsers: int
    last_prompt: datetime | None
    disconnected_since: datetime | None


@dataclass
class StateResult:
    number: int
    since: datetime
    wait: str | None = None
    evidence: dict[str, Any] | None = None


def _evidence(rec: Record | None, **extra: Any) -> dict[str, Any]:
    ev: dict[str, Any] = {
        "herramienta": rec.tool_name if rec else None,
        "comando": rec.command if rec else None,
        "desde": rec.ts.isoformat() if rec else None,
    }
    ev.update({k: v for k, v in extra.items() if v is not None})
    return ev


def active_subagents(dv: _Derived, now: datetime, th: Thresholds) -> dict[str, Record]:
    """Subagents still running: no SubagentStop and no Stop of the main agent yet.

    There is no time limit; a closed session (process gone, SessionEnd) hides
    them in the view.
    """
    del now, th
    return dict(dv.active_subagents)


def closure_of(log: SessionLog, now: datetime, th: Thresholds) -> tuple[str, datetime] | None:
    """Why and since when the session is closed, or None while it is open."""
    dv = log.derived
    if dv.end_ts is not None:
        return "session_end", dv.end_ts
    if log.closed_process_at is not None:
        return "proceso_terminado", log.closed_process_at
    if (
        dv.process is None
        and dv.last_ts is not None
        and (now - dv.last_ts).total_seconds() >= th.no_pid_close
    ):
        return "sin_pid_antiguo", dv.last_ts + timedelta(seconds=th.no_pid_close)
    return None


def pending_question(dv: _Derived) -> str | None:
    """Text of the explicit question still waiting for the user, if any."""
    for rec in dv.pending_tools.values():
        if rec.tool_name in ASK_USER_TOOLS:
            return rec.command or rec.tool_name
    if dv.question is not None:
        q = dv.question
        return q.question_text or q.command or q.tool_name
    return None


def compute_state(
    log: SessionLog, presence: Presence, now: datetime, th: Thresholds
) -> StateResult:
    """Catalog state for one session at ``now`` (without the state-20 memory)."""
    dv = log.derived
    start = dv.start_ts or dv.first_ts or now
    subagents = active_subagents(dv, now, th)

    if dv.end_ts is not None:
        # "Se va" briefly, then "Cerrado" (21).
        if (now - dv.end_ts).total_seconds() < th.exit_visible:
            return StateResult(12, dv.end_ts)
        return StateResult(21, dv.end_ts + timedelta(seconds=th.exit_visible))
    closure = closure_of(log, now, th)
    if closure is not None:
        return StateResult(21, closure[1])

    if dv.pending_permission is not None:
        perm = dv.pending_permission
        # PermissionRequest carries the tool; a permission Notification does not,
        # so fall back to the most recent running tool for the evidence.
        source = perm if perm.tool_name else (_latest(dv.pending_tools) or perm)
        return StateResult(13, perm.ts, "tu_permiso", _evidence(source, mensaje=_short(perm.text)))

    result: StateResult
    current = _latest(dv.pending_tools)
    if current is not None:
        tool = current.tool_name
        if tool in SHELL_TOOLS:
            net = network_command_match(current.command)
            elapsed = (now - current.ts).total_seconds()
            if net:
                result = StateResult(16, current.ts, "subida", _evidence(current, patron=net))
            elif elapsed >= th.program_wait:
                result = StateResult(
                    15,
                    current.ts + timedelta(seconds=th.program_wait),
                    "programa",
                    _evidence(current, segundos_sin_post_tool_use=int(elapsed)),
                )
            else:
                result = StateResult(6, current.ts)
        elif tool in ASK_USER_TOOLS:
            result = StateResult(14, current.ts, "tu_respuesta", _evidence(current))
        else:
            result = StateResult(tool_state(tool), current.ts)
    elif subagents:
        earliest = min(r.ts for r in subagents.values())
        since = max(earliest, dv.last_main.ts) if dv.last_main else earliest
        agents = [_short(r.text, 60) or r.agent_id for r in subagents.values()]
        result = StateResult(
            17,
            since,
            "agentes",
            {
                "herramienta": "Task/Agent",
                "comando": None,
                "desde": earliest.isoformat(),
                "subagentes": agents,
            },
        )
    else:
        result = _state_from_last_main(dv.last_main, start, now, th, dv.question)

    # Idle / rest: only when the agent is not waiting on anything.
    if result.wait is None and result.number != 12 and dv.last_ts is not None:
        idle_for = (now - dv.last_ts).total_seconds()
        if idle_for >= th.idle:
            idle_since = dv.last_ts + timedelta(seconds=th.idle)
            disc = presence.disconnected_since
            if (
                not presence.connected
                and disc is not None
                and (now - disc).total_seconds() >= th.rest_after_disconnect
            ):
                rest_since = max(idle_since, disc + timedelta(seconds=th.rest_after_disconnect))
                return StateResult(19, rest_since)
            return StateResult(18, idle_since)
    return result


def _latest(pending: dict[str, Record]) -> Record | None:
    return max(pending.values(), key=Record.sort_key) if pending else None


def _state_from_last_main(
    last: Record | None,
    start: datetime,
    now: datetime,
    th: Thresholds,
    question: Record | None = None,
) -> StateResult:
    if last is None or last.event_type == EventType.SESSION_START:
        if last is not None and question is not None:
            # Session reopened with its question still unanswered.
            return StateResult(
                14,
                last.ts,
                "tu_respuesta",
                {
                    "herramienta": question.tool_name,
                    "comando": None,
                    "desde": question.ts.isoformat(),
                    "evento": "pregunta_pendiente",
                    "mensaje": _short(question.question_text or question.command, 120),
                },
            )
        return StateResult(1, last.ts if last else start)
    et = last.event_type
    age = (now - last.ts).total_seconds()
    if et == EventType.CONTEXT_COMPACTION:
        return StateResult(10, last.ts)
    if et == EventType.STOP:
        # 14 only with an explicit question; otherwise the turn just ended
        # (11) and the idle rule moves it to 18/19 after STATE_IDLE_SECONDS.
        if last.question:
            return StateResult(
                14,
                last.ts,
                "tu_respuesta",
                {
                    "herramienta": None,
                    "comando": None,
                    "desde": last.ts.isoformat(),
                    "evento": "stop",
                    "mensaje": _short(last.question_text, 120),
                },
            )
        return StateResult(11, last.ts)
    if et == EventType.USER_PROMPT_SUBMIT:
        if age < th.prompt:
            return StateResult(2, last.ts)
        return StateResult(3, last.ts + timedelta(seconds=th.prompt))
    # PostToolUse, SubagentInfo, background notifications, other notifications…
    return StateResult(3, last.ts)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AgentStateEngine:
    """Per-session catalog state, presence and indicators."""

    def __init__(
        self,
        thresholds: Thresholds | None = None,
        clock: Callable[[], datetime] | None = None,
        browsers_provider: Callable[[], int] | None = None,
        process_alive: Callable[[int, float | None], bool | None] | None = None,
        lectura_local: bool = True,
        maquina_local: str | None = None,
        store: AgentEventStore | None = None,
    ) -> None:
        self.th = thresholds or Thresholds()
        # Engine-owned append-only log (independent of the classic database).
        self.store = store
        self.clock = clock or (lambda: datetime.now(UTC))
        self.browsers_provider = browsers_provider or (lambda: 0)
        self.process_alive = process_alive or _default_process_alive
        # Stage 1.2: transcripts and processes are read here only for sessions of
        # this machine; the others (and every session on the VPS) use what their
        # monitor sends (observar).
        self.lectura_local = lectura_local
        self.maquina_local = maquina_local
        # Event ids already received (a monitor resends after a lost answer).
        self._ids_recibidos: dict[str, None] = {}
        self._totals_busy: dict[str, bool] = {}
        # /oficina heartbeats: client id -> (last seen, device "pc"/"celular").
        self._heartbeats: dict[str, tuple[datetime, str]] = {}
        self._devices: list[str] = []
        self._last_process_check: datetime | None = None
        self.sessions: dict[str, SessionLog] = {}
        self.started_at = self.clock()
        # Stage 2.1: table of specific waits and thresholds of the stuck detector.
        self.ruta_esperas: Path | None = None
        self.umbrales_atasco = _atascos.Umbrales()
        self._seq = 0
        self._browsers = 0
        self._last_browser_seen: datetime | None = None
        self._snapshot: dict[str, Any] | None = None

    # -- ingestion ---------------------------------------------------------

    def accept(self, event: AnyEvent, origin: str = "hook") -> None:
        """Save an incoming event to the engine's own log, then ingest it.

        Called in arrival order. A failed save is logged and the engine keeps
        working in memory; ingestion errors never propagate to the caller.
        """
        if _resumenes.es_auxiliar(
            event.data.project_dir, event.data.working_dir, event.data.transcript_path
        ):
            return  # the summaries' helper never enters the office
        if self.store is not None:
            try:
                self.store.append(event, origin)
            except Exception:
                logger.exception(
                    "Agent event log: could not queue %s for session %s",
                    event.event_type,
                    event.session_id,
                )
        try:
            self.ingest(event, origin)
        except Exception:
            logger.exception("Agent state engine failed to ingest %s", event.event_type)

    def ingest(self, event: AnyEvent, origin: str = "hook") -> None:
        """Add one event to its session log (memory only)."""
        d = event.data
        if _resumenes.es_auxiliar(d.project_dir, d.working_dir, d.transcript_path):
            return
        self._seq += 1
        rec = record_from_event(event, self._seq)
        rec.origin = origin
        log = self.sessions.get(event.session_id)
        if log is None:
            log = self.sessions[event.session_id] = SessionLog(event.session_id)
        if event.machine_id:
            log.machine_id = event.machine_id
        d = event.data
        log.project = d.project_dir or d.working_dir or log.project or d.project_name
        if d.transcript_path:
            log.transcript_path = d.transcript_path
        if rec.event_type == EventType.STOP:
            self._detect_question(rec, event, log)
        self._update_tokens(log, event, rec.ts)
        log.add(rec)
        # Real events newer than what the transcript showed replace the
        # reconciliation.
        if log.recon is not None and (
            log.recon.evidence_ts is None or rec.ts > log.recon.evidence_ts
        ):
            log.recon = None
        # A newer event (or a new Claude Code process) reopens a session that
        # was closed because its process ended.
        if log.closed_process_at is not None and (
            rec.ts > log.closed_process_at
            or (rec.claude_pid is not None and rec.claude_pid != log.closed_pid)
        ):
            log.closed_process_at = None
            log.closed_pid = None
        self._snapshot = None

    def _detect_question(self, rec: Record, event: AnyEvent, log: SessionLog) -> None:
        """Stop: does Claude's last message end with '?' (explicit question)?

        Uses the Stop hook's ``last_assistant_message`` when the hook sends it;
        otherwise reads only the tail of the session transcript.
        """
        text = getattr(event.data, "last_assistant_message", None)
        if not text and log.transcript_path:
            # The Stop hook can fire before the final message is written: take
            # it only if the transcript already shows this turn's end;
            # otherwise leave it unknown and retry from tick().
            path, _ = self._transcript(log, log.transcript_path)
            if path is not None:
                try:
                    _, turn_end, _ = turn_progress(path)
                except OSError:
                    turn_end = None
                if turn_end is not None and turn_end[0] >= rec.ts - timedelta(seconds=30):
                    text = turn_end[1]
        if text:
            rec.question = asks_question(text)
            rec.question_text = text[-200:]
        else:
            rec.question = None

    def _update_tokens(self, log: SessionLog, event: AnyEvent, ts: datetime) -> None:
        """Latest message usage (= context size), from the event or the transcript tail."""
        d = event.data
        total: int | None = None
        if d.input_tokens is not None or d.output_tokens is not None:
            total = (d.input_tokens or 0) + (d.output_tokens or 0)
        elif d.transcript_path:
            path, problem = self._transcript(log, d.transcript_path)
            if path is None:
                log.token_problem = problem
                return
            try:
                size = path.stat().st_size
                if size == log.token_file_size:
                    return  # transcript unchanged since the last read
                log.token_file_size = size
                usage = last_usage(path)
            except OSError as exc:
                log.token_problem = f"No se pudo leer la transcripción: {exc}"
                return
            if usage is None:
                return
            total = int(usage["input_tokens"]) + int(usage["output_tokens"])
            self._scan_totals(log, path, ts)
            model = usage.get("model")
            if isinstance(model, str):
                log.modelo = model
                log.context_window = _token_tracker._context_window_for_model(model)  # pyright: ignore[reportPrivateUsage]
        if total is None:
            return
        if total != log.context_tokens or not log.token_samples:
            log.token_samples.append((ts, total))
        log.context_tokens = total
        log.token_problem = None

    def _muestra(self, log: SessionLog, ts: datetime, total: int) -> None:
        """New accumulated output tokens of a session: in memory and, if it changed, in the log."""
        anterior = log.totals_samples[-1][1] if log.totals_samples else None
        log.totals_samples.append((ts, total))
        if self.store is not None and total != anterior:
            try:
                self.store.append_muestra(log.session_id, ts, total, log.modelo)
            except Exception:
                logger.exception("Could not queue a token sample of %s", log.session_id)

    def _scan_totals(self, log: SessionLog, path: Any, ts: datetime) -> None:
        """Update the accumulated tokens of the transcript in a background thread.

        Counted since the first event of the session (the event being ingested
        is not in the records yet, so its time is the floor of a new session).
        """
        first = log.derived.first_ts
        since = min(first, ts) if first is not None else ts
        if (
            log.totals is None
            or log.totals.path != path
            or (log.totals.since is not None and since < log.totals.since)
        ):
            log.totals = TranscriptTotals(path, since=since)
            log.totals_samples.clear()
        totals = log.totals
        if self._totals_busy.get(log.session_id):
            return
        self._totals_busy[log.session_id] = True

        def run() -> None:
            try:
                value = totals.scan()
                self._muestra(log, self.clock(), value)
            except Exception:
                logger.exception("Could not read token totals of %s", log.session_id)
            finally:
                self._totals_busy[log.session_id] = False

        threading.Thread(target=run, name="agent-token-totals", daemon=True).start()

    # -- pending texts and reconciliation ----------------------------------

    def resolve_pending_texts(self) -> None:
        """Retry what the transcript did not have yet when the event arrived.

        Prompts whose text was only injected blocks are matched by time with
        the user entries of the transcript tail (up to _TEXT_ATTEMPTS tries).
        The question of a Stop without text is resolved for the latest Stop
        only, since the tail shows the latest turn.
        """
        for log in self.sessions.values():
            if not log.transcript_path or not log.records:
                continue
            prompts = [
                r for r in log.records if r.prompt_pending and r.text_attempts < _TEXT_ATTEMPTS
            ]
            last_stop = next(
                (r for r in reversed(log.records) if r.event_type == EventType.STOP), None
            )
            needs_stop = (
                last_stop is not None
                and last_stop.question is None
                and last_stop.text_attempts < _TEXT_ATTEMPTS
            )
            if not (prompts or needs_stop):
                continue
            path, _ = self._transcript(log, log.transcript_path)
            if path is None:
                continue
            changed = False
            try:
                for rec in prompts:
                    rec.text_attempts += 1
                    text = user_text_near(path, rec.ts)
                    if text:
                        rec.text = text
                        rec.prompt_pending = False
                        changed = True
                if needs_stop and last_stop is not None:
                    last_stop.text_attempts += 1
                    _, turn_end, _ = turn_progress(path)
                    text = turn_end[1] if turn_end else last_assistant_text(path)
                    if text:
                        last_stop.question = asks_question(text)
                        last_stop.question_text = text[-200:]
                        changed = True
            except OSError:
                continue
            if changed:
                log.invalidate()

    def reconcile(self, now: datetime | None = None) -> int:
        """Reconcile live sessions stuck in a working/waiting state with their transcript.

        A session qualifies when it is open, has no new event for
        STATE_RECONCILE_AFTER_SECONDS and is still working (a tool without
        PostToolUse, thinking after a prompt or a tool) or waiting on a
        program/upload. If the transcript tail shows the tool finished or the
        turn ended, the state is updated and annotated; nothing is stored.
        """
        now = now or self.clock()
        count = 0
        for log in self.sessions.values():
            if not log.transcript_path or closure_of(log, now, self.th) is not None:
                continue
            dv = log.derived
            if dv.last_ts is None or (now - dv.last_ts).total_seconds() < self.th.reconcile_after:
                continue
            last = dv.last_main
            working = bool(dv.pending_tools) or (
                last is not None
                and last.event_type
                not in (EventType.STOP, EventType.SESSION_START, EventType.SESSION_END)
            )
            if not working or dv.pending_permission is not None:
                continue
            path, _ = self._transcript(log, log.transcript_path)
            if path is None:
                continue
            try:
                finished, turn_end, last_ts = turn_progress(path)
                first_ts = tail_first_ts(path)
            except OSError:
                continue
            pending_ids = {r.tool_use_id for r in dv.pending_tools.values() if r.tool_use_id}
            # Tools older than everything in the tail, while the transcript has
            # newer activity, finished long ago (their result is just not in
            # the last 256 KB).
            moved_on = last_ts is not None and last_ts > dv.last_ts
            older = {
                r.tool_use_id
                for r in dv.pending_tools.values()
                if r.tool_use_id and moved_on and first_ts is not None and r.ts < first_ts
            }
            closed = frozenset((pending_ids & finished) | older)
            ended = turn_end if turn_end and (last is None or turn_end[0] >= last.ts) else None
            if not closed and ended is None:
                continue
            log.recon = Reconciliation(
                at=now,
                evidence_ts=last_ts,
                tool_ids=closed,
                turn_end=ended[0] if ended else None,
                text=ended[1] if ended else None,
                question=asks_question(ended[1]) if ended else False,
            )
            log.invalidate()
            count += 1
            logger.info(
                "Agent state engine reconciled %s with its transcript: %s",
                log.session_id,
                log.recon.summary(),
            )
        return count

    # -- presence ------------------------------------------------------------

    def heartbeat(self, client: str, device: str) -> None:
        """A page (/oficina) is open on a PC or phone; counts as a browser."""
        device = device if device in ("pc", "celular") else "pc"
        self._heartbeats[client[:64]] = (self.clock(), device)
        if len(self._heartbeats) > 200:  # bound memory
            oldest = min(self._heartbeats, key=lambda k: self._heartbeats[k][0])
            del self._heartbeats[oldest]
        self._snapshot = None

    def maquina_de(self, session_id: str) -> str | None:
        """Machine of a known session (None: new session, or before stage 1.1)."""
        log = self.sessions.get(session_id)
        return log.machine_id if log is not None else None

    # -- stage 1.2: local reads only for this machine; monitors for the rest --------

    def lee_local(self, log: SessionLog) -> bool:
        """Transcripts and processes of this session can be read here."""
        if not self.lectura_local:
            return False
        return (
            log.machine_id is None
            or self.maquina_local is None
            or (log.machine_id == self.maquina_local)
        )

    def _transcript(self, log: SessionLog, raw: str | None) -> tuple[Any, str | None]:
        """Readable transcript of a session, or (None, reason). Never for remote sessions."""
        if not raw or not self.lee_local(log):
            return None, None
        return resolve_transcript(raw)

    def ya_recibido(self, evento_id: str | None) -> bool:
        """True when this event id was already accepted (a monitor resending)."""
        if not evento_id:
            return False
        if evento_id in self._ids_recibidos:
            return True
        return self.store is not None and self.store.tiene_id(evento_id)

    def marcar_recibido(self, evento_id: str | None) -> None:
        """Record an accepted event id (after accept: a failed event can come back)."""
        if not evento_id:
            return
        # Memory first: a store error (locked, disk) must not let the resend in twice.
        self._ids_recibidos[evento_id] = None
        if self.store is not None:
            try:
                self.store.registrar_id(evento_id)
            except Exception:
                logger.exception("Could not persist a received event id")
        while len(self._ids_recibidos) > 100_000:
            self._ids_recibidos.pop(next(iter(self._ids_recibidos)))

    def observar(self, machine_id: str, obs: dict[str, Any], now: datetime | None = None) -> bool:
        """Observation of a session sent by its monitor (process, tokens, texts).

        Ignored for unknown sessions and for sessions of another machine.
        """
        now = now or self.clock()
        log = self.sessions.get(str(obs.get("session_id") or ""))
        if log is None or log.machine_id != machine_id:
            return False
        log.observacion = {**obs, "recibida": now.isoformat()}
        vivo = obs.get("proceso_vivo")
        if isinstance(vivo, bool):
            log.proceso_observado = vivo
        total = obs.get("tokens_salida_total")
        if isinstance(total, int) and total >= 0:
            if not isinstance(log.totals, _TotalesRemotos):
                log.totals = _TotalesRemotos(total)  # type: ignore[assignment]
                log.totals_samples.clear()
            log.totals.total = total  # type: ignore[union-attr]
            self._muestra(log, now, total)
            del log.totals_samples[:-500]
            log.token_problem = None
        contexto = obs.get("contexto_tokens")
        if isinstance(contexto, int) and contexto >= 0:
            if contexto != log.context_tokens or not log.token_samples:
                log.token_samples.append((now, contexto))
            log.context_tokens = contexto
            log.token_problem = None
        modelo = obs.get("modelo")
        if isinstance(modelo, str) and modelo:
            log.modelo = modelo
            log.context_window = _token_tracker._context_window_for_model(modelo)  # pyright: ignore[reportPrivateUsage]
        texto = obs.get("ultimo_texto_asistente")
        if isinstance(texto, str) and texto:
            stops = [r for r in log.records if r.event_type == EventType.STOP]
            ultimo = stops[-1] if stops else None
            # Only the text of this turn (as the local read: not older than the Stop).
            try:
                ts_texto = datetime.fromisoformat(str(obs.get("ultimo_ts")))
            except ValueError:
                ts_texto = None
            if ts_texto is not None and ts_texto.tzinfo is None:
                ts_texto = ts_texto.replace(tzinfo=UTC)
            if (
                ultimo is not None
                and ultimo.question is None
                and ts_texto is not None
                and ts_texto >= ultimo.ts - timedelta(seconds=30)
            ):
                ultimo.question = asks_question(texto)
                ultimo.question_text = texto[-200:]
                log.invalidate()
        self._snapshot = None
        return True

    def dispositivos_vigentes(self, now: datetime | None = None) -> tuple[bool, bool]:
        """(PC, phone): an /oficina page sent a heartbeat within the presence
        window (75 s) from that device. A browser on the WebSocket (the classic
        view, on the PC) counts as the PC."""
        now = now or self.clock()
        devices = set(self._live_heartbeats(now).values())
        pc = "pc" in devices
        if not pc:
            try:
                pc = int(self.browsers_provider()) > 0
            except Exception:
                pc = False
        return pc, "celular" in devices

    def _live_heartbeats(self, now: datetime) -> dict[str, str]:
        return {
            c: dev
            for c, (ts, dev) in self._heartbeats.items()
            if (now - ts).total_seconds() <= _HEARTBEAT_TTL
        }

    def _open_last_prompt(self, now: datetime) -> datetime | None:
        """Latest UserPromptSubmit among sessions that are not closed."""
        latest: datetime | None = None
        for log in self.sessions.values():
            ts = log.derived.last_prompt_ts
            if ts is None or closure_of(log, now, self.th) is not None:
                continue
            if latest is None or ts > latest:
                latest = ts
        return latest

    def presence(self, now: datetime | None = None) -> Presence:
        now = now or self.clock()
        browsers = self._browsers
        window = self.th.presence_window
        last_prompt = self._open_last_prompt(now)
        prompt_recent = last_prompt is not None and (now - last_prompt).total_seconds() < window
        if browsers > 0:
            reason = f"{browsers} navegador(es) conectado(s) (WebSocket o página /oficina)"
            return Presence(True, reason, browsers, last_prompt, None)
        if prompt_recent:
            mins = (now - last_prompt).total_seconds() / 60  # type: ignore[operator]
            reason = f"Respondiste a un agente (UserPromptSubmit) hace {mins:.1f} min"
            return Presence(True, reason, browsers, last_prompt, None)
        # Last moment we had evidence of the user; before the backend started we
        # cannot know, so the engine start time is the floor.
        evidence = [t for t in (self._last_browser_seen, last_prompt) if t is not None]
        disconnected_since = max([*evidence, self.started_at])
        reason = (
            "Sin navegadores conectados al WebSocket y sin encargos en los últimos "
            f"{window / 60:.0f} min"
        )
        return Presence(False, reason, browsers, last_prompt, disconnected_since)

    # -- tick / snapshot -----------------------------------------------------

    def tick(self) -> dict[str, Any]:
        """Recompute every session at the current time (called every second)."""
        now = self.clock()
        try:
            ws_browsers = int(self.browsers_provider())
        except Exception:
            ws_browsers = 0
        pages = self._live_heartbeats(now)
        browsers = ws_browsers + len(pages)
        self._devices = sorted(set(pages.values())) + (["navegador"] if ws_browsers else [])
        if browsers > 0:
            self._last_browser_seen = now
        self._browsers = browsers
        if (
            self._last_process_check is None
            or (now - self._last_process_check).total_seconds() >= self.th.process_check
        ):
            self._last_process_check = now
            self.check_processes(now)
            self.reconcile(now)
        self.resolve_pending_texts()
        presence = self.presence(now)
        agents: list[dict[str, Any]] = []
        for log in list(self.sessions.values()):
            if not self._visible(log, now):
                continue
            agents.append(self._agent_view(log, presence, now))
        agents.sort(key=lambda a: a["ultimo_evento"]["hora"] or "", reverse=True)
        self._snapshot = {
            "generado": now.isoformat(),
            "presencia": {
                "estado": "conectado" if presence.connected else "desconectado",
                "motivo": presence.reason,
                "navegadores_conectados": presence.browsers,
                "dispositivos": self._devices,
                "ultimo_encargo": presence.last_prompt.isoformat()
                if presence.last_prompt
                else None,
                "desconectado_desde": presence.disconnected_since.isoformat()
                if presence.disconnected_since
                else None,
            },
            "umbrales_segundos": {
                "programa": self.th.program_wait,
                "inactivo": self.th.idle,
                "presencia": self.th.presence_window,
                "descanso_tras_desconexion": self.th.rest_after_disconnect,
                "revision_de_procesos": self.th.process_check,
                "cierre_sin_pid": self.th.no_pid_close,
            },
            "agentes": agents,
        }
        return self._snapshot

    # -- Stage 2.1: specific waits, stuck detector, history, usage ------------

    def _reglas_esperas(self) -> list[_esperas.Regla]:
        return _esperas.cargar_reglas(self.ruta_esperas)

    def _describir(self, rec: Record, now: datetime) -> dict[str, Any]:
        segundos = (now - rec.ts).total_seconds()
        if rec.event_type == EventType.SUBAGENT_START:
            return _esperas.describir(
                "Task", None, rec.descripcion or rec.text, segundos, self._reglas_esperas()
            )
        return _esperas.describir(
            rec.tool_name, rec.command, rec.descripcion, segundos, self._reglas_esperas()
        )

    def _espera_detalle(
        self, dv: _Derived, st: StateResult, now: datetime, subagents: dict[str, Record]
    ) -> dict[str, Any] | None:
        """The current wait or long task in one short sentence with its time."""
        if st.number == 13:
            return _esperas.espera_fija("Esperando tu permiso", (now - st.since).total_seconds())
        if st.number == 14:
            return _esperas.espera_fija("Esperando tu respuesta", (now - st.since).total_seconds())
        current = _latest(dv.pending_tools)
        if current is not None:
            return self._describir(current, now)
        if subagents:
            return self._describir(max(subagents.values(), key=Record.sort_key), now)
        return None

    def _atasco(self, log: SessionLog, st: StateResult, now: datetime) -> dict[str, Any] | None:
        # Only while working: a turn that ended (also by reconciliation with the
        # transcript), an idle or resting agent, or a wait for the user is not stuck.
        if st.number not in _ESTADOS_DE_TRABAJO:
            return None
        dv = log.derived

        def limite(rec: Record) -> tuple[float | None, str]:
            d = self._describir(rec, now)
            limite_min = d["limite_min"]
            return (
                float(limite_min) if isinstance(limite_min, (int, float)) else None,
                str(d["base"]),
            )

        return _atascos.detectar(
            log.records,
            list(dv.pending_tools.values()),
            now,
            st.number in (13, 14),
            limite,
            self.umbrales_atasco,
        )

    def _muestras(self, log: SessionLog) -> list[tuple[datetime, int]]:
        if self.store is not None:
            try:
                guardadas = self.store.muestras_sesion(log.session_id)
                if guardadas:
                    return guardadas
            except Exception:
                logger.exception("Could not read the token samples of %s", log.session_id)
        return sorted(log.totals_samples)

    def historial(
        self, session_id: str, pagina: int = 1, por_pagina: int = 20
    ) -> dict[str, Any] | None:
        """Turns of a session (newest first), from memory or from the event log."""
        now = self.clock()
        log = self.sessions.get(session_id)
        if log is None and self.store is not None:
            temporal = AgentStateEngine(lectura_local=False, clock=self.clock)
            for payload, origin in self.store.eventos_sesion(session_id):
                try:
                    temporal.ingest(EventAdapter.validate_python(payload), origin)
                except ValueError:
                    continue
            log = temporal.sessions.get(session_id)
        if log is None:
            return None
        esperando = False
        if self.sessions.get(session_id) is log and closure_of(log, now, self.th) is None:
            st = self._state_with_memory(log, self.presence(now), now)
            esperando = st.number in (13, 14)
        lista = _historial.turnos(log.records, self._muestras(log), now, esperando)
        return {
            "session_id": session_id,
            "proyecto": log.project,
            "cuenta": account_for_transcript(log.transcript_path),
            "modelo": log.modelo,
            "maquina": log.machine_id,
            **_historial.pagina(lista, pagina, por_pagina),
        }

    def consumo(self, desde: datetime, hasta: datetime) -> dict[str, Any]:
        """Tokens and work time of a day (``desde``-``hasta``), by session, account and model."""
        now = self.clock()
        logs: dict[str, SessionLog] = {}
        if self.store is not None and desde < now - timedelta(hours=self._horas_cargadas()):
            temporal = AgentStateEngine(lectura_local=False, clock=self.clock)
            for payload, origin in self.store.eventos_de_sesiones(desde, hasta):
                try:
                    temporal.ingest(EventAdapter.validate_python(payload), origin)
                except ValueError:
                    continue
            logs = temporal.sessions
        else:
            logs = self.sessions
        muestras: dict[str, list[tuple[datetime, int]]] = {}
        modelos: dict[str, str] = {}
        if self.store is not None:
            try:
                muestras, modelos = self.store.muestras(desde, hasta)
            except Exception:
                logger.exception("Could not read the token samples")
        presence = self.presence(now)
        sesiones: list[dict[str, Any]] = []
        for sid, log in logs.items():
            esperando = False
            if logs is self.sessions and closure_of(log, now, self.th) is None:
                esperando = self._state_with_memory(log, presence, now).number in (13, 14)
            sesiones.append(
                {
                    "session_id": sid,
                    "proyecto": log.project,
                    "cuenta": account_for_transcript(log.transcript_path),
                    "modelo": log.modelo or modelos.get(sid),
                    "maquina": log.machine_id,
                    "records": log.records,
                    "muestras": muestras.get(sid) or sorted(log.totals_samples),
                    "esperando": esperando,
                }
            )
        return _consumo.del_dia(sesiones, desde, hasta, now)

    def _horas_cargadas(self) -> float:
        from app.config import get_settings

        return float(get_settings().STATE_EVENT_LOG_LOAD_HOURS)

    def snapshot(self) -> dict[str, Any]:
        return self.tick()

    def check_processes(self, now: datetime | None = None) -> None:
        """Close open sessions whose registered Claude Code process is gone."""
        now = now or self.clock()
        for log in self.sessions.values():
            dv = log.derived
            if dv.end_ts is not None or log.closed_process_at is not None or dv.process is None:
                continue
            pid, created = dv.process
            if not self.lee_local(log):
                alive = log.proceso_observado  # from its monitor
            else:
                try:
                    alive = self.process_alive(pid, created)
                except Exception:
                    alive = None
            if alive is True:
                log.process_seen_alive = True
            elif alive is False:
                log.closed_process_at = (
                    now if log.process_seen_alive or dv.last_ts is None else min(dv.last_ts, now)
                )
                log.closed_pid = pid

    def _visible(self, log: SessionLog, now: datetime) -> bool:
        """Visible for ``session_max_age`` after its last event or its closure."""
        dv = log.derived
        if dv.last_ts is None:
            return False
        anchor = dv.last_ts
        closure = closure_of(log, now, self.th)
        if closure is not None and closure[1] > anchor:
            anchor = closure[1]
        return (now - anchor).total_seconds() <= self.th.session_max_age

    def state_for(self, session_id: str, now: datetime | None = None) -> StateResult:
        """State of one session including the state-20 memory (for tests)."""
        now = now or self.clock()
        return self._state_with_memory(self.sessions[session_id], self.presence(now), now)

    def _state_with_memory(self, log: SessionLog, presence: Presence, now: datetime) -> StateResult:
        base = compute_state(log, presence, now, self.th)
        if log.prev_state == 21 and base.number not in (21, 12):
            # Closed session reopened: "regresa al trabajo", then its state.
            log.return_since = now
            log.return_until = now + timedelta(seconds=self.th.return_)
            log.prev_state = 20
            return StateResult(20, now)
        if base.number == 19:
            if log.prev_state != 19:
                log.resting_since = base.since
            log.return_until = None
        elif log.prev_state == 19 or (log.return_until and now < log.return_until):
            if log.prev_state == 19:
                last_prompt = log.derived.last_prompt_ts
                user_returned = presence.connected or (
                    last_prompt is not None
                    and log.resting_since is not None
                    and last_prompt >= log.resting_since
                )
                if user_returned:
                    log.return_since = now
                    log.return_until = now + timedelta(seconds=self.th.return_)
            if log.return_until and now < log.return_until and log.return_since:
                log.prev_state = 20
                return StateResult(20, log.return_since)
        log.prev_state = base.number
        return base

    def _agent_view(self, log: SessionLog, presence: Presence, now: datetime) -> dict[str, Any]:
        dv = log.derived
        st = self._state_with_memory(log, presence, now)
        current = _latest(dv.pending_tools)
        current_tool = current.tool_name if current else None
        subagents = active_subagents(dv, now, self.th)
        if current_tool is None and subagents:
            current_tool = "Task/Agent"
        closure = closure_of(log, now, self.th)
        if closure is not None:
            current_tool = None
            subagents = {}
        last = dv.last_record
        # Stage 2.1: the wait or long task in one sentence, the stuck detector
        # and the current stretch of continuous work.
        espera_detalle = None
        atasco = None
        continuo_s = 0
        if closure is None:
            espera_detalle = self._espera_detalle(dv, st, now, subagents)
            atasco = self._atasco(log, st, now)
            continuo_s = _consumo.continuo(
                _historial.turnos(log.records, [], now, st.number in (13, 14)),
                now,
            )
        return {
            "agente": {
                "session_id": log.session_id,
                "proyecto": log.project,
                "cuenta": account_for_transcript(log.transcript_path),
                "maquina": log.machine_id,
                "modelo": log.modelo,
            },
            "espera_detalle": espera_detalle,
            "atasco": atasco,
            "trabajo_continuo_s": continuo_s,
            "estado": {
                "numero": st.number,
                "nombre": STATE_NAMES[st.number],
                "desde": st.since.isoformat(),
            },
            "espera": {"tipo": st.wait, "evidencia": st.evidence} if st.wait else None,
            "herramienta_actual": current_tool,
            "ultimo_evento": {
                "tipo": last.event_type if last else None,
                "hora": last.ts.isoformat() if last else None,
            },
            "subagentes_activos": len(subagents),
            "pregunta_pendiente": pending_question(dv),
            "cierre": {"motivo": closure[0], "desde": closure[1].isoformat()} if closure else None,
            "proceso": {"pid": dv.process[0], "creado": dv.process[1]} if dv.process else None,
            "conciliado": {"en": log.recon.at.isoformat(), "detalle": log.recon.summary()}
            if log.recon
            else None,
            "indicadores": self._indicators(log, now),
            "eventos_recientes": [
                {
                    "hora": r.ts.isoformat(),
                    "tipo": r.event_type,
                    "agente": r.agent_id,
                    "herramienta": r.tool_name,
                    "detalle": _short(r.command or r.text),
                }
                for r in reversed(log.records[-_RECENT_EVENTS:])
            ],
        }

    def _indicators(self, log: SessionLog, now: datetime) -> dict[str, Any]:
        dv = log.derived
        window_start = now - timedelta(seconds=_TOOL_RATE_WINDOW)
        tools_recent = len(dv.tool_times) - bisect.bisect_left(dv.tool_times, window_start)
        minutes = _TOOL_RATE_WINDOW / 60

        tokens_per_min: float | None = None
        tokens_total: int | None = None
        context_tokens: int | None = None
        context_pct: float | None = None
        token_reason = log.token_problem
        totals = log.totals
        if totals is not None and token_reason is None:
            # Accumulated work: output tokens since the session arrived
            # (see TranscriptTotals). Context = latest message.
            if totals.ready:
                tokens_total = totals.total
                samples = log.totals_samples
                base = next((v for ts, v in reversed(samples) if ts <= window_start), None)
                if base is None and samples:
                    base = samples[0][1]
                tokens_per_min = (
                    round((tokens_total - base) / minutes, 1) if base is not None else None
                )
            else:
                token_reason = "Calculando el acumulado de la transcripción"
            context_tokens = log.context_tokens
            if context_tokens is not None and log.context_window:
                context_pct = round(min(1.0, context_tokens / log.context_window) * 100, 1)
        elif log.token_samples and token_reason is None:
            # Producers that send token counts in the event (no transcript):
            # growth of the context size approximates tokens processed.
            samples = log.token_samples
            tokens_total = samples[0][1]
            recent_growth = 0
            prev = samples[0][1]
            for ts, value in samples[1:]:
                delta = value - prev
                if delta > 0:
                    tokens_total += delta
                    if ts >= window_start:
                        recent_growth += delta
                prev = value
            tokens_per_min = round(recent_growth / minutes, 1)
            context_tokens = log.context_tokens
            if context_tokens is not None and log.context_window:
                context_pct = round(min(1.0, context_tokens / log.context_window) * 100, 1)
        elif token_reason is None:
            token_reason = "Ningún evento trajo tokens ni una transcripción legible"

        if dv.saw_error_signal:
            errors: int | None = dv.consecutive_errors
            errors_reason = None
        else:
            errors = None
            errors_reason = (
                "Los eventos de esta sesión vienen de un hook que no envía "
                "PostToolUseFailure (sin reports_tool_failures)"
            )

        return {
            "herramientas_por_minuto": round(tools_recent / minutes, 1),
            "tokens_por_minuto": tokens_per_min,
            "tokens_totales": tokens_total,
            "tokens_contexto": context_tokens,
            "tokens_motivo": token_reason,
            "minutos_con_actividad": dv.active_minutes,
            "contexto_usado_pct": context_pct,
            "errores_seguidos": errors,
            "errores_motivo": errors_reason,
        }


# ---------------------------------------------------------------------------
# App wiring: bootstrap from the DB and the 1 s recompute loop
# ---------------------------------------------------------------------------


async def bootstrap(engine: AgentStateEngine) -> dict[str, int]:
    """Rebuild the engine on start-up from its own event log.

    1. Retention: drop log entries older than STATE_EVENT_LOG_RETENTION_DAYS.
    2. Load the sessions active in the last STATE_EVENT_LOG_LOAD_HOURS.
    """
    from app.config import get_settings
    from app.core.agent_event_store import retention_cutoff
    from app.models.events import EventAdapter

    settings = get_settings()
    now = engine.clock()
    since = now - timedelta(hours=settings.STATE_EVENT_LOG_LOAD_HOURS)
    result = {"borrados": 0, "cargados": 0}
    store = engine.store
    if store is None:
        return result
    result["borrados"] = store.delete_older_than(
        retention_cutoff(now, settings.STATE_EVENT_LOG_RETENTION_DAYS)
    )
    loaded = 0
    for payload, origin in store.iter_recent(since):
        try:
            event = EventAdapter.validate_python(payload)
        except ValueError:
            logger.warning("Agent event log: skipped an unreadable event")
            continue
        engine.ingest(event, origin)
        loaded += 1
    result["cargados"] = loaded
    result["conciliados"] = engine.reconcile()
    return result


async def run_tick_loop(engine: AgentStateEngine, interval: float = 1.0) -> None:
    """Recompute time-based states every ``interval`` seconds until cancelled."""
    import asyncio

    while True:
        try:
            engine.tick()
        except Exception:
            logger.exception("Agent state engine tick failed")
        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
class _TotalesRemotos:
    """Token totals sent by a monitor (same interface as TranscriptTotals for the view)."""

    path = None
    since = None
    ready = True

    def __init__(self, total: int) -> None:
        self.total = total


# Singleton
# ---------------------------------------------------------------------------

_engine: AgentStateEngine | None = None


def get_state_engine() -> AgentStateEngine:
    global _engine
    if _engine is None:
        from app.core.agent_event_store import default_store_path

        store = AgentEventStore(default_store_path())
        store.start()
        from app.config import get_settings

        s = get_settings()
        _engine = AgentStateEngine(
            Thresholds.from_settings(),
            store=store,
            lectura_local=s.LECTURA_LOCAL,
            maquina_local=s.MAQUINA_LOCAL_ID,
        )
        _engine.ruta_esperas = (
            Path(s.ESPERAS_PATH) if s.ESPERAS_PATH else default_store_path().parent / "esperas.txt"
        )
        _esperas.crear_archivo(_engine.ruta_esperas)
        _engine.umbrales_atasco = _atascos.Umbrales(
            errores_repetidos=s.ATASCO_ERRORES_REPETIDOS,
            ventana_errores=s.ATASCO_VENTANA_ERRORES,
            sin_avance_min=s.ATASCO_SIN_AVANCE_MIN,
        )
    return _engine


def override_state_engine(instance: AgentStateEngine | None) -> None:
    global _engine
    _engine = instance


def _default_process_alive(pid: int, created: float | None) -> bool | None:
    from app.core.process_check import process_alive

    return process_alive(pid, created)

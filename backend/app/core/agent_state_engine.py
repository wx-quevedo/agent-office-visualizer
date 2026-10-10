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
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from app.core import token_tracker as _token_tracker
from app.core.transcript_tail import (
    ends_with_question,
    last_assistant_text,
    last_usage,
    resolve_transcript,
)
from app.models.events import AnyEvent, EventType

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
}

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
    subagent_expiry: float = 1800
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
            subagent_expiry=s.STATE_SUBAGENT_EXPIRY_SECONDS,
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
    text = (
        getattr(d, "prompt", None)
        or getattr(d, "error", None)
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
    )


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


def derive(records: Iterable[Record]) -> _Derived:
    """Fold an ordered record log into clock-independent session facts."""
    dv = _Derived()
    native_to_start: dict[str, str] = {}
    minutes: set[int] = set()
    for rec in records:
        et = rec.event_type
        dv.last_record = rec
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
            dv.pending_tools.clear()

        if et == EventType.PERMISSION_REQUEST or _is_permission_notification(rec):
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

    dv.active_minutes = len(minutes)
    return dv


@dataclass
class SessionLog:
    """All engine-side data for one session."""

    session_id: str
    records: list[Record] = field(default_factory=_records)
    project: str | None = None
    transcript_path: str | None = None
    token_samples: list[tuple[datetime, int]] = field(default_factory=_samples)
    token_problem: str | None = None
    context_tokens: int | None = None
    context_window: int = 200_000
    token_file_size: int = -1
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

    @property
    def derived(self) -> _Derived:
        if self._derived is None:
            self._derived = derive(self.records)
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
    """Subagents without SubagentStop that had activity within the expiry window."""
    return {
        aid: rec
        for aid, rec in dv.active_subagents.items()
        if (now - dv.subagent_activity.get(aid, rec.ts)).total_seconds() < th.subagent_expiry
    }


def compute_state(
    log: SessionLog, presence: Presence, now: datetime, th: Thresholds
) -> StateResult:
    """Catalog state for one session at ``now`` (without the state-20 memory)."""
    dv = log.derived
    start = dv.start_ts or dv.first_ts or now
    subagents = active_subagents(dv, now, th)

    if dv.end_ts is not None:
        return StateResult(12, dv.end_ts)

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
        result = _state_from_last_main(dv.last_main, start, now, th)

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
    last: Record | None, start: datetime, now: datetime, th: Thresholds
) -> StateResult:
    if last is None or last.event_type == EventType.SESSION_START:
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
    ) -> None:
        self.th = thresholds or Thresholds()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.browsers_provider = browsers_provider or (lambda: 0)
        self.sessions: dict[str, SessionLog] = {}
        self.started_at = self.clock()
        self._seq = 0
        self._browsers = 0
        self._last_browser_seen: datetime | None = None
        self._last_prompt: datetime | None = None
        self._snapshot: dict[str, Any] | None = None

    # -- ingestion ---------------------------------------------------------

    def ingest(self, event: AnyEvent) -> None:
        """Add one hook event to its session log."""
        self._seq += 1
        rec = record_from_event(event, self._seq)
        log = self.sessions.get(event.session_id)
        if log is None:
            log = self.sessions[event.session_id] = SessionLog(event.session_id)
        d = event.data
        log.project = d.project_dir or d.working_dir or log.project or d.project_name
        if d.transcript_path:
            log.transcript_path = d.transcript_path
        if rec.event_type == EventType.STOP:
            self._detect_question(rec, event, log)
        self._update_tokens(log, event, rec.ts)
        log.add(rec)
        if rec.event_type == EventType.USER_PROMPT_SUBMIT and (
            self._last_prompt is None or rec.ts > self._last_prompt
        ):
            self._last_prompt = rec.ts
        self._snapshot = None

    @staticmethod
    def _detect_question(rec: Record, event: AnyEvent, log: SessionLog) -> None:
        """Stop: does Claude's last message end with '?' (explicit question)?

        Uses the Stop hook's ``last_assistant_message`` when the hook sends it;
        otherwise reads only the tail of the session transcript.
        """
        text = getattr(event.data, "last_assistant_message", None)
        if not text and log.transcript_path:
            path, _ = resolve_transcript(log.transcript_path)
            if path is not None:
                try:
                    text = last_assistant_text(path)
                except OSError:
                    text = None
        rec.question = ends_with_question(text)
        rec.question_text = text[-200:] if text else None

    def _update_tokens(self, log: SessionLog, event: AnyEvent, ts: datetime) -> None:
        """Latest message usage (= context size), from the event or the transcript tail."""
        d = event.data
        total: int | None = None
        if d.input_tokens is not None or d.output_tokens is not None:
            total = (d.input_tokens or 0) + (d.output_tokens or 0)
        elif d.transcript_path:
            path, problem = resolve_transcript(d.transcript_path)
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
            model = usage.get("model")
            if isinstance(model, str):
                log.context_window = _token_tracker._context_window_for_model(model)  # pyright: ignore[reportPrivateUsage]
        if total is None:
            return
        if total != log.context_tokens or not log.token_samples:
            log.token_samples.append((ts, total))
        log.context_tokens = total
        log.token_problem = None

    # -- presence ------------------------------------------------------------

    def presence(self, now: datetime | None = None) -> Presence:
        now = now or self.clock()
        browsers = self._browsers
        window = self.th.presence_window
        last_prompt = self._last_prompt
        prompt_recent = last_prompt is not None and (now - last_prompt).total_seconds() < window
        if browsers > 0:
            reason = f"{browsers} navegador(es) conectado(s) al WebSocket"
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
            browsers = int(self.browsers_provider())
        except Exception:
            browsers = 0
        if browsers > 0:
            self._last_browser_seen = now
        self._browsers = browsers
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
            },
            "agentes": agents,
        }
        return self._snapshot

    def snapshot(self) -> dict[str, Any]:
        return self.tick()

    def _visible(self, log: SessionLog, now: datetime) -> bool:
        dv = log.derived
        if dv.last_ts is None:
            return False
        if (now - dv.last_ts).total_seconds() > self.th.session_max_age:
            return False
        return not (
            dv.end_ts is not None and (now - dv.end_ts).total_seconds() > self.th.exit_visible
        )

    def state_for(self, session_id: str, now: datetime | None = None) -> StateResult:
        """State of one session including the state-20 memory (for tests)."""
        now = now or self.clock()
        return self._state_with_memory(self.sessions[session_id], self.presence(now), now)

    def _state_with_memory(self, log: SessionLog, presence: Presence, now: datetime) -> StateResult:
        base = compute_state(log, presence, now, self.th)
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
        last = dv.last_record
        return {
            "agente": {
                "session_id": log.session_id,
                "proyecto": log.project,
                "cuenta": account_for_transcript(log.transcript_path),
            },
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
        if log.token_samples and token_reason is None:
            # The transcript reports the latest message usage (= context size).
            # Growth of that number approximates tokens processed; drops come
            # from compaction and are ignored.
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


async def bootstrap_from_db(engine: AgentStateEngine) -> int:
    """Load recent persisted events so a backend restart keeps the states.

    Only sessions updated within ``session_max_age`` are loaded. Returns the
    number of events ingested.
    """
    from pydantic import ValidationError
    from sqlalchemy import select

    from app.db.database import AsyncSessionLocal
    from app.db.models import EventRecord, SessionRecord
    from app.models.events import EventAdapter

    cutoff = engine.clock() - timedelta(seconds=engine.th.session_max_age)
    count = 0
    async with AsyncSessionLocal() as db:
        session_ids = (
            (await db.execute(select(SessionRecord.id).where(SessionRecord.updated_at >= cutoff)))
            .scalars()
            .all()
        )
        for sid in session_ids:
            rows = (
                (
                    await db.execute(
                        select(EventRecord)
                        .where(EventRecord.session_id == sid)
                        .order_by(EventRecord.timestamp, EventRecord.id)
                    )
                )
                .scalars()
                .all()
            )
            for rec in rows:
                try:
                    event = EventAdapter.validate_python(
                        {
                            "event_type": EventType(rec.event_type),
                            "session_id": rec.session_id,
                            "timestamp": rec.timestamp,
                            "data": rec.data or {},
                        }
                    )
                except (ValidationError, ValueError):
                    continue
                engine.ingest(event)
                count += 1
    return count


async def run_tick_loop(engine: AgentStateEngine, interval: float = 1.0) -> None:
    """Recompute time-based states every ``interval`` seconds until cancelled."""
    import asyncio

    while True:
        try:
            engine.tick()
        except Exception:
            logger.exception("Agent state engine tick failed")
        await asyncio.sleep(interval)


def count_browser_connections() -> int:
    """Browsers connected to any WebSocket feed (session, room or overview)."""
    from app.core.connection_manager import get_manager

    m = get_manager()
    return (
        sum(len(c) for c in m.active_connections.values())
        + sum(len(c) for c in m.room_connections.values())
        + len(m.overview_connections)
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine: AgentStateEngine | None = None


def get_state_engine() -> AgentStateEngine:
    global _engine
    if _engine is None:
        _engine = AgentStateEngine(
            Thresholds.from_settings(), browsers_provider=count_browser_connections
        )
    return _engine


def override_state_engine(instance: AgentStateEngine | None) -> None:
    global _engine
    _engine = instance

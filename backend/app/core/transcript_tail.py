"""Read only the end of a Claude Code JSONL transcript.

Transcripts can grow to hundreds of MB (a long session reached 428 MB), so
these helpers never load the whole file: they seek to the last
``TAIL_BYTES`` and parse complete lines from there. There is no total-size
limit. Used by the agent state engine for token usage and for the last
assistant message (question detection).
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from app.core.path_utils import is_safe_transcript_path

logger = logging.getLogger(__name__)

TAIL_BYTES = 256_000


def resolve_transcript(path: str) -> tuple[Path | None, str | None]:
    """Return ``(path, None)`` if the transcript can be read, else ``(None, reason)``."""
    from app.config import get_settings  # local import avoids cycles

    translated = get_settings().translate_path(path)
    if not is_safe_transcript_path(translated):
        return None, f"Transcripción fuera de ~/.claude y ~/.claude-demo: {path}"
    p = Path(translated)
    try:
        if not p.exists():
            return None, f"La transcripción no existe: {path}"
    except OSError as exc:
        return None, f"No se pudo leer la transcripción: {exc}"
    return p, None


def _tail_entries(path: Path, tail_bytes: int = TAIL_BYTES) -> list[dict[str, Any]]:
    """Parsed JSON objects of the complete lines in the last ``tail_bytes``."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        start = max(0, size - tail_bytes)
        f.seek(start)
        chunk = f.read()
    lines = chunk.split(b"\n")
    if start > 0:
        lines = lines[1:]  # first line is cut
    entries: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw.startswith(b"{"):
            continue
        try:
            obj = json.loads(raw.decode("utf-8", errors="ignore"))
        except ValueError:
            continue
        if isinstance(obj, dict):
            entries.append(cast(dict[str, Any], obj))
    return entries


def _message(entry: dict[str, Any]) -> dict[str, Any] | None:
    msg = entry.get("message")
    return cast(dict[str, Any], msg) if isinstance(msg, dict) else None


def last_usage(path: Path) -> dict[str, Any] | None:
    """Usage of the most recent message: input (incl. cache), output, model."""
    for entry in reversed(_tail_entries(path)):
        msg = _message(entry)
        if not msg:
            continue
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            continue
        u = cast(dict[str, Any], usage)
        result: dict[str, Any] = {
            "input_tokens": int(u.get("input_tokens", 0) or 0)
            + int(u.get("cache_creation_input_tokens", 0) or 0)
            + int(u.get("cache_read_input_tokens", 0) or 0),
            "output_tokens": int(u.get("output_tokens", 0) or 0),
        }
        model = msg.get("model")
        if isinstance(model, str):
            result["model"] = model
        return result
    return None


def last_assistant_text(path: Path) -> str | None:
    """Text of the most recent assistant message that has text content."""
    for entry in reversed(_tail_entries(path)):
        if entry.get("type") != "assistant":
            continue
        msg = _message(entry)
        if not msg:
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            texts = [
                str(cast(dict[str, Any], block).get("text", ""))
                for block in cast(list[Any], content)
                if isinstance(block, dict) and cast(dict[str, Any], block).get("type") == "text"
            ]
            text = "\n".join(t for t in texts if t.strip())
            if text:
                return text
    return None


_TRAILING = " \t\r\n*_`)\"'»”’"
_URL = re.compile(r"https?://\S+")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)


def ends_with_question(text: str | None) -> bool:
    """True when the message ends in '?' (ignoring trailing spaces/markdown)."""
    if not text:
        return False
    return text.rstrip(_TRAILING).endswith("?")


def asks_question(text: str | None) -> bool:
    """True when Claude's final message asks the user something.

    The question is often followed by the options ("¿Qué hago? Puedo buscarlo,
    crearlo o dejarlo así."), so the whole last paragraph is checked, not only
    its last character. URLs and code are ignored (they can contain "?").
    """
    if not text:
        return False
    cleaned = _FENCED_CODE.sub("", text)
    paragraphs = [p for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not paragraphs:
        return False
    last = _INLINE_CODE.sub("", _URL.sub("", paragraphs[-1]))
    return "?" in last or "¿" in last


# Blocks that Claude Code or extensions inject into the user's prompt; they are
# not what the user typed.
_INJECTED_TAGS = (
    "browser_instruction",
    "system-reminder",
    "ide_selection",
    "ide_opened_file",
    "ide_diagnostics",
    "command-message",
    "command-name",
    "command-args",
    "local-command-stdout",
    "local-command-stderr",
    "local-command-caveat",
    "user-prompt-submit-hook",
)
_TAGS = "|".join(re.escape(t) for t in _INJECTED_TAGS)
_INJECTED_BLOCK = re.compile(r"<(" + _TAGS + r")\b[^>]*>.*?</\1>", re.DOTALL)
_INJECTED_OPEN = re.compile(r"<(" + _TAGS + r")\b")


def clean_prompt(text: str | None) -> str | None:
    """User prompt without injected blocks; None if nothing of the user's is left.

    A block cut by truncation (opening tag without its closing tag) is dropped
    up to the end, since the rest of the text is part of it.
    """
    if not text:
        return None
    cleaned = _INJECTED_BLOCK.sub("", text)
    m = _INJECTED_OPEN.search(cleaned)
    if m:
        cleaned = cleaned[: m.start()]
    cleaned = cleaned.strip()
    return cleaned or None


def _text_blocks(content: object) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [
            str(cast(dict[str, Any], b).get("text", ""))
            for b in cast(list[Any], content)
            if isinstance(b, dict) and cast(dict[str, Any], b).get("type") == "text"
        ]
    return []


def _is_tool_result(content: object) -> bool:
    return isinstance(content, list) and any(
        isinstance(b, dict) and cast(dict[str, Any], b).get("type") == "tool_result"
        for b in cast(list[Any], content)
    )


def last_user_text(path: Path) -> str | None:
    """What the user typed in the most recent prompt (injected blocks removed)."""
    for entry in reversed(_tail_entries(path)):
        if entry.get("type") != "user":
            continue
        msg = _message(entry)
        if not msg or _is_tool_result(msg.get("content")):
            continue
        blocks = [clean_prompt(t) for t in _text_blocks(msg.get("content"))]
        text = "\n".join(b for b in blocks if b)
        if text:
            return text
    return None


def _entry_ts(entry: dict[str, Any]) -> datetime | None:
    raw = entry.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def tail_first_ts(path: Path) -> datetime | None:
    """Time of the oldest user/assistant entry in the tail."""
    for entry in _tail_entries(path):
        if entry.get("type") in ("user", "assistant"):
            ts = _entry_ts(entry)
            if ts is not None:
                return ts
    return None


def user_text_near(path: Path, when: datetime, tolerance_s: float = 10) -> str | None:
    """Text the user typed in the prompt sent around ``when`` (tail only)."""
    best: tuple[float, str] | None = None
    for entry in _tail_entries(path):
        if entry.get("type") != "user":
            continue
        msg = _message(entry)
        ts = _entry_ts(entry)
        if not msg or ts is None or _is_tool_result(msg.get("content")):
            continue
        diff = abs((ts - when).total_seconds())
        if diff > tolerance_s:
            continue
        blocks = [clean_prompt(t) for t in _text_blocks(msg.get("content"))]
        text = "\n".join(b for b in blocks if b)
        if text and (best is None or diff < best[0]):
            best = (diff, text)
    return best[1] if best else None


def turn_progress(
    path: Path,
) -> tuple[set[str], tuple[datetime, str] | None, datetime | None]:
    """What the transcript tail says about the current turn.

    Returns ``(finished_tool_ids, turn_end, last_ts)``: ids of tool calls that
    already have their tool_result; ``(time, text)`` of the final assistant
    message if the turn ended (the last user/assistant entry is an ``end_turn``
    assistant message); and the time of the last user/assistant entry.
    """
    entries = _tail_entries(path)
    finished: set[str] = set()
    last: dict[str, Any] | None = None
    for entry in entries:
        if entry.get("type") not in ("user", "assistant"):
            continue
        content = (_message(entry) or {}).get("content")
        if isinstance(content, list):
            for b in cast(list[Any], content):
                if isinstance(b, dict) and cast(dict[str, Any], b).get("type") == "tool_result":
                    tid = cast(dict[str, Any], b).get("tool_use_id")
                    if isinstance(tid, str):
                        finished.add(tid)
        last = entry
    if last is None:
        return finished, None, None
    last_ts = _entry_ts(last)
    msg = _message(last) or {}
    if last.get("type") == "assistant" and msg.get("stop_reason") == "end_turn" and last_ts:
        # The final message can span several lines (thinking, text) with one id.
        mid = msg.get("id")
        parts: list[str] = []
        for e in entries:
            m = _message(e) or {}
            if e.get("type") == "assistant" and m.get("id") == mid:
                parts.extend(t for t in _text_blocks(m.get("content")) if t.strip())
        return finished, (last_ts, "\n".join(parts)), last_ts
    return finished, None, last_ts


class TranscriptTotals:
    """Running token totals of a transcript, read incrementally.

    Sums, once per message id (Claude Code repeats the usage on every line of
    a message), the output tokens and the new input tokens (input + cache
    creation, without cache reads, which re-send the same context each turn).
    The first call reads the whole file; later calls only the appended bytes.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.seen: set[str] = set()
        self.output = 0
        self.new_input = 0
        self.ready = False
        self._lock = threading.Lock()

    @property
    def total(self) -> int:
        return self.output + self.new_input

    def scan(self) -> int:
        """Read new complete lines; returns the current total."""
        with self._lock:
            try:
                size = self.path.stat().st_size
            except OSError:
                return self.total
            if size < self.offset:  # file replaced: start over
                self.offset, self.output, self.new_input = 0, 0, 0
                self.seen.clear()
            if size > self.offset:
                with open(self.path, "rb") as f:
                    f.seek(self.offset)
                    chunk = f.read(size - self.offset)
                end = chunk.rfind(b"\n")
                if end >= 0:
                    self.offset += end + 1
                    self._consume(chunk[: end + 1])
            self.ready = True
            return self.total

    def _consume(self, data: bytes) -> None:
        for raw in data.split(b"\n"):
            if b'"usage"' not in raw:
                continue
            try:
                obj = json.loads(raw.decode("utf-8", errors="ignore"))
            except ValueError:
                continue
            msg: object = (
                cast(dict[str, Any], obj).get("message") if isinstance(obj, dict) else None
            )
            if not isinstance(msg, dict):
                continue
            m = cast(dict[str, Any], msg)
            usage = m.get("usage")
            mid = m.get("id")
            if not isinstance(usage, dict) or not isinstance(mid, str) or mid in self.seen:
                continue
            self.seen.add(mid)
            u = cast(dict[str, Any], usage)
            self.output += int(u.get("output_tokens", 0) or 0)
            self.new_input += int(u.get("input_tokens", 0) or 0) + int(
                u.get("cache_creation_input_tokens", 0) or 0
            )

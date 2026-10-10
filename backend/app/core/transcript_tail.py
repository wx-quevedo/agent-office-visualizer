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


def ends_with_question(text: str | None) -> bool:
    """True when the message ends in '?' (ignoring trailing spaces/markdown)."""
    if not text:
        return False
    return text.rstrip(_TRAILING).endswith("?")

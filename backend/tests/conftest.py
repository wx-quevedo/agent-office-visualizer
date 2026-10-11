"""Pytest fixtures for backend tests."""

import os
import tempfile

# The agent state engine writes its own event log; keep tests away from the
# real backend/agent_events.db.
os.environ["STATE_EVENT_LOG_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="agent-events-"), "agent_events.db"
)

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import get_settings

get_settings.cache_clear()
_ = get_settings()


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:  # pyright: ignore[reportUnusedFunction]
    """Reset the event ingestion rate limiter before each test."""
    from app.api.routes.events import reset_rate_limiter

    reset_rate_limiter()


@pytest.fixture(autouse=True)
def _allow_test_transcript_paths() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Allow transcript reads from temp directories in tests.

    Production code validates that transcript paths are under ~/.claude/,
    but tests use temp directories. Patch is_safe_transcript_path to always
    return True so existing tests don't need to change.
    """
    from contextlib import ExitStack

    with ExitStack() as stack:
        for target in ("app.core.path_utils.is_safe_transcript_path",):
            stack.enter_context(patch(target, return_value=True))
        yield


@pytest.fixture
def sample_jsonl_content() -> str:
    """Sample JSONL content for testing transcript parsing."""
    lines = [
        '{"type": "user", "message": {"role": "user", "content": "Hello"}}',
        '{"type": "assistant", "message": {"role": "assistant", '
        '"content": [{"type": "text", "text": "First response"}]}}',
        '{"type": "user", "message": {"role": "user", "content": "Another message"}}',
        '{"type": "assistant", "message": {"role": "assistant", '
        '"content": [{"type": "text", "text": "Second response"}]}}',
        '{"type": "assistant", "message": {"role": "assistant", '
        '"content": [{"type": "tool_use", "name": "Read"}]}}',
        '{"type": "assistant", "message": {"role": "assistant", '
        '"content": [{"type": "text", "text": "Final response with text"}]}}',
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture
def sample_jsonl_file(temp_dir: Path, sample_jsonl_content: str) -> Path:
    """Create a sample JSONL file for testing."""
    jsonl_path = temp_dir / "test_transcript.jsonl"
    jsonl_path.write_text(sample_jsonl_content, encoding="utf-8")
    return jsonl_path

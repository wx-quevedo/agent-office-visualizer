"""Tests for finding the Claude Code process that owns a hook call."""

import os

import pytest

from claude_office_hooks import process_info
from claude_office_hooks.process_info import CLAUDE_PROCESS_NAMES, find_claude_process


def test_returns_none_outside_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_info.os, "name", "posix")
    assert find_claude_process() is None


def test_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise OSError("no access")

    monkeypatch.setattr(process_info, "_find_windows", boom)
    monkeypatch.setattr(process_info.os, "name", "nt")
    assert find_claude_process() is None


@pytest.mark.skipif(os.name != "nt", reason="Windows process API")
def test_result_shape_on_windows() -> None:
    # Run from Claude Code it finds claude.exe/node.exe; from a plain terminal
    # there is no Claude Code ancestor and it returns None. Both are valid.
    result = find_claude_process()
    if result is not None:
        pid, created, name = result
        assert pid > 0
        assert created > 1_600_000_000
        assert name.lower() in CLAUDE_PROCESS_NAMES

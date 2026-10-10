"""Real process checks used to close sessions whose Claude Code process ended."""

import os
import subprocess
import sys

import pytest

from app.core.process_check import process_alive


def test_current_process_is_alive() -> None:
    assert process_alive(os.getpid(), None) is True


def test_finished_process_is_not_alive() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    pid = proc.pid
    del proc  # release our handle so the process object can go away
    assert process_alive(pid, None) is False


@pytest.mark.skipif(os.name != "nt", reason="creation time check uses the Windows API")
def test_same_pid_with_other_creation_time_is_not_alive() -> None:
    assert process_alive(os.getpid(), 1.0) is False


def test_invalid_pid_is_unknown() -> None:
    assert process_alive(0, None) is None

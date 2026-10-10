"""Is a Claude Code process (PID + creation time) still running?

The hook sends the PID of the Claude Code process that owns a session and its
creation time. Windows reuses PIDs, so a live process with the same PID but a
different creation time is a different process: the original one ended.
"""

from __future__ import annotations

import os

_CREATION_TOLERANCE_S = 1.0
_STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87
_FILETIME_UNIX_EPOCH = 116444736000000000


def process_alive(pid: int, created: float | None) -> bool | None:
    """True if running, False if gone (or PID reused), None if it cannot be told."""
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            return _alive_windows(pid, created)
        except Exception:
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _alive_windows(pid: int, created: float | None) -> bool | None:
    import ctypes
    from ctypes import wintypes as wt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wt.HANDLE
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        # No such process; any other error (e.g. access denied) is unknown.
        return False if ctypes.get_last_error() == _ERROR_INVALID_PARAMETER else None
    try:
        code = wt.DWORD()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != _STILL_ACTIVE:
            return False
        if created is None:
            return True
        c, e, k, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        if not kernel32.GetProcessTimes(
            handle, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)
        ):
            return None
        ticks = (c.dwHighDateTime << 32) | c.dwLowDateTime
        actual = (ticks - _FILETIME_UNIX_EPOCH) / 1e7
        return abs(actual - created) <= _CREATION_TOLERANCE_S
    finally:
        kernel32.CloseHandle(handle)

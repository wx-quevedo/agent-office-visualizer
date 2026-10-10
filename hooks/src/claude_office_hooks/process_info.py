"""Find the Claude Code process that owns the current hook invocation.

Claude Code runs hook commands through a shell, so the hook's ancestors look
like: python.exe -> claude-office-hook.exe (uv launcher) -> bash/cmd/powershell
(one or more) -> claude.exe (native install) or node.exe (npm install). This
module walks up that chain with the Windows API (no extra dependency, ~0.5 ms
plus ~12 ms to import ctypes) and returns the first Claude Code process with
its creation time, so a reused PID is not mistaken for the same process.

IMPORTANT: must not produce stdout/stderr output and must never raise.
"""

from __future__ import annotations

import os

# Executable names that identify Claude Code. node.exe covers the npm install
# (``node .../@anthropic-ai/claude-code/cli.js``); hooks are only ever run by
# Claude Code, so the first node.exe above the shells is Claude Code.
CLAUDE_PROCESS_NAMES = frozenset({"claude.exe", "claude", "node.exe", "node"})
# Stop walking at these: past them we are outside Claude Code's process tree.
STOP_NAMES = frozenset(
    {"code.exe", "explorer.exe", "windowsterminal.exe", "services.exe", "wininit.exe"}
)
_MAX_DEPTH = 15
_FILETIME_UNIX_EPOCH = 116444736000000000


def find_claude_process() -> tuple[int, float, str] | None:
    """Return ``(pid, creation_time_unix, exe_name)`` of Claude Code, or None."""
    if os.name != "nt":
        return None
    try:
        return _find_windows()
    except Exception:
        return None


def _find_windows() -> tuple[int, float, str] | None:
    import ctypes
    from ctypes import wintypes as wt

    process_query_limited_information = 0x1000

    class _ProcessBasicInformation(ctypes.Structure):
        _fields_ = [
            ("ExitStatus", ctypes.c_void_p),
            ("PebBaseAddress", ctypes.c_void_p),
            ("AffinityMask", ctypes.c_void_p),
            ("BasePriority", ctypes.c_void_p),
            ("UniqueProcessId", ctypes.c_void_p),
            ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    kernel32.OpenProcess.restype = wt.HANDLE

    def info(pid: int) -> tuple[int, str, float | None] | None:
        """(parent pid, exe name, creation time) of *pid*, or None."""
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return None
        try:
            pbi = _ProcessBasicInformation()
            status = ntdll.NtQueryInformationProcess(
                handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None
            )
            if status != 0:
                return None
            buf = ctypes.create_unicode_buffer(1024)
            size = wt.DWORD(1024)
            name = ""
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = buf.value.rsplit("\\", 1)[-1]
            created = wt.FILETIME()
            exited, kernel, user = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
            ctime: float | None = None
            if kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
                ctime = (ticks - _FILETIME_UNIX_EPOCH) / 1e7
            return int(pbi.InheritedFromUniqueProcessId or 0), name, ctime
        finally:
            kernel32.CloseHandle(handle)

    pid = os.getpid()
    current = info(pid)
    depth = 0
    while current is not None and depth < _MAX_DEPTH:
        parent_pid, _name, ctime = current
        parent = info(parent_pid) if parent_pid else None
        if parent is None:
            return None
        _, parent_name, parent_ctime = parent
        # A parent created after its child means the real parent exited and
        # Windows reused its PID: the chain is broken.
        if parent_ctime is None or (ctime is not None and parent_ctime > ctime):
            return None
        lowered = parent_name.lower()
        if lowered in CLAUDE_PROCESS_NAMES:
            return parent_pid, parent_ctime, parent_name
        if lowered in STOP_NAMES:
            return None
        current = parent
        depth += 1
    return None

"""¿Sigue vivo el proceso de Claude Code de una sesión (PID + hora de creación)?

Copia de ``backend/app/core/process_check.py``: Windows reutiliza los PID, así
que un proceso vivo con el mismo PID pero otra hora de creación es otro.
"""

from __future__ import annotations

import os

_TOLERANCIA_S = 1.0
_STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87
_FILETIME_UNIX_EPOCH = 116444736000000000


def proceso_vivo(pid: int, creado: float | None) -> bool | None:
    """True vivo, False terminó (o PID reutilizado), None si no se puede saber."""
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            return _vivo_windows(pid, creado)
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


def _vivo_windows(pid: int, creado: float | None) -> bool | None:
    import ctypes
    from ctypes import wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        err = ctypes.get_last_error()  # type: ignore[attr-defined]
        return False if err == _ERROR_INVALID_PARAMETER else None
    try:
        codigo = wt.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
            return None
        if codigo.value != _STILL_ACTIVE:
            return False
        if creado is None:
            return True
        c, e, k, u = (wt.FILETIME() for _ in range(4))
        if not k32.GetProcessTimes(
            handle, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)
        ):
            return True
        ft = (c.dwHighDateTime << 32) | c.dwLowDateTime
        inicio = (ft - _FILETIME_UNIX_EPOCH) / 10_000_000
        return abs(inicio - creado) <= _TOLERANCIA_S
    finally:
        k32.CloseHandle(handle)

"""Windows taskbar progress via the native ITaskbarList3 COM interface.

Qt 6 removed QtWinExtras, so the taskbar button progress is driven directly
through COM with ctypes (no extra dependency). Everything degrades to a no-op
off Windows or if COM initialisation fails.
"""
from __future__ import annotations

import contextlib
import ctypes
import sys

# TBPFLAG progress states.
TBPF_NOPROGRESS = 0
TBPF_INDETERMINATE = 0x1
TBPF_NORMAL = 0x2
TBPF_ERROR = 0x4


def average_progress(percents: list[float]) -> int:
    """Average of the given percentages, clamped to 0..100 (pure helper)."""
    if not percents:
        return 0
    value = sum(percents) / len(percents)
    return int(max(0, min(100, value)))


if sys.platform == "win32":
    from ctypes import wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    def _guid(text: str) -> _GUID:
        guid = _GUID()
        ctypes.oledll.ole32.CLSIDFromString(text, ctypes.byref(guid))
        return guid


class TaskbarProgress:
    """Drives the progress overlay on the window's taskbar button."""

    def __init__(self, hwnd: int) -> None:
        self.available = False
        self._taskbar = None
        self._set_value = None
        self._set_state = None
        if sys.platform != "win32":
            return
        try:
            self._hwnd = wintypes.HWND(hwnd)
            self._init_com()
            self.available = True
        except Exception:
            self.available = False

    def _init_com(self) -> None:
        ole32 = ctypes.oledll.ole32
        with contextlib.suppress(OSError):
            ole32.CoInitialize(None)  # already initialised in another mode is fine
        clsid = _guid("{56FDF344-FD6D-11d0-958A-006097C9A090}")  # CLSID_TaskbarList
        iid = _guid("{ea1afb91-9e28-4b86-90e9-9e9f8a5eefaf}")  # IID_ITaskbarList3
        ptr = ctypes.c_void_p()
        ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(ptr))
        self._taskbar = ptr
        vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))
        methods = ctypes.cast(ctypes.c_void_p(vtable[0]), ctypes.POINTER(ctypes.c_void_p))
        hr_init = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(methods[3])
        hr_init(ptr)
        self._set_value = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, wintypes.HWND, ctypes.c_ulonglong, ctypes.c_ulonglong
        )(methods[9])
        self._set_state = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, wintypes.HWND, ctypes.c_int
        )(methods[10])

    def set_progress(self, percent: float) -> None:
        if not self.available:
            return
        try:
            self._set_state(self._taskbar, self._hwnd, TBPF_NORMAL)
            self._set_value(self._taskbar, self._hwnd, int(max(0, min(100, percent))), 100)
        except Exception:
            pass

    def set_indeterminate(self) -> None:
        if not self.available:
            return
        with contextlib.suppress(Exception):
            self._set_state(self._taskbar, self._hwnd, TBPF_INDETERMINATE)

    def clear(self) -> None:
        if not self.available:
            return
        with contextlib.suppress(Exception):
            self._set_state(self._taskbar, self._hwnd, TBPF_NOPROGRESS)

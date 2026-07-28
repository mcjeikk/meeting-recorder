"""Watcher de hotplug de dispositivos en Windows (WM_DEVICECHANGE).

Dispara un callback cuando el SO notifica llegada/salida/cambio de nodos de
dispositivo. La UI debe debouncear y decidir si hace refresh profundo de
micrófonos (solo idle — Recording Always Wins).

En no-Windows es un no-op seguro.
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtCore import QAbstractNativeEventFilter

# Win32
_WM_DEVICECHANGE = 0x0219
_DBT_DEVICEARRIVAL = 0x8000
_DBT_DEVICEREMOVECOMPLETE = 0x8004
_DBT_DEVNODES_CHANGED = 0x0007

RELEVANT_DBT_EVENTS = frozenset(
    {
        _DBT_DEVICEARRIVAL,
        _DBT_DEVICEREMOVECOMPLETE,
        _DBT_DEVNODES_CHANGED,
    }
)


def is_relevant_device_change(wparam: int) -> bool:
    """True si el wParam de WM_DEVICECHANGE justifica un refresh de capturas."""
    return int(wparam) in RELEVANT_DBT_EVENTS


class DeviceChangeWatcher(QAbstractNativeEventFilter):
    """Filtro nativo: WM_DEVICECHANGE relevante → ``on_change()``."""

    def __init__(self, on_change: Callable[[], None]):
        super().__init__()
        self._on_change = on_change
        self._msg_struct = None
        if sys.platform == "win32":
            from ctypes import wintypes
            import ctypes

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD),
                    ("pt_x", wintypes.LONG),
                    ("pt_y", wintypes.LONG),
                ]

            self._msg_struct = MSG

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if self._msg_struct is None or event_type != b"windows_generic_MSG":
            return False, 0
        try:
            msg = self._msg_struct.from_address(int(message))
            if msg.message == _WM_DEVICECHANGE and is_relevant_device_change(
                int(msg.wParam)
            ):
                self._on_change()
        except Exception:
            pass
        return False, 0


def hotplug_action(*, recording: bool) -> str:
    """Política idle vs grabación: ``deep`` | ``defer``.

    ``deep`` = reiniciar lista PortAudio vía refresh auto.
    ``defer`` = marcar pendiente; no tocar streams de captura.
    """
    return "defer" if recording else "deep"

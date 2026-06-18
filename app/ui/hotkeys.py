"""Atajos de teclado GLOBALES en Windows (funcionan aunque la app no tenga foco).

Usa RegisterHotKey de Win32 y un filtro de eventos nativos de Qt para capturar
los mensajes WM_HOTKEY. En otros sistemas operativos es un no-op (Fase 1).

Atajos por defecto:
- Ctrl+Shift+R : iniciar / detener
- Ctrl+Shift+P : pausar / reanudar
- Ctrl+Shift+M : silenciar / activar micrófono
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtCore import QAbstractNativeEventFilter

# Constantes Win32
_WM_HOTKEY = 0x0312
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_NOREPEAT = 0x4000
_VK_R = 0x52
_VK_P = 0x50
_VK_M = 0x4D

_ID_TOGGLE = 1
_ID_PAUSE = 2
_ID_MUTE = 3


class GlobalHotkeys(QAbstractNativeEventFilter):
    """Registra atajos globales y dispara callbacks al activarse."""

    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_pause: Callable[[], None],
        on_mute: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._on_toggle = on_toggle
        self._on_pause = on_pause
        self._on_mute = on_mute or (lambda: None)
        self._hwnd: Optional[int] = None
        self._registered = False
        self._msg_struct = None
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

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

    def register(self, hwnd: int) -> None:
        """Registra los atajos contra la ventana dada (su HWND)."""
        if sys.platform != "win32" or self._registered:
            return
        import ctypes

        self._hwnd = int(hwnd)
        mods = _MOD_CONTROL | _MOD_SHIFT | _MOD_NOREPEAT
        try:
            user32 = ctypes.windll.user32
            user32.RegisterHotKey(self._hwnd, _ID_TOGGLE, mods, _VK_R)
            user32.RegisterHotKey(self._hwnd, _ID_PAUSE, mods, _VK_P)
            user32.RegisterHotKey(self._hwnd, _ID_MUTE, mods, _VK_M)
            self._registered = True
        except Exception:
            self._registered = False

    def unregister(self) -> None:
        if sys.platform != "win32" or not self._registered or self._hwnd is None:
            return
        import ctypes

        try:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(self._hwnd, _ID_TOGGLE)
            user32.UnregisterHotKey(self._hwnd, _ID_PAUSE)
            user32.UnregisterHotKey(self._hwnd, _ID_MUTE)
        except Exception:
            pass
        self._registered = False

    def nativeEventFilter(self, event_type, message):  # noqa: N802 (firma de Qt)
        if self._msg_struct is not None and event_type == b"windows_generic_MSG":
            try:
                msg = self._msg_struct.from_address(int(message))
                if msg.message == _WM_HOTKEY:
                    if msg.wParam == _ID_TOGGLE:
                        self._on_toggle()
                    elif msg.wParam == _ID_PAUSE:
                        self._on_pause()
                    elif msg.wParam == _ID_MUTE:
                        self._on_mute()
            except Exception:
                pass
        return False, 0

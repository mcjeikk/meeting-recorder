"""Si esta ventana aparece o no en grabaciones y capturas de pantalla.

Windows: SetWindowDisplayAffinity. WDA_EXCLUDEFROMCAPTURE (0x11) hace que el
Grabador no salga en WGC/gdigrab ni en Win+Shift+S. WDA_NONE (0) lo deja visible.
"""
from __future__ import annotations

import sys
from typing import Optional

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011


def affinity_flag(exclude_from_capture: bool) -> int:
    return WDA_EXCLUDEFROMCAPTURE if exclude_from_capture else WDA_NONE


def _apply_macos(view_ptr: Optional[int], exclude_from_capture: bool) -> bool:
    """macOS: lo que ScreenCaptureKit respeta es excluir la app del filtro; además
    `sharingType = none` para otros grabadores. `winId()` de Qt es un NSView*."""
    from app.capture.sources import set_exclude_own_window

    set_exclude_own_window(exclude_from_capture)
    if not view_ptr:
        return True
    try:
        from PySide6.QtGui import QGuiApplication

        # Solo con la plataforma "cocoa" el winId es un NSView*: con "offscreen"
        # (tests, CI) desreferenciarlo tumba el proceso.
        if QGuiApplication.platformName() != "cocoa":
            return True
    except Exception:
        return True
    try:
        import objc

        vista = objc.objc_object(c_void_p=int(view_ptr))
        ventana = vista.window()
        if ventana is not None:
            ventana.setSharingType_(0 if exclude_from_capture else 1)  # None / ReadOnly
    except Exception:
        pass
    return True


def apply_window_capture_affinity(hwnd: Optional[int], exclude_from_capture: bool) -> bool:
    if sys.platform == "darwin":
        return _apply_macos(hwnd, exclude_from_capture)
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes

        ok = ctypes.windll.user32.SetWindowDisplayAffinity(
            int(hwnd), affinity_flag(exclude_from_capture)
        )
        return bool(ok)
    except Exception:
        return False

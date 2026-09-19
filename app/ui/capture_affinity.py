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


def apply_window_capture_affinity(hwnd: Optional[int], exclude_from_capture: bool) -> bool:
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

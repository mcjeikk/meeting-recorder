"""Qué se puede grabar y con qué backend, según el sistema operativo (spec 030).

La ventana y el orquestador piden aquí las fuentes, la vista previa y las
capturas; cada sistema implementa lo suyo (Windows: WGC + WASAPI; macOS:
ScreenCaptureKit). Lo que un sistema no tiene devuelve vacío en vez de fallar.
"""
from __future__ import annotations

import sys
from typing import List, Optional

import numpy as np

from app.capture.base import VideoCapture
from app.core.config import VideoSource


def _mac() -> bool:
    return sys.platform == "darwin"


def list_monitors() -> List[VideoSource]:
    if sys.platform == "win32":
        from app.capture.windows_video import list_monitors as win

        return win()
    if _mac():
        from app.capture.mac_sck import list_monitors as mac

        return mac()
    return [VideoSource(kind="screen", title="Pantalla 1", monitor_index=1, is_primary=True)]


def list_windows() -> List[VideoSource]:
    if sys.platform == "win32":
        from app.capture.windows_video import list_windows as win

        return win()
    if _mac():
        from app.capture.mac_sck import list_windows as mac

        return mac()
    return []


def grab_window_frame(window_id: int) -> Optional[np.ndarray]:
    if sys.platform == "win32":
        from app.capture.windows_video import grab_window_frame as win

        return win(window_id)
    if _mac():
        from app.capture.mac_sck import grab_window_frame as mac

        return mac(window_id)
    return None


def grab_monitor_frame(monitor_index: int = 1) -> Optional[np.ndarray]:
    if sys.platform == "win32":
        from app.capture.windows_video import grab_monitor_frame as win

        return win(monitor_index)
    if _mac():
        from app.capture.mac_sck import grab_monitor_frame as mac

        return mac(monitor_index)
    return None


def make_video_capture(source: VideoSource, fps: int) -> VideoCapture:
    if sys.platform == "win32":
        # Ventana -> Windows.Graphics.Capture (capta contenido GPU, p. ej. Teams).
        if source.kind == "window" and source.hwnd:
            from app.capture.windows_video import WindowsGraphicsCapture

            return WindowsGraphicsCapture(source, fps=fps)
        # Pantalla completa -> WGC del monitor (GPU; gdigrab por CPU no alcanza
        # los 30 fps en monitores grandes), con respaldo automático a gdigrab.
        from app.capture.windows_video import WindowsScreenCapture

        return WindowsScreenCapture(source, fps=fps)
    if _mac():
        from app.capture.mac_sck import SCKVideoCapture

        return SCKVideoCapture(source, fps=fps)
    raise NotImplementedError("La captura de video aún no existe en este sistema (Linux: roadmap).")


def make_system_audio_capture():
    if sys.platform == "win32":
        from app.capture.windows_audio import SystemAudioCapture

        return SystemAudioCapture()
    if _mac():
        from app.capture.mac_sck import SCKSystemAudioCapture

        return SCKSystemAudioCapture()
    raise NotImplementedError("El audio del sistema aún no se captura en este sistema.")


def describe_system_audio_route() -> dict:
    """Aviso sobre la salida de audio actual. Solo Windows tiene algo que advertir
    (Bluetooth deja el loopback WASAPI en silencio); en macOS se oculta."""
    if sys.platform == "win32":
        from app.capture.windows_audio import describe_system_audio_route as win

        return win()
    return {"ok": False, "output_name": "", "loopback_name": "", "bluetooth": False, "warning": ""}


def set_exclude_own_window(value: bool) -> None:
    """macOS: excluir la propia app del filtro de captura (Windows lo hace por ventana)."""
    if _mac():
        from app.capture.mac_sck import set_exclude_own_app

        set_exclude_own_app(value)

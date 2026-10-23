"""Micrófonos conectados/desconectados en macOS (spec 030).

Windows avisa con WM_DEVICECHANGE. En macOS se consulta cada pocos segundos la
lista de entradas de audio de AVFoundation: no reinicia PortAudio (eso cortaría
un stream abierto), solo mira nombres. Si el conjunto cambia, la ventana decide
con la misma política de siempre (`hotplug_action`).
"""
from __future__ import annotations

from typing import FrozenSet


def audio_input_names() -> FrozenSet[str]:
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio

        dispositivos = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeAudio) or []
        return frozenset(str(d.localizedName()) for d in dispositivos)
    except Exception:
        return frozenset()


def changed(previous: FrozenSet[str], current: FrozenSet[str]) -> bool:
    """Hubo hotplug si cambió el conjunto (y la consulta devolvió algo)."""
    return bool(current) and current != previous

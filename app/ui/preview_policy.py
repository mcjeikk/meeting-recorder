"""Cuándo pausar la vista previa WGC (idle).

WER 2026-09-08: pythonw.exe APPCRASH en igd10um64xe.DLL (driver Intel) al abrir
sesiones WGC cortas de preview mientras Transcriptor aprieta CPU/GPU.
"""
from __future__ import annotations

_TX_OPEN = frozenset({"pending", "extracting", "running"})


def transcription_status_is_open(status: object) -> bool:
    return str(status or "").strip().lower() in _TX_OPEN


def should_pause_idle_wgc_preview(
    *,
    recording: bool,
    transcription_open: bool,
    periodic: bool = False,
) -> bool:
    """Pausa grabs WGC idle; la preview de una grabación en curso no usa este path.

    `periodic=True` es el timer de ~1.5 s: cada tick abre una sesión WGC/D3D
    nueva. En Intel (`igd10um64xe.DLL`) eso tumba pythonw incluso *después*
    de que el job ya terminó (WER 2026-09-11 00:21). Solo se permite un
    grab puntual (cambio de fuente / Actualizar), no el bucle.
    """
    if recording:
        return False
    return bool(transcription_open) or bool(periodic)

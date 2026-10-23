"""Pista de audio del sistema continua a partir de buffers con marca de tiempo.

ScreenCaptureKit puede no entregar nada mientras no suena nada (el mismo mal
que en Windows pedía un keep-alive). Cada buffer trae su instante en el reloj
del sistema, así que se escribe silencio por cada hueco: antes del primero,
entre buffers y hasta que se detiene. El WAV dura exactamente lo grabado y la
pista queda alineada con el video y el micrófono, que arrancan a la vez.

Puro y sin dependencias de macOS: se prueba en cualquier sistema.
"""
from __future__ import annotations

import numpy as np

# Por debajo de esto un "hueco" es solo jitter de entrega: no se rellena.
GAP_TOLERANCE_S = 0.02


class GapFiller:
    """Cuenta los frames escritos y dice cuánto silencio falta antes de cada buffer."""

    def __init__(self, sample_rate: int, start_time: float):
        self.rate = int(sample_rate)
        self.start = float(start_time)
        self.frames_written = 0

    def _written_until(self) -> float:
        return self.start + self.frames_written / self.rate

    def silence_before(self, pts: float, n_frames: int) -> int:
        """Frames de silencio a escribir antes de un buffer que empieza en `pts`.

        Registra también los `n_frames` del buffer: llamar una vez por buffer.
        """
        hueco = float(pts) - self._written_until()
        relleno = int(round(hueco * self.rate)) if hueco > GAP_TOLERANCE_S else 0
        self.frames_written += relleno + int(n_frames)
        return relleno

    def silence_until(self, stop_time: float) -> int:
        """Frames de silencio para que la pista llegue hasta `stop_time`."""
        hueco = float(stop_time) - self._written_until()
        relleno = int(round(hueco * self.rate)) if hueco > GAP_TOLERANCE_S else 0
        self.frames_written += relleno
        return relleno


def float_to_int16(
    raw: bytes, channels: int, frames: int, non_interleaved: bool
) -> np.ndarray:
    """Muestras float32 (planar o intercaladas) → int16 intercalado (frames, channels).

    En planar los canales van uno detrás de otro: [L0..Ln, R0..Rn].
    """
    datos = np.frombuffer(raw, dtype=np.float32)
    esperado = frames * channels
    if datos.size < esperado:
        frames = datos.size // max(1, channels)
        esperado = frames * channels
    datos = datos[:esperado]
    if non_interleaved:
        datos = datos.reshape(channels, frames).T
    else:
        datos = datos.reshape(frames, channels)
    return (np.clip(datos, -1.0, 1.0) * 32767.0).astype(np.int16)


def silence(frames: int, channels: int) -> bytes:
    return bytes(max(0, int(frames)) * int(channels) * 2)

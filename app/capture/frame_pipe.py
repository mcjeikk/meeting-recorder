"""Fotogramas BGRA → ffmpeg a tasa constante (macOS, spec 030).

Es el mismo patrón que la captura WGC de Windows: el backend deja el último
fotograma y un hilo lo escribe a ffmpeg cada 1/fps, repitiéndolo si la
pantalla no cambió. La tasa constante es la que mantiene el video alineado con
el audio. Windows conserva su propia copia en `windows_video.py`, intacta.
"""
from __future__ import annotations

import subprocess
import threading
import time
from typing import Optional

import numpy as np

from app.capture.windows_video import _encoder_args
from app.encode.ffmpeg import detect_h264_encoder, get_ffmpeg_exe


def _resize_nearest(frame: np.ndarray, w: int, h: int) -> np.ndarray:
    """Redimensiona sin dependencias (vecino más cercano): solo si la ventana cambia."""
    try:
        import cv2

        return cv2.resize(frame, (w, h))
    except Exception:
        fh, fw = frame.shape[:2]
        filas = (np.arange(h) * fh // h).clip(0, fh - 1)
        cols = (np.arange(w) * fw // w).clip(0, fw - 1)
        return frame[filas][:, cols]


def frames_due(elapsed: float, fps: int) -> int:
    """Fotogramas que debería tener el video tras `elapsed` segundos (el primero
    sale en t=0)."""
    if elapsed < 0:
        return 0
    return int(elapsed * fps) + 1


class FramePipeWriter:
    """Escribe el último fotograma a un MKV H.264 a `fps` constantes."""

    def __init__(self, output_path: str, width: int, height: int, fps: int):
        self._path = output_path
        self._w = int(width)
        self._h = int(height)
        self._fps = int(fps)
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_at: Optional[float] = None

    def put(self, frame: np.ndarray) -> None:
        with self._lock:
            self._latest = frame

    def latest(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._latest is None else np.array(self._latest, copy=True)

    def start(self) -> None:
        encoder = detect_h264_encoder()
        args = (
            [get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pixel_format", "bgra",
             "-video_size", f"{self._w}x{self._h}", "-framerate", str(self._fps),
             "-i", "pipe:0",
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-r", str(self._fps)]
            + _encoder_args(encoder, self._fps)
            + [self._path]
        )
        self._proc = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        """Cuenta fotogramas contra el reloj: si ffmpeg se atrasa (encoder por
        software, CPU ocupada) se repite el último para ponerse al día. Saltarlos
        acortaría el video frente al audio y se desincronizaría la reunión."""
        t0 = time.perf_counter()
        escritos = 0
        while self._proc is not None:
            fin = self._stop_at
            ahora = time.perf_counter() if fin is None else fin
            debidos = frames_due(ahora - t0, self._fps)
            with self._lock:
                frame = self._latest
            if frame is not None and escritos < debidos:
                if frame.shape[0] != self._h or frame.shape[1] != self._w:
                    frame = _resize_nearest(frame, self._w, self._h)
                datos = np.ascontiguousarray(frame).tobytes()
                try:
                    while escritos < debidos:
                        self._proc.stdin.write(datos)
                        escritos += 1
                except Exception:
                    break
            if fin is not None:
                break
            espera = t0 + escritos / self._fps - time.perf_counter()
            if espera > 0:
                time.sleep(min(espera, 0.05))

    def stop(self) -> None:
        self._stop_at = time.perf_counter()
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=15)
            self._thread = None
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        finally:
            if proc.stderr:
                try:
                    proc.stderr.close()
                except Exception:
                    pass

    def is_running(self) -> bool:
        return self._running

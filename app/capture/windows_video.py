"""Captura de video en Windows.

Dos backends:
- `WindowsVideoCapture` (FFmpeg `gdigrab`): para PANTALLA completa. Simple y fiable.
- `WindowsGraphicsCapture` (Windows.Graphics.Capture vía `windows-capture`): para
  capturar una VENTANA específica. A diferencia de gdigrab, SÍ captura ventanas
  aceleradas por GPU (Teams, Chrome, etc.) que con gdigrab salían en NEGRO.

Limitaciones del SO: ventanas con DRM o protegidas se graban en negro en cualquier
método; gdigrab además no captura contenido GPU por ventana (de ahí WGC).
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import List, Optional

import numpy as np

from app.capture.base import VideoCapture
from app.core.config import VideoSource
from app.encode.ffmpeg import detect_h264_encoder, get_ffmpeg_exe

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Ventanas de sistema que no tiene sentido ofrecer como fuente.
_BLOCKLIST = {
    "", "Program Manager", "Default IME", "MSCTFIME UI",
    "Windows Input Experience", "Configuración",
}


def list_windows() -> List[VideoSource]:
    """Lista las ventanas visibles con título (para que el usuario elija una)."""
    if sys.platform != "win32":
        return []

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    results: List[VideoSource] = []
    seen = set()

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
    )

    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if title in _BLOCKLIST or title in seen:
            return True
        seen.add(title)
        results.append(VideoSource(kind="window", title=title, hwnd=int(hwnd)))
        return True

    user32.EnumWindows(EnumWindowsProc(_callback), 0)
    results.sort(key=lambda v: v.title.lower())
    return results


def list_monitors() -> List[VideoSource]:
    """Lista monitores en el mismo orden 1-based que windows-capture / WGC.

    Usa EnumDisplayMonitors (como la librería Rust subyacente). Cada entrada es
    un VideoSource kind=screen con monitor_index listo para WindowsCapture.
    """
    if sys.platform != "win32":
        return [VideoSource(kind="screen", title="Pantalla 1", monitor_index=1, is_primary=True)]

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    MONITORINFOF_PRIMARY = 1

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    results: List[VideoSource] = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
    )

    def _callback(hmon, _hdc, _lprc, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return 1
        idx = len(results) + 1
        primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
        w = abs(info.rcMonitor.right - info.rcMonitor.left)
        h = abs(info.rcMonitor.bottom - info.rcMonitor.top)
        device = (info.szDevice or "").strip() or f"DISPLAY{idx}"
        results.append(
            VideoSource(
                kind="screen",
                title=f"{device} {w}x{h}",
                monitor_index=idx,
                is_primary=primary,
            )
        )
        return 1

    ok = user32.EnumDisplayMonitors(None, None, MonitorEnumProc(_callback), 0)
    if not ok or not results:
        return [VideoSource(kind="screen", title="Pantalla 1", monitor_index=1, is_primary=True)]
    return results


def _encoder_args(encoder: str, fps: int) -> List[str]:
    """Argumentos de codificación según el encoder elegido."""
    # -g = intervalo de keyframes (2 segundos): bueno para edición/seek.
    common = ["-pix_fmt", "yuv420p", "-g", str(fps * 2)]
    if encoder == "libx264":
        # Software: calidad constante, preset rápido para no saturar la CPU.
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"] + common
    # Hardware (NVENC/QSV/AMF): control por bitrate.
    return ["-c:v", encoder, "-b:v", "8M"] + common


class WindowsVideoCapture(VideoCapture):
    """Graba video (sin audio) a un MKV usando gdigrab + un encoder H.264."""

    def __init__(self, source: VideoSource, fps: int = 30):
        self._source = source
        self._fps = fps
        self._proc: Optional[subprocess.Popen] = None

    def start(self, output_path: str) -> None:
        ff = get_ffmpeg_exe()
        encoder = detect_h264_encoder()

        # Entrada: escritorio o ventana por título
        if self._source.kind == "window" and self._source.title:
            input_spec = ["-i", f"title={self._source.title}"]
        else:
            input_spec = ["-i", "desktop"]

        args = (
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "gdigrab", "-framerate", str(self._fps), "-draw_mouse", "1"]
            + input_spec
            # Asegura dimensiones pares (requisito de yuv420p / libx264)
            + ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-r", str(self._fps)]
            + _encoder_args(encoder, self._fps)
            + [output_path]
        )

        # stdin=PIPE para poder detener con 'q' de forma ordenada (cierra el MKV bien).
        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_NO_WINDOW,
        )

    def stop(self) -> None:
        if not self._proc:
            return
        proc = self._proc
        self._proc = None
        try:
            if proc.poll() is None:
                # 'q' = parada ordenada en FFmpeg (finaliza el contenedor)
                try:
                    proc.stdin.write(b"q")
                    proc.stdin.flush()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
        finally:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


class WindowsGraphicsCapture(VideoCapture):
    """Captura una VENTANA o el MONITOR con Windows.Graphics.Capture.

    Para ventanas captura por HWND (confiable) y SÍ obtiene el contenido
    acelerado por GPU (Teams, navegadores) que con gdigrab salía negro. Para
    pantalla completa captura el monitor principal: WGC va por GPU (DXGI) y
    mantiene los 30 fps donde gdigrab por CPU se queda corto (medido: ~18 fps
    en un monitor 3440x1440). Los fotogramas (BGRA) se envían a FFmpeg por una
    tubería, a tasa constante (CFR) para mantener la sincronía con el audio.
    """

    def __init__(self, source: VideoSource, fps: int = 30):
        self._source = source
        self._fps = fps
        self._cap = None
        self._ctrl = None
        self._proc: Optional[subprocess.Popen] = None
        self._writer: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._first_frame = threading.Event()
        self._running = False
        self._w = 0
        self._h = 0

    def start(self, output_path: str) -> None:
        from windows_capture import WindowsCapture

        if self._source.kind == "window":
            if not self._source.hwnd:
                raise RuntimeError("No hay handle de ventana para capturar.")
            self._cap = WindowsCapture(
                cursor_capture=True,
                draw_border=False,
                window_hwnd=int(self._source.hwnd),
            )
        else:
            # Pantalla completa: monitor elegido (1-based, orden EnumDisplayMonitors).
            # minimum_update_interval limita callbacks (compositor 60-165 Hz).
            mon = int(self._source.monitor_index or 1)
            if mon < 1:
                mon = 1
            self._cap = WindowsCapture(
                cursor_capture=True,
                draw_border=False,
                monitor_index=mon,
                minimum_update_interval=max(1, int(1000 / (self._fps * 2))),
            )

        @self._cap.event
        def on_frame_arrived(frame, capture_control):
            # frame.frame_buffer es una VISTA a memoria nativa válida solo aquí:
            # hay que copiarla.
            with self._lock:
                self._latest = np.array(frame.frame_buffer, copy=True)
            self._first_frame.set()

        @self._cap.event
        def on_closed():
            pass

        self._ctrl = self._cap.start_free_threaded()
        if not self._first_frame.wait(timeout=6):
            self._safe_stop_capture()
            if self._source.kind == "window":
                raise RuntimeError(
                    "La ventana no entregó imagen (¿está minimizada?). "
                    "Restáurala e inténtalo de nuevo."
                )
            raise RuntimeError("El monitor no entregó imagen por WGC.")

        with self._lock:
            self._h, self._w = self._latest.shape[:2]

        ff = get_ffmpeg_exe()
        encoder = detect_h264_encoder()
        args = (
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pixel_format", "bgra",
             "-video_size", f"{self._w}x{self._h}", "-framerate", str(self._fps),
             "-i", "pipe:0",
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-r", str(self._fps)]
            + _encoder_args(encoder, self._fps)
            + [output_path]
        )
        self._proc = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=_NO_WINDOW,
        )
        self._running = True
        self._writer = threading.Thread(target=self._write_loop, daemon=True)
        self._writer.start()

    def _write_loop(self) -> None:
        interval = 1.0 / self._fps
        next_t = time.perf_counter()
        while self._running and self._proc is not None:
            with self._lock:
                frame = self._latest
            if frame is not None:
                if frame.shape[0] != self._h or frame.shape[1] != self._w:
                    import cv2  # la ventana cambió de tamaño: ajustar

                    frame = cv2.resize(frame, (self._w, self._h))
                try:
                    self._proc.stdin.write(np.ascontiguousarray(frame).tobytes())
                except Exception:
                    break
            next_t += interval
            delay = next_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.perf_counter()

    def _safe_stop_capture(self) -> None:
        if self._ctrl is not None:
            try:
                self._ctrl.stop()
            except Exception:
                pass
            self._ctrl = None

    def stop(self) -> None:
        self._running = False
        if self._writer is not None:
            self._writer.join(timeout=2)
            self._writer = None
        self._safe_stop_capture()
        if self._proc is not None:
            proc = self._proc
            self._proc = None
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            finally:
                for stream in (proc.stdout, proc.stderr):
                    try:
                        if stream:
                            stream.close()
                    except Exception:
                        pass

    def is_running(self) -> bool:
        return self._running

    def latest_frame(self) -> Optional[np.ndarray]:
        """Último fotograma capturado (BGRA), para la vista previa en vivo."""
        with self._lock:
            return None if self._latest is None else np.array(self._latest, copy=True)


class WindowsScreenCapture(VideoCapture):
    """Pantalla completa: WGC por GPU, con respaldo automático a gdigrab.

    WGC mantiene los 30 fps en monitores grandes donde gdigrab no llega; si WGC
    no entrega imagen (drivers/escritorios raros), se cae a gdigrab para no
    perder la grabación.
    """

    def __init__(self, source: VideoSource, fps: int = 30):
        self._source = source
        self._fps = fps
        self._active: Optional[VideoCapture] = None

    def start(self, output_path: str) -> None:
        try:
            cap = WindowsGraphicsCapture(self._source, fps=self._fps)
            cap.start(output_path)
            self._active = cap
        except Exception:
            cap = WindowsVideoCapture(self._source, fps=self._fps)
            cap.start(output_path)
            self._active = cap

    def stop(self) -> None:
        if self._active is not None:
            self._active.stop()

    def is_running(self) -> bool:
        return self._active is not None and self._active.is_running()

    def latest_frame(self) -> Optional[np.ndarray]:
        if isinstance(self._active, WindowsGraphicsCapture):
            return self._active.latest_frame()
        return None


def grab_window_frame(hwnd: int, timeout: float = 2.0) -> Optional[np.ndarray]:
    """Captura UN solo fotograma de una ventana con WGC (BGRA) o None.

    Se usa para la vista previa cuando NO se está grabando: a diferencia de
    `QScreen.grabWindow`, sí obtiene el contenido de ventanas aceleradas por GPU.
    """
    try:
        from windows_capture import WindowsCapture
    except Exception:
        return None

    holder = {}
    evt = threading.Event()
    try:
        cap = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=int(hwnd))
    except Exception:
        return None

    @cap.event
    def on_frame_arrived(frame, capture_control):
        holder["f"] = np.array(frame.frame_buffer, copy=True)
        evt.set()
        capture_control.stop()

    @cap.event
    def on_closed():
        pass

    try:
        ctrl = cap.start_free_threaded()
    except Exception:
        return None
    evt.wait(timeout=timeout)
    try:
        ctrl.stop()
    except Exception:
        pass
    return holder.get("f")

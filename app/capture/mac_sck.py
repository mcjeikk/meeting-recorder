"""Captura en macOS con ScreenCaptureKit (spec 030).

ScreenCaptureKit (macOS 12.3+, audio desde 13) da la pantalla o una ventana Y el
audio del sistema sin instalar drivers. Se usan DOS streams independientes, uno
de video y otro solo de audio, igual que en Windows hay una captura de video y
otra de audio del sistema: el orquestador, las pausas y el mux no cambian.

- Video: el último fotograma BGRA se escribe a ffmpeg a fps constantes
  (`FramePipeWriter`), como WGC.
- Audio del sistema: float32 de ScreenCaptureKit → WAV int16 estéreo 48 kHz,
  rellenando con silencio los huecos según la marca de tiempo de cada buffer
  (`GapFiller`): sin sonido, ScreenCaptureKit puede no entregar nada.

Todo lo nativo (PyObjC) se importa dentro de las funciones: este módulo se
puede importar en Windows sin efecto. Los fallos se anotan en
`<datos>/logs/mac_capture.log`, que es lo que hay que pedir si algo no graba.
"""
from __future__ import annotations

import os
import threading
import time
import traceback
import wave
from typing import Callable, List, Optional

import numpy as np

from app.capture.audio_gaps import GapFiller, float_to_int16, silence
from app.capture.base import AudioCapture, VideoCapture
from app.core.config import VideoSource

_BGRA = 1111970369  # kCVPixelFormatType_32BGRA ('BGRA')
_NON_INTERLEAVED = 1 << 5  # kAudioFormatFlagIsNonInterleaved
_MAX_LONG_SIDE = 2560
_AUDIO_RATE = 48_000
_AUDIO_CHANNELS = 2

# Si la ventana de la app se excluye de lo que se graba (casilla de la UI).
_exclude_own_app = True


def set_exclude_own_app(value: bool) -> None:
    global _exclude_own_app
    _exclude_own_app = bool(value)


# --- diagnóstico ----------------------------------------------------------------
def _log(msg: str) -> None:
    try:
        from app.core.platform_paths import local_dir

        carpeta = local_dir() / "logs"
        carpeta.mkdir(parents=True, exist_ok=True)
        with open(carpeta / "mac_capture.log", "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg.rstrip() + "\n")
    except Exception:
        pass


def _log_exc(where: str) -> None:
    _log(f"{where}: {traceback.format_exc()}")


# --- espera de completion handlers ----------------------------------------------
def _wait(done: threading.Event, timeout: float) -> bool:
    """Espera un completion handler. En el hilo principal bombea el run loop:
    si el handler llegara por la cola principal, bloquearla sería un deadlock."""
    if threading.current_thread() is not threading.main_thread():
        return done.wait(timeout)
    try:
        from Foundation import NSDate, NSRunLoop
    except Exception:
        return done.wait(timeout)
    limite = time.monotonic() + timeout
    while not done.is_set() and time.monotonic() < limite:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.02))
    return done.is_set()


def _call_async(invoke: Callable[[Callable], None], timeout: float = 10.0) -> tuple:
    done = threading.Event()
    box: dict = {}

    def handler(*args):
        box["args"] = args
        done.set()

    invoke(handler)
    if not _wait(done, timeout):
        raise TimeoutError("ScreenCaptureKit no respondió a tiempo")
    return box.get("args", ())


def _error_text(err) -> str:
    try:
        return str(err.localizedDescription())
    except Exception:
        return str(err)


# --- contenido compartible --------------------------------------------------------
def _shareable_content():
    import ScreenCaptureKit as SCK

    args = _call_async(
        lambda h: SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
            True, True, h
        )
    )
    content = args[0] if args else None
    error = args[1] if len(args) > 1 else None
    if content is None:
        raise PermissionError(
            "macOS no deja ver la pantalla: falta el permiso de Grabación de pantalla"
            + (f" ({_error_text(error)})" if error is not None else "")
        )
    return content


def _own_pid_apps(content) -> list:
    pid = os.getpid()
    propias = []
    try:
        for app in content.applications():
            if int(app.processID()) == pid:
                propias.append(app)
    except Exception:
        _log_exc("own apps")
    return propias


def list_monitors() -> List[VideoSource]:
    try:
        import Quartz

        content = _shareable_content()
        principal = Quartz.CGMainDisplayID()
        fuentes = []
        for i, display in enumerate(content.displays(), start=1):
            fuentes.append(
                VideoSource(
                    kind="screen",
                    title=f"Pantalla {i}",
                    monitor_index=i,
                    is_primary=int(display.displayID()) == int(principal),
                )
            )
        if fuentes:
            return fuentes
    except Exception:
        _log_exc("list_monitors")
    return [VideoSource(kind="screen", title="Pantalla 1", monitor_index=1, is_primary=True)]


def list_windows() -> List[VideoSource]:
    try:
        content = _shareable_content()
    except Exception:
        _log_exc("list_windows")
        return []
    pid = os.getpid()
    fuentes = []
    for w in content.windows():
        try:
            app = w.owningApplication()
            titulo = str(w.title() or "").strip()
            if app is None or not titulo or int(app.processID()) == pid:
                continue
            if int(w.windowLayer()) != 0 or not bool(w.isOnScreen()):
                continue
            marco = w.frame()
            if marco.size.width < 80 or marco.size.height < 60:
                continue
            nombre_app = str(app.applicationName() or "").strip()
            visible = f"{nombre_app} — {titulo}" if nombre_app and nombre_app not in titulo else titulo
            fuentes.append(VideoSource(kind="window", title=visible, hwnd=int(w.windowID())))
        except Exception:
            _log_exc("list_windows item")
    fuentes.sort(key=lambda s: s.title.lower())
    return fuentes


# --- filtros y configuración ------------------------------------------------------
def _display_pixel_size(display) -> tuple:
    try:
        import Quartz

        modo = Quartz.CGDisplayCopyDisplayMode(display.displayID())
        return int(Quartz.CGDisplayModeGetPixelWidth(modo)), int(Quartz.CGDisplayModeGetPixelHeight(modo))
    except Exception:
        _log_exc("display pixel size")
        return int(display.width()) * 2, int(display.height()) * 2


def _backing_scale() -> float:
    try:
        from AppKit import NSScreen

        return float(NSScreen.mainScreen().backingScaleFactor())
    except Exception:
        return 2.0


def _capped(w: int, h: int) -> tuple:
    largo = max(w, h)
    if largo > _MAX_LONG_SIDE:
        f = _MAX_LONG_SIDE / largo
        w, h = int(w * f), int(h * f)
    return max(2, w - (w % 2)), max(2, h - (h % 2))


def _filter_and_size(source: Optional[VideoSource]):
    """(SCContentFilter, ancho, alto) para la fuente; sin fuente = pantalla principal."""
    import ScreenCaptureKit as SCK

    content = _shareable_content()
    if source is not None and source.kind == "window" and source.hwnd:
        for w in content.windows():
            if int(w.windowID()) == int(source.hwnd):
                filtro = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(w)
                escala = _backing_scale()
                marco = w.frame()
                ancho, alto = _capped(int(marco.size.width * escala), int(marco.size.height * escala))
                return filtro, ancho, alto
        raise RuntimeError("La ventana ya no está disponible (¿se cerró o se minimizó?).")
    displays = list(content.displays())
    if not displays:
        raise RuntimeError("macOS no informó ninguna pantalla.")
    idx = int((source.monitor_index if source else 1) or 1)
    display = displays[min(max(idx, 1), len(displays)) - 1]
    excluidas = _own_pid_apps(content) if _exclude_own_app else []
    filtro = SCK.SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
        display, excluidas, []
    )
    ancho, alto = _capped(*_display_pixel_size(display))
    return filtro, ancho, alto


def _configuration(width: int, height: int, fps: int, audio: bool):
    import CoreMedia
    import ScreenCaptureKit as SCK

    cfg = SCK.SCStreamConfiguration.alloc().init()
    cfg.setWidth_(int(width))
    cfg.setHeight_(int(height))
    cfg.setMinimumFrameInterval_(CoreMedia.CMTimeMake(1, int(max(1, fps))))
    cfg.setPixelFormat_(_BGRA)
    cfg.setShowsCursor_(True)
    cfg.setQueueDepth_(6)
    if audio:
        cfg.setCapturesAudio_(True)
        cfg.setSampleRate_(_AUDIO_RATE)
        cfg.setChannelCount_(_AUDIO_CHANNELS)
        cfg.setExcludesCurrentProcessAudio_(True)
    return cfg


def _output_class():
    """Clase ObjC que recibe los buffers (se define una vez, al primer uso)."""
    global _OUTPUT_CLASS
    if _OUTPUT_CLASS is not None:
        return _OUTPUT_CLASS
    import objc
    from Foundation import NSObject

    protocolo = objc.protocolNamed("SCStreamOutput")

    class MRStreamOutput(NSObject, protocols=[protocolo]):
        def initWithCallback_(self, callback):
            self = objc.super(MRStreamOutput, self).init()
            if self is None:
                return None
            self._callback = callback
            return self

        def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
            try:
                self._callback(sample_buffer, int(output_type))
            except Exception:
                _log_exc("sample callback")

    _OUTPUT_CLASS = MRStreamOutput
    return _OUTPUT_CLASS


_OUTPUT_CLASS = None
_DELEGATE_CLASS = None


def _delegate_class():
    """Delegado que anota por qué macOS detuvo un stream (si no, se pierde)."""
    global _DELEGATE_CLASS
    if _DELEGATE_CLASS is not None:
        return _DELEGATE_CLASS
    import objc
    from Foundation import NSObject

    protocolo = objc.protocolNamed("SCStreamDelegate")

    class MRStreamDelegate(NSObject, protocols=[protocolo]):
        def initWithLabel_(self, label):
            self = objc.super(MRStreamDelegate, self).init()
            if self is None:
                return None
            self._label = str(label)
            self.stopped_error = None
            return self

        def stream_didStopWithError_(self, stream, error):
            self.stopped_error = _error_text(error)
            _log(f"{self._label}: macOS detuvo el stream: {self.stopped_error}")

    _DELEGATE_CLASS = MRStreamDelegate
    return _DELEGATE_CLASS


def _sample_queue(label: str):
    try:
        from libdispatch import DISPATCH_QUEUE_SERIAL, dispatch_queue_create

        return dispatch_queue_create(label.encode(), DISPATCH_QUEUE_SERIAL)
    except Exception:
        return None  # ScreenCaptureKit usa una cola propia


class _Stream:
    """Un SCStream con una salida (pantalla o audio) y su callback Python."""

    def __init__(self, filtro, config, output_type: int, callback, label: str):
        import ScreenCaptureKit as SCK

        self._label = label
        self._delegate = _delegate_class().alloc().initWithLabel_(label)
        self._stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
            filtro, config, self._delegate
        )
        self._output = _output_class().alloc().initWithCallback_(callback)
        resultado = self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._output, output_type, _sample_queue(label), None
        )
        ok = resultado[0] if isinstance(resultado, tuple) else resultado
        if not ok:
            err = resultado[1] if isinstance(resultado, tuple) and len(resultado) > 1 else None
            raise RuntimeError(f"No se pudo preparar la captura ({_error_text(err)})")

    def start(self) -> None:
        args = _call_async(lambda h: self._stream.startCaptureWithCompletionHandler_(h))
        err = args[0] if args else None
        if err is not None:
            _log(f"{self._label}: no arrancó: {_error_text(err)}")
            raise RuntimeError(f"macOS no inició la captura: {_error_text(err)}")
        _log(f"{self._label}: arrancó")

    def stopped_error(self) -> Optional[str]:
        return getattr(self._delegate, "stopped_error", None)

    def stop(self) -> None:
        try:
            _call_async(lambda h: self._stream.stopCaptureWithCompletionHandler_(h), timeout=5)
        except Exception:
            _log_exc("stop stream")


# --- conversión de buffers -----------------------------------------------------------
def _frame_from_sample(sample_buffer) -> Optional[np.ndarray]:
    import CoreMedia
    import Quartz

    pixel_buffer = CoreMedia.CMSampleBufferGetImageBuffer(sample_buffer)
    if pixel_buffer is None:
        return None  # fotograma "sin cambios": ScreenCaptureKit no manda imagen
    Quartz.CVPixelBufferLockBaseAddress(pixel_buffer, 1)
    try:
        alto = int(Quartz.CVPixelBufferGetHeight(pixel_buffer))
        ancho = int(Quartz.CVPixelBufferGetWidth(pixel_buffer))
        por_fila = int(Quartz.CVPixelBufferGetBytesPerRow(pixel_buffer))
        base = Quartz.CVPixelBufferGetBaseAddress(pixel_buffer)
        crudo = base.as_buffer(por_fila * alto)
        datos = np.frombuffer(crudo, dtype=np.uint8).reshape(alto, por_fila)
        return datos[:, : ancho * 4].reshape(alto, ancho, 4).copy()
    finally:
        Quartz.CVPixelBufferUnlockBaseAddress(pixel_buffer, 1)


def _audio_format(sample_buffer) -> tuple:
    """(canales, intercalado?) del buffer; si no se puede leer, lo configurado."""
    import CoreMedia

    try:
        fmt = CoreMedia.CMSampleBufferGetFormatDescription(sample_buffer)
        asbd = CoreMedia.CMAudioFormatDescriptionGetStreamBasicDescription(fmt)
        if hasattr(asbd, "__getitem__") and not hasattr(asbd, "mChannelsPerFrame"):
            asbd = asbd[0]
        canales = int(asbd.mChannelsPerFrame) or _AUDIO_CHANNELS
        planar = bool(int(asbd.mFormatFlags) & _NON_INTERLEAVED)
        return canales, planar
    except Exception:
        return _AUDIO_CHANNELS, True


def _audio_bytes(sample_buffer) -> bytes:
    import CoreMedia

    bloque = CoreMedia.CMSampleBufferGetDataBuffer(sample_buffer)
    if bloque is None:
        return b""
    largo = int(CoreMedia.CMBlockBufferGetDataLength(bloque))
    resultado = CoreMedia.CMBlockBufferCopyDataBytes(bloque, 0, largo, None)
    if isinstance(resultado, tuple):
        datos = resultado[-1]
    else:
        datos = resultado
    if datos is None:
        return b""
    return bytes(datos)


def _seconds(cmtime) -> float:
    import CoreMedia

    return float(CoreMedia.CMTimeGetSeconds(cmtime))


def host_now() -> float:
    """Ahora, en el reloj del sistema que usan las marcas de ScreenCaptureKit."""
    import CoreMedia

    return _seconds(CoreMedia.CMClockGetTime(CoreMedia.CMClockGetHostTimeClock()))


# --- capturas -------------------------------------------------------------------------
class SCKVideoCapture(VideoCapture):
    """Pantalla o ventana → MKV H.264 a fps constantes."""

    def __init__(self, source: VideoSource, fps: int = 30):
        self._source = source
        self._fps = int(fps)
        self._stream: Optional[_Stream] = None
        self._writer = None
        self._first = threading.Event()
        self._latest: Optional[np.ndarray] = None

    def _on_sample(self, sample_buffer, output_type: int) -> None:
        import ScreenCaptureKit as SCK

        if output_type != int(SCK.SCStreamOutputTypeScreen):
            return
        frame = _frame_from_sample(sample_buffer)
        if frame is None:
            return
        self._latest = frame
        if self._writer is not None:
            self._writer.put(frame)
        self._first.set()

    def start(self, output_path: str) -> None:
        import ScreenCaptureKit as SCK

        from app.capture.frame_pipe import FramePipeWriter

        filtro, ancho, alto = _filter_and_size(self._source)
        _log(f"video: {self._source.kind} {ancho}x{alto} @ {self._fps} fps")
        config = _configuration(ancho, alto, self._fps, audio=False)
        self._stream = _Stream(filtro, config, int(SCK.SCStreamOutputTypeScreen), self._on_sample, "mr.video")
        self._stream.start()
        if not _wait(self._first, 6):
            motivo = self._stream.stopped_error()
            self._stream.stop()
            self._stream = None
            _log(f"video: sin primer fotograma en 6 s ({motivo or 'sin error de macOS'})")
            raise RuntimeError(
                "La pantalla no entregó imagen. Revisa el permiso de Grabación de "
                "pantalla (Ajustes del Sistema → Privacidad y seguridad)."
                + (f" Detalle: {motivo}" if motivo else "")
            )
        alto_real, ancho_real = self._latest.shape[:2]
        self._writer = FramePipeWriter(output_path, ancho_real, alto_real, self._fps)
        self._writer.put(self._latest)
        self._writer.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
        if self._writer is not None:
            self._writer.stop()
            self._writer = None

    def is_running(self) -> bool:
        return self._writer is not None and self._writer.is_running()

    def latest_frame(self) -> Optional[np.ndarray]:
        frame = self._latest
        return None if frame is None else np.array(frame, copy=True)


class SCKSystemAudioCapture(AudioCapture):
    """Audio del sistema (sin la propia app) → WAV int16 estéreo 48 kHz, continuo."""

    def __init__(self):
        self._stream: Optional[_Stream] = None
        self._wave: Optional[wave.Wave_write] = None
        self._lock = threading.Lock()
        self._gaps: Optional[GapFiller] = None
        self._level = 0.0
        self._fallos = 0

    def _on_sample(self, sample_buffer, output_type: int) -> None:
        import CoreMedia
        import ScreenCaptureKit as SCK

        if output_type != int(SCK.SCStreamOutputTypeAudio):
            return
        try:
            n = int(CoreMedia.CMSampleBufferGetNumSamples(sample_buffer))
            if n <= 0:
                return
            canales, planar = _audio_format(sample_buffer)
            muestras = float_to_int16(_audio_bytes(sample_buffer), canales, n, planar)
            if canales == 1:
                muestras = np.repeat(muestras, 2, axis=1)
            elif canales > 2:
                muestras = muestras[:, :2]
            pts = _seconds(CoreMedia.CMSampleBufferGetPresentationTimeStamp(sample_buffer))
        except Exception:
            self._fallos += 1
            if self._fallos <= 3:
                _log_exc("audio sample")
            return
        with self._lock:
            if self._wave is None or self._gaps is None:
                return
            relleno = self._gaps.silence_before(pts, muestras.shape[0])
            if relleno:
                self._wave.writeframes(silence(relleno, _AUDIO_CHANNELS))
            self._wave.writeframes(np.ascontiguousarray(muestras).tobytes())
        x = muestras.astype(np.float32) / 32768.0
        self._level = min(1.0, float(np.sqrt(np.mean(np.square(x)))) * 3.0) if x.size else 0.0

    def start(self, output_path: str) -> None:
        import ScreenCaptureKit as SCK

        filtro, _w, _h = _filter_and_size(None)
        config = _configuration(2, 2, 1, audio=True)
        w = wave.open(output_path, "wb")
        w.setnchannels(_AUDIO_CHANNELS)
        w.setsampwidth(2)
        w.setframerate(_AUDIO_RATE)
        with self._lock:
            self._wave = w
            self._gaps = GapFiller(_AUDIO_RATE, host_now())
        try:
            self._stream = _Stream(filtro, config, int(SCK.SCStreamOutputTypeAudio), self._on_sample, "mr.audio")
            self._stream.start()
        except Exception:
            with self._lock:
                self._wave = None
                self._gaps = None
            w.close()
            raise

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
        with self._lock:
            if self._wave is not None and self._gaps is not None:
                try:
                    relleno = self._gaps.silence_until(host_now())
                    if relleno:
                        self._wave.writeframes(silence(relleno, _AUDIO_CHANNELS))
                except Exception:
                    _log_exc("audio tail")
            if self._wave is not None:
                try:
                    self._wave.close()
                except Exception:
                    pass
            self._wave = None
            self._gaps = None
        self._level = 0.0

    def current_level(self) -> float:
        return self._level


# --- vista previa puntual --------------------------------------------------------------
def _grab(source: VideoSource, timeout: float = 3.0) -> Optional[np.ndarray]:
    try:
        import ScreenCaptureKit as SCK

        filtro, ancho, alto = _filter_and_size(source)
        escala = min(1.0, 960 / max(ancho, alto))
        ancho, alto = _capped(int(ancho * escala), int(alto * escala))
        config = _configuration(ancho, alto, 5, audio=False)
        listo = threading.Event()
        caja: dict = {}

        def _on(sample_buffer, output_type):
            if output_type != int(SCK.SCStreamOutputTypeScreen) or listo.is_set():
                return
            frame = _frame_from_sample(sample_buffer)
            if frame is not None:
                caja["frame"] = frame
                listo.set()

        stream = _Stream(filtro, config, int(SCK.SCStreamOutputTypeScreen), _on, "mr.preview")
        stream.start()
        try:
            listo.wait(timeout)
        finally:
            stream.stop()
        return caja.get("frame")
    except Exception:
        _log_exc("preview grab")
        return None


def grab_window_frame(window_id: int, timeout: float = 3.0) -> Optional[np.ndarray]:
    return _grab(VideoSource(kind="window", hwnd=int(window_id)), timeout)


def grab_monitor_frame(monitor_index: int = 1, timeout: float = 3.0) -> Optional[np.ndarray]:
    return _grab(VideoSource(kind="screen", monitor_index=int(monitor_index or 1)), timeout)

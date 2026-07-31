"""Monitor de audio en vivo (sin grabar) para los medidores de nivel.

Mientras la app está abierta pero NO grabando, abre flujos ligeros del micrófono
y del audio del sistema solo para calcular el nivel (RMS) y que los medidores se
muevan al hablar o al reproducir sonido — útil para verificar antes de grabar.

No escribe archivos. Se detiene al iniciar la grabación (el grabador toma los
dispositivos) y al minimizar la ventana (libera el micrófono).
"""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np

from app.capture.windows_audio import _rms_level, resolve_wasapi_loopback
from app.core.config import AudioDevice

_CHUNK = 1024


class AudioMonitor:
    """Mide niveles de micrófono y audio del sistema sin grabar."""

    def __init__(self):
        self._lock = threading.Lock()
        self._mic_level = 0.0
        self._sys_level = 0.0
        self._mic_stream = None
        self._pa = None
        self._sys_stream = None
        self._running = False
        self._mic_device: Optional[AudioDevice] = None

    # --- audio del sistema ---------------------------------------------------
    def _start_system(self) -> None:
        try:
            import pyaudiowpatch as pyaudio

            self._pa = pyaudio.PyAudio()
            dev = resolve_wasapi_loopback(self._pa)

            def _cb(in_data, _n, _t, _s):
                self._sys_level = _rms_level(np.frombuffer(in_data, dtype=np.int16))
                return (None, pyaudio.paContinue)

            self._sys_stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=max(1, int(dev["maxInputChannels"])),
                rate=int(dev["defaultSampleRate"]),
                frames_per_buffer=_CHUNK,
                input=True,
                input_device_index=dev["index"],
                stream_callback=_cb,
            )
            self._sys_stream.start_stream()
        except Exception:
            self._sys_stream = None  # sin monitor de sistema; no es crítico
            if self._pa is not None:
                try:
                    self._pa.terminate()
                except Exception:
                    pass
                self._pa = None

    def _stop_system(self) -> None:
        if self._sys_stream is not None:
            try:
                self._sys_stream.stop_stream()
                self._sys_stream.close()
            except Exception:
                pass
            self._sys_stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
        self._sys_level = 0.0

    # --- micrófono -----------------------------------------------------------
    def _start_mic(self, device: Optional[AudioDevice]) -> None:
        if device is None:
            return
        try:
            import sounddevice as sd

            def _cb(indata, _frames, _time, _status):
                self._mic_level = _rms_level(indata.reshape(-1))

            self._mic_stream = sd.InputStream(
                samplerate=int(device.sample_rate),
                blocksize=_CHUNK,
                device=device.index,
                channels=max(1, int(device.channels)),
                dtype="int16",
                callback=_cb,
            )
            self._mic_stream.start()
        except Exception:
            self._mic_stream = None

    def _stop_mic(self) -> None:
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None
        self._mic_level = 0.0

    # --- API pública ---------------------------------------------------------
    def start(self, mic_device: Optional[AudioDevice]) -> None:
        if self._running:
            return
        self._running = True
        self._mic_device = mic_device
        self._start_system()
        self._start_mic(mic_device)

    def set_mic(self, device: Optional[AudioDevice]) -> None:
        """Cambia el micrófono monitoreado (al cambiar la selección en la UI)."""
        self._mic_device = device
        if not self._running:
            return
        self._stop_mic()
        self._start_mic(device)

    def restart_system(self) -> None:
        """Reabre el loopback (p. ej. tras cambiar la salida por defecto / BT)."""
        if not self._running:
            return
        self._stop_system()
        self._start_system()

    def restart(self, mic_device: Optional[AudioDevice] = None) -> None:
        """Reinicia mic + sistema (tras hotplug o Actualizar)."""
        if mic_device is not None:
            self._mic_device = mic_device
        was = self._running
        if was:
            self.stop()
        self.start(self._mic_device)

    def stop(self) -> None:
        self._running = False
        self._stop_mic()
        self._stop_system()

    def is_running(self) -> bool:
        return self._running

    def mic_level(self) -> float:
        return self._mic_level

    def system_level(self) -> float:
        return self._sys_level

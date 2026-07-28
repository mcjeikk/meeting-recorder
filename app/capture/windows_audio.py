"""Captura de audio en Windows.

- `SystemAudioCapture`: graba el AUDIO DEL SISTEMA (lo que suena en los parlantes)
  usando WASAPI loopback vía PyAudioWPatch. No requiere "Stereo Mix" ni cables.
- `MicCapture`: graba el MICRÓFONO vía sounddevice. Está basado en SEGMENTOS para
  permitir CAMBIAR DE MICRÓFONO a mitad de la grabación: cada dispositivo se graba
  en su formato nativo como un archivo aparte con su instante de inicio; FFmpeg los
  normaliza y los une en una sola pista al multiplexar.

Ambas exponen `current_level()` (0–1) para los medidores de la interfaz.
"""
from __future__ import annotations

import os
import threading
import wave
from typing import List, Optional, Tuple

import numpy as np

from app.capture.base import AudioCapture
from app.core.config import AudioDevice

_CHUNK = 1024


def _rms_level(samples_int16: np.ndarray) -> float:
    """Nivel RMS normalizado a 0–1 a partir de muestras int16."""
    if samples_int16.size == 0:
        return 0.0
    x = samples_int16.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(np.square(x))))
    return min(1.0, rms * 3.0)  # ligera compresión para que el medidor se vea mejor


def reinitialize_portaudio() -> None:
    """Fuerza a PortAudio a re-escanear dispositivos (hotplug).

    sounddevice/PortAudio congela la lista en ``Pa_Initialize()``. Un micrófono
    Bluetooth/USB conectado después del arranque NO aparece en ``query_devices()``
    hasta ``_terminate()`` + ``_initialize()``.

    El llamador DEBE cerrar antes cualquier ``InputStream``/``OutputStream`` de
    sounddevice; si no, PortAudio corta esos flujos.
    """
    import sounddevice as sd

    sd._terminate()
    sd._initialize()


def list_microphones(*, refresh: bool = False) -> List[AudioDevice]:
    """Lista los micrófonos disponibles (solo WASAPI: lista limpia y sin duplicados).

    Filtramos al host API WASAPI porque (a) evita los duplicados MME/DirectSound y
    (b) es la ruta moderna y fiable en Windows. Cada dispositivo se grabará en su
    formato NATIVO (algunos auriculares Bluetooth solo dan 16 kHz mono).

    Con ``refresh=True`` reinicia PortAudio para ver dispositivos recién conectados.
    Solo usar cuando no hay streams sounddevice abiertos (p. ej. medidor detenido,
    sin grabación activa). Los endpoints solo-salida (A2DP Stereo) tienen
    ``max_input_channels == 0`` y se omiten a propósito — el mic BT suele vivir
    en el perfil Hands-Free (HFP).
    """
    try:
        import sounddevice as sd
    except Exception:
        return []

    if refresh:
        try:
            reinitialize_portaudio()
        except Exception:
            pass  # best-effort: seguir con la lista cacheada si el reinicio falla

    hostapis = sd.query_hostapis()
    wasapi_idx = next((i for i, h in enumerate(hostapis) if "WASAPI" in h["name"]), None)

    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) <= 0:
            continue
        if wasapi_idx is not None and dev.get("hostapi") != wasapi_idx:
            continue
        devices.append(
            AudioDevice(
                index=idx,
                name=dev["name"],
                channels=max(1, int(dev["max_input_channels"])),
                sample_rate=int(dev.get("default_samplerate") or 48_000),
            )
        )
    return devices


class SystemAudioCapture(AudioCapture):
    """Graba el audio del sistema (WASAPI loopback) a un WAV.

    Incluye un "keep-alive": una salida de silencio digital que mantiene activo el
    motor de audio. Sin esto, WASAPI loopback NO entrega datos cuando no suena nada
    (o durante silencios largos), lo que dejaría la pista vacía o desincronizada.
    """

    def __init__(self):
        self._pa = None
        self._stream = None
        self._keepalive = None
        self._wave: Optional[wave.Wave_write] = None
        self._lock = threading.Lock()
        self._level = 0.0
        self._channels = 2
        self._rate = 48_000

    def _find_loopback_device(self, pa):
        import pyaudiowpatch as pyaudio

        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        speakers = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        if not speakers.get("isLoopbackDevice", False):
            for lb in pa.get_loopback_device_info_generator():
                if speakers["name"] in lb["name"]:
                    return lb
            raise RuntimeError(
                "No se encontró un dispositivo de loopback para los parlantes por defecto."
            )
        return speakers

    def _start_keepalive(self) -> None:
        """Reproduce silencio digital para mantener activo el motor de audio."""
        try:
            import sounddevice as sd

            def _silence(outdata, _frames, _time, _status):
                outdata.fill(0)

            self._keepalive = sd.OutputStream(
                samplerate=48_000, channels=2, dtype="float32",
                blocksize=_CHUNK, callback=_silence,
            )
            self._keepalive.start()
        except Exception:
            self._keepalive = None  # no es crítico

    def start(self, output_path: str) -> None:
        import pyaudiowpatch as pyaudio

        self._start_keepalive()

        self._pa = pyaudio.PyAudio()
        device = self._find_loopback_device(self._pa)
        self._channels = max(1, int(device["maxInputChannels"]))
        self._rate = int(device["defaultSampleRate"])

        self._wave = wave.open(output_path, "wb")
        self._wave.setnchannels(self._channels)
        self._wave.setsampwidth(2)
        self._wave.setframerate(self._rate)

        def _callback(in_data, _frame_count, _time_info, _status):
            with self._lock:
                if self._wave is not None:
                    self._wave.writeframes(in_data)
            self._level = _rms_level(np.frombuffer(in_data, dtype=np.int16))
            return (None, pyaudio.paContinue)

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._rate,
            frames_per_buffer=_CHUNK,
            input=True,
            input_device_index=device["index"],
            stream_callback=_callback,
        )
        self._stream.start_stream()

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._keepalive is not None:
            try:
                self._keepalive.stop()
                self._keepalive.close()
            except Exception:
                pass
            self._keepalive = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
        with self._lock:
            if self._wave is not None:
                try:
                    self._wave.close()
                except Exception:
                    pass
                self._wave = None
        self._level = 0.0

    def current_level(self) -> float:
        return self._level


class MicCapture(AudioCapture):
    """Graba el micrófono en SEGMENTOS, soportando cambio de dispositivo en caliente.

    Cada segmento es un WAV en el formato nativo del micrófono, con el instante en
    que empezó (medido desde el inicio de la grabación). Al cambiar de micrófono se
    cierra el segmento actual y se abre otro con el nuevo dispositivo. FFmpeg luego
    normaliza y coloca cada segmento en su lugar para formar una pista continua.
    """

    def __init__(self, temp_dir: str):
        self._temp_dir = temp_dir
        self._lock = threading.Lock()
        self._level = 0.0
        self._stream = None
        self._wave: Optional[wave.Wave_write] = None
        self._device: Optional[AudioDevice] = None
        # Cada segmento: (ruta_wav, tramo). El desfase se calcula al final.
        self._segments: List[Tuple[str, int]] = []
        self._cycle = 0
        self._seg_count = 0
        self._muted = False

    def set_muted(self, muted: bool) -> None:
        """Silencia/activa el micrófono. Muteado = se graba SILENCIO (pista continua)."""
        self._muted = muted

    def is_muted(self) -> bool:
        return self._muted

    def start(self, device: Optional[AudioDevice], cycle: int = 0) -> None:
        """Inicia la captura en el tramo `cycle`."""
        self._cycle = cycle
        if device is not None:
            self._open_segment(device)

    def _open_segment(self, device: AudioDevice) -> None:
        import sounddevice as sd

        rate = int(device.sample_rate)
        ch = max(1, int(device.channels))
        path = os.path.join(self._temp_dir, f"mic_seg_{self._seg_count}.wav")
        self._seg_count += 1

        w = wave.open(path, "wb")
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)

        def _callback(indata, _frames, _time, _status):
            if self._muted:
                # Muteado: graba silencio para mantener la pista continua y en sync.
                data = np.zeros_like(indata).tobytes()
                level = 0.0
            else:
                data = indata.tobytes()
                level = _rms_level(indata.reshape(-1))
            with self._lock:
                if self._wave is not None:
                    self._wave.writeframes(data)
            self._level = level

        stream = sd.InputStream(
            samplerate=rate,
            blocksize=_CHUNK,
            device=device.index,
            channels=ch,
            dtype="int16",
            callback=_callback,
        )
        with self._lock:
            self._wave = w
            self._segments.append((path, self._cycle))
        self._stream = stream
        self._device = device
        stream.start()

    def _close_segment(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        with self._lock:
            if self._wave is not None:
                try:
                    self._wave.close()
                except Exception:
                    pass
                self._wave = None
        self._level = 0.0

    def switch_device(self, device: Optional[AudioDevice], cycle: Optional[int] = None) -> None:
        """Cambia de micrófono (o lo apaga con None) durante la grabación."""
        if cycle is not None:
            self._cycle = cycle
        self._close_segment()
        if device is not None:
            self._open_segment(device)
        else:
            self._device = None

    def stop(self) -> None:
        self._close_segment()

    def segments(self) -> List[Tuple[str, int]]:
        """Lista de (ruta_wav, tramo) de cada segmento grabado."""
        with self._lock:
            return list(self._segments)

    @property
    def device(self) -> Optional[AudioDevice]:
        return self._device

    def current_level(self) -> float:
        return self._level

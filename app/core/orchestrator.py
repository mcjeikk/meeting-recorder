"""Orquestador de la grabación: coordina video + audio del sistema + micrófono.

Soporta:
- Grabar pantalla/ventana + audio del sistema + micrófono.
- CAMBIAR de micrófono en caliente (cada mic es un segmento).
- PAUSAR / REANUDAR: cada tramo activo es un segmento de video y de sistema; al
  final se concatena el video y se colocan los audios en su tiempo grabado (sin
  contar las pausas). Así no quedan huecos por las pausas.

Flujo:
1. `start(settings)` arranca el primer tramo.
2. `pause()` cierra los segmentos actuales; `resume()` abre tramos nuevos.
3. `stop()` cierra todo y, en un HILO de fondo, concatena + multiplexa el MP4.

Resultados por callbacks: `on_status`, `on_finished`, `on_error`.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
from collections import OrderedDict
from typing import Callable, List, Optional, Tuple

from app.capture.base import VideoCapture
from app.core.clock import MasterClock
from app.core.config import AudioDevice, RecordingSettings, VideoSource, recording_stem
from app.encode.ffmpeg import (
    Segment,
    Track,
    concat_videos,
    mux_recording,
    probe_duration,
)


def _make_video_capture(source: VideoSource, fps: int) -> VideoCapture:
    """Crea el backend de captura de video según el sistema operativo y la fuente."""
    if sys.platform == "win32":
        # Ventana -> Windows.Graphics.Capture (capta contenido GPU, p. ej. Teams).
        if source.kind == "window" and source.hwnd:
            from app.capture.windows_video import WindowsGraphicsCapture

            return WindowsGraphicsCapture(source, fps=fps)
        # Pantalla completa -> WGC del monitor (GPU; gdigrab por CPU no alcanza
        # los 30 fps en monitores grandes), con respaldo automático a gdigrab.
        from app.capture.windows_video import WindowsScreenCapture

        return WindowsScreenCapture(source, fps=fps)
    raise NotImplementedError(
        "La captura de video solo está implementada en Windows (Fase 1). "
        "macOS y Linux están en el roadmap."
    )


class Recorder:
    """Controlador de alto nivel de una grabación."""

    def __init__(
        self,
        on_status: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
    ):
        self._on_status = on_status or (lambda _msg: None)
        self._on_finished = on_finished or (lambda _path: None)
        self._on_error = on_error or (lambda _msg: None)
        self._on_progress = on_progress or (lambda _pct: None)

        self._clock = MasterClock()
        self._video: Optional[VideoCapture] = None
        self._system_audio = None  # SystemAudioCapture del tramo actual
        self._mic = None           # MicCapture (persiste entre pausas)

        self._settings: Optional[RecordingSettings] = None
        self._temp_dir: Optional[str] = None
        self._video_segments: List[str] = []
        self._system_segments: List[Tuple[str, int]] = []  # (ruta, tramo)
        self._current_mic_device: Optional[AudioDevice] = None
        self._cycle = 0  # contador de tramos (sube en cada reanudación)

        self._recording = False
        self._paused = False
        self._mic_muted = False

    # --- estado / métricas para la UI ---------------------------------------
    def is_recording(self) -> bool:
        return self._recording

    def is_paused(self) -> bool:
        return self._paused

    def elapsed_seconds(self) -> float:
        if not self._recording:
            return 0.0
        return self._clock.recorded_now()

    def system_level(self) -> float:
        return self._system_audio.current_level() if self._system_audio else 0.0

    def mic_level(self) -> float:
        return self._mic.current_level() if self._mic else 0.0

    def current_video_frame(self):
        """Último fotograma del video (BGRA ndarray) si el backend lo expone (WGC)."""
        cap = self._video
        if cap is not None and hasattr(cap, "latest_frame"):
            try:
                return cap.latest_frame()
            except Exception:
                return None
        return None

    # --- ciclo de vida ------------------------------------------------------
    def start(self, settings: RecordingSettings) -> None:
        if self._recording:
            raise RuntimeError("Ya hay una grabación en curso.")

        from app.capture.windows_audio import MicCapture

        settings.output_dir.mkdir(parents=True, exist_ok=True)
        self._settings = settings
        self._temp_dir = tempfile.mkdtemp(prefix="recsess_")
        self._video_segments = []
        self._system_segments = []
        self._cycle = 0
        self._current_mic_device = settings.mic_device

        self._mic = MicCapture(self._temp_dir)
        self._clock.reset()
        try:
            self._open_video_segment()
            if settings.capture_system_audio:
                self._open_system_segment()
            self._mic.start(settings.mic_device, cycle=0)
            self._mic.set_muted(self._mic_muted)
        except Exception as exc:
            self._stop_current_captures()
            if self._mic is not None:
                self._mic.stop()
            self._cleanup_temp()
            raise RuntimeError(f"No se pudo iniciar la grabación: {exc}") from exc

        self._recording = True
        self._paused = False
        self._on_status("Grabando…")

    def pause(self) -> None:
        if not self._recording or self._paused:
            return
        self._clock.pause()          # congela el tiempo grabado
        self._stop_current_captures()
        if self._mic is not None:
            self._mic.switch_device(None)  # cierra el segmento de mic actual
        self._paused = True
        self._on_status("Pausado")

    def resume(self) -> None:
        if not self._recording or not self._paused:
            return
        self._clock.resume()
        self._cycle += 1
        try:
            self._open_video_segment()
            if self._settings and self._settings.capture_system_audio:
                self._open_system_segment()
            if self._mic is not None:
                self._mic.switch_device(self._current_mic_device, cycle=self._cycle)
        except Exception as exc:
            self._on_status(f"No se pudo reanudar: {exc}")
            return
        self._paused = False
        self._on_status("Grabando…")

    def stop(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self._paused = False
        self._on_status("Procesando la grabación…")
        self._stop_current_captures()
        if self._mic is not None:
            self._mic.stop()
        threading.Thread(target=self._finalize, daemon=True).start()

    def change_mic(self, device: Optional[AudioDevice]) -> None:
        """Cambia el micrófono EN CALIENTE durante la grabación (o lo apaga con None)."""
        if not self._recording or self._mic is None:
            return
        self._current_mic_device = device
        if self._paused:
            return  # se aplicará al reanudar
        try:
            self._mic.switch_device(device)
            self._mic.set_muted(self._mic_muted)
        except Exception as exc:
            self._on_status(f"No se pudo cambiar el micrófono: {exc}")

    def set_mic_muted(self, muted: bool) -> None:
        """Silencia/activa el micrófono (graba silencio mientras está muteado)."""
        self._mic_muted = muted
        if self._mic is not None:
            self._mic.set_muted(muted)

    def is_mic_muted(self) -> bool:
        return self._mic_muted

    # --- apertura de segmentos ---------------------------------------------
    def _open_video_segment(self) -> None:
        assert self._settings is not None and self._temp_dir is not None
        path = os.path.join(self._temp_dir, f"video_seg{self._cycle}.mkv")
        cap = _make_video_capture(self._settings.video_source, self._settings.fps)
        cap.start(path)
        self._video = cap
        self._video_segments.append(path)

    def _open_system_segment(self) -> None:
        from app.capture.windows_audio import SystemAudioCapture

        assert self._temp_dir is not None
        path = os.path.join(self._temp_dir, f"system_seg{self._cycle}.wav")
        cap = SystemAudioCapture()
        cap.start(path)
        self._system_audio = cap
        self._system_segments.append((path, self._cycle))

    # --- internos -----------------------------------------------------------
    def _stop_current_captures(self) -> None:
        for cap in (self._system_audio, self._video):
            if cap is not None:
                try:
                    cap.stop()
                except Exception:
                    pass
        self._video = None
        self._system_audio = None

    def _finalize(self) -> None:
        assert self._settings is not None and self._temp_dir is not None
        try:
            # 1) Duración real de cada tramo de video y su inicio en el video unido.
            video_durs = [probe_duration(p) for p in self._video_segments]
            cycle_start = []  # inicio (s) de cada tramo en el video concatenado
            acc = 0.0
            for d in video_durs:
                cycle_start.append(acc)
                acc += d

            # 2) Unir los tramos de video (si hubo pausas).
            video_final = os.path.join(self._temp_dir, "video_final.mkv")
            video_final = concat_videos(self._video_segments, video_final)

            # 3) Pistas de audio, alineadas POR EL FINAL de cada tramo: como todos
            #    los flujos se detienen a la vez, el audio (que arranca un poco más
            #    tarde que el video) se coloca de modo que su FIN coincida con el fin
            #    del tramo de video. Esto autocorrige la latencia de arranque.
            tracks: List[Track] = []
            tracks += self._build_system_track(video_durs, cycle_start)
            tracks += self._build_mic_track(video_durs, cycle_start)
            total_seconds = sum(video_durs)

            # Cancelación de eco INTEGRADA: se limpia el micrófono ANTES del mux,
            # así el video se procesa una sola vez (no se re-multiplexa después).
            if self._settings.reduce_echo:
                tracks = self._apply_aec_to_tracks(tracks)

            stem = recording_stem(self._settings.video_source)
            out_path = str(self._settings.output_dir / f"{stem}.mp4")

            self._on_status("Guardando…")
            mux_recording(
                video_path=video_final,
                tracks=tracks,
                output_path=out_path,
                sample_rate=self._settings.sample_rate,
                total_seconds=total_seconds,
                progress_cb=self._on_progress,
            )

            self._on_status("Listo")
            self._on_finished(out_path)
        except Exception as exc:
            self._on_error(str(exc))
        finally:
            self._cleanup_temp()

    def _apply_aec_to_tracks(self, tracks: List[Track]) -> List[Track]:
        """Reemplaza la pista de micrófono por una sin eco (usando el sistema como
        referencia). Procesa SOLO audio (rápido), antes del mux de video."""
        sys_track = next((t for t in tracks if t.label == "Sistema" and t.segments), None)
        mic_track = next((t for t in tracks if t.label == "Microfono" and t.segments), None)
        if not sys_track or not mic_track:
            return tracks
        self._on_status("Reduciendo eco…")
        try:
            from app.encode.aec import _read_wav_mono, _write_wav_mono, cancel_echo
            from app.encode.ffmpeg import render_track_mono_wav

            assert self._temp_dir is not None
            sys_wav = os.path.join(self._temp_dir, "aec_sys.wav")
            mic_wav = os.path.join(self._temp_dir, "aec_mic.wav")
            clean_wav = os.path.join(self._temp_dir, "aec_clean.wav")
            render_track_mono_wav(sys_track, sys_wav, 16_000)
            render_track_mono_wav(mic_track, mic_wav, 16_000)
            ref, _ = _read_wav_mono(sys_wav)
            mic, _ = _read_wav_mono(mic_wav)
            cleaned = cancel_echo(mic, ref)
            _write_wav_mono(clean_wav, cleaned, 16_000)
            # La pista limpia es un único segmento ya alineado (offset 0).
            return [
                Track("Microfono", [Segment(clean_wav, 0.0)]) if t.label == "Microfono" else t
                for t in tracks
            ]
        except Exception as exc:
            self._on_status(f"Aviso: no se pudo reducir el eco ({exc})")
            return tracks

    def _build_system_track(self, video_durs, cycle_start) -> List[Track]:
        segs = []
        for path, cycle in self._system_segments:
            if not os.path.exists(path) or cycle >= len(video_durs):
                continue
            da = probe_duration(path)
            offset = max(0.0, cycle_start[cycle] + video_durs[cycle] - da)
            segs.append(Segment(path, offset))
        return [Track("Sistema", segs)] if segs else []

    def _build_mic_track(self, video_durs, cycle_start) -> List[Track]:
        if self._mic is None:
            return []
        # Agrupar los segmentos de micrófono por tramo, en orden.
        groups: "OrderedDict[int, List[str]]" = OrderedDict()
        for path, cycle in self._mic.segments():
            if os.path.exists(path) and cycle < len(video_durs):
                groups.setdefault(cycle, []).append(path)

        segs = []
        for cycle, paths in groups.items():
            durs = [probe_duration(p) for p in paths]
            block = sum(durs)
            # El bloque (contiguo) de micrófono termina junto con el video del tramo.
            running = max(0.0, cycle_start[cycle] + video_durs[cycle] - block)
            for p, d in zip(paths, durs):
                segs.append(Segment(p, running))
                running += d
        return [Track("Microfono", segs)] if segs else []

    def _cleanup_temp(self) -> None:
        if self._temp_dir and os.path.isdir(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None

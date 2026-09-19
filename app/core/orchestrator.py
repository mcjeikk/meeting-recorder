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
3. `stop()` cierra todo y, en un HILO de fondo, concatena + multiplexa el MP4
   a una ruta local corta; solo entonces copia al destino del usuario. Si el
   guardado falla, la sesión NO se borra (`on_save_failed`).

Resultados por callbacks: `on_status`, `on_finished`, `on_error`.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from app.capture.base import VideoCapture
from app.core.clock import MasterClock
from app.core.config import AudioDevice, RecordingSettings, VideoSource, recording_stem
from app.core.output_path import (
    PendingSave,
    clear_pending,
    copy_mp4_verified,
    dest_file_path,
    ffmpeg_path_too_long,
    new_session_dir,
    session_has_media,
    staging_mp4_path,
    write_pending,
    load_pending,
)
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
        on_save_failed: Optional[Callable[[str], None]] = None,
    ):
        self._on_status = on_status or (lambda _msg: None)
        self._on_finished = on_finished or (lambda _path: None)
        self._on_error = on_error or (lambda _msg: None)
        self._on_progress = on_progress or (lambda _pct: None)
        # Fallo al guardar: la sesión SIGUE en disco. Distinto de on_error de arranque.
        self._on_save_failed = on_save_failed or on_error or (lambda _msg: None)

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

        self._staging_mp4: Optional[str] = None
        self._stem: Optional[str] = None
        self._video_final: Optional[str] = None
        self._tracks: List[Track] = []
        self._total_seconds: float = 0.0

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

        try:
            settings.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # La carpeta de destino puede ser inutilizable (ruta larga, sin permiso).
            # Igual grabamos a LOCALAPPDATA; al detener se pedirá una carpeta válida.
            pass
        self._settings = settings
        self._temp_dir = new_session_dir()
        self._staging_mp4 = None
        self._stem = None
        self._video_final = None
        self._tracks = []
        self._total_seconds = 0.0
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
            if not session_has_media(self._temp_dir or ""):
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

    def has_unsaved_session(self) -> bool:
        if self._staging_mp4 and os.path.isfile(self._staging_mp4) and os.path.getsize(self._staging_mp4) > 0:
            return True
        return bool(self._temp_dir) and session_has_media(self._temp_dir)

    def _remember_pending(self, intended: str) -> None:
        write_pending(
            PendingSave(
                temp_dir=self._temp_dir or "",
                staging_mp4=self._staging_mp4 or "",
                intended_dest=intended,
                stem=self._stem or "",
            )
        )

    def _mux_to_staging(self) -> str:
        assert self._video_final is not None
        assert self._stem is not None
        staging = staging_mp4_path(self._stem)
        if ffmpeg_path_too_long(staging):
            raise RuntimeError(
                f"La ruta local de trabajo también es demasiado larga:\n{staging}"
            )
        self._on_status("Guardando…")
        mux_recording(
            video_path=self._video_final,
            tracks=self._tracks,
            output_path=str(staging),
            sample_rate=self._settings.sample_rate if self._settings else 48_000,
            total_seconds=self._total_seconds,
            progress_cb=self._on_progress,
        )
        if not os.path.isfile(staging) or os.path.getsize(staging) <= 0:
            raise RuntimeError("FFmpeg no dejó un MP4 de trabajo usable.")
        self._staging_mp4 = str(staging)
        return self._staging_mp4

    def _deliver_to(self, output_dir: Path) -> str:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_file_path(output_dir, self._stem or "Grabacion")
        if not (self._staging_mp4 and os.path.isfile(self._staging_mp4) and os.path.getsize(self._staging_mp4) > 0):
            staging = self._mux_to_staging()
        else:
            staging = self._staging_mp4
        copy_mp4_verified(Path(staging), dest)
        return str(dest)

    def adopt_pending(self, pending: PendingSave) -> None:
        """Retoma una sesión persistida (p. ej. tras reiniciar la app)."""
        self._temp_dir = pending.temp_dir or None
        self._staging_mp4 = pending.staging_mp4 or None
        if self._staging_mp4 and not os.path.isfile(self._staging_mp4):
            self._staging_mp4 = None
        self._stem = pending.stem or "Grabacion"
        if self._temp_dir and os.path.isdir(self._temp_dir):
            segs = sorted(Path(self._temp_dir).glob("video_seg*.mkv"))
            self._video_segments = [str(p) for p in segs]

    def retry_save(self, output_dir: Path) -> None:
        """Reintenta copiar (o mux + copiar) a una carpeta que eligió el usuario."""
        try:
            if not self._stem or not (self._staging_mp4 or self._temp_dir):
                pending = load_pending()
                if pending is not None:
                    self.adopt_pending(pending)
            if self._settings is not None:
                self._settings.output_dir = Path(output_dir)
            elif self._settings is None:
                from app.core.config import VideoSource as _VS

                self._settings = RecordingSettings(
                    video_source=_VS(kind="screen", monitor_index=1, is_primary=True),
                    mic_device=None,
                    output_dir=Path(output_dir),
                )
            if not (self._staging_mp4 and os.path.isfile(self._staging_mp4)):
                if not self._video_final or not os.path.isfile(self._video_final):
                    if not self._video_segments:
                        raise RuntimeError("No hay segmentos de video para reconstruir el MP4.")
                    video_final = os.path.join(self._temp_dir or "", "video_final.mkv")
                    self._video_final = concat_videos(self._video_segments, video_final)
                    video_durs = [probe_duration(p) for p in self._video_segments]
                    cycle_start = []
                    acc = 0.0
                    for d in video_durs:
                        cycle_start.append(acc)
                        acc += d
                    tracks: List[Track] = []
                    tracks += self._build_system_track(video_durs, cycle_start)
                    tracks += self._build_mic_track(video_durs, cycle_start)
                    if not tracks and self._temp_dir:
                        from app.encode.ffmpeg import Segment, Track as _Trk

                        sys_files = sorted(Path(self._temp_dir).glob("system_seg*.wav"))
                        mic_files = sorted(Path(self._temp_dir).glob("mic_seg_*.wav"))
                        if sys_files:
                            tracks.append(
                                _Trk("Sistema", [Segment(str(p), 0.0) for p in sys_files])
                            )
                        if mic_files:
                            tracks.append(
                                _Trk("Microfono", [Segment(str(p), 0.0) for p in mic_files])
                            )
                    self._tracks = tracks
                    self._total_seconds = sum(video_durs)
            intended = str(dest_file_path(Path(output_dir), self._stem or "Grabacion"))
            self._remember_pending(intended)
            dest = self._deliver_to(Path(output_dir))
            self._finish_success(dest)
        except Exception as exc:
            self._remember_pending(str(Path(output_dir) / f"{self._stem or 'Grabacion'}.mp4"))
            self._on_save_failed(
                "No se pudo guardar en esa carpeta.\n\n"
                f"{exc}\n\n"
                "Los archivos de la grabación NO se han borrado. Elige otra carpeta."
            )

    def _finish_success(self, dest: str) -> None:
        clear_pending()
        self._on_status("Listo")
        self._on_finished(dest)
        self._cleanup_temp()
        self._cleanup_staging()

    def _cleanup_staging(self) -> None:
        if self._staging_mp4 and os.path.isfile(self._staging_mp4):
            try:
                os.remove(self._staging_mp4)
            except OSError:
                pass
        self._staging_mp4 = None

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
            self._video_final = concat_videos(self._video_segments, video_final)

            # 3) Pistas de audio, alineadas POR EL FINAL de cada tramo: como todos
            #    los flujos se detienen a la vez, el audio (que arranca un poco más
            #    tarde que el video) se coloca de modo que su FIN coincida con el fin
            #    del tramo de video. Esto autocorrige la latencia de arranque.
            tracks: List[Track] = []
            tracks += self._build_system_track(video_durs, cycle_start)
            tracks += self._build_mic_track(video_durs, cycle_start)
            self._tracks = tracks
            self._total_seconds = sum(video_durs)

            # Cancelación de eco INTEGRADA: se limpia el micrófono ANTES del mux,
            # así el video se procesa una sola vez (no se re-multiplexa después).
            if self._settings.reduce_echo:
                self._tracks = self._apply_aec_to_tracks(self._tracks)

            self._stem = recording_stem(self._settings.video_source)
            intended = str(dest_file_path(self._settings.output_dir, self._stem))
            self._remember_pending(intended)

            self._mux_to_staging()
            dest = self._deliver_to(self._settings.output_dir)
            self._finish_success(dest)
        except Exception as exc:
            intended = ""
            if self._settings is not None and self._stem:
                intended = str(dest_file_path(self._settings.output_dir, self._stem))
            self._remember_pending(intended)
            if self.has_unsaved_session():
                self._on_save_failed(
                    "No se pudo guardar el archivo de la grabación.\n\n"
                    f"{exc}\n\n"
                    "Los archivos NO se han borrado. Elige una carpeta de salida "
                    "(mejor una ruta corta: Escritorio o Videos)."
                )
            else:
                self._on_error(str(exc))

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

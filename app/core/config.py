"""Configuración de la aplicación y parámetros de una grabación.

Aquí viven dos cosas:
- `RecordingSettings`: lo que el usuario elige para UNA grabación (fuente, mic, etc.).
- `AppConfig`: preferencias persistentes (p. ej. la última carpeta de salida),
  guardadas en un JSON en la carpeta del usuario.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# --- Parámetros técnicos por defecto (estables para Windows) -----------------
DEFAULT_FPS = 30
DEFAULT_SAMPLE_RATE = 48_000          # 48 kHz: estándar de video; evita resampleos extra
DEFAULT_VIDEO_BITRATE = "8M"           # razonable para 1080p/30


def default_output_dir() -> Path:
    """Carpeta de salida por defecto: ~/Videos/Grabaciones (o ~/Grabaciones)."""
    videos = Path.home() / "Videos"
    base = videos if videos.exists() else Path.home()
    out = base / "Grabaciones"
    return out


def default_transcriptor_dir() -> str:
    """Mejor estimación de la carpeta del proyecto Transcriptor.

    El Transcriptor vive junto al Recorder (Apps/Transcriptor). Se prueba también
    la ubicación antigua (Proyectos/Transcriptor) por compatibilidad. Si no está
    en ninguna, se devuelve cadena vacía y el usuario puede fijar la ruta en
    config.json.
    """
    recorder_root = Path(__file__).resolve().parents[2]
    candidatos = (
        recorder_root.parent / "Transcriptor",          # Apps/Transcriptor (actual)
        recorder_root.parent.parent / "Transcriptor",   # Proyectos/Transcriptor (legado)
    )
    for candidato in candidatos:
        if (candidato / "transcribe.py").exists():
            return str(candidato)
    return ""


@dataclass
class VideoSource:
    """Describe QUÉ se va a grabar en video."""
    kind: str                 # "screen" (pantalla completa) | "window" (una ventana)
    title: str = ""           # título de la ventana (si kind == "window") o etiqueta de monitor
    hwnd: Optional[int] = None  # handle de ventana en Windows (opcional)
    monitor_index: Optional[int] = None  # 1-based WGC index (si kind == "screen")
    is_primary: bool = False

    @property
    def label(self) -> str:
        if self.kind == "screen":
            n = self.monitor_index or 1
            base = f"Pantalla {n}"
            if self.is_primary:
                base += " (principal)"
            return base
        return f"Ventana: {self.title}"


@dataclass
class AudioDevice:
    """Describe un dispositivo de entrada de audio (p. ej. un micrófono)."""
    index: int
    name: str
    channels: int = 1
    sample_rate: int = DEFAULT_SAMPLE_RATE


@dataclass
class RecordingSettings:
    """Todo lo necesario para iniciar una grabación."""
    video_source: VideoSource
    mic_device: Optional[AudioDevice]      # None = sin micrófono
    capture_system_audio: bool = True
    reduce_echo: bool = False              # cancelar el eco del sistema en el micrófono
    output_dir: Path = field(default_factory=default_output_dir)
    fps: int = DEFAULT_FPS
    sample_rate: int = DEFAULT_SAMPLE_RATE


# --- Configuración persistente -----------------------------------------------
def _config_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "MeetingRecorder"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


@dataclass
class AppConfig:
    """Preferencias que se recuerdan entre sesiones."""
    output_dir: str = ""
    capture_system_audio: bool = True
    reduce_echo: bool = False
    last_mic_name: str = ""
    # --- Transcripción ---
    transcribe_after_recording: bool = False
    transcription_language: str = "es"        # código ISO o "auto"
    transcription_preset: str = "equilibrado"  # rapido|equilibrado|maxima_calidad
    transcriptor_dir: str = field(default_factory=default_transcriptor_dir)
    pause_transcription_while_recording: bool = True  # suspender el proceso al grabar

    @classmethod
    def load(cls) -> "AppConfig":
        from app.transcription.jobs import normalize_language
        from app.transcription.presets import normalize_preset

        path = _config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cfg = cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
                cfg.transcription_preset = normalize_preset(cfg.transcription_preset)
                cfg.transcription_language = normalize_language(cfg.transcription_language)
                return cfg
            except Exception:
                pass  # config corrupta -> usar valores por defecto
        cfg = cls(output_dir=str(default_output_dir()))
        return cfg

    def save(self) -> None:
        from app.transcription.jobs import normalize_language
        from app.transcription.presets import normalize_preset

        try:
            self.transcription_preset = normalize_preset(self.transcription_preset)
            self.transcription_language = normalize_language(self.transcription_language)
            _config_path().write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass  # no es crítico si falla

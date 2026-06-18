"""Preprocesamiento de audio: convierte cualquier formato a WAV mono 16 kHz con ffmpeg."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Extensiones de audio/vídeo que intentaremos procesar.
AUDIO_EXTS = {
    ".m4a", ".mp3", ".wav", ".flac", ".ogg", ".opus", ".aac",
    ".wma", ".mp4", ".m4b", ".mkv", ".webm", ".mov", ".avi",
}


def ffmpeg_disponible() -> bool:
    """True si 'ffmpeg' está disponible en el PATH."""
    return shutil.which("ffmpeg") is not None


def asegurar_ffmpeg() -> None:
    if not ffmpeg_disponible():
        raise RuntimeError(
            "No se encontró 'ffmpeg' en el PATH.\n"
            "Instálalo con:  winget install Gyan.FFmpeg   (o:  choco install ffmpeg)\n"
            "y vuelve a abrir la terminal."
        )


def convertir_a_wav16k(origen: Path, destino_dir: Path) -> Path:
    """Convierte `origen` (m4a/mp3/...) a WAV mono 16 kHz dentro de `destino_dir`.

    Devuelve la ruta del WAV generado. 16 kHz mono es el formato que esperan
    tanto faster-whisper como pyannote.
    """
    asegurar_ffmpeg()
    origen = Path(origen)
    destino_dir = Path(destino_dir)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"{origen.stem}_16k.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(origen),
        "-vn",              # ignora pista de vídeo si la hay
        "-ac", "1",         # mono
        "-ar", "16000",     # 16 kHz
        "-loglevel", "error",
        str(destino),
    ]
    subprocess.run(cmd, check=True)
    return destino

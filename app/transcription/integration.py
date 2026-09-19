"""Integración con el proyecto Transcriptor (Fase 2).

El Transcriptor (faster-whisper + pyannote) vive en su propia carpeta con su
propio .venv. Este módulo NO importa nada de él: lo invoca como subproceso con
su intérprete, así los dos proyectos conservan sus dependencias intactas.

Piezas:
- `extract_audio_for_transcription()`: el MP4 del grabador tiene PISTAS de
  audio separadas (Sistema / Microfono / Mezcla). El conversor del Transcriptor
  no usa `-map`, y ante varias pistas ffmpeg elegiría solo una (se perdería la
  voz del usuario). Aquí se extrae la pista correcta — "Mezcla" identificada
  por su metadato de título — a WAV mono 16 kHz antes de invocar.
- `build_command()`: línea de comandos SIEMPRE como lista de argumentos (las
  rutas de OneDrive llevan espacios; nada de shell=True).
- `transcribe()`: envoltorio síncrono de cortesía para scripts/verificación.
  La app NO lo usa: usa el worker asíncrono (app/transcription/worker.py).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from app.encode.ffmpeg import get_ffmpeg_exe
from app.transcription.pc_impact import (
    BELOW_NORMAL_PRIORITY,
    DEFAULT_PC_IMPACT,
    priority_class,
    thread_env,
    threads_for_impact,
)

# En Windows, evita ventanas de consola. La prioridad del CLI de transcripción
# la elige Uso del PC (usable → IDLE; full → BELOW_NORMAL). ffmpeg de extracción
# sigue en BELOW_NORMAL (corta).
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
BELOW_NORMAL = BELOW_NORMAL_PRIORITY


# --- Ubicaciones ---------------------------------------------------------------
def transcripts_base() -> Path:
    """Carpeta de trabajo de la integración: %LOCALAPPDATA%/MeetingRecorder/transcripts.

    LOCALAPPDATA (no APPDATA/roaming, no OneDrive): aquí van la cola de trabajos,
    los logs y los WAV temporales — nada de esto debe sincronizarse.
    """
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "MeetingRecorder" / "transcripts"


def transcriptor_paths(transcriptor_dir: str) -> Tuple[Path, Path]:
    """(python.exe del venv del Transcriptor, ruta de transcribe.py)."""
    root = Path(transcriptor_dir)
    return root / ".venv" / "Scripts" / "python.exe", root / "transcribe.py"


def is_available(transcriptor_dir: Optional[str] = None) -> bool:
    """True si el proyecto Transcriptor está donde se espera, con su venv."""
    if not transcriptor_dir:
        from app.core.config import default_transcriptor_dir
        transcriptor_dir = default_transcriptor_dir()
    if not transcriptor_dir:
        return False
    py, script = transcriptor_paths(transcriptor_dir)
    return py.exists() and script.exists()


TRANSCRIPTION_AVAILABLE = is_available()


# --- Inspección y extracción de pistas de audio ---------------------------------
_STREAM_RE = re.compile(r"^Stream #0:\d+(?:\[[^\]]*\])?(?:\([^)]*\))?: (\w+)")
_TITLE_RE = re.compile(r"^(title|handler_name)\s*:\s*(.+)$")

# Valores por defecto del muxer que NO son un nombre de pista real.
_GENERIC_HANDLERS = {"soundhandler", "videohandler", "core media audio", "core media video"}


def list_audio_streams(media: Path) -> List[dict]:
    """Pistas de audio del archivo: [{"ordinal": n, "title": "Mezcla"}, ...].

    `ordinal` es el índice ENTRE pistas de audio (lo que espera `-map 0:a:N`).
    Se parsea el stderr de `ffmpeg -i` (imageio-ffmpeg no trae ffprobe), igual
    que hace `probe_duration` en app/encode/ffmpeg.py. El nombre se toma de
    `title` o de `handler_name` (en MP4 el título de pista vive en el átomo
    hdlr; los valores genéricos tipo "SoundHandler" se ignoran).
    """
    proc = subprocess.run(
        [get_ffmpeg_exe(), "-hide_banner", "-i", str(media)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW,
    )
    text = proc.stderr.decode("utf-8", "replace")

    streams: List[dict] = []
    current: Optional[dict] = None
    for raw in text.splitlines():
        line = raw.strip()
        m = _STREAM_RE.match(line)
        if m:
            if m.group(1) == "Audio":
                current = {"ordinal": len(streams), "title": ""}
                streams.append(current)
            else:
                current = None
            continue
        if current is not None:
            t = _TITLE_RE.match(line)
            if t and not current["title"]:
                valor = t.group(2).strip()
                if valor.lower() not in _GENERIC_HANDLERS:
                    current["title"] = valor
    return streams


def _choose_audio_args(streams: List[dict]) -> Tuple[List[str], str]:
    """Argumentos ffmpeg para quedarse con el audio completo de la reunión.

    Prioridad: pista titulada "Mezcla" (todo: sistema + micrófono) > única
    pista > mezclar todas con amix (caso sin títulos o formato inesperado).
    """
    if not streams:
        raise RuntimeError("El archivo no tiene pistas de audio")
    for s in streams:
        if s["title"].lower() == "mezcla":
            return ["-map", f"0:a:{s['ordinal']}"], f"pista 'Mezcla' (0:a:{s['ordinal']})"
    if len(streams) == 1:
        return ["-map", "0:a:0"], "única pista de audio"
    entradas = "".join(f"[0:a:{s['ordinal']}]" for s in streams)
    filtro = f"{entradas}amix=inputs={len(streams)}:normalize=0[aout]"
    return ["-filter_complex", filtro, "-map", "[aout]"], f"mezcla amix de {len(streams)} pistas"


def extract_audio_for_transcription(
    media: Path, work_dir: Path, attempts: int = 3, retry_wait: float = 5.0
) -> Tuple[Path, str]:
    """Extrae el audio de la reunión a WAV mono 16 kHz (formato que espera el ASR).

    Devuelve (ruta_wav, descripción de la pista usada). Reintenta con espera:
    OneDrive o el antivirus pueden tener el MP4 con un handle abierto justo
    después de guardarse.
    """
    media = Path(media)
    work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / (media.stem + ".wav")

    last_err = ""
    for intento in range(attempts):
        if intento:
            time.sleep(retry_wait)
        streams = list_audio_streams(media)
        try:
            map_args, desc = _choose_audio_args(streams)
        except RuntimeError as e:
            last_err = str(e)
            continue
        args = [
            get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(media), *map_args,
            "-vn", "-sn",
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out),
        ]
        proc = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=NO_WINDOW | BELOW_NORMAL,
        )
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 44:
            return out, desc
        last_err = proc.stderr.decode("utf-8", "replace").strip()[-500:]
    raise RuntimeError(f"No se pudo extraer el audio de {media.name}: {last_err}")


# --- Invocación del Transcriptor -------------------------------------------------
def build_command(
    transcriptor_dir: str,
    wav: Path | Sequence[Path],
    language: str,
    out_dir: Path,
    extra_args: Tuple[str, ...] = (),
) -> List[str]:
    """Línea de comandos para transcribir uno o más WAV con el CLI hermano.

    Varios WAV en el mismo argv = una sola carga de modelos. --output absoluta.
    """
    py, script = transcriptor_paths(transcriptor_dir)
    if isinstance(wav, (str, Path)):
        wavs = [Path(wav)]
    else:
        wavs = [Path(w) for w in wav]
    return [
        str(py), "-u", "-X", "utf8", str(script),
        *[str(w) for w in wavs],
        "--language", language, "--output", str(out_dir), *extra_args,
    ]


def subprocess_env(pc_impact: object = DEFAULT_PC_IMPACT) -> dict:
    """Entorno del CLI: modo plano, UTF-8, y tope de hilos OpenMP/torch."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["TRANSCRIPTOR_PLAIN"] = "1"
    env.update(thread_env(pc_impact))
    return env


def cpu_threads_for_job(
    pc_impact: object = DEFAULT_PC_IMPACT, *, cpu_count: Optional[int] = None
) -> int:
    """Hilos ASR + diarización según Uso del PC (no solo cpu-2)."""
    return threads_for_impact(pc_impact, cpu_count=cpu_count)


def creationflags_for_job(pc_impact: object = DEFAULT_PC_IMPACT) -> int:
    return NO_WINDOW | priority_class(pc_impact)


def _absolute_media(media: Path) -> Path:
    path = Path(media).expanduser()
    try:
        return path.resolve()
    except OSError:
        return path if path.is_absolute() else Path.cwd() / path


def _resolved_output_base(output_base: object = None) -> Optional[Path]:
    if output_base is None:
        return None
    text = str(output_base).strip()
    if not text:
        return None
    return _absolute_media(Path(text))


def output_dir_for(media: Path, output_base: object = None) -> Path:
    """Carpeta Transcripciones visible (absoluta) para el CLI `--output`.

    Si hay `output_base` (Carpeta de salida al encolar), los resultados van ahí.
    Si no (jobs viejos / reuniones cuyo MP4 ya vive en esa carpeta), se usa el
    padre del media. Relativa acaba DENTRO del Transcriptor: siempre absoluta.
    """
    base = _resolved_output_base(output_base)
    if base is not None:
        return base / "Transcripciones"
    return _absolute_media(media).parent / "Transcripciones"


def result_dir_for(media: Path, output_base: object = None) -> Path:
    """Carpeta final: <destino>/Transcripciones/<stem>/."""
    media = _absolute_media(media)
    return output_dir_for(media, output_base=output_base) / media.stem


def transcript_exists(media_path: object, output_base: object = None) -> bool:
    """¿Ya hay transcripción de este archivo en el destino? (spec 023)

    Al podar el histórico, el registro `done` deja de ser quien recuerda que un
    archivo ya se transcribió: lo recuerda el disco. Se mira `transcripcion.txt`,
    el mismo artefacto con el que el worker decide el éxito. Si el destino no se
    puede consultar, se responde que NO existe: repetir trabajo es aceptable,
    perder una transcripción no.
    """
    try:
        return (
            result_dir_for(Path(str(media_path)), output_base=output_base)
            / "transcripcion.txt"
        ).is_file()
    except OSError:
        return False


def transcribe(media_path: str, language: Optional[str] = "es") -> str:
    """Transcribe un archivo de forma SÍNCRONA y devuelve la ruta del texto.

    Pensado para scripts y verificación (verify_transcription.py); la app usa
    el worker asíncrono. Bloquea durante horas en reuniones largas.
    """
    from app.core.config import AppConfig

    cfg = AppConfig.load()
    if not is_available(cfg.transcriptor_dir):
        raise RuntimeError(
            "No se encontró el proyecto Transcriptor; fija 'transcriptor_dir' en config.json"
        )
    media = Path(media_path)
    wav, _desc = extract_audio_for_transcription(media, transcripts_base() / "work" / media.stem)
    dest = getattr(cfg, "output_dir", None)
    out_dir = output_dir_for(media, output_base=dest)
    impact = getattr(cfg, "transcription_pc_impact", DEFAULT_PC_IMPACT)
    cmd = build_command(
        cfg.transcriptor_dir, wav, language or "es", out_dir,
        extra_args=("--threads", str(cpu_threads_for_job(impact))),
    )
    proc = subprocess.run(
        cmd, cwd=cfg.transcriptor_dir, env=subprocess_env(impact),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=creationflags_for_job(impact),
    )
    result = result_dir_for(media, output_base=dest) / "transcripcion.txt"
    if proc.returncode != 0 or not result.exists():
        salida = proc.stdout.decode("utf-8", "replace")[-800:]
        raise RuntimeError(f"La transcripción falló (exit {proc.returncode}):\n{salida}")
    try:
        wav.unlink()
    except OSError:
        pass
    return str(result)

"""Rutas de guardado: staging corto, destino del usuario, sesión no sincronizada.

El muxer (FFmpeg) falla con "No such file or directory" en rutas Windows >~260
caracteres. La sesión NUNCA se borra hasta que el MP4 de destino existe y
coincide en tamaño con el staging.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# Margen bajo el clásico MAX_PATH (260 con NUL). FFmpeg no usa \\?\ .
SAFE_FFMPEG_PATH = 240
PENDING_NAME = "pending_save.json"


def recorder_data_root() -> Path:
    """%LOCALAPPDATA%/MeetingRecorder — fuera de OneDrive y del Temp del sistema."""
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    root = base / "MeetingRecorder"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sessions_dir() -> Path:
    d = recorder_data_root() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def saves_dir() -> Path:
    d = recorder_data_root() / "saves"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pending_save_path() -> Path:
    return recorder_data_root() / PENDING_NAME


def new_session_dir() -> str:
    """Carpeta recsess_* bajo LOCALAPPDATA (no %TEMP%)."""
    return tempfile.mkdtemp(prefix="recsess_", dir=str(sessions_dir()))


def staging_mp4_path(stem: str) -> Path:
    safe = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in (stem or "Grabacion"))
    if len(safe) > 80:
        safe = safe[:80].rstrip(" .")
    return saves_dir() / f"{safe}.mp4"


def win_long_path(path: Path) -> str:
    """Prefijo \\\\?\\ para que Windows copie más allá de MAX_PATH."""
    raw = str(Path(path))
    if raw.startswith("\\\\?\\"):
        return raw
    abs_path = os.path.abspath(raw)
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abs_path[2:]
    return "\\\\?\\" + abs_path


def path_length(path: Path | str) -> int:
    return len(str(path))


def dest_file_path(output_dir: Path, stem: str) -> Path:
    return Path(output_dir) / f"{stem}.mp4"


def ffmpeg_path_too_long(path: Path | str) -> bool:
    return path_length(path) >= SAFE_FFMPEG_PATH


def folder_looks_unusable(output_dir: Path | str) -> Optional[str]:
    """Mensaje si no se puede usar como carpeta de destino; None si parece usable.

    No exige que el MP4 final quepa en SAFE_FFMPEG_PATH: el mux va a staging.
    Sí exige carpeta no vacía y, si existe, que sea directorio.
    """
    text = str(output_dir or "").strip()
    if not text:
        return "No hay carpeta de salida. Elige una carpeta para guardar la grabación."
    path = Path(text)
    if path.exists() and not path.is_dir():
        return f"La ruta de salida no es una carpeta:\n{path}"
    return None


def session_has_media(session_dir: str | Path) -> bool:
    root = Path(session_dir)
    if not root.is_dir():
        return False
    for p in root.iterdir():
        if p.is_file() and p.suffix.lower() in {".mkv", ".wav", ".mp4"} and p.stat().st_size > 0:
            return True
    return False


def copy_mp4_verified(src: Path, dest: Path) -> Path:
    """Copia src → dest y comprueba tamaño. Crea el directorio destino si hace falta."""
    src = Path(src)
    dest = Path(dest)
    if not src.is_file() or src.stat().st_size <= 0:
        raise OSError(f"No hay archivo de staging para copiar: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_s = win_long_path(src) if os.name == "nt" else str(src)
    dest_s = win_long_path(dest) if os.name == "nt" else str(dest)
    shutil.copy2(src_s, dest_s)
    if not dest.is_file():
        # pathlib puede no ver \\\\?\\ ; comprobar con os.path
        if not os.path.isfile(dest_s) and not os.path.isfile(str(dest)):
            raise OSError(f"La copia no creó el archivo:\n{dest}")
    src_size = src.stat().st_size
    try:
        dest_size = dest.stat().st_size
    except OSError:
        dest_size = os.path.getsize(dest_s)
    if dest_size != src_size or dest_size <= 0:
        raise OSError(
            f"La copia quedó incompleta ({dest_size} bytes, se esperaban {src_size}):\n{dest}"
        )
    return dest


@dataclass
class PendingSave:
    temp_dir: str
    staging_mp4: str
    intended_dest: str
    stem: str
    created: str = ""

    def has_media(self) -> bool:
        if self.staging_mp4 and Path(self.staging_mp4).is_file() and Path(self.staging_mp4).stat().st_size > 0:
            return True
        return session_has_media(self.temp_dir)


def write_pending(pending: PendingSave) -> None:
    if not pending.created:
        pending.created = datetime.now().isoformat(timespec="seconds")
    pending_save_path().write_text(
        json.dumps(asdict(pending), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_pending() -> Optional[PendingSave]:
    path = pending_save_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pending = PendingSave(
            temp_dir=str(data.get("temp_dir") or ""),
            staging_mp4=str(data.get("staging_mp4") or ""),
            intended_dest=str(data.get("intended_dest") or ""),
            stem=str(data.get("stem") or ""),
            created=str(data.get("created") or ""),
        )
    except Exception:
        return None
    if not pending.has_media():
        return None
    return pending


def clear_pending() -> None:
    path = pending_save_path()
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass

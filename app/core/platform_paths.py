"""Dónde guarda la app sus cosas en cada sistema operativo (spec 030).

Windows separa preferencias (%APPDATA%, roaming) de datos de trabajo
(%LOCALAPPDATA%: cola, logs, sesiones, WAV): estos últimos no deben
sincronizarse. macOS no tiene esa distinción: todo va a
~/Library/Application Support/MeetingRecorder, que no sincroniza nada por
defecto. Las variables de entorno se leen en cada llamada, como siempre: los
sandboxes de verificación y los tests las cambian sobre la marcha.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "MeetingRecorder"


def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"


def _mac_support_root() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_DIR_NAME


def config_dir() -> Path:
    """Carpeta de config.json (no se crea aquí)."""
    if is_macos():
        return _mac_support_root()
    return Path(os.environ.get("APPDATA", Path.home())) / APP_DIR_NAME


def local_dir() -> Path:
    """Datos de trabajo que NO se sincronizan (no se crea aquí)."""
    if is_macos():
        return _mac_support_root()
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / APP_DIR_NAME


def cache_dir() -> Path:
    """Descargas re-obtenibles (paquetes del motor). Se puede borrar sin perder nada."""
    if is_macos():
        return Path.home() / "Library" / "Caches" / APP_DIR_NAME
    return local_dir() / "cache"


def engine_dir() -> Path:
    """Motor de transcripción instalado por la propia app (macOS, spec 030)."""
    return local_dir() / "engine"


def venv_python(venv_root: Path) -> Path:
    """Intérprete de un venv: Scripts\\python.exe en Windows, bin/python en el resto."""
    if is_windows():
        return Path(venv_root) / "Scripts" / "python.exe"
    return Path(venv_root) / "bin" / "python"

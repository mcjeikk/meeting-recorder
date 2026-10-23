# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: "Grabador de Reuniones.app" para macOS Apple Silicon (spec 030).
# Se construye con packaging/macos/build.sh (que define MR_UV_BIN y MR_VERSION).
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]
APP_NAME = "Grabador de Reuniones"
BUNDLE_ID = "com.mcjeikk.meetingrecorder"
VERSION = os.environ.get("MR_VERSION", "0.1.0")
UV_BIN = os.environ.get("MR_UV_BIN", "")
ICON = os.environ.get("MR_ICNS", "")

# El código del Transcriptor viaja con la app y se copia al motor en el primer
# uso. Nunca su .venv, ni el .env (token), ni salidas o pruebas.
_SKIP_DIRS = {".venv", "__pycache__", "tests", "salida", "input", "output", ".git", ".pytest_cache"}
_SKIP_FILES = {".env"}


def transcriptor_datas():
    base = ROOT / "transcriptor"
    out = []
    for carpeta, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".venv")]
        for nombre in files:
            if nombre in _SKIP_FILES or nombre.endswith((".pyc", ".bat", ".ps1")):
                continue
            origen = Path(carpeta) / nombre
            destino = Path("transcriptor") / origen.parent.relative_to(base)
            out.append((str(origen), str(destino)))
    return out


datas = [(str(ROOT / "assets"), "assets")]
datas += transcriptor_datas()
datas += collect_data_files("imageio_ffmpeg", include_py_files=False)

binaries = []
if UV_BIN:
    binaries.append((UV_BIN, "bin"))

hiddenimports = collect_submodules("app") + [
    "objc", "Foundation", "AppKit", "Quartz", "CoreMedia", "AVFoundation",
    "ScreenCaptureKit", "libdispatch",
]

a = Analysis(
    [str(ROOT / "packaging" / "macos" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "cv2", "pyaudiowpatch", "windows_capture", "winrt", "winsdk",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtPdf", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, strip=False, upx=False)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=ICON or None,
    bundle_identifier=BUNDLE_ID,
    version=VERSION,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSMicrophoneUsageDescription":
            "Para grabar tu voz en la reunión.",
        "NSScreenCaptureUsageDescription":
            "Para grabar la pantalla o la ventana de la reunión y su audio.",
        "NSAudioCaptureUsageDescription":
            "Para grabar lo que suena en la reunión.",
    },
)

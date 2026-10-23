"""Permisos de macOS para grabar (spec 030).

- Grabación de pantalla: cubre pantalla, ventanas y audio del sistema
  (ScreenCaptureKit). macOS a veces solo lo aplica tras reabrir la app.
- Micrófono: solo hace falta si hay un micrófono elegido.

Sin un permiso no se graba: una grabación que pierde la pantalla o una voz en
silencio es peor que no empezar (FR-007).
"""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from typing import List

SCREEN = "screen"
MICROPHONE = "microphone"

_SETTINGS_URL = {
    SCREEN: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
    MICROPHONE: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


@dataclass(frozen=True)
class Missing:
    kind: str
    title: str
    why: str


_TEXT = {
    SCREEN: Missing(
        SCREEN,
        "Grabación de pantalla y audio del sistema",
        "Para grabar la pantalla o una ventana y lo que suena en la reunión.",
    ),
    MICROPHONE: Missing(
        MICROPHONE,
        "Micrófono",
        "Para grabar tu voz.",
    ),
}


def screen_allowed(request: bool = False) -> bool:
    try:
        import Quartz

        if Quartz.CGPreflightScreenCaptureAccess():
            return True
        if request:
            return bool(Quartz.CGRequestScreenCaptureAccess())
        return False
    except Exception:
        return True  # sin la API no se puede saber: que lo diga la captura


def microphone_allowed(request: bool = False, timeout: float = 30.0) -> bool:
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
    except Exception:
        return True
    estado = int(AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio))
    if estado == 3:  # Authorized
        return True
    if estado != 0 or not request:  # Denied / Restricted, o no se debe preguntar
        return False
    listo = threading.Event()
    caja = {"ok": False}

    def _respuesta(concedido):
        caja["ok"] = bool(concedido)
        listo.set()

    AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVMediaTypeAudio, _respuesta)
    from app.capture.mac_sck import _wait

    _wait(listo, timeout)
    return caja["ok"]


def missing_for_recording(needs_screen: bool, needs_microphone: bool) -> List[Missing]:
    """Permisos que faltan; pide los que macOS aún no ha preguntado nunca."""
    faltan = []
    if needs_screen and not screen_allowed(request=True):
        faltan.append(_TEXT[SCREEN])
    if needs_microphone and not microphone_allowed(request=True):
        faltan.append(_TEXT[MICROPHONE])
    return faltan


def open_settings(kind: str) -> None:
    url = _SETTINGS_URL.get(kind)
    if url:
        subprocess.Popen(["/usr/bin/open", url])


def explanation(faltan: List[Missing]) -> str:
    lineas = ["Para grabar falta darle permiso a la app en macOS:", ""]
    for m in faltan:
        lineas.append(f"• {m.title}: {m.why}")
    lineas += [
        "",
        "Se abrirá Ajustes del Sistema → Privacidad y seguridad. Activa "
        "«Grabador de Reuniones» en cada sección y vuelve a abrir la app "
        "(macOS a veces solo aplica el permiso al reabrirla).",
    ]
    return "\n".join(lineas)

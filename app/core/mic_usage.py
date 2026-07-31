"""Detección de qué aplicaciones están USANDO el micrófono ahora mismo (Windows).

Windows registra el uso del micrófono en:
  HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager
       \\ConsentStore\\microphone
Cada app tiene `LastUsedTimeStart` y `LastUsedTimeStop` (FILETIME). Cuando una app
EMPIEZA a usar el micrófono, `LastUsedTimeStop` se pone en 0; cuando lo suelta, se
escribe la hora de fin. Por eso:  **LastUsedTimeStop == 0  ⇒  en uso ahora.**

Es exactamente lo que muestra el ícono del micrófono junto al reloj. Sirve para
saber si Teams/Meet/Zoom (u otra app) tiene el micrófono activo = reunión en curso.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional

_MIC_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager"
    r"\ConsentStore\microphone"
)


@dataclass
class MicUser:
    raw: str       # identidad cruda (ruta de exe o package family name)
    name: str      # nombre legible


def _friendly_name(raw: str) -> str:
    """Convierte la clave del registro en un nombre legible."""
    # NonPackaged: ruta de exe con '#' en vez de '\'
    path = raw.replace("#", "\\")
    base = path.split("\\")[-1] if "\\" in path else path
    low = base.lower()
    known = {
        "ms-teams.exe": "Microsoft Teams",
        "teams.exe": "Microsoft Teams",
        "msteams": "Microsoft Teams",
        "zoom.exe": "Zoom",
        "slack.exe": "Slack",
        "chrome.exe": "Google Chrome",
        "msedge.exe": "Microsoft Edge",
        "firefox.exe": "Firefox",
        "discord.exe": "Discord",
    }
    for key, label in known.items():
        if key in low:
            return label
    return base


def _stop_is_zero(hkey) -> bool:
    """True si LastUsedTimeStop == 0 (micrófono en uso ahora)."""
    import winreg

    try:
        stop, _ = winreg.QueryValueEx(hkey, "LastUsedTimeStop")
        start, _ = winreg.QueryValueEx(hkey, "LastUsedTimeStart")
        return start not in (None, 0) and stop == 0
    except FileNotFoundError:
        return False
    except OSError:
        return False


def microphone_users(exclude_substrings: tuple = ()) -> List[MicUser]:
    """Apps que están usando el micrófono AHORA, excluyendo las que coincidan."""
    if sys.platform != "win32":
        return []
    import winreg

    excludes = tuple(s.lower() for s in exclude_substrings if s)
    users: List[MicUser] = []

    def _maybe_add(raw: str, hkey) -> None:
        low = raw.lower()
        if any(ex in low for ex in excludes):
            return
        if _stop_is_zero(hkey):
            users.append(MicUser(raw=raw, name=_friendly_name(raw)))

    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MIC_KEY)
    except OSError:
        return []

    try:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, sub) as subkey:
                    if sub == "NonPackaged":
                        # cada hijo es la ruta de un exe (con '#')
                        j = 0
                        while True:
                            try:
                                app = winreg.EnumKey(subkey, j)
                            except OSError:
                                break
                            j += 1
                            try:
                                with winreg.OpenKey(subkey, app) as appkey:
                                    _maybe_add(app, appkey)
                            except OSError:
                                continue
                    else:
                        # app "packaged" (p. ej. Teams nuevo): valores directos
                        _maybe_add(sub, subkey)
            except OSError:
                continue
    finally:
        root.Close()

    return users


def is_microphone_in_use_by_others(own_hints: tuple = ()) -> bool:
    """¿Hay alguna OTRA app usando el micrófono (probable reunión)?"""
    # Excluir nuestro propio proceso (python.exe / el exe empaquetado).
    own = list(own_hints)
    try:
        own.append(sys.executable.split("\\")[-1])
    except Exception:
        pass
    return len(microphone_users(tuple(own))) > 0


def desired_follow_meeting_mute(others_using: bool) -> bool:
    """Mute deseado para el modo experimental follow-meeting.

    Si nadie más usa el mic → silenciar nuestra pista; si hay uso → activar.
    """
    return not bool(others_using)


def should_apply_follow_meeting_mute(
    others_using: bool,
    prev_others_using: Optional[bool],
) -> Optional[bool]:
    """Mute a aplicar solo en flanco (edge), no en cada poll.

    - Primera muestra (prev is None) o cambio de others_using → desired mute.
    - Mismo others_using que el poll anterior → None (no pisar mute manual).

    Así, si el usuario silencia a mano durante una llamada, el mute se mantiene
    hasta que la llamada termine o vuelva a empezar.
    """
    others = bool(others_using)
    if prev_others_using is None or bool(prev_others_using) != others:
        return desired_follow_meeting_mute(others)
    return None

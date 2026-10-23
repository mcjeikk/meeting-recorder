"""Atajos de teclado GLOBALES en macOS (spec 030).

Carbon `RegisterEventHotKey`: funciona aunque la app no tenga foco y, a
diferencia de los "event taps", no pide el permiso de Accesibilidad. Los
eventos llegan al run loop principal, el mismo que mueve Qt.

Atajos: ⌃⌥R grabar/detener, ⌃⌥P pausar/reanudar, ⌃⌥M silenciar micrófono
(⌘⇧ ya lo usan navegadores y apps de reunión). Misma interfaz que
`GlobalHotkeys` de Windows, para que la ventana no distinga.
"""
from __future__ import annotations

import ctypes
from typing import Callable, List, Optional

from PySide6.QtCore import QAbstractNativeEventFilter

SHORTCUT_LABELS = {"toggle": "⌃⌥R", "pause": "⌃⌥P", "mute": "⌃⌥M"}

_KEY_R, _KEY_P, _KEY_M = 15, 35, 46  # kVK_ANSI_*
_CONTROL, _OPTION = 1 << 12, 1 << 11  # controlKey, optionKey


def _fourcc(text: str) -> int:
    return int.from_bytes(text.encode("ascii"), "big")


_SIGNATURE = _fourcc("MRhk")
_EVENT_CLASS_KEYBOARD = _fourcc("keyb")
_EVENT_HOTKEY_PRESSED = 5
_PARAM_DIRECT_OBJECT = _fourcc("----")
_TYPE_HOTKEY_ID = _fourcc("hkid")


class _HotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


class MacGlobalHotkeys(QAbstractNativeEventFilter):
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_pause: Callable[[], None],
        on_mute: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._acciones = {1: on_toggle, 2: on_pause, 3: on_mute or (lambda: None)}
        self._refs: List[ctypes.c_void_p] = []
        self._handler_ref = ctypes.c_void_p()
        self._callback = _HANDLER(self._on_event)  # referencia viva: si no, crash
        self._carbon = None
        self._registered = False

    def _on_event(self, _next_handler, event, _user_data) -> int:
        try:
            hk = _HotKeyID()
            self._carbon.GetEventParameter(
                ctypes.c_void_p(event), _PARAM_DIRECT_OBJECT, _TYPE_HOTKEY_ID,
                None, ctypes.sizeof(hk), None, ctypes.byref(hk),
            )
            accion = self._acciones.get(int(hk.id))
            if accion is not None and hk.signature == _SIGNATURE:
                accion()
        except Exception:
            pass
        return 0

    def register(self, _window_id: int = 0) -> None:
        if self._registered:
            return
        try:
            carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
            carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
            carbon.InstallEventHandler.argtypes = [
                ctypes.c_void_p, _HANDLER, ctypes.c_uint32,
                ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
            ]
            carbon.RegisterEventHotKey.argtypes = [
                ctypes.c_uint32, ctypes.c_uint32, _HotKeyID, ctypes.c_void_p,
                ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
            ]
            carbon.GetEventParameter.argtypes = [
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
            ]
            carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
            self._carbon = carbon
            destino = carbon.GetApplicationEventTarget()
            spec = _EventTypeSpec(_EVENT_CLASS_KEYBOARD, _EVENT_HOTKEY_PRESSED)
            carbon.InstallEventHandler(
                destino, self._callback, 1, ctypes.byref(spec), None,
                ctypes.byref(self._handler_ref),
            )
            mods = _CONTROL | _OPTION
            for ident, tecla in ((1, _KEY_R), (2, _KEY_P), (3, _KEY_M)):
                ref = ctypes.c_void_p()
                estado = carbon.RegisterEventHotKey(
                    tecla, mods, _HotKeyID(_SIGNATURE, ident), destino, 0, ctypes.byref(ref)
                )
                if estado == 0:
                    self._refs.append(ref)
            self._registered = bool(self._refs)
        except Exception:
            self._registered = False

    def unregister(self) -> None:
        if not self._registered or self._carbon is None:
            return
        for ref in self._refs:
            try:
                self._carbon.UnregisterEventHotKey(ref)
            except Exception:
                pass
        self._refs = []
        self._registered = False

    def nativeEventFilter(self, event_type, message):  # noqa: N802 (firma de Qt)
        return False, 0

"""Recorrido de la interfaz instalada. Solo graba una ventana de prueba identificada.

Uso desde el checkout: python -m tools.verify_recorder_front CARPETA
Desde el .app: Grabador de Reuniones --verify-frontend CARPETA
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
import wave
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.core.config import AppConfig
from app.encode.ffmpeg import get_ffmpeg_exe, probe_duration


def fixture_window(title):
    app = QApplication.instance() or QApplication([])
    label = QLabel("Ventana de prueba del grabador")
    label.setAttribute(Qt.WA_ShowWithoutActivating)
    label.setWindowTitle(title)
    label.setAlignment(Qt.AlignCenter)
    label.resize(420, 240)
    label.move(24, 48)
    label.setStyleSheet("background:#148852; color:white; font-size:18px")
    label.show()
    timer = QTimer(label)
    timer.timeout.connect(lambda: label.setText("Prueba de video  " + str(int(time.monotonic() * 10))))
    timer.start(180)
    return app.exec()


def wait_for(app, predicate, label, timeout=30):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        if predicate():
            return
        time.sleep(.025)
    raise RuntimeError(f"Tiempo agotado esperando {label}")


def control(window, name):
    item = window.view.rootObject().findChild(QQuickItem, name)
    if item is None:
        pending = [window.view.rootObject()]
        while pending:
            node = pending.pop()
            if node.objectName() == name:
                return node
            pending.extend(node.childItems())
    if item is None:
        raise RuntimeError(f"No se encontró {name}")
    return item


def click(window, name):
    # Los delegates y las posiciones de Flow se calculan en el siguiente frame.
    QTest.qWait(80)
    item = control(window, name)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    if not item.isVisible() or not item.isEnabled():
        raise RuntimeError(f"Control no disponible: {name}")
    QTest.mouseClick(window.view, Qt.LeftButton, pos=point.toPoint())
    QApplication.processEvents()


class Tone:
    """Fuente WASAPI de prueba para Windows: nunca lee audio del escritorio."""
    def start(self, path):
        self.path, self.started = path, time.monotonic()

    def stop(self):
        import numpy as np
        samples = np.arange(max(1, int(48000 * (time.monotonic() - self.started))))
        pcm = (3200 * np.sin(samples * (440 * 2 * np.pi / 48000))).astype("<i2")
        with wave.open(self.path, "wb") as wav:
            wav.setparams((1, 2, 48000, 0, "NONE", ""))
            wav.writeframes(pcm.tobytes())

    def current_level(self):
        return .1


def check_file(path, elapsed):
    ff = get_ffmpeg_exe()
    meta = subprocess.run([ff, "-hide_banner", "-i", str(path)],
                          capture_output=True).stderr.decode(errors="replace")
    if "Video: h264" not in meta or "Audio: aac" not in meta or "Sistema" not in meta:
        raise RuntimeError("Falta la pista de video o de sistema en el MP4.\n" + meta[-1300:])
    rgb = subprocess.check_output([ff, "-v", "error", "-i", str(path), "-an", "-frames:v", "1",
                        "-vf", "scale=1:1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    if len(rgb) != 3 or rgb[1] <= max(rgb[0], rgb[2]) + 12:
        raise RuntimeError(f"El MP4 no contiene la ventana verde elegida. Color medio {list(rgb)}")
    duration = probe_duration(str(path))
    if duration < 1 or abs(duration - elapsed) > .65:
        raise RuntimeError(f"Duración del MP4 {duration:.2f} s; tiempo grabado {elapsed:.2f} s.")
    print(f"MP4 reproducible · H.264 + Sistema (AAC) · {duration:.2f} s · RGB {list(rgb)}", flush=True)


def run(output):
    from app.ui.audio_inputs import AudioInputs
    from app.ui.main_window import MainWindow
    from app.ui.preview import Preview
    from app.capture import sources
    from app.transcription.worker import TranscriptionWorker

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    state = output / "estado"
    state.mkdir(exist_ok=True)
    title = "Recorder QA " + uuid.uuid4().hex[:10]

    def fixture_source():
        if child.poll() is not None:
            raise RuntimeError(f"La ventana de prueba terminó antes de capturarla ({child.returncode})")
        # ScreenCaptureKit muestra «Aplicación — Título» en el selector de macOS.
        return next((source for source in sources.list_windows()
                     if source.title == title or source.title.endswith(" — " + title)), None)

    frozen = getattr(sys, "frozen", False)
    launch = [sys.executable] if frozen else [sys.executable, str(Path(__file__).resolve())]
    child = subprocess.Popen([*launch, "--frontend-fixture", title], cwd=str(output))
    try:
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with ExitStack() as stack:
            # La configuración, la cola y las recuperaciones son exclusivas de esta prueba.
            stack.enter_context(patch.dict(os.environ, APPDATA=str(state), LOCALAPPDATA=str(state)))
            stack.enter_context(patch("app.core.platform_paths._mac_support_root", return_value=state))
            stack.enter_context(patch.object(AppConfig, "load", return_value=AppConfig(output_dir=str(output))))
            stack.enter_context(patch.object(AudioInputs, "refresh"))
            stack.enter_context(patch.object(TranscriptionWorker, "start"))
            stack.enter_context(patch.object(MainWindow, "_update_usage"))
            if sys.platform == "win32":
                stack.enter_context(patch.object(sources, "make_system_audio_capture", Tone))
            # Abrir el grabador sin tomar una miniatura del escritorio real.
            with patch.object(Preview, "refresh"):
                win = MainWindow()
                win.setAttribute(Qt.WA_ShowWithoutActivating)
                win.show()
                if sys.platform == "darwin":
                    from app.core.mac_permissions import screen_allowed
                    if not screen_allowed(request=False):
                        raise RuntimeError("El grabador de prueba necesita el permiso de grabación de pantalla de macOS")
                wait_for(app, fixture_source, "ventana de prueba")
                window_id = fixture_source().hwnd
                win.picker.refresh()
                index = next(i for i, w in enumerate(win.picker.items) if w.kind == "window" and w.hwnd == window_id)
                win.picker.select(index)
            win.preview.refresh()
            app.processEvents()
            source = win.picker.selected
            assert source.kind == "window" and source.hwnd == window_id
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes
                affinity = ctypes.windll.user32.GetWindowDisplayAffinity
                affinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                value = wintypes.DWORD()
                for hidden, expected in ((True, 0x11), (False, 0), (True, 0x11)):
                    win.pref.flag("exclude_window_from_capture", hidden)
                    if not affinity(int(win.winId()), ctypes.byref(value)) or value.value != expected:
                        raise RuntimeError("Windows no aplicó la exclusión de captura solicitada")
            win.resize(480, 720)
            app.processEvents()
            print(f"Grabador abierto · {win.view.rootObject().width():.0f} × {win.view.rootObject().height():.0f}", flush=True)
            wait_for(app, lambda: bool(win.preview.url), "miniatura de la ventana seleccionada")
            QTest.qWait(80)
            win.view.grabFramebuffer().save(str(output / "grabar.png"))
            click(win, "recordButton")

            def reached(phase):
                def check():
                    if win.session.phase in ("idle", "recovery") and win.statusText not in ("Iniciando grabación…",):
                        raise RuntimeError(win.statusText)
                    return win.session.phase == phase
                return check

            wait_for(app, reached("recording"), "inicio de captura")
            started = time.monotonic()
            wait_for(app, lambda: time.monotonic() - started >= 1.1, "primer tramo")
            click(win, "pauseButton")
            wait_for(app, reached("paused"), "pausa")
            elapsed = win.session.recorder.elapsed_seconds()
            QTest.qWait(400)
            assert elapsed == win.session.recorder.elapsed_seconds()
            assert control(win, "pauseButton").property("text") == "Reanudar"
            if sys.platform == "win32":
                # Entregar WM_HOTKEY únicamente a esta ventana para evitar tocar otra grabación.
                import ctypes
                ctypes.windll.user32.PostMessageW(int(win.winId()), 0x0312, 2, 0)
            else:
                click(win, "pauseButton")
            wait_for(app, reached("recording"), "reanudación")
            started = time.monotonic()
            wait_for(app, lambda: time.monotonic() - started >= 1.2, "segundo tramo")
            elapsed = win.session.recorder.elapsed_seconds()
            click(win, "recordButton")
            wait_for(app, lambda: win._last_output or win.session.phase == "recovery", "guardado", 90)
            if not win._last_output:
                raise RuntimeError(win.statusText)
            path = Path(win._last_output)
            check_file(path, elapsed)
            win.close()
        return 0
    finally:
        child.terminate()
        child.wait(timeout=15)


if __name__ == "__main__":
    if sys.argv[1] == "--frontend-fixture":
        raise SystemExit(fixture_window(sys.argv[2]))
    raise SystemExit(run(sys.argv[1]))

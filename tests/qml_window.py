"""Pruebas de la ventana real sin dispositivos, bandeja ni cola del usuario."""
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.config import AppConfig, VideoSource
from app.transcription.jobs import JobStore
from app.ui.main_window import MainWindow


def make_window(case, *, available=True):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    case.app = QApplication.instance() or QApplication([])
    root = Path(case.enterContext(tempfile.TemporaryDirectory()))
    cfg = AppConfig(output_dir=str(root), transcriptor_dir="")
    case.enterContext(patch.object(cfg, "save"))
    for name in ("_prewarm_encoder", "_setup_tray", "_setup_hotkeys", "_setup_device_watcher",
                 "_offer_pending_save", "_apply_capture_affinity"):
        case.enterContext(patch.object(MainWindow, name))
    case.enterContext(patch("app.ui.main_window.AppConfig.load", return_value=cfg))
    case.enterContext(patch("app.ui.main_window.is_available", return_value=available))
    case.enterContext(patch("app.ui.audio_inputs.AudioInputs.refresh"))
    case.enterContext(patch("app.ui.transcriptions.JobStore", return_value=JobStore(root / "jobs")))
    case.enterContext(patch("app.transcription.worker.TranscriptionWorker.start"))
    case.enterContext(patch("app.ui.source_picker.sources.list_monitors", return_value=[
        VideoSource("screen", monitor_index=1, is_primary=True), VideoSource("screen", monitor_index=2)]))
    case.windows = case.enterContext(patch("app.ui.source_picker.sources.list_windows", return_value=[]))
    check_preview = case.enterContext(patch("app.ui.preview.Preview.refresh"))
    w = MainWindow()
    check_preview.reset_mock()
    w._tray = Mock()
    w._hotkeys = Mock()
    w._hotkeys_registered = True
    w._timer.stop()
    if w.platformMac:
        w._mac_device_poll = Mock()
    w.show()
    case.app.processEvents()

    def cleanup():
        # Cada prueba puede dejar la sesión en pausa para inspeccionar controles.
        w.session._set_phase("idle")
        w.library.worker._current = None
        w.close()
        case.app.processEvents()
        w.deleteLater()

    case.addCleanup(cleanup)
    return w


def item(w, name):
    found = w.view.rootObject().findChild(QQuickItem, name)
    if found is None:
        # Los delegates creados por Repeater viven en el árbol visual.
        def search(parent):
            if parent.objectName() == name:
                return parent
            return next((match for child in parent.childItems() if (match := search(child))), None)
        found = search(w.view.rootObject())
    if found is None:
        raise AssertionError(f"Control ausente: {name}")
    return found


def position(control):
    return control.mapToScene(QPointF(control.width() / 2, control.height() / 2)).toPoint()


def click(w, name):
    QTest.mouseClick(w.view, Qt.LeftButton, pos=position(item(w, name)))
    QApplication.processEvents()

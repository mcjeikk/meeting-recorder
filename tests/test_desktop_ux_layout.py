"""Los controles de sesión permanecen al alcance con ratón y teclado."""
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from tests.qml_window import click, item, make_window, position


class TestDesktopUxLayout(unittest.TestCase):
    def test_first_view_and_pinned_actions(self):
        w = make_window(self)
        w.resize(480, 720)
        self.app.processEvents()
        footer = item(w, "recordButton")
        for name in ("sourcePicker", "micPicker", "systemAudio", "autoTranscribe"):
            control = item(w, name)
            self.assertTrue(control.isVisible())
            self.assertTrue(0 < position(control).y() < position(footer).y() < 720)
        self.assertEqual(footer.property("text"), "Grabar")
        for size in ((480, 720), (360, 320)):
            w.resize(*size)
            self.app.processEvents()
            y = position(footer).y()
            scroller = item(w, "recordingScroll").property("contentItem")
            scroller.setProperty("contentY", 200)
            self.app.processEvents()
            self.assertEqual(position(footer).y(), y)
            self.assertLess(y, size[1])
            self.assertGreater(y, 0)
            w.session._set_phase("paused")
            self.assertTrue(item(w, "pauseButton").isVisible())
            self.assertLess(position(item(w, "pauseButton")).x(), position(footer).x())
            w.session._set_phase("idle")

    def test_keyboard_navigation_and_settings(self):
        w = make_window(self)
        tab = item(w, "tab0")
        tab.forceActiveFocus()
        QTest.keyClick(w.view, Qt.Key_Right)
        self.assertEqual(w.view.rootObject().property("page"), 1)
        self.assertTrue(item(w, "importButton").isVisible())
        click(w, "tab2")
        self.assertTrue(item(w, "transcription_num_speakers").isVisible())
        self.assertTrue(item(w, "recordButton").isVisible())

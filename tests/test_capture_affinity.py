"""Checkbox: ocultar o no esta ventana en grabaciones/capturas."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from app.ui.capture_affinity import (
    WDA_EXCLUDEFROMCAPTURE,
    WDA_NONE,
    affinity_flag,
)


class TestAffinityFlag(unittest.TestCase):
    def test_checked_excludes(self) -> None:
        self.assertEqual(affinity_flag(True), WDA_EXCLUDEFROMCAPTURE)
        self.assertEqual(affinity_flag(False), WDA_NONE)


@unittest.skipUnless(os.environ.get("QT_QPA_PLATFORM") != "skip", "Qt UI")
class TestCaptureAffinityCheckbox(unittest.TestCase):
    def test_checkbox_default_on_and_persists_toggle(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)
        from app.core.config import AppConfig
        from app.ui.main_window import MainWindow

        cfg = AppConfig()
        with patch("app.ui.main_window.threading.Thread") as thr:
            thr.return_value = MagicMock()
            with patch.object(MainWindow, "_update_preview", lambda self: None):
                with patch("app.ui.main_window.AudioMonitor"):
                    with patch("app.ui.main_window.apply_window_capture_affinity"):
                        with patch("app.ui.main_window.AppConfig.load", return_value=cfg):
                            w = MainWindow()
        try:
            self.assertTrue(hasattr(w, "_hide_self_check"))
            self.assertTrue(w._hide_self_check.isChecked())
            self.assertTrue(w._config.exclude_window_from_capture)
            with patch.object(w._config, "save"):
                w._hide_self_check.setChecked(False)
            self.assertFalse(w._config.exclude_window_from_capture)
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()

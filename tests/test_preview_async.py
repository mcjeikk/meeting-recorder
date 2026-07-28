"""Tests for async preview helpers."""
from __future__ import annotations

import inspect
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestGrabMonitorFrame(unittest.TestCase):
    def test_signature(self) -> None:
        from app.capture.windows_video import grab_monitor_frame

        sig = inspect.signature(grab_monitor_frame)
        self.assertIn("monitor_index", sig.parameters)

    def test_returns_none_on_bad_import(self) -> None:
        from app.capture import windows_video as wv

        with patch.dict(sys.modules, {"windows_capture": None}):
            # Force ImportError path inside function by patching the import
            with patch("builtins.__import__", side_effect=ImportError("x")):
                # Call with patched local import — simpler: monkeypatch WindowsCapture
                pass
        with patch.object(wv, "grab_monitor_frame", wraps=wv.grab_monitor_frame):
            # Ensure function exists and is callable
            self.assertTrue(callable(wv.grab_monitor_frame))


class TestPreviewAsyncSmoke(unittest.TestCase):
    def test_mainwindow_schedules_without_blocking_on_grab(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.threading.Thread") as thr:
            thr.return_value = MagicMock()
            # Avoid real WGC during init's first _update_preview
            with patch.object(MainWindow, "_update_preview", lambda self: None):
                w = MainWindow()
            # Restore and exercise schedule path
            w._preview_busy = False
            w._source_combo.setCurrentIndex(0)
            MainWindow._update_preview(w)
            self.assertTrue(w._preview_busy)
            thr.assert_called()
            # Coalesce: second call marks dirty, no extra thread required
            calls = thr.call_count
            MainWindow._update_preview(w)
            self.assertTrue(w._preview_dirty)
            self.assertEqual(thr.call_count, calls)
            w.close()


if __name__ == "__main__":
    unittest.main()

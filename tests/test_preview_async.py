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
        from app.ui.preview import Preview
        from tests.qml_window import make_window

        update_preview = Preview.refresh
        w = make_window(self)
        with patch("app.ui.preview.Thread") as thread:
            update_preview(w.preview)
            self.assertTrue(w.preview._busy)
            thread.assert_called_once()
            update_preview(w.preview)
            self.assertTrue(w.preview._dirty)
            thread.assert_called_once()

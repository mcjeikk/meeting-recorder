"""Tests: device hotplug watcher + idle/recording policy."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.ui.device_watcher import (
    RELEVANT_DBT_EVENTS,
    hotplug_action,
    is_relevant_device_change,
)


class TestDeviceChangeRelevance(unittest.TestCase):
    def test_relevant_events(self) -> None:
        for w in RELEVANT_DBT_EVENTS:
            self.assertTrue(is_relevant_device_change(w))

    def test_ignores_unrelated(self) -> None:
        # DBT_CONFIGCHANGED etc.
        self.assertFalse(is_relevant_device_change(0x0018))
        self.assertFalse(is_relevant_device_change(0))


class TestHotplugAction(unittest.TestCase):
    def test_idle_is_deep(self) -> None:
        self.assertEqual(hotplug_action(recording=False), "deep")

    def test_recording_defers(self) -> None:
        self.assertEqual(hotplug_action(recording=True), "defer")


class TestDeviceChangeWatcherCallback(unittest.TestCase):
    def test_filter_invokes_callback_on_devicechange(self) -> None:
        if __import__("sys").platform != "win32":
            self.skipTest("Windows-only MSG layout")

        import ctypes
        from ctypes import wintypes

        from app.ui.device_watcher import DeviceChangeWatcher, _WM_DEVICECHANGE
        from app.ui.device_watcher import _DBT_DEVICEARRIVAL

        called = MagicMock()
        watcher = DeviceChangeWatcher(called)

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt_x", wintypes.LONG),
                ("pt_y", wintypes.LONG),
            ]

        msg = MSG()
        msg.message = _WM_DEVICECHANGE
        msg.wParam = _DBT_DEVICEARRIVAL
        watcher.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
        called.assert_called_once()

    def test_filter_ignores_other_messages(self) -> None:
        if __import__("sys").platform != "win32":
            self.skipTest("Windows-only MSG layout")

        import ctypes
        from ctypes import wintypes

        from app.ui.device_watcher import DeviceChangeWatcher

        called = MagicMock()
        watcher = DeviceChangeWatcher(called)

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt_x", wintypes.LONG),
                ("pt_y", wintypes.LONG),
            ]

        msg = MSG()
        msg.message = 0x0312  # WM_HOTKEY
        msg.wParam = 1
        watcher.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
        called.assert_not_called()


if __name__ == "__main__":
    unittest.main()

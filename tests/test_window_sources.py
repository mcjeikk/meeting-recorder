"""Selección de ventanas que se abren, se cierran o cambian de título."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import Mock, patch

from app.core.config import AppConfig, VideoSource


@unittest.skipUnless(sys.platform == "win32", "Enumeración Win32")
class TestWindowsInventory(unittest.TestCase):
    def test_visible_handles_with_duplicate_or_settings_titles(self):
        import ctypes
        from ctypes import wintypes as w
        from app.capture.windows_video import list_windows

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        create = user32.CreateWindowExW
        create.argtypes = (w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int,
                           ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND,
                           w.HMENU, w.HINSTANCE, w.LPVOID)
        create.restype = w.HWND
        user32.DestroyWindow.argtypes = (w.HWND,)

        def test_window(title, visible=True):
            # Fuera del área de trabajo, sin foco ni botón en la barra de tareas.
            style = 0x80000000 | (0x10000000 if visible else 0)
            hwnd = create(0x08000080, "STATIC", title, style, -32000, -32000,
                          24, 24, None, None, None, None)
            self.assertTrue(hwnd)
            self.addCleanup(user32.DestroyWindow, hwnd)
            return hwnd

        first = test_window("Reunión de prueba del selector")
        second = test_window("Reunión de prueba del selector")
        settings = test_window("Configuración")
        hidden = test_window("Reunión interna de prueba", visible=False)
        handles = {source.hwnd for source in list_windows()}
        self.assertTrue({first, second, settings} <= handles)
        self.assertNotIn(hidden, handles)


@unittest.skipUnless(sys.platform == "win32", "Selector de ventanas de Windows")
class TestWindowPicker(unittest.TestCase):
    def setUp(self):
        from tests.qml_window import make_window, item
        self.window = make_window(self)
        self.combo = item(self.window, "sourcePicker")
        self.picker = self.window.picker
        self.calendar = VideoSource("window", "Calendario de Teams", hwnd=101)
        self.meeting = VideoSource("window", "Reunión de Teams", hwnd=202)
        self.windows.return_value = [self.calendar]
        self.picker.refresh()

    def test_keyboard_and_mouse_open_refresh_without_recapturing_monitor(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from tests.qml_window import click
        self.picker.select(1)
        self.window.preview.refresh.reset_mock()
        self.windows.return_value = [self.calendar, self.meeting]
        self.combo.forceActiveFocus()
        QTest.keyClick(self.window.view, Qt.Key_Down, Qt.AltModifier)
        self.assertEqual(self.picker.items[3], self.meeting)
        QTest.keyClick(self.window.view, Qt.Key_Escape)
        self.windows.return_value = [self.meeting]
        click(self.window, "sourcePicker")
        self.assertEqual(self.picker.items[2:], [self.meeting])
        self.assertEqual(self.picker.selected.monitor_index, 2)
        self.window.preview.refresh.assert_not_called()

    def test_duplicate_selection_reaches_preview_and_recording_after_rename(self):
        from tests.qml_window import click
        twin = VideoSource("window", self.meeting.title, hwnd=303)
        self.windows.return_value = [self.meeting, twin]
        click(self.window, "sourceRefresh")
        self.assertNotEqual(self.picker.labels[2], self.picker.labels[3])
        self.picker.select(3)
        self.assertEqual(self.window.preview.picker.selected.hwnd, twin.hwnd)
        renamed = VideoSource("window", "Nuevo título", hwnd=twin.hwnd)
        self.windows.return_value = [renamed, self.meeting]
        click(self.window, "sourceRefresh")
        self.assertEqual(self.window._build_settings().video_source, renamed)

    def test_failed_query_preserves_window_then_closed_window_uses_screen(self):
        self.picker.select(2)
        self.windows.side_effect = OSError("enumeración interrumpida")
        self.picker.refresh()
        self.assertEqual(self.picker.selected, self.calendar)
        self.windows.side_effect = None
        self.windows.return_value = [VideoSource("window", self.calendar.title, hwnd=404)]
        self.picker.refresh()
        self.assertEqual(self.picker.selected.monitor_index, 1)
        self.assertIn("Pantalla 1", self.window.statusText)

    def test_busy_and_recording_disable_refresh(self):
        from tests.qml_window import click, item
        for state in ("starting", "recording", "saving"):
            self.window.session._set_phase(state)
            self.assertFalse(self.combo.isEnabled())
            self.assertFalse(item(self.window, "sourceRefresh").isEnabled())
            self.windows.reset_mock()
            click(self.window, "sourceRefresh")
            self.picker.refresh()
            self.windows.assert_not_called()

    def test_late_preview_from_previous_window_is_discarded(self):
        from PySide6.QtGui import QImage
        self.windows.return_value = [self.calendar, self.meeting]
        self.picker.refresh()
        self.picker.select(2)
        preview = self.window.preview
        previous = preview._generation
        self.picker.select(3)
        preview.receive(QImage(2, 2, QImage.Format_RGB32), previous)
        self.assertEqual(preview.url, "")
        self.assertEqual(preview.picker.selected.hwnd, self.meeting.hwnd)

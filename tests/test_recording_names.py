"""Tests for recording basename from selected video source title."""
from __future__ import annotations

import unittest
from datetime import datetime

from app.core.config import VideoSource, recording_stem, sanitize_filename_component


class TestSanitizeFilenameComponent(unittest.TestCase):
    def test_strips_invalid_chars(self) -> None:
        self.assertEqual(
            sanitize_filename_component('Reunión: "Standup" / Team?'),
            "Reunión Standup Team",
        )

    def test_empty_and_whitespace(self) -> None:
        self.assertEqual(sanitize_filename_component(""), "")
        self.assertEqual(sanitize_filename_component("   "), "")
        self.assertEqual(sanitize_filename_component("..."), "")

    def test_truncates(self) -> None:
        long = "A" * 200
        out = sanitize_filename_component(long, max_len=20)
        self.assertEqual(len(out), 20)

    def test_reserved_windows_names(self) -> None:
        self.assertEqual(sanitize_filename_component("CON"), "")
        self.assertEqual(sanitize_filename_component("nul"), "")


class TestRecordingStem(unittest.TestCase):
    def setUp(self) -> None:
        self.when = datetime(2026, 8, 11, 12, 30, 45)

    def test_window_uses_picker_title(self) -> None:
        src = VideoSource(kind="window", title="Daily Sync - Microsoft Teams", hwnd=1)
        self.assertEqual(
            recording_stem(src, when=self.when),
            "Daily Sync - Microsoft Teams_2026-08-11_12-30-45",
        )

    def test_window_blank_falls_back(self) -> None:
        src = VideoSource(kind="window", title="  ", hwnd=1)
        self.assertEqual(
            recording_stem(src, when=self.when),
            "Grabacion_2026-08-11_12-30-45",
        )

    def test_screen_uses_visible_label(self) -> None:
        src = VideoSource(kind="screen", title="DISPLAY1 1920x1080", monitor_index=1, is_primary=True)
        self.assertEqual(
            recording_stem(src, when=self.when),
            "Pantalla 1 (principal)_2026-08-11_12-30-45",
        )

    def test_screen_secondary(self) -> None:
        src = VideoSource(kind="screen", monitor_index=2, is_primary=False)
        self.assertEqual(
            recording_stem(src, when=self.when),
            "Pantalla 2_2026-08-11_12-30-45",
        )


if __name__ == "__main__":
    unittest.main()

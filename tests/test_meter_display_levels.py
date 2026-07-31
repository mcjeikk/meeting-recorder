"""Tests for VU meter gating (mute / system-audio off → empty bars)."""
from __future__ import annotations

import os
import unittest

# Avoid needing a display when importing MainWindow's helper.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from app.ui.main_window import meter_display_levels


class TestMeterDisplayLevels(unittest.TestCase):
    def test_passes_through_when_active(self) -> None:
        mic, sys = meter_display_levels(0.4, 0.7, mic_muted=False, system_enabled=True)
        self.assertEqual(mic, 0.4)
        self.assertEqual(sys, 0.7)

    def test_mic_muted_forces_zero(self) -> None:
        mic, sys = meter_display_levels(0.9, 0.5, mic_muted=True, system_enabled=True)
        self.assertEqual(mic, 0.0)
        self.assertEqual(sys, 0.5)

    def test_system_disabled_forces_zero(self) -> None:
        mic, sys = meter_display_levels(0.3, 0.8, mic_muted=False, system_enabled=False)
        self.assertEqual(mic, 0.3)
        self.assertEqual(sys, 0.0)

    def test_both_inactive(self) -> None:
        mic, sys = meter_display_levels(1.0, 1.0, mic_muted=True, system_enabled=False)
        self.assertEqual(mic, 0.0)
        self.assertEqual(sys, 0.0)


if __name__ == "__main__":
    unittest.main()

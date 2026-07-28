"""Tests for multi-monitor source enumeration and labels."""
from __future__ import annotations

import sys
import unittest

from app.core.config import VideoSource


class TestScreenLabels(unittest.TestCase):
    def test_primary_and_secondary(self) -> None:
        primary = VideoSource(kind="screen", monitor_index=1, is_primary=True)
        other = VideoSource(kind="screen", monitor_index=2, is_primary=False)
        self.assertEqual(primary.label, "Pantalla 1 (principal)")
        self.assertEqual(other.label, "Pantalla 2")


class TestListMonitors(unittest.TestCase):
    def test_1based_indexes(self) -> None:
        if sys.platform != "win32":
            self.skipTest("Windows only")
        from app.capture.windows_video import list_monitors

        mons = list_monitors()
        self.assertTrue(mons)
        self.assertTrue(all(m.kind == "screen" for m in mons))
        indexes = [m.monitor_index for m in mons]
        self.assertEqual(indexes, list(range(1, len(mons) + 1)))
        self.assertGreaterEqual(sum(1 for m in mons if m.is_primary), 1)


if __name__ == "__main__":
    unittest.main()

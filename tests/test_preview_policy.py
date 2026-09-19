"""Idle WGC preview must not run while a transcription is open."""
from __future__ import annotations

import unittest

from app.ui.preview_policy import (
    should_pause_idle_wgc_preview,
    transcription_status_is_open,
)


class TestPreviewPolicy(unittest.TestCase):
    def test_open_statuses(self) -> None:
        for s in ("pending", "extracting", "running", "RUNNING"):
            self.assertTrue(transcription_status_is_open(s), s)
        for s in ("done", "error", "cancelled", "", None):
            self.assertFalse(transcription_status_is_open(s), s)

    def test_pause_only_when_idle_and_tx_open(self) -> None:
        self.assertTrue(
            should_pause_idle_wgc_preview(recording=False, transcription_open=True)
        )
        self.assertFalse(
            should_pause_idle_wgc_preview(recording=False, transcription_open=False)
        )
        self.assertFalse(
            should_pause_idle_wgc_preview(recording=True, transcription_open=True)
        )
        self.assertFalse(
            should_pause_idle_wgc_preview(recording=True, transcription_open=False)
        )

    def test_periodic_idle_always_paused(self) -> None:
        self.assertTrue(
            should_pause_idle_wgc_preview(
                recording=False, transcription_open=False, periodic=True
            )
        )
        self.assertFalse(
            should_pause_idle_wgc_preview(
                recording=True, transcription_open=False, periodic=True
            )
        )


if __name__ == "__main__":
    unittest.main()

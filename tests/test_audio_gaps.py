"""Relleno de silencio del audio del sistema en macOS (spec 030)."""
from __future__ import annotations

import unittest

import numpy as np

from app.capture.audio_gaps import GapFiller, float_to_int16, silence

RATE = 48_000


class TestGapFiller(unittest.TestCase):
    def test_silence_before_the_first_buffer(self) -> None:
        g = GapFiller(RATE, start_time=100.0)
        self.assertEqual(g.silence_before(100.5, 480), RATE // 2)

    def test_contiguous_buffers_need_nothing(self) -> None:
        g = GapFiller(RATE, start_time=10.0)
        self.assertEqual(g.silence_before(10.0, 480), 0)
        self.assertEqual(g.silence_before(10.01, 480), 0)
        self.assertEqual(g.silence_before(10.02, 480), 0)

    def test_jitter_below_tolerance_is_not_padded(self) -> None:
        g = GapFiller(RATE, start_time=0.0)
        g.silence_before(0.0, 480)
        self.assertEqual(g.silence_before(0.025, 480), 0)

    def test_gap_between_buffers_is_padded(self) -> None:
        g = GapFiller(RATE, start_time=0.0)
        g.silence_before(0.0, 480)              # hasta 0.01 s
        self.assertEqual(g.silence_before(3.01, 480), 3 * RATE)

    def test_track_lasts_until_stop(self) -> None:
        g = GapFiller(RATE, start_time=0.0)
        g.silence_before(1.0, RATE)             # 1 s de silencio + 1 s de audio
        self.assertEqual(g.silence_until(5.0), 3 * RATE)
        self.assertEqual(g.frames_written, 5 * RATE)

    def test_nothing_ever_arrived(self) -> None:
        g = GapFiller(RATE, start_time=2.0)
        self.assertEqual(g.silence_until(4.0), 2 * RATE)

    def test_late_buffer_overlap_is_not_negative(self) -> None:
        g = GapFiller(RATE, start_time=0.0)
        g.silence_before(0.0, RATE)
        self.assertEqual(g.silence_before(0.5, 480), 0)


class TestConversion(unittest.TestCase):
    def test_planar_is_interleaved(self) -> None:
        left = np.array([0.5, -0.5, 0.0], dtype=np.float32)
        right = np.array([1.0, -1.0, 0.25], dtype=np.float32)
        raw = np.concatenate([left, right]).tobytes()
        out = float_to_int16(raw, channels=2, frames=3, non_interleaved=True)
        self.assertEqual(out.shape, (3, 2))
        self.assertEqual(out[0].tolist(), [16383, 32767])
        self.assertEqual(out[1].tolist(), [-16383, -32767])

    def test_interleaved_stays_interleaved(self) -> None:
        raw = np.array([0.5, 1.0, -0.5, -1.0], dtype=np.float32).tobytes()
        out = float_to_int16(raw, channels=2, frames=2, non_interleaved=False)
        self.assertEqual(out.tolist(), [[16383, 32767], [-16383, -32767]])

    def test_clipping(self) -> None:
        raw = np.array([2.0, -3.0], dtype=np.float32).tobytes()
        out = float_to_int16(raw, channels=1, frames=2, non_interleaved=False)
        self.assertEqual(out.reshape(-1).tolist(), [32767, -32767])

    def test_short_buffer_does_not_crash(self) -> None:
        raw = np.zeros(5, dtype=np.float32).tobytes()
        out = float_to_int16(raw, channels=2, frames=4, non_interleaved=False)
        self.assertEqual(out.shape, (2, 2))

    def test_silence_bytes(self) -> None:
        self.assertEqual(len(silence(10, 2)), 40)
        self.assertEqual(silence(-3, 2), b"")


if __name__ == "__main__":
    unittest.main()

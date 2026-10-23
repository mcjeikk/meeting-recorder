"""Escritor de fotogramas a tasa constante (macOS, spec 030).

El fallo que vigila: si ffmpeg se atrasaba, el escritor reiniciaba su reloj y
el video salía más corto que el tiempo grabado (CI macOS: 5,1 s de video para
~7 s grabados) → video desincronizado del audio.
"""
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from app.capture import frame_pipe as fp


class FramesDueTests(unittest.TestCase):
    def test_first_frame_at_zero(self):
        self.assertEqual(fp.frames_due(0.0, 30), 1)

    def test_one_second(self):
        self.assertEqual(fp.frames_due(1.0, 30), 31)

    def test_negative_is_zero(self):
        self.assertEqual(fp.frames_due(-0.1, 30), 0)


class _SlowStdin:
    """ffmpeg lento: cada fotograma tarda `delay` en entrar al pipe."""

    def __init__(self, delay: float):
        self.delay = delay
        self.count = 0
        self.lock = threading.Lock()

    def write(self, data: bytes) -> None:
        time.sleep(self.delay)
        with self.lock:
            self.count += 1

    def close(self) -> None:
        pass


class _FakeProc:
    def __init__(self, stdin):
        self.stdin = stdin
        self.stderr = None

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        pass


def _run_with(stdin, seconds: float, fps: int = 30) -> int:
    w = fp.FramePipeWriter("x.mkv", 8, 6, fps)
    w.put(np.zeros((6, 8, 4), dtype=np.uint8))
    w._proc = _FakeProc(stdin)
    w._running = True
    w._thread = threading.Thread(target=w._loop, daemon=True)
    w._thread.start()
    time.sleep(seconds)
    w.stop()
    return stdin.count


class CatchUpTests(unittest.TestCase):
    def test_fast_encoder_gets_exact_count(self):
        n = _run_with(_SlowStdin(0.0), 1.0)
        self.assertTrue(29 <= n <= 33, n)

    def test_slow_encoder_still_gets_every_frame(self):
        # El encoder solo traga ~10 fps: antes salían ~10 fotogramas por segundo.
        n = _run_with(_SlowStdin(0.1), 1.0)
        self.assertTrue(29 <= n <= 33, n)


@unittest.skipUnless(Path(fp.get_ffmpeg_exe()).exists(), "sin ffmpeg empaquetado")
class RealFfmpegTests(unittest.TestCase):
    def test_duration_matches_wall_time(self):
        from app.encode.ffmpeg import probe_duration

        with tempfile.TemporaryDirectory() as tmp:
            salida = str(Path(tmp) / "v.mkv")
            w = fp.FramePipeWriter(salida, 64, 48, 30)
            w.put(np.zeros((48, 64, 4), dtype=np.uint8))
            w.start()
            time.sleep(1.5)
            w.stop()
            dur = probe_duration(salida)
            self.assertAlmostEqual(dur, 1.5, delta=0.2)


if __name__ == "__main__":
    unittest.main()

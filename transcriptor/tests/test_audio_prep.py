"""Skip second ffmpeg when work audio is already 16 kHz mono PCM."""
from __future__ import annotations

import struct
import tempfile
import unittest
import wave
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.audio import es_wav16k_mono_pcm, preparar_wav16k  # noqa: E402


def _write_pcm_wav(path: Path, *, channels: int, rate: int, sampwidth: int) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(rate)
        wf.writeframes(struct.pack("<h", 0) * (rate // 10))


class TestWav16kReuse(unittest.TestCase):
    def test_detects_work_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.wav"
            _write_pcm_wav(path, channels=1, rate=16000, sampwidth=2)
            self.assertTrue(es_wav16k_mono_pcm(path))
            out, reused = preparar_wav16k(path, Path(tmp) / "conv")
            self.assertTrue(reused)
            self.assertEqual(out.resolve(), path.resolve())

    def test_rejects_stereo_or_44k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stereo = Path(tmp) / "st.wav"
            _write_pcm_wav(stereo, channels=2, rate=16000, sampwidth=2)
            self.assertFalse(es_wav16k_mono_pcm(stereo))
            hz = Path(tmp) / "44k.wav"
            _write_pcm_wav(hz, channels=1, rate=44100, sampwidth=2)
            self.assertFalse(es_wav16k_mono_pcm(hz))
            mp3 = Path(tmp) / "x.mp3"
            mp3.write_bytes(b"not-a-wav")
            self.assertFalse(es_wav16k_mono_pcm(mp3))


if __name__ == "__main__":
    unittest.main()

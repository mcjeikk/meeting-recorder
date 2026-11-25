"""La reanudación confirma un solo tramo o conserva íntegra la pausa."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.config import AudioDevice, RecordingSettings, VideoSource
from app.core.orchestrator import Recorder


class Capture:
    def __init__(self, fail=False):
        self.fail = fail
        self.closed = False

    def start(self, path):
        Path(path).write_bytes(b"tramo de prueba")
        if self.fail:
            raise RuntimeError("dispositivo desconectado")

    def stop(self):
        self.closed = True


class TestResumeTransaction(unittest.TestCase):
    def test_old_pending_sessions_with_nonconsecutive_cycles_keep_order(self):
        from app.core.output_path import PendingSave
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for number in (0, 2, 10):
                (root / f"video_seg{number}.mkv").touch()
                (root / f"system_seg{number}.wav").touch()
            rec = Recorder()
            rec.adopt_pending(PendingSave(tmp, "", "", "Prueba"))
            self.assertEqual([Path(p).stem for p in rec._video_segments],
                             ["video_seg0", "video_seg2", "video_seg10"])
            self.assertEqual([(Path(p).stem, c) for p, c in rec._system_segments],
                             [("system_seg0", 0), ("system_seg2", 1), ("system_seg10", 2)])

    def test_encoder_warmup_does_not_shorten_the_video_clock(self):
        import numpy as np
        from app.capture.windows_video import WindowsGraphicsCapture

        capture = WindowsGraphicsCapture(VideoSource("window", "Prueba", hwnd=1), fps=10)
        capture._w = capture._h = 2
        capture._latest = np.zeros((2, 2, 4), dtype=np.uint8)
        capture._proc = Mock()
        capture._running = True
        elapsed = 0.
        writes = []

        def advance(seconds):
            nonlocal elapsed
            elapsed += seconds

        def write(frame):
            writes.append(elapsed)
            if len(writes) == 1:
                advance(.35)
            if len(writes) == 6:
                capture._running = False

        capture._proc.stdin.write.side_effect = write
        with patch("app.capture.windows_video.time.perf_counter", side_effect=lambda: elapsed), \
             patch("app.capture.windows_video.time.sleep", side_effect=advance):
            capture._write_loop()
        self.assertAlmostEqual(writes[-1], .5)

    def test_mic_stream_open_and_start_failure_leave_no_wav(self):
        from app.capture.windows_audio import MicCapture
        for failure in ("constructor", "start"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                mic = MicCapture(tmp)
                device = AudioDevice(1, "Prueba", 1)
                with patch("sounddevice.InputStream") as stream:
                    if failure == "constructor":
                        stream.side_effect = OSError("mic ausente")
                    else:
                        stream.return_value.start.side_effect = OSError("mic ocupado")
                    with self.assertRaises(OSError):
                        mic.start(device, cycle=1)
                    if failure == "start":
                        stream.return_value.close.assert_called_once()
                self.assertEqual(mic.segments(), [])
                self.assertIsNone(mic.device)
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_failed_attempt_preserves_clock_media_and_can_retry(self):
        for failure in ("video", "system", "mic"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                rec = Recorder()
                root = Path(tmp)
                previous = root / "video_seg0.mkv"
                previous.write_bytes(b"grabacion original")
                rec._settings = RecordingSettings(VideoSource("window", "Prueba", 32),
                                                  AudioDevice(1, "Mic", 1), output_dir=root)
                rec._current_mic_device = rec._settings.mic_device
                rec._settings.capture_system_audio = failure != "video"
                rec._recording = True
                rec._temp_dir = tmp
                rec._video_segments = [str(previous)]
                rec._mic = Mock()
                rec._mic.segments.return_value = []
                rec.pause()
                frozen = rec.elapsed_seconds()
                video = Capture(failure == "video")
                system = Capture(failure == "system")
                if failure == "mic":
                    rec._mic.switch_device.side_effect = RuntimeError("micrófono desconectado")
                with patch("app.core.orchestrator._make_video_capture", return_value=video), \
                     patch("app.capture.sources.make_system_audio_capture", return_value=system):
                    rec.resume()
                self.assertTrue(rec.is_paused())
                self.assertTrue(rec._clock.is_paused)
                self.assertAlmostEqual(rec.elapsed_seconds(), frozen)
                self.assertTrue(video.closed)
                if failure != "video":
                    self.assertTrue(system.closed)
                self.assertEqual(rec._video_segments, [str(previous)])
                self.assertEqual(rec._system_segments, [])
                self.assertEqual(list(root.iterdir()), [previous])
                self.assertEqual(previous.read_bytes(), b"grabacion original")
                rec._mic.switch_device.side_effect = None
                with patch("app.core.orchestrator._make_video_capture", return_value=Capture()), \
                     patch("app.capture.sources.make_system_audio_capture", return_value=Capture()):
                    rec.resume()
                    rec.resume()
                self.assertFalse(rec.is_paused())
                self.assertFalse(rec._clock.is_paused)
                self.assertEqual(rec._video_segments, [str(previous), str(root / "video_seg1.mkv")])
                self.assertEqual(len(rec._system_segments), int(rec._settings.capture_system_audio))

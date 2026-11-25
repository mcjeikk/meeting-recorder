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

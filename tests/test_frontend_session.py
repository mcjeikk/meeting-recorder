"""El mismo botón y atajo actúan sobre el estado confirmado por el motor."""
import shutil
import subprocess
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.core.config import AudioDevice
from app.encode.ffmpeg import get_ffmpeg_exe
from tests.qml_window import click, item, make_window


class TestSessionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.video = Path(cls.temp.name) / "original.mkv"
        subprocess.run([get_ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i",
                        "color=c=green:s=96x64:r=10", "-t", "0.5", "-c:v", "libx264", str(cls.video)],
                       check=True, capture_output=True)

    def wait(self, predicate):
        until = time.monotonic() + 10
        while time.monotonic() < until:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(.01)
        self.fail(f"Sin transición: {self.window.session.phase}, {self.window.statusText}")

    def setUp(self):
        self.window = w = make_window(self)
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch("app.core.output_path.recorder_data_root", return_value=root))
        self.enterContext(patch.object(w, "_confirm", return_value=True))
        self.enterContext(patch.object(w, "_mac_permissions_ok", return_value=True))
        self.fail_device = ""
        fixture = self

        class Video:
            def start(self, path):
                shutil.copyfile(fixture.video, path)
                if fixture.fail_device == "video":
                    raise OSError("ventana cerrada")
            def stop(self):
                pass

        class System:
            def start(self, path):
                with wave.open(path, "wb") as wav:
                    wav.setparams((1, 2, 48000, 0, "NONE", ""))
                    wav.writeframes(bytes(48000))
                if fixture.fail_device == "system":
                    raise OSError("salida desconectada")
            def stop(self):
                pass
            def current_level(self):
                return 0.

        class Input:
            def __init__(self, *, callback, **kwargs):
                self.callback = callback
            def start(self):
                if fixture.fail_device == "mic":
                    raise OSError("micrófono desconectado")
                self.callback(np.zeros((24000, 1), dtype=np.int16), 24000, None, None)
            def stop(self):
                pass
            def close(self):
                pass

        self.enterContext(patch("app.core.orchestrator._make_video_capture", side_effect=lambda *_: Video()))
        self.enterContext(patch("app.capture.sources.make_system_audio_capture", System))
        self.enterContext(patch("sounddevice.InputStream", Input))

    def record_and_pause(self, system, mic):
        w = self.window
        w.pref.flag("capture_system_audio", system)
        w.audio.devices = [AudioDevice(1, "Micrófono de prueba", 1)] if mic else []
        w.audio._index = int(mic)
        w.audio.changed.emit()
        click(w, "recordButton")
        self.wait(lambda: w.session.phase == "recording")
        click(w, "pauseButton")
        self.wait(lambda: w.session.phase == "paused")

    def test_failed_resume_keeps_button_clock_and_saves_completed_tracks(self):
        w = self.window
        for system, mic in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(system=system, mic=mic):
                self.fail_device = ""
                self.record_and_pause(system, mic)
                rec = w.session.recorder
                frozen = rec.elapsed_seconds()
                self.fail_device = "mic" if mic else "system" if system else "video"
                w.session.togglePause()  # La bandeja y el atajo usan esta misma acción.
                self.wait(lambda: w.session.phase == "paused")
                self.assertIn("No se pudo reanudar", w.statusText)
                self.assertEqual(item(w, "pauseButton").property("text"), "Reanudar")
                self.assertEqual(rec.elapsed_seconds(), frozen)
                click(w, "recordButton")
                self.wait(lambda: w.session.phase == "idle" and w.lastFile)
                probe = subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-i", w._last_output],
                                       capture_output=True).stderr.decode(errors="replace")
                self.assertIn("Video: h264", probe)
                self.assertEqual(probe.count("Audio: aac"), int(system) + int(mic) + int(system and mic))
                for present, name in ((system, "Sistema"), (mic, "Microfono"), (system and mic, "Mezcla")):
                    self.assertEqual(name in probe, present)

    def test_retry_and_recovery_after_failed_delivery(self):
        w = self.window
        self.record_and_pause(True, False)
        self.fail_device = "system"
        click(w, "pauseButton")
        self.wait(lambda: w.session.phase == "paused")
        self.fail_device = ""
        click(w, "pauseButton")
        self.wait(lambda: w.session.phase == "recording")
        self.assertEqual(len(w.session.recorder._video_segments), 2)
        with patch("app.core.orchestrator.copy_mp4_verified", side_effect=OSError("destino lleno")):
            click(w, "recordButton")
            self.wait(lambda: w.session.phase == "recovery")
        self.assertEqual(item(w, "recordButton").property("text"), "Recuperar")
        with patch("app.ui.main_window.QFileDialog.getExistingDirectory", return_value=str(w.pref.directory)):
            click(w, "recordButton")
        self.wait(lambda: w.session.phase == "idle" and w.lastFile)
        self.assertTrue(Path(w._last_output).is_file())

    def test_reopen_recovers_only_committed_video_and_audio(self):
        from app.core.orchestrator import Recorder
        from app.core.output_path import load_pending

        w = self.window
        self.record_and_pause(True, True)
        click(w, "pauseButton")
        self.wait(lambda: w.session.phase == "recording")
        with patch("app.core.orchestrator.mux_recording", side_effect=OSError("destino lleno")):
            click(w, "recordButton")
            self.wait(lambda: w.session.phase == "recovery")
        pending = load_pending()
        self.assertIsNotNone(pending)
        root = Path(pending.temp_dir)
        # Un intento interrumpido dejó residuos ajenos al último tramo confirmado.
        for filename in ("video_seg2.mkv", "system_seg2.wav", "mic_seg_2.wav"):
            (root / filename).write_bytes(b"incompleto")
        saved = []
        recorder = Recorder(on_finished=saved.append)
        recorder.adopt_pending(pending)
        self.assertEqual(len(recorder._video_segments), 2)
        self.assertEqual(len(recorder._system_segments), 2)
        self.assertEqual([c for _, c in recorder._mic_segments()], [0, 1])
        recorder.retry_save(w.pref.directory)
        self.assertEqual(len(saved), 1)
        probe = subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-i", saved[0]],
                               capture_output=True).stderr.decode(errors="replace")
        self.assertEqual(probe.count("Audio: aac"), 3)
        self.assertIsNone(load_pending())

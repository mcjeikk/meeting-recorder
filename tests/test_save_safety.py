"""Guardado a prueba de rutas largas: no borrar la sesión si el MP4 no está."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import RecordingSettings, VideoSource
from app.core.orchestrator import Recorder
from app.core.output_path import (
    PendingSave,
    clear_pending,
    copy_mp4_verified,
    dest_file_path,
    ffmpeg_path_too_long,
    folder_looks_unusable,
    load_pending,
    session_has_media,
    staging_mp4_path,
    write_pending,
)


class TestOutputPath(unittest.TestCase):
    def test_empty_folder_is_unusable(self) -> None:
        self.assertIsNotNone(folder_looks_unusable(""))
        self.assertIsNotNone(folder_looks_unusable("   "))

    def test_long_ffmpeg_path(self) -> None:
        long_dir = Path("C:/") / ("a" * 250)
        self.assertTrue(ffmpeg_path_too_long(long_dir))
        self.assertTrue(ffmpeg_path_too_long(dest_file_path(long_dir, "clip")))
        self.assertFalse(ffmpeg_path_too_long(Path("C:/Videos/Grabaciones")))

    def test_copy_verified_and_session_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "a.mp4"
            src.write_bytes(b"hello-mp4-bytes")
            dest = root / "out" / "b.mp4"
            copy_mp4_verified(src, dest)
            self.assertEqual(dest.read_bytes(), src.read_bytes())
            sess = root / "recsess_x"
            sess.mkdir()
            self.assertFalse(session_has_media(sess))
            (sess / "video_seg0.mkv").write_bytes(b"x" * 10)
            self.assertTrue(session_has_media(sess))

    def test_pending_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sess = root / "recsess_p"
            sess.mkdir()
            (sess / "video_seg0.mkv").write_bytes(b"x" * 8)
            with patch("app.core.output_path.recorder_data_root", return_value=root):
                write_pending(
                    PendingSave(
                        temp_dir=str(sess),
                        staging_mp4="",
                        intended_dest=str(root / "dest.mp4"),
                        stem="s",
                    )
                )
                loaded = load_pending()
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertTrue(loaded.has_media())
                clear_pending()
                self.assertIsNone(load_pending())


class TestFinalizeKeepsSession(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.session = self.root / "recsess_t"
        self.session.mkdir()
        (self.session / "video_seg0.mkv").write_bytes(b"v" * 64)
        self.dest_dir = self.root / "dest"
        self.dest_dir.mkdir()
        self.finished: list[str] = []
        self.failed: list[str] = []
        self.errors: list[str] = []

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _recorder(self) -> Recorder:
        rec = Recorder(
            on_finished=self.finished.append,
            on_error=self.errors.append,
            on_save_failed=self.failed.append,
        )
        rec._settings = RecordingSettings(
            video_source=VideoSource(kind="screen", monitor_index=1, is_primary=True),
            mic_device=None,
            output_dir=self.dest_dir,
        )
        rec._temp_dir = str(self.session)
        rec._video_segments = [str(self.session / "video_seg0.mkv")]
        return rec

    def _write_staging(self, *args, **kwargs):
        out = Path(kwargs["output_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"STAGING-MP4" * 20)

    def test_mux_failure_does_not_delete_session(self) -> None:
        rec = self._recorder()
        with patch("app.core.output_path.recorder_data_root", return_value=self.root):
            with patch("app.core.orchestrator.probe_duration", return_value=1.0):
                with patch(
                    "app.core.orchestrator.concat_videos",
                    side_effect=lambda paths, out: paths[0],
                ):
                    with patch(
                        "app.core.orchestrator.mux_recording",
                        side_effect=RuntimeError("FFmpeg falló al multiplexar: No such file"),
                    ):
                        rec._finalize()
        self.assertTrue(self.session.is_dir())
        self.assertTrue((self.session / "video_seg0.mkv").is_file())
        self.assertTrue(self.failed)
        self.assertFalse(self.finished)
        self.assertTrue(rec.has_unsaved_session())

    def test_copy_failure_keeps_session_and_retry_saves(self) -> None:
        rec = self._recorder()
        good = self.root / "ok"
        with patch("app.core.output_path.recorder_data_root", return_value=self.root):
            with patch("app.core.orchestrator.probe_duration", return_value=1.0):
                with patch(
                    "app.core.orchestrator.concat_videos",
                    side_effect=lambda paths, out: paths[0],
                ):
                    with patch(
                        "app.core.orchestrator.mux_recording",
                        side_effect=self._write_staging,
                    ):
                        with patch(
                            "app.core.orchestrator.copy_mp4_verified",
                            side_effect=OSError("path too long"),
                        ):
                            rec._finalize()
                        self.assertTrue(self.session.is_dir())
                        self.assertTrue(self.failed)
                        self.assertTrue(rec.has_unsaved_session())
                        rec.retry_save(good)
        self.assertTrue(self.finished)
        saved = Path(self.finished[-1])
        self.assertTrue(saved.is_file())
        self.assertGreater(saved.stat().st_size, 0)
        self.assertFalse(self.session.is_dir())

    def test_success_cleans_session(self) -> None:
        rec = self._recorder()
        with patch("app.core.output_path.recorder_data_root", return_value=self.root):
            with patch("app.core.orchestrator.probe_duration", return_value=1.0):
                with patch(
                    "app.core.orchestrator.concat_videos",
                    side_effect=lambda paths, out: paths[0],
                ):
                    with patch(
                        "app.core.orchestrator.mux_recording",
                        side_effect=self._write_staging,
                    ):
                        rec._finalize()
        self.assertTrue(self.finished)
        self.assertFalse(self.failed)
        self.assertFalse(self.session.is_dir())
        dest = Path(self.finished[0])
        self.assertTrue(dest.is_file())
        self.assertGreater(dest.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()

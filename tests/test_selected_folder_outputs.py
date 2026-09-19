"""After changing Carpeta de salida, meeting conversion/transcript paths follow that folder."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.core.config import (
    AppConfig,
    apply_selected_output_dir,
    default_output_dir,
    resolve_output_dir,
)
from app.transcription.integration import (
    build_command,
    output_dir_for,
    result_dir_for,
    transcripts_base,
)
from app.transcription.jobs import JobStore


def _under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class TestResolveOutputDir(unittest.TestCase):
    def test_resolves_absolute_and_ignores_factory_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp) / "project-B"
            b.mkdir()
            resolved = resolve_output_dir(b)
            self.assertTrue(resolved.is_absolute())
            self.assertEqual(resolved, b.resolve())
            self.assertNotEqual(resolved, default_output_dir().resolve())

    def test_empty_raises_instead_of_default(self) -> None:
        with self.assertRaises(ValueError):
            resolve_output_dir("  ")

    def test_apply_selected_updates_config_in_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp) / "chosen"
            b.mkdir()
            cfg = AppConfig(output_dir=str(default_output_dir()))
            applied = apply_selected_output_dir(cfg, b)
            self.assertEqual(Path(cfg.output_dir).resolve(), b.resolve())
            self.assertEqual(applied, b.resolve())


class TestSelectedFolderConversionPaths(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.folder_b = Path(self._tmp.name) / "recordings-B"
        self.folder_b.mkdir()
        self.selected = resolve_output_dir(self.folder_b)
        self.mp4 = self.selected / "Standup_2026-08-20_12-00-00.mp4"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_meeting_mp4_and_transcripts_live_under_B(self) -> None:
        factory = default_output_dir().resolve()
        self.assertNotEqual(self.selected, factory)
        self.assertFalse(_under(self.mp4, factory))
        self.assertTrue(_under(self.mp4, self.selected))

        tx = output_dir_for(self.mp4)
        result = result_dir_for(self.mp4)
        self.assertTrue(tx.is_absolute())
        self.assertTrue(result.is_absolute())
        self.assertTrue(_under(tx, self.selected))
        self.assertTrue(_under(result, self.selected))
        self.assertEqual(tx, (self.selected / "Transcripciones").resolve())
        self.assertEqual(
            result,
            (self.selected / "Transcripciones" / self.mp4.stem).resolve(),
        )
        self.assertFalse(_under(tx, transcripts_base()))
        self.assertFalse(_under(result, transcripts_base()))

    def test_build_command_output_is_absolute_under_B(self) -> None:
        tx = output_dir_for(self.mp4)
        cmd = build_command(
            r"C:\Apps\Transcriptor",
            Path("work.wav"),
            "es",
            tx,
        )
        self.assertIn("--output", cmd)
        out_flag = Path(cmd[cmd.index("--output") + 1])
        self.assertTrue(out_flag.is_absolute())
        self.assertTrue(_under(out_flag, self.selected))
        self.assertFalse(str(out_flag).replace("\\", "/").endswith("/output"))
        self.assertNotEqual(out_flag.name.lower(), "output")

    def test_open_folder_candidates_are_under_B(self) -> None:
        recordings_dir = self.mp4.parent
        transcript_dir = result_dir_for(self.mp4)
        self.assertEqual(recordings_dir.resolve(), self.selected)
        self.assertTrue(_under(transcript_dir, self.selected))


class TestRelativeMediaDoesNotLandInSiblingProject(unittest.TestCase):
    def test_relative_media_yields_absolute_transcripciones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grab = root / "Grabaciones"
            grab.mkdir()
            media = grab / "meet.mp4"
            media.write_bytes(b"x")
            old = os.getcwd()
            try:
                os.chdir(root)
                rel = Path("Grabaciones") / "meet.mp4"
                out = output_dir_for(rel)
                self.assertTrue(out.is_absolute())
                self.assertEqual(out, (grab / "Transcripciones").resolve())
                cmd = build_command(r"C:\Apps\Transcriptor", rel, "es", out)
                flag = Path(cmd[cmd.index("--output") + 1])
                self.assertTrue(flag.is_absolute())
                self.assertTrue(_under(flag, grab))
            finally:
                os.chdir(old)


class TestImportsFollowSelectedFolder(unittest.TestCase):
    def test_import_from_A_lands_under_selected_B(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "old-A"
            b = Path(tmp) / "new-B"
            a.mkdir()
            b.mkdir()
            media_a = a / "entrevista.mp4"
            media_a.write_bytes(b"x")
            out = output_dir_for(media_a, output_base=b)
            result = result_dir_for(media_a, output_base=b)
            self.assertTrue(_under(result, b))
            self.assertFalse(_under(result, a))
            self.assertEqual(out, (b / "Transcripciones").resolve())
            self.assertEqual(
                result,
                (b / "Transcripciones" / "entrevista").resolve(),
            )
            cmd = build_command(r"C:\Apps\Transcriptor", Path("work.wav"), "es", out)
            flag = Path(cmd[cmd.index("--output") + 1])
            self.assertTrue(flag.is_absolute())
            self.assertTrue(_under(flag, b))
            self.assertFalse(_under(flag, a))

    def test_empty_output_base_stays_beside_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "src"
            a.mkdir()
            media = a / "clip.mp4"
            result = result_dir_for(media, output_base="")
            self.assertTrue(_under(result, a))
            self.assertEqual(
                result,
                (a / "Transcripciones" / "clip").resolve(),
            )

    def test_enqueue_snapshots_absolute_output_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(base=Path(tmp) / "tx")
            a = Path(tmp) / "src"
            b = Path(tmp) / "out"
            a.mkdir()
            b.mkdir()
            media = a / "clip.mp4"
            media.write_bytes(b"x")
            job = store.enqueue(str(media), language="es", output_base=str(b))
            self.assertIsNotNone(job)
            stored = Path(job.output_base)
            self.assertTrue(stored.is_absolute())
            self.assertEqual(stored, b.resolve())
            result = result_dir_for(Path(job.media_path), output_base=job.output_base)
            self.assertTrue(_under(result, b))
            self.assertFalse(_under(result, a))
            self.assertTrue(media.is_file())
            self.assertFalse((b / media.name).exists())


class TestEnqueueCanonicalPath(unittest.TestCase):
    def test_enqueue_stores_absolute_media_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(base=Path(tmp) / "tx")
            root = Path(tmp)
            grab = root / "Grabaciones"
            grab.mkdir()
            media = grab / "clip.mp4"
            media.write_bytes(b"x")
            old = os.getcwd()
            try:
                os.chdir(root)
                job = store.enqueue(str(Path("Grabaciones") / "clip.mp4"), language="es")
                self.assertIsNotNone(job)
                stored = Path(job.media_path)
                self.assertTrue(stored.is_absolute())
                self.assertEqual(stored, media.resolve())
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()

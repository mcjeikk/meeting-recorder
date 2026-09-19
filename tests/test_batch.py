"""Agrupar jobs para un solo CLI (reutilización de modelos)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.transcription.batch import compatible_batch, job_fingerprint
from app.transcription.jobs import JobStore
from app.transcription.presets import cli_args_from_job_fields


class TestCompatibleBatch(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_three_same_fingerprint_group(self) -> None:
        a = self.store.enqueue(str(Path(self._tmp.name) / "a.mp4"), language="es")
        b = self.store.enqueue(str(Path(self._tmp.name) / "b.mp4"), language="es")
        c = self.store.enqueue(str(Path(self._tmp.name) / "c.mp4"), language="es")
        assert a and b and c
        group = compatible_batch(a, self.store.pending())
        self.assertEqual(group[0].id, a.id)
        self.assertEqual({j.id for j in group}, {a.id, b.id, c.id})
        self.assertEqual(len(group), 3)
        self.assertEqual(job_fingerprint(a), job_fingerprint(b))

    def test_different_output_base_not_grouped(self) -> None:
        a = self.store.enqueue(
            str(Path(self._tmp.name) / "a.mp4"),
            language="es",
            output_base=str(Path(self._tmp.name) / "out1"),
        )
        b = self.store.enqueue(
            str(Path(self._tmp.name) / "b.mp4"),
            language="es",
            output_base=str(Path(self._tmp.name) / "out2"),
        )
        assert a and b
        group = compatible_batch(a, self.store.pending())
        self.assertEqual([j.id for j in group], [a.id])

    def test_different_language_not_grouped(self) -> None:
        a = self.store.enqueue(str(Path(self._tmp.name) / "a.mp4"), language="es")
        b = self.store.enqueue(str(Path(self._tmp.name) / "b.mp4"), language="en")
        assert a and b
        group = compatible_batch(a, self.store.pending())
        self.assertEqual([j.id for j in group], [a.id])

    def test_speakers_snapshot(self) -> None:
        job = self.store.enqueue(
            str(Path(self._tmp.name) / "a.mp4"),
            language="es",
            num_speakers=2,
        )
        assert job is not None
        self.assertEqual(job.num_speakers, 2)
        auto = self.store.enqueue(str(Path(self._tmp.name) / "b.mp4"), language="es")
        assert auto is not None
        self.assertEqual(auto.num_speakers, 0)
        self.assertNotEqual(job_fingerprint(job), job_fingerprint(auto))
        args = cli_args_from_job_fields(
            model=job.model,
            beam_size=job.beam_size,
            no_diarize=False,
            num_speakers=2,
        )
        self.assertIn("--speakers", args)
        self.assertIn("2", args)

    def test_build_command_lists_all_wavs(self) -> None:
        from app.transcription.integration import build_command

        cmd = build_command(
            r"C:\Apps\Transcriptor",
            [Path("a.wav"), Path("b.wav")],
            "es",
            Path(r"D:\out\Transcripciones"),
        )
        joined = " ".join(cmd)
        self.assertIn("a.wav", joined)
        self.assertIn("b.wav", joined)
        self.assertLess(cmd.index("a.wav"), cmd.index("--language"))
        self.assertLess(cmd.index("b.wav"), cmd.index("--language"))


if __name__ == "__main__":
    unittest.main()

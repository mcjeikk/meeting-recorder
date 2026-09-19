"""OOM degrade and queue counts."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.transcription.jobs import ERROR, PENDING, JobStore
from app.transcription.pc_impact import PROFILE_USABLE
from app.transcription.process_guard import apply_oom_degrade, log_looks_like_oom
from app.transcription.presets import PRESET_EQUILIBRADO, get_preset


class TestOomDetect(unittest.TestCase):
    def test_markers(self) -> None:
        self.assertTrue(log_looks_like_oom("Unable to allocate 973. MiB for an array"))
        self.assertTrue(log_looks_like_oom("mkl_malloc: failed to allocate memory"))
        self.assertFalse(log_looks_like_oom("transcribiendo... 20%"))


class TestOomDegrade(unittest.TestCase):
    def test_model_then_speakers(self) -> None:
        job = SimpleNamespace(
            no_diarize=False, model="large-v3", pc_impact="full", note=""
        )
        self.assertTrue(apply_oom_degrade(job))
        self.assertFalse(job.no_diarize)
        self.assertEqual(job.pc_impact, PROFILE_USABLE)
        self.assertEqual(job.model, get_preset(PRESET_EQUILIBRADO).model)
        self.assertTrue(apply_oom_degrade(job))
        self.assertTrue(job.no_diarize)
        self.assertFalse(apply_oom_degrade(job))

    def test_usable_turbo_drops_speakers_last(self) -> None:
        job = SimpleNamespace(
            no_diarize=False,
            model=get_preset(PRESET_EQUILIBRADO).model,
            pc_impact=PROFILE_USABLE,
            note="",
        )
        self.assertTrue(apply_oom_degrade(job))
        self.assertTrue(job.no_diarize)


class TestQueueCountsAndRetry(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_counts(self) -> None:
        a = self.store.enqueue(str(Path(self._tmp.name) / "a.mp4"))
        b = self.store.enqueue(str(Path(self._tmp.name) / "b.mp4"))
        c = self.store.enqueue(str(Path(self._tmp.name) / "c.mp4"))
        assert a and b and c
        b.status = ERROR
        b.error = "Unable to allocate 973. MiB"
        self.store.save(b)
        c.status = "running"
        self.store.save(c)
        counts = self.store.queue_counts()
        self.assertEqual(counts["pending"], 1)
        self.assertEqual(counts["running"], 1)
        self.assertEqual(counts["failed"], 1)

    def test_retry_oom_keeps_speakers_first(self) -> None:
        job = self.store.enqueue(str(Path(self._tmp.name) / "long.mp4"))
        assert job is not None
        job.status = ERROR
        job.error = "mkl_malloc: failed to allocate memory"
        job.no_diarize = False
        job.model = "large-v3"
        job.pc_impact = "full"
        self.store.save(job)
        retried = self.store.retry(job.id)
        assert retried is not None
        self.assertEqual(retried.status, PENDING)
        self.assertFalse(retried.no_diarize)
        self.assertEqual(retried.model, get_preset(PRESET_EQUILIBRADO).model)
        self.assertEqual(retried.pc_impact, PROFILE_USABLE)


if __name__ == "__main__":
    unittest.main()

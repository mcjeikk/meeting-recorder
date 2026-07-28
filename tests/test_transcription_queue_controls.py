"""Unit tests: queue cancel/clear and language normalize."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.transcription.jobs import (
    CANCELLED,
    DEFAULT_LANGUAGE,
    DONE,
    ERROR,
    PENDING,
    JobStore,
    normalize_language,
)


class TestNormalizeLanguage(unittest.TestCase):
    def test_known(self) -> None:
        self.assertEqual(normalize_language("es"), "es")
        self.assertEqual(normalize_language("EN"), "en")
        self.assertEqual(normalize_language(" Auto "), "auto")

    def test_unknown(self) -> None:
        self.assertEqual(normalize_language(""), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language("fr"), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language(None), DEFAULT_LANGUAGE)


class TestJobStoreCancelClear(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cancel_pending(self) -> None:
        job = self.store.enqueue(str(Path(self._tmp.name) / "a.mp4"), language="en")
        assert job is not None
        cancelled = self.store.cancel(job.id)
        assert cancelled is not None
        self.assertEqual(cancelled.status, CANCELLED)
        self.assertIn("Cancelado", cancelled.error)
        reloaded = self.store._load(self.store._path(job.id))
        assert reloaded is not None
        self.assertEqual(reloaded.status, CANCELLED)
        self.assertEqual(reloaded.language, "en")

    def test_cancel_done_noop(self) -> None:
        job = self.store.enqueue(str(Path(self._tmp.name) / "b.mp4"))
        assert job is not None
        job.status = DONE
        self.store.save(job)
        self.assertIsNone(self.store.cancel(job.id))

    def test_clear_failed_leaves_pending_and_done(self) -> None:
        pending = self.store.enqueue(str(Path(self._tmp.name) / "p.mp4"))
        assert pending is not None
        done = self.store.enqueue(str(Path(self._tmp.name) / "d.mp4"))
        assert done is not None
        done.status = DONE
        self.store.save(done)
        # second enqueue of same media after error path: create error job via save
        err = self.store.enqueue(str(Path(self._tmp.name) / "e.mp4"))
        assert err is not None
        err.status = ERROR
        err.error = "boom"
        self.store.save(err)
        cancelled = self.store.enqueue(str(Path(self._tmp.name) / "c.mp4"))
        assert cancelled is not None
        self.store.cancel(cancelled.id)

        n = self.store.clear_failed()
        self.assertEqual(n, 2)
        ids = {j.id for j in self.store.all()}
        self.assertIn(pending.id, ids)
        self.assertIn(done.id, ids)
        self.assertNotIn(err.id, ids)
        self.assertNotIn(cancelled.id, ids)
        self.assertEqual(self.store.count_clearable(), 0)

    def test_enqueue_normalizes_language(self) -> None:
        job = self.store.enqueue(str(Path(self._tmp.name) / "l.mp4"), language="FR")
        assert job is not None
        self.assertEqual(job.language, DEFAULT_LANGUAGE)


if __name__ == "__main__":
    unittest.main()

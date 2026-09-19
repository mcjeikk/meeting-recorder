"""Queue status lines for the UI list."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.transcription.jobs import ERROR, PENDING, RUNNING, JobStore
from app.transcription.queue_status import (
    batch_suffix,
    format_queue_line,
    format_queue_lines,
    visible_queue_jobs,
)


class TestQueueStatusLines(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_three_files_show_three_rows(self) -> None:
        a = self.store.enqueue(str(Path(self._tmp.name) / "Parte 1.mp4"))
        b = self.store.enqueue(str(Path(self._tmp.name) / "Parte 2.mp4"))
        c = self.store.enqueue(str(Path(self._tmp.name) / "Parte 3.mp4"))
        assert a and b and c
        a.status = RUNNING
        self.store.save(a)
        rows = format_queue_lines(self.store.all(), current_id=a.id, progress=20)
        self.assertEqual(len(rows), 3)
        self.assertTrue(any("Parte 1" in r and "En curso" in r for r in rows))
        self.assertTrue(any("Parte 2" in r and "En espera" in r for r in rows))
        self.assertTrue(any("Parte 3" in r and "En espera" in r for r in rows))
        dones = [j for j in self.store.all() if j.status == "done"]
        self.assertEqual(visible_queue_jobs(dones), [])

    def test_all_running_only_live_is_in_progress(self) -> None:
        a = self.store.enqueue(str(Path(self._tmp.name) / "reunion-1.mp4"))
        b = self.store.enqueue(str(Path(self._tmp.name) / "reunion-2.mp4"))
        c = self.store.enqueue(str(Path(self._tmp.name) / "reunion-3.mp4"))
        assert a and b and c
        for job in (a, b, c):
            job.status = RUNNING
            job.pid = 4242
            self.store.save(job)
        rows = format_queue_lines(self.store.all(), current_id=b.id, progress=40)
        self.assertEqual(len(rows), 3)
        self.assertTrue(any("reunion-2" in r and "En curso (40%)" in r for r in rows))
        self.assertTrue(any("reunion-1" in r and "En espera" in r for r in rows))
        self.assertTrue(any("reunion-3" in r and "En espera" in r for r in rows))
        counts = self.store.queue_counts(live_id=b.id)
        self.assertEqual(counts["running"], 1)
        self.assertEqual(counts["pending"], 2)

    def test_batch_suffix_only_for_real_batches(self) -> None:
        self.assertEqual(batch_suffix({"batch_pos": 4, "batch_total": 10}), "  ·  archivo 4 de 10")
        self.assertEqual(batch_suffix({"batch_pos": 1, "batch_total": 1}), "")
        self.assertEqual(batch_suffix({"batch_pos": 0, "batch_total": 0}), "")
        self.assertEqual(batch_suffix({}), "")
        self.assertEqual(batch_suffix({"batch_pos": 11, "batch_total": 10}), "")

    def test_error_line_includes_reason(self) -> None:
        job = self.store.enqueue(str(Path(self._tmp.name) / "largo.mp4"))
        assert job is not None
        job.status = ERROR
        job.error = "Unable to allocate 973. MiB"
        self.assertIn("Falló", format_queue_line(job))
        self.assertIn("Unable to allocate", format_queue_line(job))
        job.status = PENDING
        self.assertIn("En espera", format_queue_line(job))


if __name__ == "__main__":
    unittest.main()

"""Uso del PC: thread budget, snapshot, legacy jobs, env."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.transcription.integration import (
    cpu_threads_for_job,
    creationflags_for_job,
    subprocess_env,
)
from app.transcription.jobs import DONE, PENDING, JobStore
from app.core.config import AppConfig
from app.transcription.pc_impact import (
    BELOW_NORMAL_PRIORITY,
    DEFAULT_PC_IMPACT,
    FACTORY_DEFAULT_REV,
    IDLE_PRIORITY,
    LEGACY_JOB_PC_IMPACT,
    PROFILE_FULL,
    PROFILE_USABLE,
    THREAD_ENV_KEYS,
    apply_factory_pc_impact,
    normalize_pc_impact,
    priority_class,
    threads_for_impact,
)
from app.transcription.presets import PRESET_MAXIMA, get_preset


class TestNormalizePcImpact(unittest.TestCase):
    def test_known(self) -> None:
        self.assertEqual(normalize_pc_impact("usable"), PROFILE_USABLE)
        self.assertEqual(normalize_pc_impact("FULL"), PROFILE_FULL)
        self.assertEqual(normalize_pc_impact("bajo"), PROFILE_USABLE)

    def test_unknown_defaults_full(self) -> None:
        self.assertEqual(DEFAULT_PC_IMPACT, PROFILE_FULL)
        self.assertEqual(normalize_pc_impact(""), DEFAULT_PC_IMPACT)
        self.assertEqual(normalize_pc_impact(None), DEFAULT_PC_IMPACT)
        self.assertEqual(normalize_pc_impact("xyz"), DEFAULT_PC_IMPACT)
        self.assertEqual(AppConfig().transcription_pc_impact, PROFILE_FULL)


class TestThreadBudget(unittest.TestCase):
    def test_table(self) -> None:
        self.assertEqual(threads_for_impact(PROFILE_USABLE, cpu_count=8), 4)
        self.assertEqual(threads_for_impact(PROFILE_FULL, cpu_count=8), 6)
        self.assertEqual(threads_for_impact(PROFILE_USABLE, cpu_count=16), 4)
        self.assertEqual(threads_for_impact(PROFILE_FULL, cpu_count=16), 14)
        self.assertEqual(threads_for_impact(PROFILE_USABLE, cpu_count=4), 2)
        self.assertEqual(threads_for_impact(PROFILE_FULL, cpu_count=4), 2)
        self.assertEqual(threads_for_impact(PROFILE_USABLE, cpu_count=2), 1)
        self.assertEqual(threads_for_impact(PROFILE_FULL, cpu_count=2), 1)

    def test_usable_never_exceeds_full(self) -> None:
        for n in (2, 4, 6, 8, 12, 16, 32):
            u = threads_for_impact(PROFILE_USABLE, cpu_count=n)
            f = threads_for_impact(PROFILE_FULL, cpu_count=n)
            self.assertLessEqual(u, f, n)
            self.assertGreaterEqual(u, 1)

    def test_usable_strictly_smaller_above_4(self) -> None:
        self.assertLess(
            threads_for_impact(PROFILE_USABLE, cpu_count=8),
            threads_for_impact(PROFILE_FULL, cpu_count=8),
        )
        self.assertEqual(
            cpu_threads_for_job(PROFILE_USABLE, cpu_count=8),
            threads_for_impact(PROFILE_USABLE, cpu_count=8),
        )


class TestEnvAndPriority(unittest.TestCase):
    def test_env_caps_match_threads(self) -> None:
        env = subprocess_env(PROFILE_USABLE)
        n = str(cpu_threads_for_job(PROFILE_USABLE))
        for key in THREAD_ENV_KEYS:
            self.assertEqual(env[key], n, key)
        self.assertEqual(env["TRANSCRIPTOR_PLAIN"], "1")

    def test_priority_differs(self) -> None:
        self.assertEqual(priority_class(PROFILE_USABLE), IDLE_PRIORITY)
        self.assertEqual(priority_class(PROFILE_FULL), BELOW_NORMAL_PRIORITY)
        if IDLE_PRIORITY or BELOW_NORMAL_PRIORITY:
            self.assertNotEqual(
                creationflags_for_job(PROFILE_USABLE),
                creationflags_for_job(PROFILE_FULL),
            )


class TestJobSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))
        self.media = Path(self._tmp.name) / "meet.mp4"
        self.media.write_bytes(b"x")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_new_enqueue_defaults_full(self) -> None:
        job = self.store.enqueue(str(self.media), language="es")
        assert job is not None
        self.assertEqual(job.pc_impact, PROFILE_FULL)
        self.assertEqual(job.status, PENDING)

    def test_factory_rev_migrates_old_usable_once(self) -> None:
        class Cfg:
            transcription_pc_impact = PROFILE_USABLE
            pc_impact_factory_rev = 1

        cfg = Cfg()
        self.assertTrue(apply_factory_pc_impact(cfg))
        self.assertEqual(cfg.transcription_pc_impact, PROFILE_FULL)
        self.assertEqual(cfg.pc_impact_factory_rev, FACTORY_DEFAULT_REV)
        cfg.transcription_pc_impact = PROFILE_USABLE
        self.assertFalse(apply_factory_pc_impact(cfg))
        self.assertEqual(cfg.transcription_pc_impact, PROFILE_USABLE)

    def test_snapshot_keeps_full_when_asked(self) -> None:
        job = self.store.enqueue(
            str(self.media), language="es", pc_impact=PROFILE_FULL
        )
        assert job is not None
        self.assertEqual(job.pc_impact, PROFILE_FULL)
        loaded = self.store._load(self.store._path(job.id))
        assert loaded is not None
        self.assertEqual(loaded.pc_impact, PROFILE_FULL)

    def test_legacy_job_without_field_is_full(self) -> None:
        job = self.store.enqueue(str(self.media), language="es")
        assert job is not None
        path = self.store._path(job.id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("pc_impact", None)
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = self.store._load(path)
        assert loaded is not None
        self.assertEqual(loaded.pc_impact, LEGACY_JOB_PC_IMPACT)
        self.assertEqual(LEGACY_JOB_PC_IMPACT, PROFILE_FULL)

    def test_retry_keeps_pc_impact(self) -> None:
        job = self.store.enqueue(
            str(self.media), language="es", pc_impact=PROFILE_FULL
        )
        assert job is not None
        job.status = "error"
        job.error = "boom"
        self.store.save(job)
        retried = self.store.retry(job.id)
        assert retried is not None
        self.assertEqual(retried.pc_impact, PROFILE_FULL)

    def test_maxima_plus_usable(self) -> None:
        job = self.store.enqueue(
            str(self.media),
            language="es",
            preset=PRESET_MAXIMA,
            pc_impact=PROFILE_USABLE,
        )
        assert job is not None
        self.assertEqual(job.preset, PRESET_MAXIMA)
        self.assertEqual(job.model, get_preset(PRESET_MAXIMA).model)
        self.assertFalse(job.no_diarize)
        self.assertEqual(job.pc_impact, PROFILE_USABLE)

    def test_set_pc_impact_retargets_open_not_done(self) -> None:
        pending = self.store.enqueue(
            str(self.media), language="es", pc_impact=PROFILE_USABLE
        )
        assert pending is not None
        other = Path(self._tmp.name) / "old.mp4"
        other.write_bytes(b"y")
        done = self.store.enqueue(str(other), language="es", pc_impact=PROFILE_USABLE)
        assert done is not None
        done.status = DONE
        self.store.save(done)
        n = self.store.set_pc_impact_on_open(PROFILE_FULL)
        self.assertEqual(n, 1)
        self.assertEqual(
            self.store._load(self.store._path(pending.id)).pc_impact, PROFILE_FULL
        )
        self.assertEqual(
            self.store._load(self.store._path(done.id)).pc_impact, PROFILE_USABLE
        )

    def test_ui_change_does_not_rewrite_job(self) -> None:
        job = self.store.enqueue(
            str(self.media), language="es", pc_impact=PROFILE_USABLE
        )
        assert job is not None
        # A later enqueue of same file is a no-op (done/active dedupe); mutate UI
        # would only affect a *new* media. Pending job stays.
        self.assertEqual(job.pc_impact, PROFILE_USABLE)
        loaded = self.store._load(self.store._path(job.id))
        assert loaded is not None
        self.assertEqual(loaded.status, PENDING)
        self.assertEqual(loaded.pc_impact, PROFILE_USABLE)
        self.assertNotEqual(loaded.status, DONE)


if __name__ == "__main__":
    unittest.main()

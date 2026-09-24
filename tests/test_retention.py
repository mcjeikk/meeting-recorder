"""Poda del histórico de la cola (spec 023): la regla y su aplicación."""
from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.transcription.jobs import (
    CANCELLED,
    DONE,
    ERROR,
    EXTRACTING,
    PENDING,
    RUNNING,
    JobStore,
    TranscriptionJob,
)
from app.transcription.retention import (
    HISTORY_DAYS,
    MAX_DELETIONS_PER_PASS,
    MAX_HISTORY,
    job_age_key,
    oldest_first,
    prunable_job_ids,
    prunable_log_paths,
)

NOW = datetime(2026, 9, 18, 20, 0, 0)


class TestRule(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _job(self, nombre: str, *, status: str = DONE, days_ago: float = 0.0):
        job = self.store.enqueue(str(Path(self._tmp.name) / f"{nombre}.mp4"))
        assert job is not None
        job.status = status
        job.finished_at = (NOW - timedelta(days=days_ago)).isoformat(timespec="milliseconds")
        self.store.save(job)
        return job

    def test_old_finished_records_are_prunable(self) -> None:
        viejo = self._job("vieja", days_ago=HISTORY_DAYS + 1)
        nuevo = self._job("reciente", days_ago=1)
        sobran = prunable_job_ids(self.store.all(), now=NOW)
        self.assertEqual(sobran, {viejo.id})
        self.assertNotIn(nuevo.id, sobran)

    def test_record_inside_the_window_survives(self) -> None:
        justo = self._job("justo", days_ago=HISTORY_DAYS - 0.5)
        self.assertEqual(prunable_job_ids(self.store.all(), now=NOW), set())
        self.assertIn(justo.id, {j.id for j in self.store.all()})

    def test_count_cap_keeps_only_the_newest(self) -> None:
        jobs = [self._job(f"r{i:03d}", days_ago=i * 0.1) for i in range(12)]
        sobran = prunable_job_ids(self.store.all(), now=NOW, max_history=5)
        self.assertEqual(len(sobran), 7)
        for j in jobs[:5]:  # los 5 más recientes (días_ago menor)
            self.assertNotIn(j.id, sobran)
        for j in jobs[5:]:
            self.assertIn(j.id, sobran)

    def test_live_and_failed_records_are_never_prunable(self) -> None:
        """INV-1: trabajo vivo y fallos visibles no son histórico."""
        protegidos = [
            self._job("pendiente", status=PENDING, days_ago=400),
            self._job("extrayendo", status=EXTRACTING, days_ago=400),
            self._job("corriendo", status=RUNNING, days_ago=400),
            self._job("fallida", status=ERROR, days_ago=400),
            self._job("cancelada", status=CANCELLED, days_ago=400),
        ]
        sobran = prunable_job_ids(self.store.all(), now=NOW, max_history=1)
        self.assertEqual(sobran, set())
        self.assertEqual(len(self.store.all()), len(protegidos))

    def test_unreadable_timestamp_is_old_not_immortal(self) -> None:
        """INV-2: una fecha corrupta no puede volver inmortal a un registro."""
        roto = self._job("rota", days_ago=0)
        roto.finished_at = "no es una fecha"
        roto.created_at = ""
        self.store.save(roto)
        self.assertEqual(job_age_key(roto), datetime.min)
        self.assertIn(roto.id, prunable_job_ids(self.store.all(), now=NOW))

    def test_falls_back_to_created_at(self) -> None:
        job = self._job("sin_fin", days_ago=0)
        job.finished_at = ""
        job.created_at = (NOW - timedelta(days=HISTORY_DAYS + 5)).isoformat()
        self.store.save(job)
        self.assertIn(job.id, prunable_job_ids(self.store.all(), now=NOW))

    def test_empty_queue_is_fine(self) -> None:
        self.assertEqual(prunable_job_ids([], now=NOW), set())

    def test_budget_takes_the_oldest_first(self) -> None:
        jobs = [self._job(f"r{i}", days_ago=HISTORY_DAYS + 10 - i) for i in range(5)]
        sobran = prunable_job_ids(self.store.all(), now=NOW)
        elegidos = oldest_first(self.store.all(), sobran, budget=2)
        self.assertEqual(elegidos, [jobs[0].id, jobs[1].id])

    def test_budget_of_zero_deletes_nothing(self) -> None:
        self._job("vieja", days_ago=400)
        sobran = prunable_job_ids(self.store.all(), now=NOW)
        self.assertEqual(oldest_first(self.store.all(), sobran, budget=0), [])


class TestApply(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _job(self, nombre: str, *, status: str = DONE, days_ago: float = 0.0, log: bool = True):
        job = self.store.enqueue(str(Path(self._tmp.name) / f"{nombre}.mp4"))
        assert job is not None
        job.status = status
        job.finished_at = (NOW - timedelta(days=days_ago)).isoformat(timespec="milliseconds")
        self.store.save(job)
        if log:
            Path(job.log_path).write_text("log\n", encoding="utf-8")
        return job

    def test_prune_removes_records_and_their_logs(self) -> None:
        viejo = self._job("vieja", days_ago=HISTORY_DAYS + 10)
        nuevo = self._job("reciente", days_ago=1)
        fallida = self._job("fallida", status=ERROR, days_ago=400)

        resultado = self.store.prune_history(now=NOW)

        self.assertEqual(resultado, {"records": 1, "logs": 1})
        ids = {j.id for j in self.store.all()}
        self.assertEqual(ids, {nuevo.id, fallida.id})
        self.assertFalse(Path(viejo.log_path).exists())
        self.assertTrue(Path(nuevo.log_path).exists())
        self.assertTrue(Path(fallida.log_path).exists())

    def test_orphan_log_is_removed(self) -> None:
        """Limpiezas manuales anteriores dejaron logs sin registro."""
        self._job("reciente", days_ago=1)
        huerfano = self.store.logs_dir / "reunion vieja_abc123def456.log"
        huerfano.write_text("x", encoding="utf-8")
        resultado = self.store.prune_history(now=NOW)
        self.assertEqual(resultado["logs"], 1)
        self.assertFalse(huerfano.exists())

    def test_pruning_twice_removes_nothing_the_second_time(self) -> None:
        """INV-3: idempotente."""
        self._job("vieja", days_ago=HISTORY_DAYS + 10)
        self._job("reciente", days_ago=1)
        primero = self.store.prune_history(now=NOW)
        segundo = self.store.prune_history(now=NOW)
        self.assertEqual(primero["records"], 1)
        self.assertEqual(segundo, {"records": 0, "logs": 0})

    def test_nothing_to_do_is_silent(self) -> None:
        """SC-006: una cola dentro de los límites no pierde nada."""
        self._job("a", days_ago=1)
        self._job("b", days_ago=2)
        self.assertEqual(self.store.prune_history(now=NOW), {"records": 0, "logs": 0})
        self.assertEqual(len(self.store.all()), 2)

    def test_locked_log_does_not_abort_the_pass(self) -> None:
        """INV-7: un log que no se puede borrar se reintenta el próximo arranque."""
        uno = self._job("vieja1", days_ago=HISTORY_DAYS + 5)
        dos = self._job("vieja2", days_ago=HISTORY_DAYS + 6)
        with open(uno.log_path, "r", encoding="utf-8"):  # handle abierto (Windows)
            resultado = self.store.prune_history(now=NOW)
        self.assertEqual(resultado["records"], 2)  # los registros sí se fueron
        self.assertFalse(Path(dos.log_path).exists())
        self.store.prune_history(now=NOW)  # segundo intento, ya sin el handle
        self.assertFalse(Path(uno.log_path).exists())

    def test_three_hundred_records_are_pruned_fast(self) -> None:
        """SC-001/SC-002: un año de historia se acota en una pasada.

        Los registros se escriben directos (no por `enqueue`): el dedupe relee la
        cola entera en cada alta, y con 300 archivos eso es justo el costo que
        esta feature existe para acotar.
        """
        for i in range(300):
            job = TranscriptionJob(
                media_path=str(Path(self._tmp.name) / f"r{i:03d}.mp4"),
                status=DONE,
                finished_at=(NOW - timedelta(days=i * 1.2)).isoformat(timespec="milliseconds"),
            )
            self.store.save(job)
        # Con Defender en tiempo real, la PRIMERA apertura de cada archivo recién
        # escrito cuesta ~14 ms (lo escanea): 300 archivos = ~4.3 s, y la segunda
        # lectura 0.03 s. En la cola real los registros nacen de a uno a lo largo
        # de semanas; aquí nacen todos a la vez. Se lee una vez antes de medir
        # para que el tiempo sea el de la poda y no el del antivirus.
        self.store.all()
        t0 = time.perf_counter()
        primera = self.store.prune_history(now=NOW)
        elapsed = time.perf_counter() - t0

        # Una pasada no paga la deuda entera: borra hasta el presupuesto…
        self.assertEqual(primera["records"], MAX_DELETIONS_PER_PASS)
        self.assertLess(elapsed, 5.0)
        # …y lo hace por los más viejos primero.
        quedan = self.store.all()
        self.assertEqual(len(quedan), 300 - MAX_DELETIONS_PER_PASS)
        self.assertTrue(all(job_age_key(j) > NOW - timedelta(days=300 * 1.2) for j in quedan))

        # Arranques sucesivos convergen a los límites y luego no tocan nada.
        for _ in range(10):
            if self.store.prune_history(now=NOW)["records"] == 0:
                break
        finales = self.store.all()
        self.assertLessEqual(len(finales), MAX_HISTORY)
        self.assertTrue(all(job_age_key(j) >= NOW - timedelta(days=HISTORY_DAYS) for j in finales))
        self.assertEqual(self.store.prune_history(now=NOW), {"records": 0, "logs": 0})

    def test_logs_of_surviving_records_are_kept(self) -> None:
        """INV-6: tras la pasada, todo log que queda tiene registro."""
        for i in range(4):
            self._job(f"r{i}", days_ago=i)
        self._job("vieja", days_ago=HISTORY_DAYS + 1)
        self.store.prune_history(now=NOW)
        vivos = {Path(j.log_path).name for j in self.store.all()}
        for log in self.store.logs_dir.glob("*.log"):
            self.assertIn(log.name, vivos)


class TestLogMatching(unittest.TestCase):
    def test_old_style_log_path_is_matched_by_id(self) -> None:
        """Registros antiguos construían log_path de otra forma."""
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(base=Path(tmp))
            job = store.enqueue(str(Path(tmp) / "reunion.mp4"))
            assert job is not None
            job.log_path = ""  # como si nunca se hubiera guardado
            store.save(job)
            log = store.logs_dir / f"otro nombre_{job.id}.log"
            log.write_text("x", encoding="utf-8")
            self.assertEqual(prunable_log_paths(store.logs_dir, [job]), [])

    def test_missing_log_dir_is_not_an_error(self) -> None:
        self.assertEqual(prunable_log_paths(Path("C:/no/existe/logs"), []), [])


if __name__ == "__main__":
    unittest.main()

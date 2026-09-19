"""Progreso por tiempo y hora estimada de término (spec 021).

Reloj inyectado: nada aquí depende de la hora real ni de un proceso.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.transcription.eta import (
    DEFAULT_FACTORS,
    MIN_SAMPLES,
    STARTUP_SECONDS,
    ProgressTracker,
    SpeedStore,
    estimate_total_seconds,
    format_finish,
    key_for_job,
    speed_key,
    wav_duration_seconds,
    weighted_progress,
)


def _wav(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * (44 + int(seconds * 16000 * 2)))
    return path


class TestAudioDuration(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_duration_from_wav_size(self) -> None:
        wav = _wav(self.root / "a.wav", 600)
        self.assertAlmostEqual(wav_duration_seconds(wav), 600.0, places=3)

    def test_unknown_when_missing_or_empty(self) -> None:
        self.assertEqual(wav_duration_seconds(self.root / "no.wav"), 0.0)
        self.assertEqual(wav_duration_seconds(""), 0.0)
        vacio = self.root / "v.wav"
        vacio.write_bytes(b"\0" * 44)
        self.assertEqual(wav_duration_seconds(vacio), 0.0)


class TestSpeedStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "speed.json"
        self.addCleanup(self._tmp.cleanup)

    def test_key_from_job_fields(self) -> None:
        job = SimpleNamespace(model="large-v3-turbo", no_diarize=False, pc_impact="full")
        self.assertEqual(key_for_job(job), "large-v3-turbo|speakers|full")
        self.assertEqual(
            speed_key("large-v3", True, "usable"), "large-v3|nospeakers|usable"
        )

    def test_default_until_three_samples_then_own_median(self) -> None:
        store = SpeedStore(self.path)
        key = "large-v3-turbo|speakers|full"
        self.assertEqual(store.factor_for(key), DEFAULT_FACTORS[key])
        for factor in (2.0, 2.2, 2.4):
            store.record(key, 3600.0, 3600.0 * factor)
        self.assertEqual(len(SpeedStore(self.path).keys()), 1)
        # Con MIN_SAMPLES muestras manda la máquina, no el default.
        self.assertAlmostEqual(SpeedStore(self.path).factor_for(key), 2.2, places=2)
        self.assertEqual(MIN_SAMPLES, 3)

    def test_short_files_do_not_poison_the_factor(self) -> None:
        store = SpeedStore(self.path)
        key = "large-v3-turbo|speakers|full"
        for _ in range(5):
            store.record(key, 20.0, 120.0)  # 20 s de audio, 6x por la carga de modelos
        self.assertEqual(store.factor_for(key), DEFAULT_FACTORS[key])

    def test_impossible_measurements_are_ignored(self) -> None:
        store = SpeedStore(self.path)
        key = "large-v3-turbo|speakers|full"
        for _ in range(5):
            store.record(key, 600.0, 0.004)   # medición absurda (factor ~0)
            store.record(key, 600.0, 20.0)    # trabajo de segundos: imposible
            store.record(key, 600.0, 60_000)  # 100x: imposible
        self.assertEqual(store.keys(), [])
        self.assertEqual(store.factor_for(key), DEFAULT_FACTORS[key])

    def test_corrupt_store_behaves_as_empty(self) -> None:
        self.path.write_text("{no es json", encoding="utf-8")
        store = SpeedStore(self.path)
        self.assertEqual(store.keys(), [])
        store.record("large-v3-turbo|speakers|full", 600.0, 700.0)
        self.assertTrue(json.loads(self.path.read_text(encoding="utf-8"))["samples"])

    def test_unknown_key_falls_back_to_same_model_with_speakers(self) -> None:
        store = SpeedStore(self.path)
        self.assertEqual(
            store.factor_for("large-v3-turbo|speakers|raro"),
            DEFAULT_FACTORS["large-v3-turbo|speakers|full"],
        )


class TestWeightedProgress(unittest.TestCase):
    """El % sale del tiempo: avanza también en la diarización."""

    def test_advances_during_speaker_phase(self) -> None:
        total = estimate_total_seconds(3600, 1.10)  # ~66 min + arranque
        antes, _, _ = weighted_progress(total_seconds=total, active_elapsed=0.30 * total, now=0)
        despues, _, _ = weighted_progress(
            total_seconds=total, active_elapsed=0.75 * total, previous=antes, now=0
        )
        self.assertGreater(despues, antes)
        self.assertLess(despues, 100)

    def test_never_goes_backwards(self) -> None:
        pct, _, _ = weighted_progress(total_seconds=1000, active_elapsed=500, previous=60, now=0)
        self.assertGreaterEqual(pct, 60)

    def test_asr_percent_is_a_floor(self) -> None:
        # Máquina más rápida que el estimado: el 80% real del ASR no se oculta.
        pct, _, _ = weighted_progress(
            total_seconds=10_000, active_elapsed=100, asr_pct=80, now=0
        )
        self.assertGreater(pct, 1)

    def test_caps_at_99_until_the_transcript_exists(self) -> None:
        # Muy pasado del estimado: sigue subiendo hacia 99, sin clavarse ni llegar a 100.
        apenas, _, _ = weighted_progress(total_seconds=100, active_elapsed=100, now=0)
        mucho, _, _ = weighted_progress(total_seconds=100, active_elapsed=99_999, now=0)
        self.assertGreater(mucho, apenas)
        self.assertEqual(mucho, 99)
        listo, eta, _ = weighted_progress(total_seconds=100, active_elapsed=50, done=True, now=0)
        self.assertEqual(listo, 100)
        self.assertEqual(eta, 0.0)

    def test_estimate_is_extended_instead_of_promising_the_past(self) -> None:
        total = 1000.0
        pct, eta, usado = weighted_progress(
            total_seconds=total, active_elapsed=1200, now=5000.0
        )
        self.assertGreater(usado, total)
        self.assertGreater(eta, 5000.0)
        self.assertLess(pct, 100)

    def test_unknown_duration_keeps_the_raw_percent_and_no_eta(self) -> None:
        pct, eta, _ = weighted_progress(total_seconds=0, active_elapsed=99, asr_pct=40, now=0)
        self.assertEqual(pct, 40)
        self.assertEqual(eta, 0.0)
        sin_nada, eta2, _ = weighted_progress(total_seconds=0, active_elapsed=99, now=0)
        self.assertIsNone(sin_nada)
        self.assertEqual(eta2, 0.0)

    def test_startup_allowance_for_very_short_audio(self) -> None:
        self.assertGreaterEqual(estimate_total_seconds(10, 1.10), STARTUP_SECONDS)
        self.assertEqual(estimate_total_seconds(0, 1.10), 0.0)


class TestProgressTracker(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = SpeedStore(self.root / "speed.json")

    def _job(self, seconds: float, **kw):
        wav = _wav(self.root / "w" / "reunion.wav", seconds)
        base = dict(
            id="j1", work_wav=str(wav), model="large-v3-turbo",
            no_diarize=False, pc_impact="full",
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_paused_time_does_not_consume_the_estimate(self) -> None:
        tracker = ProgressTracker(self.store)
        tracker.reset(self._job(3600))
        tracker.tick(True, now=0)
        tracker.tick(True, now=600)          # 10 min trabajando
        tracker.tick(False, now=1200)        # suspendido (grabando)
        tracker.tick(False, now=5400)
        tracker.tick(True, now=5401)
        tracker.tick(True, now=5461)         # 1 min más de trabajo
        self.assertAlmostEqual(tracker.active, 660.0, places=1)

    def test_no_speakers_preset_is_faster(self) -> None:
        conmigo = ProgressTracker(self.store)
        conmigo.reset(self._job(3600))
        rapido = ProgressTracker(self.store)
        rapido.reset(self._job(3600, no_diarize=True))
        self.assertLess(rapido.total, conmigo.total)

    def test_unknown_duration_gives_no_eta(self) -> None:
        tracker = ProgressTracker(self.store)
        tracker.reset(SimpleNamespace(id="x", work_wav="", model="", no_diarize=False, pc_impact="full"))
        pct, eta = tracker.compute(asr_pct=30, now=0)
        self.assertEqual(pct, 30)
        self.assertEqual(eta, 0.0)


class TestFinishTimeFormat(unittest.TestCase):
    def _epoch(self, y: int, m: int, d: int, hh: int, mm: int) -> float:
        return datetime(y, m, d, hh, mm).timestamp()

    def test_rounds_up_to_five_minutes(self) -> None:
        ahora = self._epoch(2026, 9, 18, 19, 0)
        texto = format_finish(self._epoch(2026, 9, 18, 21, 37), now=ahora)
        self.assertEqual(texto, "listo ~21:40")

    def test_tomorrow_and_later_days_are_explicit(self) -> None:
        ahora = self._epoch(2026, 9, 18, 22, 0)  # viernes
        self.assertEqual(
            format_finish(self._epoch(2026, 9, 19, 3, 18), now=ahora), "listo mañana ~03:20"
        )
        self.assertIn("listo el dom", format_finish(self._epoch(2026, 9, 20, 9, 11), now=ahora))

    def test_never_shows_a_past_time(self) -> None:
        ahora = self._epoch(2026, 9, 18, 19, 0)
        texto = format_finish(self._epoch(2026, 9, 18, 18, 0), now=ahora)
        self.assertEqual(texto, "listo ~19:05")

    def test_empty_when_unknown(self) -> None:
        self.assertEqual(format_finish(0.0, now=1000.0), "")


if __name__ == "__main__":
    unittest.main()

"""Seguimiento de un lote: el archivo en curso, lo listo y lo que espera.

Conduce el bucle real de `_monitor` con un log que imita al del Transcriptor
(un solo log compartido por los N archivos del argv).
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, List

from app.transcription.cli_progress import (
    cli_name_for_job,
    error_in_section,
    log_section_for,
    section_ended_in_diarization,
)
from app.transcription.eta import ProgressTracker
from app.transcription.jobs import (
    CANCELLED,
    DONE,
    PENDING,
    RUNNING,
    JobStore,
)
from app.transcription.worker import TranscriptionWorker

_PID = 424242


class _FakeProc:
    """Proceso psutil-like: vivo, sin suspender de verdad."""

    def __init__(self, pid: int = _PID) -> None:
        self.pid = pid

    def is_running(self) -> bool:
        return True

    def suspend(self) -> None:
        pass

    def resume(self) -> None:
        pass


class _LogDriver:
    """Popen-like: cada poll() avanza un paso del log y al final termina."""

    def __init__(self, log_path: Path, steps: List[Callable[[], None]]) -> None:
        self.log_path = log_path
        self.steps = list(steps)
        self.returncode = None

    def poll(self):
        if self.steps:
            self.steps.pop(0)()
            return None
        self.returncode = 0
        return 0


class TestBatchTracking(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.out = self.root / "salida"
        self.out.mkdir()
        self.store = JobStore(base=self.root / "tx")
        self.log = self.store.logs_dir / "lote.log"
        self.log.write_text("--- intento 1 · 3 archivo(s) ---\n", encoding="utf-8")
        self.emitted: List[dict] = []
        self.worker = TranscriptionWorker(
            self.store,
            lambda: SimpleNamespace(
                pause_transcription_while_recording=True, transcriptor_dir=""
            ),
            self.emitted.append,
            is_recording=lambda: False,
        )
        self.worker.POLL_SECONDS = 0

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _job(self, nombre: str, status: str, audio_seconds: float = 600.0):
        media = self.root / f"{nombre}.mp4"
        media.write_bytes(b"fake")
        job = self.store.enqueue(str(media), output_base=str(self.out))
        assert job is not None
        wav_dir = self.store.work_dir / job.id
        wav_dir.mkdir(parents=True, exist_ok=True)
        wav = wav_dir / f"{nombre}.wav"
        # WAV de trabajo real (16 kHz mono PCM): de su tamaño sale la duración.
        wav.write_bytes(b"\0" * (44 + int(audio_seconds * 16000 * 2)))
        job.work_wav = str(wav)
        job.log_path = str(self.log)
        job.pid = _PID
        job.status = status
        self.store.save(job)
        return job

    def _append(self, texto: str) -> Callable[[], None]:
        def step() -> None:
            with self.log.open("a", encoding="utf-8") as f:
                f.write(texto)

        return step

    def _finish(self, nombre: str) -> Callable[[], None]:
        def step() -> None:
            d = self.out / "Transcripciones" / nombre
            d.mkdir(parents=True, exist_ok=True)
            (d / "transcripcion.txt").write_text("hola", encoding="utf-8")

        return step

    def _status(self, job) -> str:
        return self.store._load(self.store._path(job.id)).status

    def test_live_file_progress_done_and_waiting(self) -> None:
        a = self._job("uno", RUNNING)
        b = self._job("dos", PENDING)
        c = self._job("tres", PENDING)
        driver = _LogDriver(
            self.log,
            [
                self._append("> Procesando: uno.wav\n    transcribiendo... 50%\n"),
                self._append("  - Identificando hablantes (diarizacion)...\n"),
                self._finish("uno"),
                self._append("  OK en 90s  ->  x\n> Procesando: dos.wav\n"),
                self._append("    transcribiendo... 20%\n"),
            ],
        )
        rc = self.worker._monitor(a, _FakeProc(), owned=driver, cohort=[a, b, c])
        self.assertEqual(rc, 0)

        # El primero queda listo; el segundo es el que va; el tercero espera.
        self.assertEqual(self._status(a), DONE)
        self.assertEqual(self._status(b), RUNNING)
        self.assertEqual(self._status(c), PENDING)

        activos = [s for s in self.emitted if s["status"] == RUNNING]
        # En diarización hay cifra (sale del tiempo, spec 021) y no es el 50% del ASR.
        diariz = [s for s in activos if "hablantes" in (s["stage"] or "")]
        self.assertTrue(diariz)
        self.assertIsNotNone(diariz[-1]["progress"])
        self.assertNotEqual(diariz[-1]["progress"], 50)
        self.assertGreater(diariz[-1]["eta_epoch"], time.time())
        # El aviso sigue al archivo que el CLI procesa de verdad, no al primero.
        ultimo = activos[-1]
        self.assertEqual(Path(ultimo["media_path"]).stem, "dos")
        self.assertEqual((ultimo["batch_pos"], ultimo["batch_total"]), (2, 3))
        # El lote termina después que el archivo en curso.
        self.assertGreater(ultimo["batch_eta_epoch"], ultimo["eta_epoch"])
        # SC-003: una vez listo, el aviso no vuelve a nombrar ese archivo.
        listo = next(
            i for i, s in enumerate(self.emitted)
            if s["id"] == a.id and s["status"] == DONE
        )
        posteriores = [s for s in self.emitted[listo + 1 :] if s["status"] == RUNNING]
        self.assertTrue(posteriores, "tras terminar 'uno' debe seguir avisando del siguiente")
        self.assertNotIn("uno", [Path(s["media_path"]).stem for s in posteriores])

    def test_batch_estimate_carries_one_model_load_not_one_per_file(self) -> None:
        # El CLI carga los modelos una vez por ejecución: los pendientes del
        # mismo argv solo añaden trabajo (spec 025 SC-001).
        a = self._job("uno", RUNNING, audio_seconds=600)
        pendientes = [
            self._job(f"p{i}", PENDING, audio_seconds=600) for i in range(1, 4)
        ]
        tracker = ProgressTracker(self.worker._speed)
        tracker.reset(a)
        factor = tracker.factor
        ahora = 1_000_000.0

        def lote(grupo):
            return self.worker._batch_eta(grupo, a, tracker, now=ahora)

        con_uno = lote([a, pendientes[0]])
        con_tres = lote([a] + pendientes)
        # Cada pendiente añade su trabajo, sin un arranque propio.
        self.assertAlmostEqual(con_uno - ahora, tracker.remaining() + 600 * factor, places=2)
        self.assertAlmostEqual(con_tres - con_uno, 2 * 600 * factor, places=2)
        # Y el lote entero no lleva más de un arranque que el archivo en curso.
        self.assertLess(
            con_tres - ahora - tracker.remaining() - 3 * 600 * factor,
            1.0,
        )

    def test_a_file_promoted_inside_a_running_engine_pays_no_model_load(self) -> None:
        # El segundo archivo del argv no espera la carga de modelos: su estimación
        # no debe incluirla (spec 025 SC-002).
        a = self._job("uno", RUNNING, audio_seconds=600)
        b = self._job("dos", PENDING, audio_seconds=600)
        driver = _LogDriver(
            self.log,
            [
                self._append("> Procesando: uno.wav\n    transcribiendo... 50%\n"),
                self._finish("uno"),
                self._append("  OK en 90s  ->  x\n> Procesando: dos.wav\n"),
                self._append("    transcribiendo... 10%\n"),
            ],
        )
        arranque = time.time()
        self.worker._monitor(a, _FakeProc(), owned=driver, cohort=[a, b])
        de_dos = [
            s for s in self.emitted
            if s["id"] == b.id and s["status"] == RUNNING and s["eta_epoch"]
        ]
        self.assertTrue(de_dos)
        referencia = ProgressTracker(self.worker._speed)
        referencia.reset(b, load_models=False)
        # El restante prometido no excede el trabajo puro (más el poco tiempo del test).
        self.assertLess(de_dos[0]["eta_epoch"] - arranque, referencia.total + 5.0)

    def test_unknown_duration_keeps_progress_indeterminate(self) -> None:
        # Sin WAV de trabajo medible no se puede estimar: en diarización el
        # progreso queda indeterminado en vez de congelar el % del ASR (020 FR-004).
        a = self._job("uno", RUNNING, audio_seconds=0)
        driver = _LogDriver(
            self.log,
            [
                self._append("> Procesando: uno.wav\n    transcribiendo... 90%\n"),
                self._append("  - Identificando hablantes (diarizacion)...\n"),
            ],
        )
        self.worker._monitor(a, _FakeProc(), owned=driver, cohort=[a])
        diariz = [
            s for s in self.emitted
            if s["status"] == RUNNING and "hablantes" in (s["stage"] or "")
        ]
        self.assertTrue(diariz)
        self.assertIsNone(diariz[-1]["progress"])
        self.assertEqual(diariz[-1]["eta_epoch"], 0.0)

    def test_phase_drives_the_label_and_the_percent(self) -> None:
        """Spec 024: nunca 'Audio listo… NN%', y el % del ASR deja de mandar
        cuando el CLI dice que la transcripción terminó (sin hablantes de por medio)."""
        a = self._job("uno", RUNNING)
        driver = _LogDriver(
            self.log,
            [
                self._append("> Procesando: uno.wav\n"),
                self._append("  - Audio ya en WAV 16 kHz; se omite reconversión.\n"),
                self._append("  - Transcribiendo (modelo large-v3-turbo, idioma es)...\n"),
                self._append("    transcribiendo... 40%\n"),
                self._append("    -> dispositivo: cpu\n"),
            ],
        )
        self.worker._monitor(a, _FakeProc(), owned=driver, cohort=[a])

        etiquetas = [s["stage"] for s in self.emitted if s["status"] == RUNNING]
        self.assertTrue(etiquetas)
        self.assertFalse([e for e in etiquetas if "Audio listo" in (e or "")])
        # Antes del primer porcentaje ya dice que transcribe.
        self.assertEqual(etiquetas[0], "Transcribiendo…")
        # Y al terminar el ASR pasa a guardar, no se queda en "Transcribiendo".
        self.assertEqual(etiquetas[-1], "Guardando resultados…")
        guardando = [
            s for s in self.emitted
            if s["status"] == RUNNING and s["stage"] == "Guardando resultados…"
        ]
        self.assertNotEqual(guardando[-1]["progress"], 40)

    def test_cancelled_file_is_not_resurrected(self) -> None:
        a = self._job("uno", RUNNING)
        b = self._job("dos", PENDING)
        self.store.cancel(b.id)
        driver = _LogDriver(
            self.log,
            [
                self._append("> Procesando: uno.wav\n    transcribiendo... 30%\n"),
                self._finish("uno"),
                self._append("  OK en 30s  ->  x\n> Procesando: dos.wav\n"),
            ],
        )
        self.worker._monitor(a, _FakeProc(), owned=driver, cohort=[a, b])
        self.assertEqual(self._status(a), DONE)
        self.assertEqual(self._status(b), CANCELLED)
        self.assertNotIn(
            RUNNING, [s["status"] for s in self.emitted if s["id"] == b.id]
        )

    def test_file_skipped_without_result_returns_to_queue(self) -> None:
        a = self._job("uno", RUNNING)
        b = self._job("dos", PENDING)
        driver = _LogDriver(
            self.log,
            [
                self._append("> Procesando: uno.wav\n    transcribiendo... 40%\n"),
                self._append("  [X] Error con uno.wav: boom\n> Procesando: dos.wav\n"),
            ],
        )
        self.worker._monitor(a, _FakeProc(), owned=driver, cohort=[a, b])
        # Sin transcripcion.txt no se marca listo: vuelve a la cola.
        self.assertEqual(self._status(a), PENDING)
        self.assertEqual(self._status(b), RUNNING)


class TestWorkDirHousekeeping(unittest.TestCase):
    """Los WAV de trabajo de jobs terminados no deben quedarse ocupando disco."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(base=Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _work_wav(self, job_id: str, nombre: str, size: int) -> Path:
        d = self.store.work_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        wav = d / nombre
        wav.write_bytes(b"\0" * size)
        return wav

    def test_purges_finished_and_unknown_keeps_active(self) -> None:
        activo = self.store.enqueue(str(Path(self._tmp.name) / "activo.mp4"))
        listo = self.store.enqueue(str(Path(self._tmp.name) / "listo.mp4"))
        assert activo and listo
        listo.status = DONE
        self.store.save(listo)
        vivo = self._work_wav(activo.id, "activo.wav", 100)
        muerto = self._work_wav(listo.id, "listo.wav", 500)
        huerfano = self._work_wav("cafecafecafe", "viejo.wav", 400)

        liberados = self.store.purge_orphan_work_dirs()
        self.assertEqual(liberados, 900)
        self.assertTrue(vivo.exists())
        self.assertFalse(muerto.exists())
        self.assertFalse(huerfano.exists())
        self.assertFalse(muerto.parent.exists())


class TestPerFileAttribution(unittest.TestCase):
    """Un log compartido: el error de un archivo no es el de los demás."""

    LOG = "\n".join(
        [
            "--- intento 1 · 3 archivo(s) ---",
            "> Procesando: uno.wav",
            "    transcribiendo... 90%",
            "  - Identificando hablantes (diarizacion)...",
            "  OK en 100s  ->  C:\\out\\uno",
            "> Procesando: dos.wav",
            "    transcribiendo... 40%",
            "  [X] Error con dos.wav: Unable to allocate 973. MiB",
            "> Procesando: tres.wav",
            "    transcribiendo... 100%",
            "  - Identificando hablantes (diarizacion)...",
            "",
        ]
    )

    def test_error_belongs_to_its_file(self) -> None:
        uno = log_section_for(self.LOG, "uno.wav")
        dos = log_section_for(self.LOG, "dos.wav")
        tres = log_section_for(self.LOG, "tres.wav")
        self.assertEqual(error_in_section(uno), "")
        self.assertIn("Unable to allocate", error_in_section(dos))
        self.assertEqual(error_in_section(tres), "")

    def test_diarization_failure_scoped_to_last_file(self) -> None:
        self.assertFalse(
            section_ended_in_diarization(log_section_for(self.LOG, "uno.wav"))
        )
        self.assertTrue(
            section_ended_in_diarization(log_section_for(self.LOG, "tres.wav"))
        )

    def test_file_that_never_started_has_no_section(self) -> None:
        self.assertEqual(log_section_for(self.LOG, "cuatro.wav"), "")

    def test_cli_name_from_job_fields(self) -> None:
        self.assertEqual(
            cli_name_for_job(SimpleNamespace(work_wav=r"C:\w\x\Reunión 1.wav")),
            "Reunión 1.wav",
        )
        self.assertEqual(
            cli_name_for_job(SimpleNamespace(work_wav="", media_path=r"C:\v\Clip.mp4")),
            "Clip.wav",
        )


if __name__ == "__main__":
    unittest.main()

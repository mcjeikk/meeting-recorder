"""Decisiones del chequeo rápido (verify_transcription.py) sin ejecutar el motor."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.transcription.jobs import DONE, ERROR
from verify_transcription import (
    ARTIFACTS,
    EXIT_OK,
    EXIT_WIRING,
    _parse_args,
    cleanup_sandbox,
    pick_recording,
    sandbox_paths,
    slice_args,
    speakers_in_result,
    verdict,
)


class _Cfg:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir


def _update(nombre: str, *, eta: float = 0.0) -> dict:
    return {
        "media_path": str(Path("C:/x") / nombre),
        "status": "running",
        "stage": "Transcribiendo…",
        "progress": 40,
        "eta_epoch": eta,
    }


class TestArguments(unittest.TestCase):
    def test_quick_rejects_force(self) -> None:
        """V-2: el sandbox no puede chocar con datos del usuario."""
        with self.assertRaises(SystemExit):
            _parse_args(["--quick", "--force"])

    def test_quick_defaults_to_a_sample_with_speakers(self) -> None:
        args = _parse_args(["--quick"])
        self.assertEqual(args.seconds, 60)
        self.assertFalse(args.no_speakers)

    def test_absurdly_short_sample_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            _parse_args(["--quick", "--seconds", "1"])


class TestSample(unittest.TestCase):
    def test_slice_copies_every_stream(self) -> None:
        """V-4: sin recodificar y con -map 0, para que la pista Mezcla siga ahí."""
        args = slice_args(Path("C:/x/Reunión.mp4"), Path("C:/tmp/m.mp4"), 30)
        self.assertIsInstance(args, list)  # V-5: nunca shell=True
        self.assertEqual(args[args.index("-t") + 1], "30")
        self.assertIn("-map", args)
        self.assertEqual(args[args.index("-map") + 1], "0")
        self.assertEqual(args[args.index("-c") + 1], "copy")

    def test_sandbox_destination_is_outside_the_user_folder(self) -> None:
        """INV-1: el destino del modo rápido vive dentro del sandbox."""
        sandbox = Path(tempfile.gettempdir()) / "verify_tx_test"
        cola, salida = sandbox_paths(sandbox)
        self.assertTrue(str(cola).startswith(str(sandbox)))
        self.assertTrue(str(salida).startswith(str(sandbox)))
        self.assertNotEqual(cola, salida)

    def test_sandbox_is_removed(self) -> None:
        """INV-5: tras un éxito no queda carpeta temporal."""
        sandbox = Path(tempfile.mkdtemp(prefix="verify_tx_test_"))
        (sandbox / "tx" / "logs").mkdir(parents=True)
        (sandbox / "tx" / "logs" / "a.log").write_text("x", encoding="utf-8")
        self.assertTrue(cleanup_sandbox(sandbox))
        self.assertFalse(sandbox.exists())

    def test_newest_recording_is_picked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            viejo, nuevo = carpeta / "vieja.mp4", carpeta / "nueva.mp4"
            viejo.write_bytes(b"0")
            nuevo.write_bytes(b"0")
            import os

            os.utime(viejo, (1, 1))
            self.assertEqual(pick_recording(_Cfg(tmp)), nuevo)

    def test_no_recording_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                pick_recording(_Cfg(tmp))


class TestVerdict(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.result = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_artifacts(self, hablantes: object = 2) -> None:
        for nombre in ARTIFACTS:
            (self.result / nombre).write_text("x", encoding="utf-8")
        (self.result / "transcripcion.json").write_text(
            json.dumps({"hablantes": hablantes}), encoding="utf-8"
        )

    def _verdict(self, **kw):
        base = dict(
            status=DONE,
            result_dir=self.result,
            updates=[_update("m.mp4", eta=1.0)],
            media_name="m.mp4",
            want_speakers=True,
        )
        base.update(kw)
        return verdict(**base)

    def test_complete_run_passes(self) -> None:
        self._write_artifacts()
        code, motivo, detalles = self._verdict()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(motivo, "")
        self.assertEqual(detalles["hablantes"], 2)

    def test_failed_job_fails(self) -> None:
        self._write_artifacts()
        code, motivo, _ = self._verdict(status=ERROR)
        self.assertEqual(code, EXIT_WIRING)
        self.assertIn("error", motivo)

    def test_missing_artifact_fails(self) -> None:
        self._write_artifacts()
        (self.result / "transcripcion.srt").unlink()
        code, motivo, _ = self._verdict()
        self.assertEqual(code, EXIT_WIRING)
        self.assertIn("transcripcion.srt", motivo)

    def test_artifacts_without_progress_updates_fail(self) -> None:
        """INV-3: transcripción producida pero la UI nunca supo de este archivo."""
        self._write_artifacts()
        code, motivo, _ = self._verdict(updates=[_update("otra.mp4", eta=1.0)])
        self.assertEqual(code, EXIT_WIRING)
        self.assertIn("avance", motivo)

    def test_missing_finish_estimate_fails(self) -> None:
        self._write_artifacts()
        code, motivo, _ = self._verdict(updates=[_update("m.mp4")])
        self.assertEqual(code, EXIT_WIRING)
        self.assertIn("hora estimada", motivo)

    def test_speakers_silently_dropped_fail(self) -> None:
        """INV-4: sin token el motor sale con éxito y sin hablantes."""
        self._write_artifacts(hablantes=0)
        code, motivo, _ = self._verdict()
        self.assertEqual(code, EXIT_WIRING)
        self.assertIn("hablantes", motivo)

    def test_speakers_not_requested_are_not_required(self) -> None:
        self._write_artifacts(hablantes=0)
        code, _, _ = self._verdict(want_speakers=False)
        self.assertEqual(code, EXIT_OK)

    def test_speaker_map_is_counted(self) -> None:
        """El CLI escribe un mapa, no una lista: contarlo mal daba falso negativo."""
        self._write_artifacts(hablantes={"SPEAKER_00": {"tiempo": 12.0}})
        self.assertEqual(speakers_in_result(self.result), 1)
        code, _, _ = self._verdict()
        self.assertEqual(code, EXIT_OK)

    def test_speaker_list_is_counted(self) -> None:
        self._write_artifacts(hablantes=["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"])
        self.assertEqual(speakers_in_result(self.result), 3)

    def test_corrupt_result_counts_zero_speakers(self) -> None:
        (self.result / "transcripcion.json").write_text("{no json", encoding="utf-8")
        self.assertEqual(speakers_in_result(self.result), 0)


if __name__ == "__main__":
    unittest.main()

"""Parseo del log plano: qué archivo va y cuándo resetear el %."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.transcription.cli_progress import (
    PHASE_ASR,
    PHASE_PREPARE,
    PHASE_SAVING,
    PHASE_SPEAKERS,
    PHASES_WITHOUT_ASR_PERCENT,
    job_for_cli_name,
    job_matches_cli_name,
    label_for_phase,
    parse_plain_chunk,
)
from app.transcription.jobs import JobStore

# Log real de un job terminado (verify_transcription.py, 2026-09-18).
LOG_REAL = """--- intento 1 · 1 archivo(s) · única pista de audio ---
Archivos a procesar: 1

> Procesando: reunion [muestra 20s].wav
  - Audio ya en WAV 16 kHz; se omite reconversión.
  - Transcribiendo (modelo large-v3-turbo, idioma es)...
    transcribiendo... 24%
    transcribiendo... 61%
    transcribiendo... 93%
    -> dispositivo: cpu
  - Identificando hablantes (diarizacion)...
    -> 1 hablante(s) detectado(s)
  OK en 32s  ->  C:\\out\\reunion [muestra 20s]
      - transcripcion.txt
      - transcripcion.srt
      - transcripcion.json

Finalizado. 1/1 archivo(s) correctos."""


class TestParsePlainChunk(unittest.TestCase):
    def test_file_switch_resets_percent(self) -> None:
        stage, pct, name, nota, phase = parse_plain_chunk(
            "\n".join(
                [
                    "> Procesando: reunion-1.wav",
                    "    transcribiendo... 90%",
                    "  - Identificando hablantes (diarizacion)...",
                    "  OK en 12s  ->  C:\\out\\reunion-1",
                    "> Procesando: reunion-2.wav",
                    "    transcribiendo... 10%",
                ]
            )
        )
        self.assertEqual(name, "reunion-2.wav")
        self.assertEqual(pct, 10)
        self.assertEqual(phase, PHASE_ASR)
        self.assertEqual(stage, "Transcribiendo…")
        self.assertIsNone(nota)

    def test_diarization_clears_asr_percent(self) -> None:
        stage, pct, name, _nota, phase = parse_plain_chunk(
            "\n".join(
                [
                    "> Procesando: elite.wav",
                    "    transcribiendo... 90%",
                    "  - Identificando hablantes (diarizacion)...",
                ]
            )
        )
        self.assertEqual(name, "elite.wav")
        self.assertEqual(pct, -1)
        self.assertEqual(phase, PHASE_SPEAKERS)
        self.assertIn("hablantes", stage or "")


class TestPhaseIsTruthful(unittest.TestCase):
    """Spec 024: la etiqueta nombra la fase que corre AHORA."""

    def test_announcement_alone_says_transcribing(self) -> None:
        """Sin ninguna cifra todavía (archivo corto): ya está transcribiendo."""
        stage, pct, _name, _nota, phase = parse_plain_chunk(
            "\n".join(
                [
                    "> Procesando: corta.wav",
                    "  - Audio ya en WAV 16 kHz; se omite reconversión.",
                    "  - Transcribiendo (modelo large-v3-turbo, idioma es)...",
                ]
            )
        )
        self.assertEqual(phase, PHASE_ASR)
        self.assertEqual(stage, "Transcribiendo…")
        self.assertEqual(pct, 0)  # el 0 lo puso el cambio de archivo

    def test_audio_already_wav_is_not_a_phase(self) -> None:
        """El viejo 'Audio listo… 35%': una acción omitida no es una fase."""
        stage, pct, _name, _nota, phase = parse_plain_chunk(
            "  - Audio ya en WAV 16 kHz; se omite reconversión."
        )
        self.assertIsNone(phase)
        self.assertIsNone(stage)
        self.assertIsNone(pct)

    def test_preparation_label_never_carries_an_asr_percent(self) -> None:
        stage, pct, _name, _nota, phase = parse_plain_chunk(
            "\n".join(
                [
                    "  - Audio ya en WAV 16 kHz; se omite reconversión.",
                    "  - Transcribiendo (modelo large-v3-turbo, idioma es)...",
                    "    transcribiendo... 35%",
                ]
            )
        )
        self.assertEqual((phase, stage, pct), (PHASE_ASR, "Transcribiendo…", 35))
        self.assertNotIn("Audio listo", stage or "")

    def test_converting_audio_is_preparation(self) -> None:
        stage, _pct, _name, _nota, phase = parse_plain_chunk(
            "  - Convirtiendo audio a WAV 16 kHz..."
        )
        self.assertEqual(phase, PHASE_PREPARE)
        self.assertEqual(stage, "Preparando audio…")

    def test_device_line_means_transcription_ended(self) -> None:
        """El CLI la imprime DESPUÉS de transcribir: no puede decir 'transcribiendo'."""
        stage, pct, _name, _nota, phase = parse_plain_chunk("    -> dispositivo: cuda")
        self.assertEqual(phase, PHASE_SAVING)
        self.assertEqual(stage, "Guardando resultados…")
        self.assertEqual(pct, -1)

    def test_speaker_count_means_speakers_ended(self) -> None:
        stage, pct, _name, _nota, phase = parse_plain_chunk(
            "\n".join(
                [
                    "  - Identificando hablantes (diarizacion)...",
                    "    -> 3 hablante(s) detectado(s)",
                ]
            )
        )
        self.assertEqual(phase, PHASE_SAVING)
        self.assertEqual(stage, "Guardando resultados…")
        self.assertEqual(pct, -1)

    def test_diarization_failure_saves_and_notes_it(self) -> None:
        for linea in (
            "  [!] La diarizacion no se completo (RuntimeError: boom).",
            "  [!] Diarizacion solicitada pero no hay token de HuggingFace.",
        ):
            _stage, pct, _name, nota, phase = parse_plain_chunk(
                "  - Identificando hablantes (diarizacion)...\n" + linea
            )
            self.assertEqual(phase, PHASE_SAVING, linea)
            self.assertEqual(nota, "sin hablantes", linea)
            self.assertEqual(pct, -1, linea)

    def test_unknown_lines_change_nothing(self) -> None:
        for texto in ("", "ruido cualquiera\notra línea", "  OK en 32s  ->  C:\\out\\x"):
            stage, pct, name, nota, phase = parse_plain_chunk(texto)
            self.assertEqual((stage, pct, name, nota, phase), (None,) * 5, texto)

    def test_real_log_replayed_line_by_line(self) -> None:
        """SC-001: preparar → transcribir → hablantes → guardar, sin volver atrás."""
        secuencia = []
        for linea in LOG_REAL.splitlines():
            _stage, _pct, _name, _nota, phase = parse_plain_chunk(linea)
            if phase and (not secuencia or secuencia[-1] != phase):
                secuencia.append(phase)
        self.assertEqual(secuencia, [PHASE_ASR, PHASE_SAVING, PHASE_SPEAKERS, PHASE_SAVING])
        # Ninguna fase se re-anuncia después de que el CLI la dio por terminada:
        # tras el recuento de hablantes solo queda guardar.
        self.assertEqual(secuencia[-1], PHASE_SAVING)

    def test_whole_chunk_reports_the_last_phase(self) -> None:
        stage, pct, name, _nota, phase = parse_plain_chunk(LOG_REAL)
        self.assertEqual(phase, PHASE_SAVING)
        self.assertEqual(stage, "Guardando resultados…")
        self.assertEqual(pct, -1)
        self.assertEqual(name, "reunion [muestra 20s].wav")

    def test_percent_applicability_is_a_value_not_a_word(self) -> None:
        """INV-6: la regla se enuncia una vez, sobre fases."""
        self.assertEqual(PHASES_WITHOUT_ASR_PERCENT, {PHASE_SPEAKERS, PHASE_SAVING})
        self.assertNotIn(PHASE_ASR, PHASES_WITHOUT_ASR_PERCENT)
        self.assertNotIn(PHASE_PREPARE, PHASES_WITHOUT_ASR_PERCENT)

    def test_every_phase_has_exactly_one_label(self) -> None:
        etiquetas = [
            label_for_phase(p)
            for p in (PHASE_PREPARE, PHASE_ASR, PHASE_SPEAKERS, PHASE_SAVING)
        ]
        self.assertTrue(all(etiquetas))
        self.assertEqual(len(set(etiquetas)), 4)
        self.assertIsNone(label_for_phase(None))
        self.assertIsNone(label_for_phase("inventada"))


class TestJobMatching(unittest.TestCase):
    def test_matches_work_wav_stem(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = JobStore(base=Path(tmp.name))
        media = Path(tmp.name) / "élite [PAP].mp4"
        job = store.enqueue(str(media))
        assert job is not None
        job.work_wav = str(Path(tmp.name) / "work" / job.id / "élite [PAP].wav")
        store.save(job)
        self.assertTrue(job_matches_cli_name(job, "élite [PAP].wav"))
        self.assertIs(job_for_cli_name([job], "élite [PAP].wav"), job)
        self.assertIsNone(job_for_cli_name([job], "otra.wav"))


if __name__ == "__main__":
    unittest.main()

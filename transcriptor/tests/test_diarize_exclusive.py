"""Exclusive diarization for ASR merge (no model download)."""
from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.diarize import _anotacion_para_asr, _extraer_turnos  # noqa: E402


class _Ann:
    def __init__(self, turns: list[tuple[float, float, str]]) -> None:
        self._turns = turns

    def itertracks(self, yield_label: bool = True):
        for start, end, speaker in self._turns:
            yield SimpleNamespace(start=start, end=end), None, speaker


class TestExclusiveForAsr(unittest.TestCase):
    def test_prefers_exclusive_over_regular(self) -> None:
        exclusive = _Ann([(0.0, 1.5, "SPEAKER_00"), (1.5, 3.0, "SPEAKER_01")])
        regular = _Ann([(0.0, 2.0, "SPEAKER_00"), (1.0, 3.0, "SPEAKER_01")])
        salida = SimpleNamespace(
            speaker_diarization=regular,
            exclusive_speaker_diarization=exclusive,
        )
        self.assertIs(_anotacion_para_asr(salida), exclusive)
        turnos = _extraer_turnos(salida)
        self.assertEqual(
            turnos,
            [
                {"start": 0.0, "end": 1.5, "speaker": "SPEAKER_00"},
                {"start": 1.5, "end": 3.0, "speaker": "SPEAKER_01"},
            ],
        )

    def test_falls_back_to_regular(self) -> None:
        regular = _Ann([(0.0, 1.0, "SPEAKER_00")])
        salida = SimpleNamespace(speaker_diarization=regular)
        self.assertIs(_anotacion_para_asr(salida), regular)
        self.assertEqual(
            _extraer_turnos(salida),
            [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}],
        )

    def test_plain_annotation_pyannote3(self) -> None:
        ann = _Ann([(0.0, 2.0, "SPEAKER_00")])
        self.assertIs(_anotacion_para_asr(ann), ann)
        self.assertEqual(len(_extraer_turnos(ann)), 1)


if __name__ == "__main__":
    unittest.main()

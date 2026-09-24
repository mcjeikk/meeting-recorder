"""Caché in-process y ASR sin condition_on_previous_text (sin descargar modelos)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import asr as asr_mod  # noqa: E402
from pipeline import diarize as diarize_mod  # noqa: E402


class TestAsrCacheAndFlags(unittest.TestCase):
    def setUp(self) -> None:
        asr_mod._model_cache.clear()
        diarize_mod._pipeline_cache.clear()

    def tearDown(self) -> None:
        asr_mod._model_cache.clear()
        diarize_mod._pipeline_cache.clear()

    def test_whisper_reused_in_process(self) -> None:
        fake = MagicMock(name="whisper")
        with patch.object(asr_mod, "WhisperModel", return_value=fake) as ctor:
            with patch.object(asr_mod, "detectar_device", return_value="cpu"):
                a = asr_mod.cargar_modelo("tiny", device="cpu")
                b = asr_mod.cargar_modelo("tiny", device="cpu")
        self.assertIs(a, b)
        self.assertEqual(ctor.call_count, 1)

    def test_condition_on_previous_text_is_false(self) -> None:
        model = MagicMock()
        model.transcribe.return_value = (
            iter([]),
            MagicMock(duration=1.0, language="es"),
        )
        model.model.device = "cpu"
        with patch.object(asr_mod, "cargar_modelo", return_value=model):
            asr_mod.transcribir(Path("x.wav"))
        kwargs = model.transcribe.call_args.kwargs
        self.assertIs(kwargs["condition_on_previous_text"], False)

    def test_pyannote_reused_in_process(self) -> None:
        pipe = MagicMock(name="pipeline")
        with patch("pyannote.audio.Pipeline.from_pretrained", return_value=pipe) as ctor:
            with patch.object(diarize_mod.torch, "cuda") as cuda:
                cuda.is_available.return_value = False
                a = diarize_mod.cargar_pipeline("hf_test")
                b = diarize_mod.cargar_pipeline("hf_test")
        self.assertIs(a, b)
        self.assertEqual(ctor.call_count, 1)


if __name__ == "__main__":
    unittest.main()

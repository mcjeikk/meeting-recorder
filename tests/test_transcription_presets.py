"""Unit tests: preset → CLI mapping and normalize_preset."""
from __future__ import annotations

import unittest

from app.transcription.presets import (
    DEFAULT_PRESET,
    PRESET_EQUILIBRADO,
    PRESET_MAXIMA,
    PRESET_RAPIDO,
    cli_args_from_job_fields,
    normalize_preset,
    to_cli_args,
)


class TestNormalizePreset(unittest.TestCase):
    def test_known_ids(self) -> None:
        self.assertEqual(normalize_preset("rapido"), PRESET_RAPIDO)
        self.assertEqual(normalize_preset("equilibrado"), PRESET_EQUILIBRADO)
        self.assertEqual(normalize_preset("maxima_calidad"), PRESET_MAXIMA)

    def test_case_and_whitespace(self) -> None:
        self.assertEqual(normalize_preset("  Rapido  "), PRESET_RAPIDO)

    def test_unknown_and_empty(self) -> None:
        self.assertEqual(normalize_preset(""), DEFAULT_PRESET)
        self.assertEqual(normalize_preset("medium"), DEFAULT_PRESET)
        self.assertEqual(normalize_preset(None), DEFAULT_PRESET)
        self.assertEqual(normalize_preset(123), DEFAULT_PRESET)


class TestToCliArgs(unittest.TestCase):
    def test_rapido(self) -> None:
        self.assertEqual(
            to_cli_args(PRESET_RAPIDO),
            ["--model", "large-v3-turbo", "--beam-size", "5", "--no-diarize"],
        )

    def test_equilibrado(self) -> None:
        self.assertEqual(
            to_cli_args(PRESET_EQUILIBRADO),
            ["--model", "large-v3-turbo", "--beam-size", "5"],
        )

    def test_maxima(self) -> None:
        self.assertEqual(
            to_cli_args(PRESET_MAXIMA),
            ["--model", "large-v3", "--beam-size", "5"],
        )

    def test_rapido_not_medium(self) -> None:
        args = to_cli_args(PRESET_RAPIDO)
        self.assertNotIn("medium", args)

    def test_unknown_falls_back_to_equilibrado(self) -> None:
        self.assertEqual(to_cli_args("nope"), to_cli_args(PRESET_EQUILIBRADO))


class TestCliArgsFromJobFields(unittest.TestCase):
    def test_degraded_forces_no_diarize_once(self) -> None:
        args = cli_args_from_job_fields(
            model="large-v3-turbo", beam_size=5, no_diarize=True
        )
        self.assertEqual(
            args, ["--model", "large-v3-turbo", "--beam-size", "5", "--no-diarize"]
        )
        self.assertEqual(args.count("--no-diarize"), 1)


if __name__ == "__main__":
    unittest.main()

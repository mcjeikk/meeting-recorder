"""Encontrar el Transcriptor tal como lo deja quien clona los dos repos (spec 028).

`git clone` crea `meeting-recorder\` y `meeting-transcriber\` lado a lado; la
autodetección solo buscaba `Transcriptor\`, así que una instalación nueva hecha
al pie de la letra no transcribía.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import (
    AppConfig,
    default_transcriptor_dir,
    resolve_transcriptor_dir,
)


def _make_transcriptor(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "transcribe.py").write_text("# cli\n", encoding="utf-8")
    return path


class TestDiscovery(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.recorder = self.root / "meeting-recorder"
        self.recorder.mkdir()

    def test_finds_the_folder_git_clone_creates(self) -> None:
        tx = _make_transcriptor(self.root / "meeting-transcriber")
        self.assertEqual(default_transcriptor_dir(self.recorder), str(tx))

    def test_still_finds_the_development_folder_name(self) -> None:
        tx = _make_transcriptor(self.root / "Transcriptor")
        self.assertEqual(default_transcriptor_dir(self.recorder), str(tx))

    def test_still_finds_the_legacy_location_one_level_up(self) -> None:
        anidado = self.root / "Apps" / "meeting-recorder"
        anidado.mkdir(parents=True)
        tx = _make_transcriptor(self.root / "Transcriptor")
        self.assertEqual(default_transcriptor_dir(anidado), str(tx))

    def test_a_folder_without_the_cli_is_not_a_transcriptor(self) -> None:
        (self.root / "meeting-transcriber").mkdir()
        self.assertEqual(default_transcriptor_dir(self.recorder), "")

    def test_nothing_installed_yields_empty(self) -> None:
        self.assertEqual(default_transcriptor_dir(self.recorder), "")


class TestResolve(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.recorder = self.root / "meeting-recorder"
        self.recorder.mkdir()

    def test_a_valid_saved_path_wins(self) -> None:
        elegido = _make_transcriptor(self.root / "otro" / "sitio")
        _make_transcriptor(self.root / "meeting-transcriber")
        self.assertEqual(
            resolve_transcriptor_dir(str(elegido), self.recorder), str(elegido)
        )

    def test_empty_saved_path_is_rediscovered(self) -> None:
        # Abrió la app antes de instalar el Transcriptor: config.json guardó "".
        tx = _make_transcriptor(self.root / "meeting-transcriber")
        self.assertEqual(resolve_transcriptor_dir("", self.recorder), str(tx))

    def test_stale_saved_path_is_rediscovered(self) -> None:
        tx = _make_transcriptor(self.root / "meeting-transcriber")
        viejo = str(self.root / "ya_no_existe")
        self.assertEqual(resolve_transcriptor_dir(viejo, self.recorder), str(tx))

    def test_nothing_found_keeps_what_was_saved_so_the_error_names_it(self) -> None:
        viejo = str(self.root / "ya_no_existe")
        self.assertEqual(resolve_transcriptor_dir(viejo, self.recorder), viejo)


class TestLoadHealsTheSavedPath(unittest.TestCase):
    def test_load_replaces_an_empty_saved_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp)
            (appdata / "MeetingRecorder").mkdir()
            (appdata / "MeetingRecorder" / "config.json").write_text(
                json.dumps({"output_dir": tmp, "transcriptor_dir": ""}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"APPDATA": str(appdata)}), patch(
                "app.core.config.default_transcriptor_dir",
                return_value=r"C:\encontrado\meeting-transcriber",
            ):
                cfg = AppConfig.load()
        self.assertEqual(cfg.transcriptor_dir, r"C:\encontrado\meeting-transcriber")


if __name__ == "__main__":
    unittest.main()

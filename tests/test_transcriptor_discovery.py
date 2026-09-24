"""Encontrar el Transcriptor que de verdad se puede lanzar (specs 028 y 029).

Desde la spec 029 el Transcriptor viene dentro del repo (`transcriptor/`), en
todo clon, tenga o no su `.venv`. Por eso "encontrarlo" significa encontrar uno
**completo** (CLI + entorno): elegir la carpeta del repo solo por tener
`transcribe.py` rompería una instalación que funcionaba en cuanto se actualiza.
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


def _make_transcriptor(path: Path, with_env: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "transcribe.py").write_text("# cli\n", encoding="utf-8")
    if with_env:
        scripts = path / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "python.exe").write_bytes(b"")
    return path


class _Layout(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.recorder = self.root / "meeting-recorder"
        self.recorder.mkdir()

    @property
    def bundled(self) -> Path:
        return self.recorder / "transcriptor"


class TestDiscovery(_Layout):
    def test_bundled_transcriptor_is_found(self) -> None:
        tx = _make_transcriptor(self.bundled)
        self.assertEqual(default_transcriptor_dir(self.recorder), str(tx))

    def test_bundled_wins_over_a_sibling_when_both_are_complete(self) -> None:
        tx = _make_transcriptor(self.bundled)
        _make_transcriptor(self.root / "Transcriptor")
        self.assertEqual(default_transcriptor_dir(self.recorder), str(tx))

    def test_bundled_without_environment_never_beats_a_complete_sibling(self) -> None:
        # Justo después de actualizar el repo: transcriptor/ llegó, su .venv no.
        _make_transcriptor(self.bundled, with_env=False)
        hermano = _make_transcriptor(self.root / "Transcriptor")
        self.assertEqual(default_transcriptor_dir(self.recorder), str(hermano))

    def test_sibling_from_a_separate_clone_is_still_found(self) -> None:
        tx = _make_transcriptor(self.root / "meeting-transcriber")
        self.assertEqual(default_transcriptor_dir(self.recorder), str(tx))

    def test_legacy_location_one_level_up_is_still_found(self) -> None:
        anidado = self.root / "Apps" / "meeting-recorder"
        anidado.mkdir(parents=True)
        tx = _make_transcriptor(self.root / "Transcriptor")
        self.assertEqual(default_transcriptor_dir(anidado), str(tx))

    def test_with_nothing_complete_the_cli_folder_is_named(self) -> None:
        # Un clon recién hecho sin el entorno instalado: el aviso debe apuntar
        # a la carpeta del repo, que es donde falta el .venv.
        _make_transcriptor(self.bundled, with_env=False)
        self.assertEqual(default_transcriptor_dir(self.recorder), str(self.bundled))

    def test_a_folder_without_the_cli_is_not_a_transcriptor(self) -> None:
        self.bundled.mkdir()
        (self.root / "meeting-transcriber").mkdir()
        self.assertEqual(default_transcriptor_dir(self.recorder), "")


class TestResolve(_Layout):
    def test_a_complete_saved_path_wins(self) -> None:
        elegido = _make_transcriptor(self.root / "otro" / "sitio")
        _make_transcriptor(self.bundled)
        self.assertEqual(
            resolve_transcriptor_dir(str(elegido), self.recorder), str(elegido)
        )

    def test_an_incomplete_saved_path_yields_to_a_complete_one(self) -> None:
        incompleto = _make_transcriptor(self.root / "viejo", with_env=False)
        tx = _make_transcriptor(self.bundled)
        self.assertEqual(
            resolve_transcriptor_dir(str(incompleto), self.recorder), str(tx)
        )

    def test_empty_saved_path_is_rediscovered(self) -> None:
        # Abrió la app antes de instalar el Transcriptor: config.json guardó "".
        tx = _make_transcriptor(self.bundled)
        self.assertEqual(resolve_transcriptor_dir("", self.recorder), str(tx))

    def test_stale_saved_path_is_rediscovered(self) -> None:
        tx = _make_transcriptor(self.root / "meeting-transcriber")
        viejo = str(self.root / "ya_no_existe")
        self.assertEqual(resolve_transcriptor_dir(viejo, self.recorder), str(tx))

    def test_nothing_found_keeps_what_was_saved_so_the_error_names_it(self) -> None:
        viejo = str(self.root / "ya_no_existe")
        self.assertEqual(resolve_transcriptor_dir(viejo, self.recorder), viejo)

    def test_incomplete_everywhere_prefers_the_saved_cli_folder(self) -> None:
        guardado = _make_transcriptor(self.root / "mio", with_env=False)
        _make_transcriptor(self.bundled, with_env=False)
        self.assertEqual(
            resolve_transcriptor_dir(str(guardado), self.recorder), str(guardado)
        )


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
                return_value=r"C:\encontrado\transcriptor",
            ):
                cfg = AppConfig.load()
        self.assertEqual(cfg.transcriptor_dir, r"C:\encontrado\transcriptor")


if __name__ == "__main__":
    unittest.main()

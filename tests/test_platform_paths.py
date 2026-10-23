"""Rutas por sistema operativo (spec 030): Windows no cambia; macOS usa Library."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import platform_paths as P


class TestWindowsUnchanged(unittest.TestCase):
    def setUp(self) -> None:
        self._plat = patch.object(P.sys, "platform", "win32")
        self._plat.start()
        self.addCleanup(self._plat.stop)

    def test_config_follows_appdata(self) -> None:
        with patch.dict(os.environ, {"APPDATA": r"C:\X\Roaming"}):
            self.assertEqual(P.config_dir(), Path(r"C:\X\Roaming") / "MeetingRecorder")

    def test_local_follows_localappdata(self) -> None:
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\X\Local"}):
            self.assertEqual(P.local_dir(), Path(r"C:\X\Local") / "MeetingRecorder")

    def test_local_without_variable_uses_home(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "LOCALAPPDATA"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                P.local_dir(), Path.home() / "AppData" / "Local" / "MeetingRecorder"
            )

    def test_venv_python_is_scripts_exe(self) -> None:
        self.assertEqual(
            P.venv_python(Path("t") / ".venv"), Path("t") / ".venv" / "Scripts" / "python.exe"
        )


class TestMacOS(unittest.TestCase):
    def setUp(self) -> None:
        self._plat = patch.object(P.sys, "platform", "darwin")
        self._plat.start()
        self.addCleanup(self._plat.stop)

    def test_everything_under_application_support(self) -> None:
        base = Path.home() / "Library" / "Application Support" / "MeetingRecorder"
        with patch.dict(os.environ, {"APPDATA": "x", "LOCALAPPDATA": "y"}):
            self.assertEqual(P.config_dir(), base)
            self.assertEqual(P.local_dir(), base)
            self.assertEqual(P.engine_dir(), base / "engine")

    def test_cache_is_in_library_caches(self) -> None:
        self.assertEqual(
            P.cache_dir(), Path.home() / "Library" / "Caches" / "MeetingRecorder"
        )

    def test_venv_python_is_bin_python(self) -> None:
        self.assertEqual(P.venv_python(Path("t")), Path("t") / "bin" / "python")

    def test_engine_is_first_transcriptor_candidate(self) -> None:
        from app.core.config import _transcriptor_candidates

        candidatos = _transcriptor_candidates(Path("repo"))
        self.assertEqual(candidatos[0], P.engine_dir() / "transcriptor")
        self.assertEqual(candidatos[1], Path("repo") / "transcriptor")


class TestCandidatesOnWindows(unittest.TestCase):
    def test_no_engine_candidate_on_windows(self) -> None:
        from app.core.config import _transcriptor_candidates

        with patch.object(P.sys, "platform", "win32"):
            candidatos = _transcriptor_candidates(Path("repo"))
        self.assertEqual(candidatos[0], Path("repo") / "transcriptor")
        self.assertEqual(len(candidatos), 4)


if __name__ == "__main__":
    unittest.main()

"""CLI acepta varios archivos en un argv."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import transcribe  # noqa: E402


class TestCliMultiFile(unittest.TestCase):
    def test_nargs_plus_keeps_all_paths(self) -> None:
        argv = ["transcribe.py", "a.wav", "b.wav", "--language", "es", "--output", r"D:\out"]
        with patch.object(sys, "argv", argv):
            args = transcribe.parsear_args()
        self.assertEqual(args.entrada, ["a.wav", "b.wav"])
        self.assertEqual(args.idioma, "es")
        self.assertEqual(args.carpeta_salida, r"D:\out")

    def test_listar_entradas_varios_archivos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.wav"
            b = Path(tmp) / "b.wav"
            a.write_bytes(b"x")
            b.write_bytes(b"y")
            files = transcribe.listar_entradas([a, b], batch=False)
        self.assertEqual(files, [a, b])


if __name__ == "__main__":
    unittest.main()

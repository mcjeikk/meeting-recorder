"""Todo lo que importa la app está en requirements.txt (spec 028).

`psutil` se usaba desde el worker pero nunca se declaró: en esta máquina estaba
instalado a mano y todo pasaba, y en un clon limpio la app ni siquiera abría.
Este fallo solo se ve en una instalación nueva, así que se vigila aquí.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Módulo importado -> distribución de PyPI que lo instala.
DISTRIBUTION_FOR_MODULE = {
    "PySide6": "pyside6",
    "cv2": "opencv-python",
    "imageio_ffmpeg": "imageio-ffmpeg",
    "numpy": "numpy",
    "psutil": "psutil",
    "pyaudiowpatch": "pyaudiowpatch",
    "sounddevice": "sounddevice",
    "windows_capture": "windows-capture",
}


def third_party_imports() -> dict:
    """{módulo de primer nivel: primer archivo que lo importa}, sin stdlib ni app."""
    encontrados: dict = {}
    for archivo in sorted((ROOT / "app").rglob("*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
                nombres = [nodo.module]
            else:
                continue
            for nombre in nombres:
                top = nombre.split(".")[0]
                if top == "app" or top in sys.stdlib_module_names:
                    continue
                encontrados.setdefault(top, archivo.relative_to(ROOT).as_posix())
    return encontrados


def declared_distributions() -> set:
    nombres = set()
    for linea in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        m = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", linea)
        if m:
            nombres.add(m.group(0).lower().replace("_", "-"))
    return nombres


class TestRequirementsDeclared(unittest.TestCase):
    def test_every_third_party_import_is_known(self) -> None:
        desconocidos = {
            mod: donde
            for mod, donde in third_party_imports().items()
            if mod not in DISTRIBUTION_FOR_MODULE
        }
        self.assertEqual(
            desconocidos,
            {},
            "Import de terceros nuevo: añádelo a requirements.txt y a "
            "DISTRIBUTION_FOR_MODULE en este test.",
        )

    def test_every_third_party_import_is_declared(self) -> None:
        declaradas = declared_distributions()
        faltan = {
            mod: donde
            for mod, donde in third_party_imports().items()
            if mod in DISTRIBUTION_FOR_MODULE
            and DISTRIBUTION_FOR_MODULE[mod] not in declaradas
        }
        self.assertEqual(
            faltan, {}, "Importado por la app pero ausente de requirements.txt"
        )

    def test_psutil_is_declared(self) -> None:
        # El caso que lo originó: sin psutil la app no abre en un clon limpio.
        self.assertIn("psutil", declared_distributions())


if __name__ == "__main__":
    unittest.main()

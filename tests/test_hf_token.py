"""Token de Hugging Face (spec 030): validación sin red y almacenamiento."""
import tempfile
import unittest
from pathlib import Path

from app.transcription import hf_token as hf

FAKE = "hf_" + "A1b2C3d4E5" * 3 + "xyzw"


def fetcher(whoami: int, model: int):
    def _fetch(url, token):
        return whoami if "whoami" in url else model

    return _fetch


class ValidateTests(unittest.TestCase):
    def test_garbage_is_invalid_without_network(self):
        def boom(url, token):
            raise AssertionError("no debe llamar a la red")

        self.assertEqual(hf.validate("hola", boom).result, hf.INVALID)
        self.assertEqual(hf.validate("", boom).result, hf.INVALID)

    def test_rejected_token(self):
        self.assertEqual(hf.validate(FAKE, fetcher(401, 200)).result, hf.INVALID)

    def test_terms_not_accepted(self):
        r = hf.validate(FAKE, fetcher(200, 403))
        self.assertEqual(r.result, hf.TERMS)
        self.assertIn(hf.MODEL_URL, r.message)

    def test_ok(self):
        self.assertEqual(hf.validate(FAKE, fetcher(200, 200)).result, hf.OK)

    def test_offline(self):
        def offline(url, token):
            raise OSError("sin red")

        self.assertEqual(hf.validate(FAKE, offline).result, hf.NETWORK)

    def test_whitespace_is_trimmed(self):
        self.assertEqual(hf.validate(f"  {FAKE}\n", fetcher(200, 200)).result, hf.OK)


class MaskTests(unittest.TestCase):
    def test_never_shows_whole_token(self):
        m = hf.mask(FAKE)
        self.assertNotIn(FAKE, m)
        self.assertTrue(m.startswith("hf_"))
        self.assertTrue(m.endswith(FAKE[-4:]))

    def test_empty(self):
        self.assertEqual(hf.mask(None), "")
        self.assertEqual(hf.mask("corto"), "…")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.env = Path(self._tmp.name) / ".env"

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip_preserves_other_lines(self):
        self.env.write_text("OTRA=1\nHUGGINGFACE_TOKEN=hf_xxxplaceholder\n", encoding="utf-8")
        self.assertIsNone(hf.read_token(self.env))
        hf.write_token(self.env, FAKE)
        self.assertEqual(hf.read_token(self.env), FAKE)
        texto = self.env.read_text(encoding="utf-8")
        self.assertIn("OTRA=1", texto)
        self.assertEqual(texto.count("HUGGINGFACE_TOKEN"), 1)

    def test_remove(self):
        hf.write_token(self.env, FAKE)
        hf.write_token(self.env, None)
        self.assertIsNone(hf.read_token(self.env))

    def test_missing_file(self):
        self.assertIsNone(hf.read_token(self.env))

    def test_quoted_value(self):
        self.env.write_text(f'HUGGINGFACE_TOKEN="{FAKE}"\n', encoding="utf-8")
        self.assertEqual(hf.read_token(self.env), FAKE)


if __name__ == "__main__":
    unittest.main()

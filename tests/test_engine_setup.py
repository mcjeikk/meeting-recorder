"""Motor al primer uso (spec 030): decisiones puras y operaciones de disco."""
import tempfile
import unittest
from pathlib import Path

from app.transcription import engine_setup as es


class LockChoiceTests(unittest.TestCase):
    def test_macos14_and_later_use_validated_pins(self):
        for major in (14, 15, 26):
            self.assertEqual(es.lock_name_for(major), es.LOCK_MACOS)

    def test_macos13_has_its_own_lock(self):
        self.assertEqual(es.lock_name_for(13), es.LOCK_MACOS13)

    def test_unknown_version_uses_default_lock(self):
        self.assertEqual(es.lock_name_for(0), es.LOCK_MACOS)

    def test_macos_major_parses(self):
        self.assertEqual(es.macos_major("14.5"), 14)
        self.assertEqual(es.macos_major("13"), 13)
        self.assertEqual(es.macos_major(""), 0)
        self.assertEqual(es.macos_major("x"), 0)

    def test_both_locks_exist_in_repo(self):
        src = es.bundled_source_dir()
        for name in (es.LOCK_MACOS, es.LOCK_MACOS13):
            lock = src / name
            self.assertTrue(lock.exists(), name)
            texto = lock.read_text(encoding="utf-8")
            self.assertIn("pyannote-audio==", texto)
            self.assertIn("faster-whisper==", texto)
            pins = [l for l in texto.splitlines() if l and not l.startswith("#")]
            self.assertFalse([p for p in pins if "+cpu" in p])


class EvaluateTests(unittest.TestCase):
    def test_absent(self):
        s = es.evaluate(es.EngineState(), False, "h1", False)
        self.assertEqual(s.state, es.ABSENT)
        self.assertFalse(s.ready)

    def test_ready_when_installed(self):
        s = es.evaluate(es.EngineState(state=es.READY, lock_hash="h1"), True, "h1", False)
        self.assertTrue(s.ready)
        self.assertFalse(s.outdated)

    def test_new_lock_means_outdated_but_still_usable(self):
        s = es.evaluate(es.EngineState(state=es.READY, lock_hash="h1"), True, "h2", False)
        self.assertTrue(s.ready)
        self.assertTrue(s.outdated)

    def test_interrupted_install_is_failed(self):
        s = es.evaluate(es.EngineState(state=es.INSTALLING), False, "h1", installer_alive=False)
        self.assertEqual(s.state, es.FAILED)
        self.assertFalse(s.ready)
        self.assertIn("interrump", s.error)

    def test_install_in_progress_is_not_failed(self):
        s = es.evaluate(es.EngineState(state=es.INSTALLING), False, "h1", installer_alive=True)
        self.assertEqual(s.state, es.INSTALLING)

    def test_failed_reinstall_keeps_previous_engine(self):
        st = es.EngineState(state=es.FAILED, lock_hash="h1", error="red caída")
        s = es.evaluate(st, True, "h2", False)
        self.assertTrue(s.ready)
        self.assertEqual(s.error, "red caída")

    def test_venv_without_successful_install_is_not_ready(self):
        s = es.evaluate(es.EngineState(state=es.FAILED), True, "h1", False)
        self.assertFalse(s.ready)


class DiskTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_state_roundtrip(self):
        p = self.root / "state.json"
        es.EngineState(state=es.READY, lock_hash="abc", consented=True).save(p)
        st = es.EngineState.load(p)
        self.assertEqual((st.state, st.lock_hash, st.consented), (es.READY, "abc", True))

    def test_corrupt_state_is_absent(self):
        p = self.root / "state.json"
        p.write_text("{no json", encoding="utf-8")
        self.assertEqual(es.EngineState.load(p).state, es.ABSENT)

    def test_unknown_state_value_is_absent(self):
        p = self.root / "state.json"
        p.write_text('{"state": "raro"}', encoding="utf-8")
        self.assertEqual(es.EngineState.load(p).state, es.ABSENT)

    def test_sync_sources_keeps_venv_and_env(self):
        src = self.root / "src"
        (src / "pipeline").mkdir(parents=True)
        (src / "transcribe.py").write_text("v2", encoding="utf-8")
        (src / "pipeline" / "asr.py").write_text("x", encoding="utf-8")
        (src / ".env").write_text("HUGGINGFACE_TOKEN=del_repo", encoding="utf-8")
        (src / ".venv").mkdir()
        dst = self.root / "dst"
        (dst / ".venv").mkdir(parents=True)
        (dst / ".venv" / "marca").write_text("venv", encoding="utf-8")
        (dst / ".env").write_text("HUGGINGFACE_TOKEN=del_usuario", encoding="utf-8")
        (dst / "transcribe.py").write_text("v1", encoding="utf-8")

        self.assertTrue(es.sync_sources(src, dst))
        self.assertEqual((dst / "transcribe.py").read_text(encoding="utf-8"), "v2")
        self.assertTrue((dst / "pipeline" / "asr.py").exists())
        self.assertTrue((dst / ".venv" / "marca").exists())
        self.assertEqual((dst / ".env").read_text(encoding="utf-8"), "HUGGINGFACE_TOKEN=del_usuario")

    def test_sync_sources_keeps_modules_named_like_data_folders(self):
        # Un patrón global "output*" se saltaba pipeline/output.py (CI macOS).
        src = self.root / "src"
        (src / "pipeline").mkdir(parents=True)
        (src / "output").mkdir()
        (src / "transcribe.py").write_text("x", encoding="utf-8")
        (src / "pipeline" / "output.py").write_text("x", encoding="utf-8")
        (src / "pipeline" / "input.py").write_text("x", encoding="utf-8")
        (src / "output" / "reunion.txt").write_text("x", encoding="utf-8")
        dst = self.root / "dst"
        es.sync_sources(src, dst)
        self.assertTrue((dst / "pipeline" / "output.py").exists())
        self.assertTrue((dst / "pipeline" / "input.py").exists())
        self.assertFalse((dst / "output").exists())

    def test_sync_copies_the_real_transcriptor_completely(self):
        src = es.bundled_source_dir()
        dst = self.root / "motor"
        es.sync_sources(src, dst)
        for py in (src / "pipeline").glob("*.py"):
            self.assertTrue((dst / "pipeline" / py.name).exists(), py.name)

    def test_sync_sources_without_cli_does_nothing(self):
        self.assertFalse(es.sync_sources(self.root / "vacio", self.root / "dst"))
        self.assertFalse((self.root / "dst").exists())

    def test_swap_venv_replaces_old(self):
        raiz = self.root
        (raiz / ".venv").mkdir()
        (raiz / ".venv" / "viejo").write_text("1", encoding="utf-8")
        (raiz / ".venv.partial").mkdir()
        (raiz / ".venv.partial" / "nuevo").write_text("2", encoding="utf-8")
        es._swap_venv(raiz, raiz / ".venv.partial")
        self.assertTrue((raiz / ".venv" / "nuevo").exists())
        self.assertFalse((raiz / ".venv" / "viejo").exists())
        self.assertFalse((raiz / ".venv.partial").exists())
        self.assertFalse((raiz / ".venv.old").exists())

    def test_file_hash_changes_with_content(self):
        p = self.root / "lock.txt"
        p.write_text("a==1", encoding="utf-8")
        h1 = es.file_hash(p)
        p.write_text("a==2", encoding="utf-8")
        self.assertNotEqual(h1, es.file_hash(p))
        self.assertEqual(es.file_hash(self.root / "no.txt"), "")


if __name__ == "__main__":
    unittest.main()

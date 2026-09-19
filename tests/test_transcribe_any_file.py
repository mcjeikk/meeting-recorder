"""Tests: transcribe arbitrary files (extensions, classify, enqueue, no copy)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.transcription.import_media import (
    ALREADY_ACTIVE,
    ALREADY_DONE,
    FOLDER,
    MISSING_FILE,
    MISSING_TOOL,
    OK,
    SUPPORTED_MEDIA_EXTS,
    UNSUPPORTED,
    canonical_media_path,
    classify_import,
    enqueue_imports,
    file_dialog_filter,
    is_supported_media,
    summarize_import_results,
)
from app.transcription.jobs import DONE, PENDING, JobStore


class TestSupportedMedia(unittest.TestCase):
    def test_common_types(self) -> None:
        for ext in (".mp3", ".m4a", ".wav", ".mp4", ".mkv", ".flac"):
            self.assertTrue(is_supported_media(Path(f"x{ext}")), ext)
            self.assertTrue(is_supported_media(Path(f"x{ext.upper()}")), ext)

    def test_rejects_text(self) -> None:
        self.assertFalse(is_supported_media(Path("notes.txt")))
        self.assertFalse(is_supported_media(Path("doc.docx")))

    def test_dialog_filter_lists_exts(self) -> None:
        filt = file_dialog_filter()
        self.assertIn("*.mp3", filt)
        self.assertIn("*.mp4", filt)
        self.assertIn("Todos los archivos", filt)
        for ext in SUPPORTED_MEDIA_EXTS:
            self.assertIn(f"*{ext}", filt)


class TestClassifyAndEnqueue(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = JobStore(base=self.root / "tx")
        self.media = self.root / "podcast.mp3"
        self.media.write_bytes(b"fake-audio")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _enqueue_fn(self):
        def _go(path: str, language: str, preset: str | None):
            job = self.store.enqueue(path, language, preset=preset)
            return job.snapshot() if job else None

        return _go

    def test_ok_file(self) -> None:
        r = classify_import(self.store, str(self.media), tool_available=True)
        self.assertEqual(r.kind, OK)
        self.assertEqual(r.path, canonical_media_path(self.media))

    def test_missing_file(self) -> None:
        r = classify_import(self.store, str(self.root / "gone.wav"), tool_available=True)
        self.assertEqual(r.kind, MISSING_FILE)

    def test_folder(self) -> None:
        folder = self.root / "album"
        folder.mkdir()
        r = classify_import(self.store, str(folder), tool_available=True)
        self.assertEqual(r.kind, FOLDER)

    def test_unsupported(self) -> None:
        txt = self.root / "notes.txt"
        txt.write_text("hi", encoding="utf-8")
        r = classify_import(self.store, str(txt), tool_available=True)
        self.assertEqual(r.kind, UNSUPPORTED)

    def test_missing_tool(self) -> None:
        r = classify_import(self.store, str(self.media), tool_available=False)
        self.assertEqual(r.kind, MISSING_TOOL)

    def test_already_active(self) -> None:
        job = self.store.enqueue(canonical_media_path(self.media), "es", preset="rapido")
        assert job is not None
        self.assertEqual(job.status, PENDING)
        r = classify_import(self.store, str(self.media), tool_available=True)
        self.assertEqual(r.kind, ALREADY_ACTIVE)

    def test_already_done(self) -> None:
        path = canonical_media_path(self.media)
        job = self.store.enqueue(path, "en", preset="equilibrado")
        assert job is not None
        job.status = DONE
        job.result_dir = str(self.root / "Transcripciones" / self.media.stem)
        self.store.save(job)
        r = classify_import(self.store, str(self.media), tool_available=True)
        self.assertEqual(r.kind, ALREADY_DONE)
        self.assertEqual(r.result_dir, job.result_dir)

    def _write_transcript(self, base: Path, media: Path) -> Path:
        destino = base / "Transcripciones" / media.stem
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "transcripcion.txt").write_text("texto", encoding="utf-8")
        return destino

    def test_transcript_on_disk_counts_without_a_record(self) -> None:
        """Spec 023: al podar el histórico, el disco es quien recuerda."""
        salida = self.root / "salida"
        destino = self._write_transcript(salida, self.media)
        r = classify_import(
            self.store, str(self.media), tool_available=True, output_base=str(salida)
        )
        self.assertEqual(r.kind, ALREADY_DONE)
        self.assertEqual(Path(r.result_dir), destino.resolve())
        self.assertIn("Ya hay una transcripción", r.message)

    def test_deleted_transcript_is_queued_again(self) -> None:
        salida = self.root / "salida"
        r = classify_import(
            self.store, str(self.media), tool_available=True, output_base=str(salida)
        )
        self.assertEqual(r.kind, OK)

    def test_pruned_record_with_transcript_is_not_re_enqueued(self) -> None:
        salida = self.root / "salida"
        self._write_transcript(salida, self.media)
        results = enqueue_imports(
            [str(self.media)],
            store=self.store,
            enqueue=self._enqueue_fn(),
            language="es",
            preset="equilibrado",
            tool_available=True,
            output_base=str(salida),
        )
        self.assertEqual([r.kind for r in results], [ALREADY_DONE])
        self.assertEqual(self.store.all(), [])
        self.assertIn("ya había transcripción", summarize_import_results(results))

    def test_existing_record_still_wins(self) -> None:
        """El registro sigue primero: trae la carpeta y el snapshot del job."""
        salida = self.root / "salida"
        self._write_transcript(salida, self.media)
        job = self.store.enqueue(canonical_media_path(self.media), "es")
        assert job is not None
        job.status = DONE
        job.result_dir = str(self.root / "otra" / "carpeta")
        self.store.save(job)
        r = classify_import(
            self.store, str(self.media), tool_available=True, output_base=str(salida)
        )
        self.assertEqual(r.kind, ALREADY_DONE)
        self.assertEqual(r.result_dir, job.result_dir)
        self.assertIsNotNone(r.job)

    def test_enqueue_does_not_copy_original(self) -> None:
        before = self.media.read_bytes()
        results = enqueue_imports(
            [str(self.media)],
            store=self.store,
            enqueue=self._enqueue_fn(),
            language="es",
            preset="rapido",
            tool_available=True,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].kind, OK)
        self.assertTrue(self.media.exists())
        self.assertEqual(self.media.read_bytes(), before)
        copies = [p for p in self.store.base.rglob("podcast.mp3") if p.is_file()]
        self.assertEqual(copies, [])
        stored = self.store.all()[0]
        self.assertEqual(stored.media_path, canonical_media_path(self.media))
        self.assertEqual(stored.language, "es")
        self.assertEqual(stored.preset, "rapido")

    def test_mixed_paths(self) -> None:
        wav = self.root / "clip.wav"
        wav.write_bytes(b"x")
        txt = self.root / "readme.txt"
        txt.write_text("no", encoding="utf-8")
        results = enqueue_imports(
            [str(self.media), str(txt), str(wav)],
            store=self.store,
            enqueue=self._enqueue_fn(),
            language="en",
            preset="equilibrado",
            tool_available=True,
        )
        kinds = [r.kind for r in results]
        self.assertEqual(kinds, [OK, UNSUPPORTED, OK])
        self.assertEqual(len(self.store.all()), 2)
        summary = summarize_import_results(results)
        self.assertIn("2 archivos en cola", summary)
        self.assertIn("readme.txt", summary)

    def test_second_enqueue_of_done_is_not_duplicated(self) -> None:
        enqueue_imports(
            [str(self.media)],
            store=self.store,
            enqueue=self._enqueue_fn(),
            language="es",
            preset="equilibrado",
            tool_available=True,
        )
        job = self.store.all()[0]
        job.status = DONE
        self.store.save(job)
        results = enqueue_imports(
            [str(self.media)],
            store=self.store,
            enqueue=self._enqueue_fn(),
            language="es",
            preset="equilibrado",
            tool_available=True,
        )
        self.assertEqual(results[0].kind, ALREADY_DONE)
        self.assertEqual(len(self.store.all()), 1)


@unittest.skipUnless(os.environ.get("QT_QPA_PLATFORM") != "skip", "Qt UI")
class TestImportButtonHeadless(unittest.TestCase):
    def test_mainwindow_has_transcribe_file_button(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        from PySide6.QtWidgets import QApplication
        import sys

        app = QApplication.instance() or QApplication(sys.argv)
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.threading.Thread") as thr:
            thr.return_value = MagicMock()
            with patch.object(MainWindow, "_update_preview", lambda self: None):
                with patch("app.ui.main_window.AudioMonitor"):
                    w = MainWindow()
        try:
            self.assertTrue(hasattr(w, "_tx_file_btn"))
            self.assertIn("Transcribir archivo", w._tx_file_btn.text())
            self.assertTrue(hasattr(w, "_tx_queue_list"))
            self.assertTrue(hasattr(w, "_tx_speakers"))
            self.assertIn("Carpeta de salida", w._tx_file_hint.text())
            self.assertTrue(w.acceptDrops())
            w._tx_file_btn.setEnabled(True)
            w._set_recording_ui(True)
            self.assertTrue(w._tx_file_btn.isEnabled())
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()

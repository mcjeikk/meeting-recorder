"""Importar voz de prueba por la interfaz, transcribirla y abrir resultado y log."""
import argparse
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog

from app.core.config import AppConfig
from app.transcription.jobs import JobStore
from app.ui import transcriptions
from app.ui.audio_inputs import AudioInputs
from app.ui.main_window import MainWindow
from app.ui.preview import Preview
from tools.verify_recorder_front import click, wait_for


def run(media, engine, root):
    root.mkdir(parents=True, exist_ok=True)
    # El motor instalado recibe solo el medio de prueba y su carpeta de salida.
    cfg = AppConfig(output_dir=str(root), transcriptor_dir=str(engine),
                    transcription_preset="rapido", transcription_language="es")
    app = QApplication.instance() or QApplication([])
    with ExitStack() as stack:
        stack.enter_context(patch.object(AppConfig, "load", return_value=cfg))
        stack.enter_context(patch("app.ui.transcriptions.JobStore", return_value=JobStore(root / "cola")))
        stack.enter_context(patch.object(AudioInputs, "refresh"))
        stack.enter_context(patch.object(Preview, "refresh"))
        stack.enter_context(patch.object(MainWindow, "_offer_pending_save"))
        stack.enter_context(patch.object(QFileDialog, "getOpenFileNames", return_value=([str(media)], "")))
        window = MainWindow()
        window.setAttribute(Qt.WA_ShowWithoutActivating)
        window.show()
        app.processEvents()
        click(window, "tab1")
        click(window, "importButton")
        if not window.library.rows:
            raise RuntimeError(window.library.importStatus)
        print("Archivo de prueba importado en la cola local", flush=True)

        def finished():
            detail = window.library.detail
            if detail["state"] == "error":
                raise RuntimeError(detail["info"])
            return detail["state"] == "done"

        wait_for(app, finished, "transcripción del archivo", 1800)
        detail = window.library.detail
        result, log = Path(detail["result"]), Path(detail["log"])
        transcript = (result / "transcripcion.txt").read_text(encoding="utf-8")
        if not transcript.strip() or not log.is_file():
            raise RuntimeError("Faltan el texto o el registro del motor")
        opened = []
        actual_open = transcriptions.open_local

        def open_and_verify(path):
            success = actual_open(path)
            if success:
                opened.append(Path(path))
            return success

        with patch.object(transcriptions, "open_local", open_and_verify):
            click(window, "resultButton")
            click(window, "logButton")
        if opened != [result, log]:
            raise RuntimeError(f"El escritorio no aceptó ambas aperturas: {opened}")
        print(f"Transcripción verificada ({len(transcript)} caracteres); carpeta y registro abiertos.", flush=True)
        window.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix="recorder-front-transcript-"))
    raise SystemExit(run(args.media.resolve(), args.engine.resolve(), output.resolve()))

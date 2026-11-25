"""Estado de grabación compartido por la ventana, los atajos y la bandeja."""
from __future__ import annotations

from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.core.orchestrator import Recorder


class RecordingSession(QObject):
    changed = Signal()
    status = Signal(str)
    saved = Signal(str)
    failed = Signal(str)
    recovery = Signal(str)
    progress = Signal(int)
    _settled = Signal()
    _finished = Signal(str)
    _error = Signal(str)
    _save_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = "idle"
        self.recorder = Recorder(
            on_status=self.status.emit, on_finished=self._finished.emit,
            on_error=self._error.emit, on_progress=self.progress.emit,
            on_save_failed=self._save_failed.emit,
        )
        self._settled.connect(self._sync)
        self._finished.connect(self._on_saved)
        self._error.connect(self._on_error)
        self._save_failed.connect(self._on_recovery)

    @Property(str, notify=changed)
    def phase(self):
        return self._phase

    @Property(bool, notify=changed)
    def busy(self):
        return self._phase in ("starting", "pausing", "resuming", "saving", "changingMic")

    def priority(self):
        return self._phase not in ("idle", "recovery")

    def _set_phase(self, value):
        if value != self._phase:
            self._phase = value
            self.changed.emit()

    def _run(self, phase, operation, *, wait_for_save=False):
        self._set_phase(phase)

        def run():
            try:
                operation()
            except Exception as exc:
                self._error.emit(str(exc))
            else:
                if not wait_for_save:
                    self._settled.emit()

        Thread(target=run, daemon=True).start()

    def start(self, settings, release_monitor):
        if self._phase != "idle":
            return

        def open_devices():
            release_monitor()
            self.recorder.start(settings)

        self._run("starting", open_devices)

    @Slot()
    def togglePause(self):
        if self._phase == "recording":
            self._run("pausing", self.recorder.pause)
        elif self._phase == "paused":
            self._run("resuming", self.recorder.resume)

    @Slot()
    def stop(self):
        if self._phase in ("recording", "paused"):
            self._run("saving", self.recorder.stop, wait_for_save=True)

    def change_mic(self, device):
        if self._phase in ("recording", "paused"):
            self._run("changingMic", lambda: self.recorder.change_mic(device))

    def retry(self, directory: Path):
        if self._phase == "recovery":
            self._run("saving", lambda: self.recorder.retry_save(directory), wait_for_save=True)

    def adopt(self, pending):
        if self._phase == "idle":
            self.recorder.adopt_pending(pending)
            self._set_phase("recovery")

    @Slot()
    def _sync(self):
        if self.recorder.is_recording():
            self._set_phase("paused" if self.recorder.is_paused() else "recording")
        else:
            self._set_phase("idle")

    @Slot(str)
    def _on_saved(self, path):
        self._set_phase("idle")
        self.saved.emit(path)

    @Slot(str)
    def _on_error(self, message):
        self._sync()
        self.failed.emit(message)

    @Slot(str)
    def _on_recovery(self, message):
        self._set_phase("recovery")
        self.recovery.emit(message)

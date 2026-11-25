"""La vista lee la cola persistente y conserva la selección al recibir progreso."""
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from app.transcription.import_media import ALREADY_DONE, OK, enqueue_imports, summarize_import_results
from app.transcription.jobs import JobStore
from app.transcription.queue_status import batch_eta_text, batch_suffix, eta_suffix, format_queue_line, visible_queue_jobs
from app.transcription.worker import TranscriptionWorker


def open_local(path):
    if path and Path(path).exists():
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).absolute())))
    return False


class Transcriptions(QObject):
    changed = Signal()
    updates = Signal(dict)
    requestEngine = Signal()
    completed = Signal(str)
    message = Signal(str)

    def __init__(self, prefs, session, available, engine_ready, parent=None):
        super().__init__(parent)
        self.prefs = prefs
        self.store = JobStore()
        self._available = available
        self._selected = ""
        self._live = {}
        self._rows = []
        self._detail = {}
        self._summary = ""
        self._import_status = ""
        self.worker = TranscriptionWorker(self.store, get_config=lambda: prefs.config,
                                         on_update=self.updates.emit, is_recording=session.priority,
                                         engine_ready=engine_ready)
        self.updates.connect(self.update_job)
        self.refresh()

    @Property(bool, constant=True)
    def available(self):
        return self._available

    @Property("QVariantList", notify=changed)
    def rows(self):
        return self._rows

    @Property("QVariantMap", notify=changed)
    def detail(self):
        return self._detail

    @Property(str, notify=changed)
    def summary(self):
        return self._summary

    @Property(str, notify=changed)
    def importStatus(self):
        return self._import_status

    def open_job(self):
        return self.worker.has_active_job() or self._live.get("status") in ("pending", "extracting", "running")

    @Slot(dict)
    def update_job(self, snap):
        if snap.get("status") == "done":
            self.completed.emit(Path(snap.get("media_path", "")).name)
        self._live = snap
        self.refresh()

    @Slot(str)
    def select(self, job_id):
        self._selected = job_id
        self.refresh()

    def refresh(self):
        all_jobs = self.store.all()
        jobs = visible_queue_jobs(all_jobs)
        jobs.extend(sorted((j for j in all_jobs if j.status == "done"),
                           key=lambda j: j.created_at, reverse=True))
        live_id = self._live.get("id", "")
        self._rows = [
            {"id": job.id, "label": format_queue_line(job, live_id=live_id,
                stage=self._live.get("stage", "") if live_id == job.id else "",
                progress=self._live.get("progress") if live_id == job.id else None)}
            for job in jobs
        ]
        lookup = {j.id: j for j in jobs}
        job = lookup.get(self._selected) or lookup.get(live_id) or next(iter(jobs), None)
        snap = job.snapshot() if job else {}
        if job and job.id == live_id:
            snap.update(self._live)
        state = snap.get("status", "")
        stage = snap.get("stage") or {"pending": "En espera", "running": "Transcribiendo",
            "extracting": "Preparando audio", "done": "Transcripción lista",
            "error": "Error de transcripción", "cancelled": "Cancelada"}.get(state, "")
        self._detail = dict(
            id=snap.get("id", ""), state=state, title=Path(snap.get("media_path", "")).name,
            status=stage + batch_suffix(snap) + eta_suffix(snap), info=snap.get("error") or snap.get("note") or "",
            progress=snap.get("progress") or 0, result=snap.get("result_dir") or "",
            log=snap.get("log_path") or "", clearable=any(j.status in ("error", "cancelled") for j in jobs),
        )
        counts = self.store.queue_counts(live_id)
        parts = [f"{counts[key]} {label}" for key, label in (
            ("running", "en curso"), ("pending", "en espera"), ("failed", "con error")) if counts[key]]
        self._summary = " · ".join(filter(None, [*parts, batch_eta_text(self._live)]))
        self.changed.emit()

    def enqueue_recording(self, path):
        job = self.worker.enqueue(path, **self.prefs.transcription_options(),
                                  output_base=str(Path(path).absolute().parent))
        if job:
            self.requestEngine.emit()
        return bool(job)

    def import_paths(self, paths):
        opts = self.prefs.transcription_options()
        base = str(self.prefs.directory)
        results = enqueue_imports(paths, store=self.store, language=opts["language"], preset=opts["preset"],
            enqueue=lambda media, language, preset: self.worker.enqueue(
                media, language, preset=preset, pc_impact=opts["pc_impact"],
                num_speakers=opts["num_speakers"], output_base=base),
            tool_available=self.available, output_base=base)
        self._import_status = summarize_import_results(results)
        first = next((r for r in results if r.kind in (OK, ALREADY_DONE) and r.job), None)
        if first:
            self._selected = first.job["id"]
        if any(r.kind == OK for r in results):
            self.requestEngine.emit()
        self.refresh()

    @Slot()
    def openResult(self):
        if not open_local(self._detail["result"]):
            self.message.emit("No se pudo abrir la carpeta del resultado.")

    @Slot()
    def openLog(self):
        if not open_local(self._detail["log"]):
            self.message.emit("No se pudo abrir el registro.")

    @Slot()
    def retry(self):
        if self._detail["state"] == "error":
            self.worker.retry(self._detail["id"])
            self.refresh()

    @Slot()
    def cancel(self):
        if self._detail["state"] in ("pending", "extracting", "running"):
            self.worker.cancel(self._detail["id"])
            self.refresh()

    @Slot()
    def clearFailed(self):
        self.worker.clear_failed()
        self.refresh()

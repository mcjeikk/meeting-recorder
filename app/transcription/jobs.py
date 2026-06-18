"""Cola persistente de trabajos de transcripción.

Cada trabajo es UN archivo JSON en %LOCALAPPDATA%/MeetingRecorder/transcripts/queue/
(un archivo por job: una escritura corrupta nunca afecta a los demás). Toda
escritura es atómica (tmp + os.replace), a prueba de cierres y apagones.

La cola es el registro grabación→transcripción que el Recorder no tenía: si la
app se cierra, crashea o el PC se apaga, los trabajos pendientes siguen ahí y
el worker los retoma al siguiente arranque.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.transcription.integration import transcripts_base

# Estados de un trabajo. "running" con PID muerto se resuelve en la
# reconciliación del worker (done si hay resultado, pending si no).
PENDING = "pending"
EXTRACTING = "extracting"
RUNNING = "running"
DONE = "done"
ERROR = "error"

_ACTIVE = {PENDING, EXTRACTING, RUNNING}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class TranscriptionJob:
    media_path: str
    language: str = "es"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = PENDING
    attempts: int = 0
    max_attempts: int = 2
    pid: Optional[int] = None
    log_path: str = ""
    work_wav: str = ""
    result_dir: str = ""
    note: str = ""          # p. ej. "sin hablantes" si la diarización se degradó
    error: str = ""
    no_diarize: bool = False  # reintento degradado tras fallo de diarización
    created_at: str = field(default_factory=_now)
    started_at: str = ""
    finished_at: str = ""

    @property
    def media_name(self) -> str:
        return Path(self.media_path).name

    def snapshot(self) -> dict:
        """Copia plana para mandar a la UI por señal (sin compartir el objeto)."""
        return asdict(self)


class JobStore:
    """Persistencia de trabajos: un JSON por job en queue/."""

    def __init__(self, base: Optional[Path] = None) -> None:
        self.base = base or transcripts_base()
        self.queue_dir = self.base / "queue"
        self.logs_dir = self.base / "logs"
        self.work_dir = self.base / "work"
        for d in (self.queue_dir, self.logs_dir, self.work_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --- persistencia ---------------------------------------------------------
    def _path(self, job_id: str) -> Path:
        return self.queue_dir / f"{job_id}.json"

    def save(self, job: TranscriptionJob) -> None:
        path = self._path(job.id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(job), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp, path)

    def _load(self, path: Path) -> Optional[TranscriptionJob]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            campos = {k: v for k, v in data.items() if k in TranscriptionJob.__annotations__}
            return TranscriptionJob(**campos)
        except Exception:
            return None  # JSON corrupto/parcial: se ignora, nunca rompe la cola

    def all(self) -> List[TranscriptionJob]:
        jobs = [self._load(p) for p in sorted(self.queue_dir.glob("*.json"))]
        return sorted((j for j in jobs if j), key=lambda j: j.created_at)

    # --- operaciones ----------------------------------------------------------
    def enqueue(self, media_path: str, language: str = "es") -> Optional[TranscriptionJob]:
        """Crea un job pendiente. Devuelve None si ya hay uno activo o terminado
        para el mismo archivo (dedupe: re-encolar no debe duplicar horas de CPU)."""
        existente = self.find_by_media(media_path)
        if existente and (existente.status in _ACTIVE or existente.status == DONE):
            return None
        job = TranscriptionJob(media_path=str(media_path), language=language)
        job.log_path = str(self.logs_dir / f"{Path(media_path).stem}_{job.id}.log")
        self.save(job)
        return job

    def find_by_media(self, media_path: str) -> Optional[TranscriptionJob]:
        objetivo = os.path.normcase(str(media_path))
        for job in self.all():
            if os.path.normcase(job.media_path) == objetivo:
                return job
        return None

    def pending(self) -> List[TranscriptionJob]:
        return [j for j in self.all() if j.status == PENDING]

    def active(self) -> List[TranscriptionJob]:
        return [j for j in self.all() if j.status in _ACTIVE]

    def retry(self, job_id: str) -> Optional[TranscriptionJob]:
        """Re-encola un job en error (botón Reintentar de la UI)."""
        job = self._load(self._path(job_id))
        if not job or job.status != ERROR:
            return None
        job.status = PENDING
        job.error = ""
        job.pid = None
        self.save(job)
        return job

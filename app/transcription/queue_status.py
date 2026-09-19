"""Texto de estado de la cola (sin Qt) para la lista de la UI."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from app.transcription.eta import format_finish
from app.transcription.jobs import (
    CANCELLED,
    DONE,
    ERROR,
    EXTRACTING,
    PENDING,
    RUNNING,
    TranscriptionJob,
)

_OPEN = (PENDING, EXTRACTING, RUNNING, ERROR, CANCELLED)

_LABEL = {
    PENDING: "En espera",
    EXTRACTING: "Preparando audio",
    RUNNING: "En curso",
    ERROR: "Falló",
    CANCELLED: "Cancelada",
    DONE: "Lista",
}


def visible_queue_jobs(jobs: Iterable[TranscriptionJob]) -> List[TranscriptionJob]:
    """Jobs que el usuario debe ver: abiertos o fallidos (no el histórico done)."""
    open_jobs = [j for j in jobs if j.status in _OPEN]
    order = {RUNNING: 0, EXTRACTING: 1, PENDING: 2, ERROR: 3, CANCELLED: 4}
    return sorted(
        open_jobs,
        key=lambda j: (order.get(j.status, 9), j.created_at, j.id),
    )


def format_queue_line(
    job: TranscriptionJob,
    *,
    stage: str = "",
    progress: Optional[int] = None,
    live_id: str = "",
) -> str:
    name = Path(job.media_path).stem
    waiting_in_batch = (
        job.status == RUNNING and live_id and job.id != live_id
    )
    if waiting_in_batch:
        return f"⏳  {name}  —  En espera"
    if job.status == RUNNING:
        if progress is not None and progress > 0:
            return f"▶  {name}  —  En curso ({progress}%)"
        extra = stage.strip() if stage else "En curso"
        return f"▶  {name}  —  {extra}"
    if job.status == EXTRACTING:
        return f"▶  {name}  —  Preparando audio"
    if job.status == PENDING:
        return f"⏳  {name}  —  En espera"
    if job.status == ERROR:
        err = (job.error or "").strip()
        if len(err) > 80:
            err = err[:77] + "…"
        suffix = f"  ({err})" if err else ""
        return f"⚠  {name}  —  Falló{suffix}"
    if job.status == CANCELLED:
        return f"⛔  {name}  —  Cancelada"
    return f"•  {name}  —  {_LABEL.get(job.status, job.status)}"


def eta_suffix(snap: dict) -> str:
    """"  —  listo ~21:40" del archivo en curso; en pausa lo dice explícito."""
    if snap.get("eta_paused"):
        return "  —  estimación en pausa"
    texto = format_finish(float(snap.get("eta_epoch") or 0.0))
    return f"  —  {texto}" if texto else ""


def batch_eta_text(snap: dict) -> str:
    """"lote listo ~03:20" para el resumen de la cola (vacío si no aplica)."""
    if snap.get("status") not in ("pending", "extracting", "running"):
        return ""
    if snap.get("eta_paused"):
        return ""
    texto = format_finish(float(snap.get("batch_eta_epoch") or 0.0))
    return f"lote {texto}" if texto else ""


def batch_suffix(snap: dict) -> str:
    """"  ·  archivo 4 de 10" cuando el job va dentro de un lote; vacío si va solo."""
    try:
        pos = int(snap.get("batch_pos") or 0)
        total = int(snap.get("batch_total") or 0)
    except (TypeError, ValueError):
        return ""
    if total < 2 or not 1 <= pos <= total:
        return ""
    return f"  ·  archivo {pos} de {total}"


def format_queue_lines(
    jobs: Sequence[TranscriptionJob],
    *,
    current_id: str = "",
    stage: str = "",
    progress: Optional[int] = None,
) -> List[str]:
    rows = []
    for job in visible_queue_jobs(jobs):
        if job.id == current_id:
            rows.append(
                format_queue_line(
                    job, stage=stage, progress=progress, live_id=current_id
                )
            )
        else:
            rows.append(format_queue_line(job, live_id=current_id))
    return rows

"""Agrupar jobs compatibles para un solo CLI del Transcriptor (una carga de modelos)."""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from app.transcription.jobs import PENDING, TranscriptionJob


def job_fingerprint(job: TranscriptionJob) -> Tuple:
    """Misma huella → mismo modelo, idioma, hablantes y carpeta de salida."""
    return (
        str(getattr(job, "language", "") or ""),
        str(getattr(job, "model", "") or ""),
        int(getattr(job, "beam_size", 0) or 0),
        bool(getattr(job, "no_diarize", False)),
        int(getattr(job, "num_speakers", 0) or 0),
        str(getattr(job, "output_base", "") or ""),
    )


def compatible_batch(
    head: TranscriptionJob,
    pending: Sequence[TranscriptionJob] | Iterable[TranscriptionJob],
) -> List[TranscriptionJob]:
    """`head` más el resto de pendientes con la misma huella (orden de cola)."""
    fp = job_fingerprint(head)
    out: List[TranscriptionJob] = [head]
    seen = {head.id}
    for job in pending:
        if job.id in seen:
            continue
        if getattr(job, "status", "") != PENDING:
            continue
        if job_fingerprint(job) == fp:
            out.append(job)
            seen.add(job.id)
    return out

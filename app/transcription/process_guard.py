"""Detección de OOM y procesos transcribe.py duplicados."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import psutil

from app.transcription.pc_impact import PROFILE_USABLE
from app.transcription.presets import PRESET_EQUILIBRADO, get_preset

OOM_MARKERS = (
    "unable to allocate",
    "mkl_malloc",
    "failed to allocate memory",
    "memoryerror",
    "std::bad_alloc",
    "cuda out of memory",
)

_TURBO = get_preset(PRESET_EQUILIBRADO).model  # large-v3-turbo


def log_looks_like_oom(text: str) -> bool:
    blob = (text or "").lower()
    return any(m in blob for m in OOM_MARKERS)


def apply_oom_degrade(job: object) -> bool:
    """Aligera el job in-place. True si se puede reintentar más ligero.

    1) turbo + PC usable, manteniendo hablantes
    2) omitir diarización (último recurso, nota visible)
    """
    model = str(getattr(job, "model", "") or "")
    impact = str(getattr(job, "pc_impact", "") or "")
    lighter = False
    if model and model != _TURBO:
        job.model = _TURBO
        lighter = True
    if impact != PROFILE_USABLE:
        job.pc_impact = PROFILE_USABLE
        lighter = True
    if lighter:
        job.note = "modelo más ligero / menos CPU (poca memoria); se mantienen hablantes"
        return True
    if not getattr(job, "no_diarize", False):
        job.no_diarize = True
        job.pc_impact = PROFILE_USABLE
        job.note = "sin hablantes (poca memoria)"
        return True
    return False


def _cmdline(proc: psutil.Process) -> str:
    try:
        parts = proc.cmdline() or []
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return ""
    return " ".join(parts)


def find_transcribe_processes_for(wav: Optional[Path]) -> List[psutil.Process]:
    """Procesos transcribe.py que mencionan este WAV (o su stem)."""
    if wav is None:
        return []
    stem = Path(wav).stem.casefold()
    name = Path(wav).name.casefold()
    found: List[psutil.Process] = []
    if not stem:
        return found
    for proc in psutil.process_iter(["pid"]):
        try:
            cmd = _cmdline(proc).casefold()
            if "transcribe.py" not in cmd:
                continue
            if name in cmd or stem in cmd:
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def adopt_transcribe_process(wav: Optional[Path]) -> Optional[psutil.Process]:
    """Elige el proceso con más RAM y mata duplicados del mismo archivo."""
    procs = find_transcribe_processes_for(wav)
    if not procs:
        return None

    def _rss(p: psutil.Process) -> int:
        try:
            return int(p.memory_info().rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0

    keep = max(procs, key=_rss)
    for p in procs:
        if p.pid == keep.pid:
            continue
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return keep

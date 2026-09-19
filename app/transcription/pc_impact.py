"""Uso del PC mientras transcribe (independiente del preset de calidad).

Ver specs/011-transcription-pc-impact/. Equilibrado/Máxima congelaban el
escritorio porque pyannote/torch ignoraban --threads y saturaban todos los
núcleos; usable limita hilos + prioridad.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

PROFILE_USABLE = "usable"
PROFILE_FULL = "full"
DEFAULT_PC_IMPACT = PROFILE_FULL

# 1 = factory usable (011). 2 = factory full (2026-09-10). Configs sin este
# rev se migran una vez a full; si el usuario elige usable después, se respeta.
FACTORY_DEFAULT_REV = 2

# Jobs creados antes de este campo: no cambiar su presupuesto a mitad de cola.
LEGACY_JOB_PC_IMPACT = PROFILE_FULL

THREAD_ENV_KEYS: Tuple[str, ...] = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "TORCH_NUM_THREADS",
)

# Win32: CREATE_NO_WINDOW lo aporta integration.NO_WINDOW.
IDLE_PRIORITY = 0x00000040 if sys.platform == "win32" else 0
BELOW_NORMAL_PRIORITY = 0x00004000 if sys.platform == "win32" else 0


@dataclass(frozen=True)
class PcImpactProfile:
    id: str
    label_es: str
    hint_es: str


PROFILES: Dict[str, PcImpactProfile] = {
    PROFILE_USABLE: PcImpactProfile(
        id=PROFILE_USABLE,
        label_es="Dejar el PC usable",
        hint_es=(
            "Deja núcleos libres para otras apps (la transcripción tarda más). "
            "Puedes combinarlo con Máxima calidad. En un trabajo ya en curso "
            "solo baja la prioridad; menos hilos aplican al siguiente arranque."
        ),
    ),
    PROFILE_FULL: PcImpactProfile(
        id=PROFILE_FULL,
        label_es="Usar más CPU (más rápido)",
        hint_es=(
            "Usa casi todos los núcleos (opción por defecto). El PC puede ir "
            "muy pesado. Si ya está transcribiendo, solo cambia la prioridad; "
            "más hilos aplican a trabajos que aún no arrancaron."
        ),
    ),
}

PC_IMPACT_ORDER: Tuple[str, ...] = (PROFILE_FULL, PROFILE_USABLE)


def normalize_pc_impact(value: object) -> str:
    """Unknown/empty → full (FR-003)."""
    if not isinstance(value, str):
        return DEFAULT_PC_IMPACT
    key = value.strip().lower()
    aliases = {
        PROFILE_USABLE: PROFILE_USABLE,
        "bajo": PROFILE_USABLE,
        "low": PROFILE_USABLE,
        PROFILE_FULL: PROFILE_FULL,
        "max": PROFILE_FULL,
        "high": PROFILE_FULL,
    }
    return aliases.get(key, DEFAULT_PC_IMPACT)


def apply_factory_pc_impact(cfg: object) -> bool:
    """Migra configs del factory usable (011) a full, una sola vez.

    Devuelve True si mutó el objeto. Tras FACTORY_DEFAULT_REV, usable se
    respeta (el usuario lo eligió).
    """
    try:
        rev = int(getattr(cfg, "pc_impact_factory_rev", 1) or 1)
    except (TypeError, ValueError):
        rev = 1
    if rev >= FACTORY_DEFAULT_REV:
        return False
    cfg.transcription_pc_impact = PROFILE_FULL
    cfg.pc_impact_factory_rev = FACTORY_DEFAULT_REV
    return True


def get_pc_impact(profile_id: object) -> PcImpactProfile:
    return PROFILES[normalize_pc_impact(profile_id)]


def threads_for_impact(
    profile_id: object, *, cpu_count: Optional[int] = None
) -> int:
    n = cpu_count if cpu_count is not None else (os.cpu_count() or 4)
    n = max(1, int(n))
    if normalize_pc_impact(profile_id) == PROFILE_FULL:
        return max(1, n - 2)
    return max(1, min(4, n // 2))


def priority_class(profile_id: object) -> int:
    if normalize_pc_impact(profile_id) == PROFILE_FULL:
        return BELOW_NORMAL_PRIORITY
    return IDLE_PRIORITY


def thread_env(profile_id: object, *, cpu_count: Optional[int] = None) -> Dict[str, str]:
    n = str(threads_for_impact(profile_id, cpu_count=cpu_count))
    return {key: n for key in THREAD_ENV_KEYS}


def apply_priority_to_pid(pid: Optional[int], profile_id: object) -> bool:
    """Cambia la prioridad de un proceso vivo y sus hijos (Windows). No mata nada."""
    if not pid:
        return False
    try:
        import psutil
    except ImportError:
        return False
    if sys.platform == "win32":
        nice = (
            psutil.BELOW_NORMAL_PRIORITY_CLASS
            if normalize_pc_impact(profile_id) == PROFILE_FULL
            else psutil.IDLE_PRIORITY_CLASS
        )
    else:
        nice = 10 if normalize_pc_impact(profile_id) == PROFILE_USABLE else 5
    try:
        proc = psutil.Process(int(pid))
        targets = [proc] + proc.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False
    ok = False
    for child in targets:
        try:
            child.nice(nice)
            ok = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return ok

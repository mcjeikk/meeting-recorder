"""Presets de velocidad/calidad de transcripción (fuente única).

Mapean ids de UI/config a flags CLI del Transcriptor hermano.
Ver specs/002-transcription-speed-presets/contracts/cli-preset-mapping.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

PRESET_RAPIDO = "rapido"
PRESET_EQUILIBRADO = "equilibrado"
PRESET_MAXIMA = "maxima_calidad"

DEFAULT_PRESET = PRESET_EQUILIBRADO


@dataclass(frozen=True)
class TranscriptionPreset:
    id: str
    label_es: str
    model: str
    beam_size: int
    no_diarize: bool
    hint_es: str


PRESETS: Dict[str, TranscriptionPreset] = {
    PRESET_RAPIDO: TranscriptionPreset(
        id=PRESET_RAPIDO,
        label_es="Rápido",
        model="large-v3-turbo",
        # beam=5: beam=1 ahorra poco y fragmenta/alucina mucho el texto legible.
        # El ahorro real de Rápido es omitir la diarización (~½ del tiempo).
        beam_size=5,
        no_diarize=True,
        hint_es=(
            "Más rápido (sin diarización/hablantes); mismo reconocimiento que "
            "Equilibrado."
        ),
    ),
    PRESET_EQUILIBRADO: TranscriptionPreset(
        id=PRESET_EQUILIBRADO,
        label_es="Equilibrado",
        model="large-v3-turbo",
        beam_size=5,
        no_diarize=False,
        hint_es=(
            "Calidad habitual; con hablantes; en CPU suele tardar algo más que la "
            "duración del audio (medido ~1.1×; ~1.45× si dejas el PC usable)."
        ),
    ),
    PRESET_MAXIMA: TranscriptionPreset(
        id=PRESET_MAXIMA,
        label_es="Máxima calidad",
        model="large-v3",
        beam_size=5,
        no_diarize=False,
        hint_es=(
            "Más lento; modelo de reconocimiento más pesado; con hablantes."
        ),
    ),
}

# Orden estable para el combo de la UI.
PRESET_ORDER: Tuple[str, ...] = (PRESET_RAPIDO, PRESET_EQUILIBRADO, PRESET_MAXIMA)


def normalize_preset(value: object) -> str:
    """Unknown/empty → equilibrado (FR-012)."""
    if not isinstance(value, str):
        return DEFAULT_PRESET
    key = value.strip().lower()
    return key if key in PRESETS else DEFAULT_PRESET


def get_preset(preset_id: object) -> TranscriptionPreset:
    return PRESETS[normalize_preset(preset_id)]


def to_cli_args(preset_id: object) -> List[str]:
    """Argv extras para Transcriptor según el preset (sin --threads)."""
    p = get_preset(preset_id)
    args = ["--model", p.model, "--beam-size", str(p.beam_size)]
    if p.no_diarize:
        args.append("--no-diarize")
    return args


def cli_args_from_job_fields(
    *, model: str, beam_size: int, no_diarize: bool, num_speakers: int = 0
) -> List[str]:
    """Argv desde campos denormalizados del job (respeta no_diarize degradado)."""
    args = ["--model", model, "--beam-size", str(int(beam_size))]
    if no_diarize:
        args.append("--no-diarize")
    n = int(num_speakers or 0)
    if n > 0:
        args.extend(["--speakers", str(n)])
    return args

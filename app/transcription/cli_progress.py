"""Parseo del log plano del Transcriptor (qué archivo va y en qué %)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Tuple

from app.transcription.jobs import TranscriptionJob

_RE_ASR_PCT = re.compile(r"transcribiendo\.\.\. (\d+)%")
_RE_ASR_START = re.compile(r"- Transcribiendo \(modelo")
_RE_CONVERT = re.compile(r"Convirtiendo audio")
_RE_DIARIZE = re.compile(r"Identificando hablantes")
_RE_DEVICE = re.compile(r"-> dispositivo: (\w+)")
_RE_SPEAKERS_FOUND = re.compile(r"-> \d+ hablante")
_RE_PROCESANDO = re.compile(r"> Procesando:\s+(.+)")
_RE_ERROR = re.compile(r"\[X\] Error con .*?: (.+)")

# Fases del CLI. El valor manda; la etiqueta solo se muestra (spec 024): antes el
# worker decidía mirando la palabra "hablantes" DENTRO del texto en español.
PHASE_PREPARE = "prepare"
PHASE_ASR = "asr"
PHASE_SPEAKERS = "speakers"
PHASE_SAVING = "saving"

PHASE_LABELS = {
    PHASE_PREPARE: "Preparando audio…",
    PHASE_ASR: "Transcribiendo…",
    PHASE_SPEAKERS: "Identificando hablantes… (la fase más lenta)",
    PHASE_SAVING: "Guardando resultados…",
}

# Fases sin cifra del CLI: manda la estimación por tiempo (spec 021), nunca el
# % anterior. La diarización no imprime nada durante horas.
PHASES_WITHOUT_ASR_PERCENT = frozenset({PHASE_SPEAKERS, PHASE_SAVING})

ParseResult = Tuple[
    Optional[str], Optional[int], Optional[str], Optional[str], Optional[str]
]


def label_for_phase(phase: Optional[str]) -> Optional[str]:
    """Texto visible de una fase (único sitio donde vive el idioma)."""
    return PHASE_LABELS.get(phase or "")


def parse_plain_chunk(texto: str) -> ParseResult:
    """Último estado en un trozo de log: (stage, pct, cli_name, nota, phase).

    pct es None si no hay cifra nueva; 0 al cambiar de archivo (el % anterior
    era de otro WAV); -1 = indeterminado (fases sin cifra del CLI). Una línea
    que no reconocemos no cambia nada: el aviso se queda como estaba.

    El CLI anuncia cada fase ANTES de hacerla, salvo `-> dispositivo:`, que
    imprime DESPUÉS de terminar la transcripción: por eso marca el paso a
    "Guardando resultados…" y no una transcripción en curso.
    """
    phase = pct = cli_name = nota = None
    for linea in texto.splitlines():
        m = _RE_PROCESANDO.search(linea)
        if m:
            cli_name = m.group(1).strip()
            phase, pct = PHASE_ASR, 0
            continue
        if _RE_CONVERT.search(linea):
            phase = PHASE_PREPARE
        # "Audio ya en WAV 16 kHz" NO es una fase: es una acción que se omitió.
        if _RE_ASR_START.search(linea):
            phase = PHASE_ASR
        m = _RE_ASR_PCT.search(linea)
        if m:
            phase, pct = PHASE_ASR, int(m.group(1))
        if _RE_DEVICE.search(linea):
            phase, pct = PHASE_SAVING, -1
        if _RE_DIARIZE.search(linea):
            phase, pct = PHASE_SPEAKERS, -1
        if _RE_SPEAKERS_FOUND.search(linea):
            phase, pct = PHASE_SAVING, -1
        if "La diarizacion no se completo" in linea or "Diarizacion solicitada pero no hay" in linea:
            phase, pct, nota = PHASE_SAVING, -1, "sin hablantes"
    return label_for_phase(phase), pct, cli_name, nota, phase


def cli_name_for_job(job: TranscriptionJob) -> str:
    """Nombre con el que el CLI imprime este job (`stem.wav`)."""
    if getattr(job, "work_wav", ""):
        return Path(job.work_wav).name
    media = getattr(job, "media_path", "")
    return (Path(media).stem + ".wav") if media else ""


def log_section_for(texto: str, cli_name: str) -> str:
    """Trozo del log que pertenece SOLO a este archivo.

    En un lote todos los archivos comparten un log: sin recortar, el error (o
    el fallo de diarización) de uno contamina la decisión de reintento de los
    demás. Cadena vacía = ese archivo nunca llegó a empezar.
    """
    if not texto or not cli_name:
        return ""
    name = Path(cli_name).name
    inicio = None
    for m in _RE_PROCESANDO.finditer(texto):
        actual = Path(m.group(1).strip().strip('"')).name
        if inicio is not None:
            return texto[inicio : m.start()]
        if actual == name:
            inicio = m.end()
    return texto[inicio:] if inicio is not None else ""


def error_in_section(seccion: str) -> str:
    """Último `[X] Error con …` del trozo (cadena vacía si no hubo)."""
    ultimo = None
    for ultimo in _RE_ERROR.finditer(seccion or ""):
        pass
    return ultimo.group(1).strip()[:300] if ultimo else ""


def section_ended_in_diarization(seccion: str) -> bool:
    """El archivo murió en la diarización (fase más lenta): reintentar sin ella."""
    if not seccion:
        return False
    ultimo = seccion.rfind("Identificando hablantes")
    return ultimo != -1 and "OK en" not in seccion[ultimo:]


def job_matches_cli_name(job: TranscriptionJob, cli_name: str) -> bool:
    """El CLI imprime el nombre del WAV de trabajo (`stem.wav`)."""
    if not cli_name:
        return False
    name = Path(cli_name.strip().strip('"')).name
    stem = Path(name).stem
    candidates = []
    if getattr(job, "work_wav", ""):
        candidates.append(Path(job.work_wav))
    if getattr(job, "media_path", ""):
        candidates.append(Path(job.media_path))
    for path in candidates:
        if path.name == name or path.stem == stem:
            return True
    return False


def job_for_cli_name(
    jobs: Iterable[TranscriptionJob], cli_name: str
) -> Optional[TranscriptionJob]:
    for job in jobs:
        if job_matches_cli_name(job, cli_name):
            return job
    return None

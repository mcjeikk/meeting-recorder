"""Importar audio/vídeo existente a la cola de transcripción (sin Qt).

El archivo original no se copia ni se mueve: el job apunta a la ruta absoluta
del origen. El worker extrae WAV de trabajo a LOCALAPPDATA (como las reuniones).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from app.transcription.integration import result_dir_for, transcript_exists
from app.transcription.jobs import (
    DONE,
    EXTRACTING,
    PENDING,
    RUNNING,
    JobStore,
)

# Mismo conjunto que Transcriptor pipeline/audio.py AUDIO_EXTS.
SUPPORTED_MEDIA_EXTS = frozenset(
    {
        ".m4a",
        ".mp3",
        ".wav",
        ".flac",
        ".ogg",
        ".opus",
        ".aac",
        ".wma",
        ".mp4",
        ".m4b",
        ".mkv",
        ".webm",
        ".mov",
        ".avi",
    }
)

OK = "ok"
UNSUPPORTED = "unsupported"
FOLDER = "folder"
MISSING_FILE = "missing_file"
MISSING_TOOL = "missing_tool"
ALREADY_ACTIVE = "already_active"
ALREADY_DONE = "already_done"

_ACTIVE = frozenset({PENDING, EXTRACTING, RUNNING})

EnqueueFn = Callable[[str, str, Optional[str]], Optional[dict]]


@dataclass
class ImportResult:
    path: str
    kind: str
    name: str = ""
    job: Optional[dict] = None
    result_dir: str = ""
    message: str = ""


def is_supported_media(path: Path | str) -> bool:
    return Path(path).suffix.casefold() in SUPPORTED_MEDIA_EXTS


def file_dialog_filter() -> str:
    exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_MEDIA_EXTS))
    return f"Audio y vídeo ({exts});;Todos los archivos (*.*)"


def canonical_media_path(path: str | Path) -> str:
    """Ruta absoluta normalizada para dedupe y para el job."""
    return str(Path(path).expanduser().resolve())


def classify_import(
    store: JobStore,
    path: str,
    *,
    tool_available: bool,
    output_base: str = "",
) -> ImportResult:
    raw = Path(path)
    name = raw.name or str(raw)
    if raw.exists() and raw.is_dir():
        return ImportResult(
            path=str(raw),
            kind=FOLDER,
            name=name,
            message="Las carpetas no se transcriben; elige archivos de audio o vídeo.",
        )
    if not tool_available:
        return ImportResult(
            path=str(raw),
            kind=MISSING_TOOL,
            name=name,
            message="No se encontró el proyecto Transcriptor.",
        )
    if not raw.is_file():
        return ImportResult(
            path=str(raw),
            kind=MISSING_FILE,
            name=name,
            message=f"No se encontró el archivo: {name}",
        )
    if not is_supported_media(raw):
        return ImportResult(
            path=str(raw),
            kind=UNSUPPORTED,
            name=name,
            message=f"Tipo no admitido: {name}",
        )

    canonical = canonical_media_path(raw)
    existente = store.find_by_media(canonical)
    if existente is None and canonical != str(raw):
        existente = store.find_by_media(str(raw))
    if existente is not None:
        if existente.status in _ACTIVE:
            return ImportResult(
                path=canonical,
                kind=ALREADY_ACTIVE,
                name=name,
                job=existente.snapshot(),
                message=f"Ya está en cola: {name}",
            )
        if existente.status == DONE:
            result = existente.result_dir or str(
                result_dir_for(
                    Path(existente.media_path),
                    output_base=getattr(existente, "output_base", "") or None,
                )
            )
            return ImportResult(
                path=canonical,
                kind=ALREADY_DONE,
                name=name,
                job=existente.snapshot(),
                result_dir=result,
                message=f"Ya hay una transcripción de {name}",
            )

    # Sin registro: lo recuerda el disco (el histórico se poda, spec 023).
    if transcript_exists(canonical, output_base or None):
        return ImportResult(
            path=canonical,
            kind=ALREADY_DONE,
            name=name,
            result_dir=str(result_dir_for(Path(canonical), output_base=output_base or None)),
            message=f"Ya hay una transcripción de {name}",
        )

    return ImportResult(path=canonical, kind=OK, name=name)


def enqueue_imports(
    paths: Iterable[str],
    *,
    store: JobStore,
    enqueue: EnqueueFn,
    language: str,
    preset: str,
    tool_available: bool,
    output_base: str = "",
) -> List[ImportResult]:
    """Clasifica cada path y encola los válidos. Nunca copia ni mueve el original.

    `output_base` es la Carpeta de salida configurada: con ella se resuelve el
    mismo destino que usaría el job, para saber si ya hay transcripción en disco.
    """
    results: List[ImportResult] = []
    for raw in paths:
        item = classify_import(
            store, raw, tool_available=tool_available, output_base=output_base
        )
        if item.kind != OK:
            results.append(item)
            continue
        snap = enqueue(item.path, language, preset)
        if snap is None:
            # Carrera o dedupe del store: re-clasificar.
            again = classify_import(
                store, item.path, tool_available=tool_available, output_base=output_base
            )
            if again.kind == OK:
                again.kind = ALREADY_ACTIVE
                again.message = f"Ya está en cola: {item.name}"
            results.append(again)
            continue
        item.job = snap
        results.append(item)
    return results


def summarize_import_results(results: Sequence[ImportResult]) -> str:
    if not results:
        return ""
    n_ok = sum(1 for r in results if r.kind == OK)
    n_done = sum(1 for r in results if r.kind == ALREADY_DONE)
    n_active = sum(1 for r in results if r.kind == ALREADY_ACTIVE)
    n_bad = len(results) - n_ok - n_done - n_active
    parts: List[str] = []
    if n_ok:
        parts.append("1 archivo en cola" if n_ok == 1 else f"{n_ok} archivos en cola")
    if n_done:
        parts.append(
            "ya había transcripción" if n_done == 1 else f"{n_done} ya transcritos"
        )
    if n_active:
        parts.append("ya en cola" if n_active == 1 else f"{n_active} ya en cola")
    if n_bad:
        first_bad = next(r for r in results if r.kind not in {OK, ALREADY_DONE, ALREADY_ACTIVE})
        if n_bad == 1 and first_bad.message:
            parts.append(first_bad.message)
        else:
            parts.append(f"{n_bad} no admitidos")
    return " · ".join(parts)

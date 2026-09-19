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
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.transcription.integration import transcripts_base
from app.transcription.pc_impact import (
    DEFAULT_PC_IMPACT,
    LEGACY_JOB_PC_IMPACT,
    normalize_pc_impact,
)
from app.transcription.presets import DEFAULT_PRESET, get_preset, normalize_preset

# Estados de un trabajo. "running" con PID muerto se resuelve en la
# reconciliación del worker (done si hay resultado, pending si no).
PENDING = "pending"
EXTRACTING = "extracting"
RUNNING = "running"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"

_ACTIVE = {PENDING, EXTRACTING, RUNNING}
_CLEARABLE = {ERROR, CANCELLED}

# Un registro puede estar bloqueado un instante por el antivirus o el indexador:
# se reintenta ~0.5 s antes de rendirse. La contención entre nuestros propios
# hilos NO se resuelve reintentando, sino con `_io_lock` (ver JobStore.save).
_SAVE_RETRIES = 5
_SAVE_BACKOFF = 0.05

DEFAULT_LANGUAGE = "es"
_ALLOWED_LANGUAGES = frozenset({"es", "en", "auto"})

# Defaults = Equilibrado (jobs antiguos sin campos de preset).
_EQ = get_preset(DEFAULT_PRESET)


def _canonical_media_path(path: str) -> str:
    """Ruta absoluta para el job y para --output (evita relativo → Transcriptor RAIZ)."""
    try:
        return str(Path(path).expanduser().resolve())
    except OSError:
        p = Path(path).expanduser()
        return str(p if p.is_absolute() else Path.cwd() / p)


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def normalize_num_speakers(value: object) -> int:
    """0 = auto; 1–12 exactos; el resto → auto."""
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return n if 1 <= n <= 12 else 0


def normalize_language(value: object) -> str:
    """es|en|auto; desconocido → es (default del producto)."""
    if value is None:
        return DEFAULT_LANGUAGE
    code = str(value).strip().casefold()
    return code if code in _ALLOWED_LANGUAGES else DEFAULT_LANGUAGE


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
    preset: str = DEFAULT_PRESET
    model: str = _EQ.model
    beam_size: int = _EQ.beam_size
    no_diarize: bool = False  # preset Rápido o reintento degradado tras fallo de diarización
    pc_impact: str = DEFAULT_PC_IMPACT  # usable|full; snapshot al encolar
    output_base: str = ""  # Carpeta de salida al encolar; vacío = padre del media (legacy)
    num_speakers: int = 0  # 0 = auto; 1–12 = --speakers N
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
        # En Windows, un lector abierto impide reemplazar el archivo: leer y
        # escribir registros desde el hilo de Qt y el del worker a la vez se
        # estorba de verdad, y reintentar solo lo hace improbable. Serializar
        # nuestra propia E/S lo vuelve imposible (spec 027).
        self._io_lock = threading.RLock()

    # --- persistencia ---------------------------------------------------------
    def _path(self, job_id: str) -> Path:
        return self.queue_dir / f"{job_id}.json"

    def save(self, job: TranscriptionJob) -> None:
        """Escritura atómica del registro, tolerante a bloqueos momentáneos.

        Tres capas, porque el fallo real (visto en el rastro: `PermissionError`
        al reemplazar, y el job marcado como fallido) tenía dos causas:

        1. `_io_lock`: nuestros hilos no se pisan entre ellos.
        2. temporal con pid+hilo: si aun así coincidieran (otro proceso), cada
           escritor tiene el suyo.
        3. reintento corto: para el antivirus o el indexador, que son de fuera.
        """
        path = self._path(job.id)
        tmp = path.with_name(f"{path.stem}.{os.getpid()}.{threading.get_ident()}.tmp")
        datos = json.dumps(asdict(job), indent=2, ensure_ascii=False)
        with self._io_lock:
            try:
                for intento in range(_SAVE_RETRIES):
                    try:
                        tmp.write_text(datos, encoding="utf-8")
                        os.replace(tmp, path)
                        return
                    except OSError:
                        if intento == _SAVE_RETRIES - 1:
                            raise
                        time.sleep(_SAVE_BACKOFF * (intento + 1))
            finally:
                try:
                    tmp.unlink()  # si algo falló, no dejar basura en la cola
                except OSError:
                    pass

    def _load(self, path: Path) -> Optional[TranscriptionJob]:
        try:
            data = json.loads(self._read(path))
            campos = {k: v for k, v in data.items() if k in TranscriptionJob.__annotations__}
            job = TranscriptionJob(**campos)
            # Jobs antiguos sin preset → equilibrado (defaults del dataclass).
            job.preset = normalize_preset(getattr(job, "preset", DEFAULT_PRESET))
            if "pc_impact" not in data:
                job.pc_impact = LEGACY_JOB_PC_IMPACT
            else:
                job.pc_impact = normalize_pc_impact(job.pc_impact)
            job.num_speakers = normalize_num_speakers(getattr(job, "num_speakers", 0))
            if "model" not in data or "beam_size" not in data:
                p = get_preset(job.preset)
                if "model" not in data:
                    job.model = p.model
                if "beam_size" not in data:
                    job.beam_size = p.beam_size
                if "no_diarize" not in data:
                    job.no_diarize = p.no_diarize
            return job
        except Exception:
            return None  # JSON corrupto/parcial: se ignora, nunca rompe la cola

    def _read(self, path: Path) -> str:
        """Lee el registro sin cruzarse con una escritura, y reintenta si acaso.

        Un lector abierto impide reemplazar el archivo, así que leer va bajo el
        mismo lock que escribir. Sin esto, `_load` devolvía None y el job parecía
        no existir — que es como se cuela un duplicado en la cola (spec 027).
        "No existe" no se reintenta: eso es una respuesta, no un tropiezo.
        """
        with self._io_lock:
            for intento in range(_SAVE_RETRIES):
                try:
                    return path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    raise
                except OSError:
                    if intento == _SAVE_RETRIES - 1:
                        raise
                    time.sleep(_SAVE_BACKOFF * (intento + 1))
        return ""  # inalcanzable: el último intento levanta

    def all(self) -> List[TranscriptionJob]:
        jobs = [self._load(p) for p in sorted(self.queue_dir.glob("*.json"))]
        return sorted((j for j in jobs if j), key=lambda j: j.created_at)

    # --- operaciones ----------------------------------------------------------
    def enqueue(
        self,
        media_path: str,
        language: str = "es",
        preset: Optional[str] = None,
        pc_impact: Optional[str] = None,
        output_base: Optional[str] = None,
        num_speakers: Optional[int] = None,
    ) -> Optional[TranscriptionJob]:
        """Crea un job pendiente. Devuelve None si ya hay uno activo o terminado
        para el mismo archivo (dedupe: re-encolar no debe duplicar horas de CPU).

        `preset`, `pc_impact` y `output_base` se capturan al encolar; cambios
        posteriores en la UI no mutan este job. `output_base` vacío = destino
        junto al media (jobs antiguos).
        """
        media_path = _canonical_media_path(media_path)
        existente = self.find_by_media(media_path)
        if existente and (existente.status in _ACTIVE or existente.status == DONE):
            return None
        preset_id = normalize_preset(preset)
        p = get_preset(preset_id)
        dest = ""
        if output_base is not None and str(output_base).strip():
            dest = _canonical_media_path(str(output_base).strip())
        job = TranscriptionJob(
            media_path=media_path,
            language=normalize_language(language),
            preset=preset_id,
            model=p.model,
            beam_size=p.beam_size,
            no_diarize=p.no_diarize,
            pc_impact=normalize_pc_impact(
                pc_impact if pc_impact is not None else DEFAULT_PC_IMPACT
            ),
            output_base=dest,
            num_speakers=normalize_num_speakers(num_speakers),
        )
        job.log_path = str(self.logs_dir / f"{Path(media_path).stem}_{job.id}.log")
        self.save(job)
        return job

    def find_by_media(self, media_path: str) -> Optional[TranscriptionJob]:
        objetivo = os.path.normcase(_canonical_media_path(media_path))
        for job in self.all():
            if os.path.normcase(_canonical_media_path(job.media_path)) == objetivo:
                return job
        return None

    def set_pc_impact_on_open(self, pc_impact: object) -> int:
        """Reasigna Uso del PC a jobs pending/extracting/running. No toca done."""
        impact = normalize_pc_impact(pc_impact)
        n = 0
        for job in self.active():
            if job.pc_impact == impact:
                continue
            job.pc_impact = impact
            self.save(job)
            n += 1
        return n

    def pending(self) -> List[TranscriptionJob]:
        return [j for j in self.all() if j.status == PENDING]

    def active(self) -> List[TranscriptionJob]:
        return [j for j in self.all() if j.status in _ACTIVE]

    def retry(self, job_id: str) -> Optional[TranscriptionJob]:
        """Re-encola un job en error (botón Reintentar de la UI)."""
        from app.transcription.process_guard import apply_oom_degrade, log_looks_like_oom

        job = self._load(self._path(job_id))
        if not job or job.status != ERROR:
            return None
        if log_looks_like_oom(job.error):
            apply_oom_degrade(job)
        job.status = PENDING
        job.error = ""
        job.pid = None
        self.save(job)
        return job

    def queue_counts(self, live_id: str = "") -> dict:
        """Resumen para el banner: en curso / espera / fallidas (no incluye done).

        En un lote CLI, varios JSON pueden estar `running` a la vez; solo
        `live_id` cuenta como en curso, el resto del lote como en espera.
        """
        n_run = n_pend = n_fail = 0
        live = str(live_id or "")
        for job in self.all():
            if job.status in (EXTRACTING, RUNNING):
                if live and job.status == RUNNING and job.id != live:
                    n_pend += 1
                else:
                    n_run += 1
            elif job.status == PENDING:
                n_pend += 1
            elif job.status in _CLEARABLE:
                n_fail += 1
        return {"running": n_run, "pending": n_pend, "failed": n_fail}

    def cancel(self, job_id: str) -> Optional[TranscriptionJob]:
        """Marca pending/extracting/running como cancelled. No toca done/error."""
        job = self._load(self._path(job_id))
        if not job or job.status not in _ACTIVE:
            return None
        job.status = CANCELLED
        job.error = "Cancelado por el usuario"
        job.finished_at = _now()
        job.pid = None
        self.save(job)
        return job

    def clear_failed(self) -> int:
        """Borra jobs en error o cancelled. Devuelve cuántos eliminó."""
        n = 0
        for job in self.all():
            if job.status not in _CLEARABLE:
                continue
            path = self._path(job.id)
            try:
                path.unlink(missing_ok=True)
                n += 1
            except OSError:
                pass
        return n

    def count_clearable(self) -> int:
        return sum(1 for j in self.all() if j.status in _CLEARABLE)

    def prune_history(self, *, now: Optional[datetime] = None) -> dict:
        """Poda el histórico: terminados viejos o de más, y sus logs (spec 023).

        Silenciosa y tolerante a fallos: un unlink que falla se salta y se
        reintenta en el próximo arranque (una limpieza que revienta es una
        limpieza que deja de correr). No modifica ningún registro.
        """
        from app.transcription.retention import (
            MAX_DELETIONS_PER_PASS,
            oldest_first,
            prunable_job_ids,
            prunable_log_paths,
        )

        jobs = self.all()
        sobran = prunable_job_ids(jobs, now=now or datetime.now())
        # Presupuesto por pasada: el resto se va en los próximos arranques.
        esta_vez = set(oldest_first(jobs, sobran))
        n_jobs = 0
        for job_id in esta_vez:
            try:
                self._path(job_id).unlink(missing_ok=True)
                n_jobs += 1
            except OSError:
                pass
        vivos = [j for j in jobs if j.id not in esta_vez]
        n_logs = 0
        for log in prunable_log_paths(self.logs_dir, vivos)[:MAX_DELETIONS_PER_PASS]:
            try:
                log.unlink()
                n_logs += 1
            except OSError:
                pass
        return {"records": n_jobs, "logs": n_logs}

    def purge_orphan_work_dirs(self) -> int:
        """Borra WAV de trabajo de jobs ya terminados o inexistentes.

        `_cleanup_wav` puede fallar en silencio (el CLI aún cerrando el handle,
        antivirus) y nadie volvía a pasar: son WAV de 16 kHz de reuniones
        completas, cientos de MB. Devuelve los bytes liberados.
        """
        vivos = {j.id for j in self.all() if j.status in _ACTIVE}
        liberados = 0
        for carpeta in self.work_dir.glob("*"):
            if not carpeta.is_dir() or carpeta.name in vivos:
                continue
            for f in carpeta.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    size = f.stat().st_size
                    f.unlink()
                    liberados += size
                except OSError:
                    pass
            try:
                carpeta.rmdir()
            except OSError:
                pass
        return liberados

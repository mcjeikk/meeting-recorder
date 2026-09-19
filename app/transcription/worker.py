"""Worker de transcripción: procesa la cola en segundo plano, de a un trabajo.

Principios de diseño (ver también integration.py y jobs.py):
- La grabación SIEMPRE tiene prioridad: no se arranca ningún trabajo mientras
  se graba y, si una grabación empieza a mitad de una transcripción, el proceso
  se SUSPENDE por completo (cero CPU; el avance no se pierde) y se reanuda al
  terminar. Además el subproceso corre con prioridad baja e hilos limitados.
- El subproceso es independiente del ciclo de vida de la app: su salida va
  directa a un archivo de log (no a un pipe), así que cerrar el Recorder no lo
  interrumpe. Al reabrir, la reconciliación lo re-adopta por PID o recoge su
  resultado.
- El éxito se decide por transcripcion.txt (en un CLI con varios WAV el exit
  code es global). El parseo del log alimenta el % y qué archivo va ahora
  (`> Procesando:`). La diarización se valida leyendo "hablantes" del JSON
  (el CLI degrada en silencio con exit 0 si falta el token de HuggingFace).
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

import psutil

from app.core.config import AppConfig
from app.transcription import jobs as J
from app.transcription.integration import (
    build_command,
    cpu_threads_for_job,
    creationflags_for_job,
    extract_audio_for_transcription,
    is_available,
    output_dir_for,
    result_dir_for,
    subprocess_env,
)
from app.transcription.pc_impact import (
    DEFAULT_PC_IMPACT,
    apply_priority_to_pid,
    normalize_pc_impact,
)
from app.transcription.batch import compatible_batch
from app.transcription.event_log import EventLog
from app.transcription.cli_progress import (
    PHASE_ASR,
    PHASES_WITHOUT_ASR_PERCENT,
    cli_name_for_job,
    error_in_section,
    job_for_cli_name,
    label_for_phase,
    log_section_for,
    parse_plain_chunk,
    section_ended_in_diarization,
)
from app.transcription.eta import (
    ProgressTracker,
    SpeedStore,
    estimate_total_seconds,
    key_for_job,
    wav_duration_seconds,
)
from app.transcription.process_guard import (
    adopt_transcribe_process,
    apply_oom_degrade,
    log_looks_like_oom,
)
from app.transcription.jobs import JobStore, TranscriptionJob
from app.transcription.presets import cli_args_from_job_fields, get_preset

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def _keep_awake(active: bool) -> None:
    """Evita que el equipo se suspenda con un trabajo de horas en marcha.

    Es por-hilo: debe llamarse desde el hilo del worker (que vive toda la sesión).
    """
    if sys.platform != "win32":
        return
    flags = _ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED if active else 0)
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def _is_transcription_pid(pid: int) -> Optional[psutil.Process]:
    """El proceso `pid` ¿es realmente una transcripción nuestra? (los PID se reciclan)."""
    try:
        proc = psutil.Process(pid)
        if any("transcribe.py" in parte for parte in proc.cmdline()):
            return proc
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return None


class TranscriptionWorker:
    """Hilo de fondo que drena la cola de transcripciones, una a la vez.

    on_update recibe un dict (snapshot del job + "stage"/"progress") desde el
    hilo del worker: la UI debe pasarle el .emit de una señal Qt.
    """

    POLL_SECONDS = 1.0
    IDLE_SECONDS = 2.0
    # La barra debe moverse aunque el log calle (diarización: horas sin líneas).
    PROGRESS_EMIT_SECONDS = 15.0

    def __init__(
        self,
        store: JobStore,
        get_config: Callable[[], AppConfig],
        on_update: Callable[[dict], None],
        is_recording: Callable[[], bool],
    ) -> None:
        self._store = store
        self._get_config = get_config
        self._on_update = on_update
        self._is_recording = is_recording
        self._wake = threading.Event()
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        self._lock_handle = None
        self._current: Optional[TranscriptionJob] = None
        # Junto a la cola: una cola de prueba (tests, verify) no toca el
        # historial real de la máquina.
        self._speed = SpeedStore(store.base / "speed.json")
        # Rastro para revisar una cola desatendida (spec 026). Diagnóstico puro:
        # nadie lo lee para decidir nada y sus fallos son invisibles.
        self._events = EventLog(store.base / "events.jsonl")
        # Tiempo ACTIVO por job (no de pared): alimenta el historial de velocidad.
        self._active_seconds: dict[str, float] = {}

    # --- API pública (hilo de Qt) -------------------------------------------------
    def start(self) -> None:
        if not self._acquire_lock():
            # Otra instancia del Recorder ya procesa la cola: esta queda pasiva
            # (encolar sigue funcionando; el otro proceso hará el trabajo).
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="transcription-worker")
        self._thread.start()

    def enqueue(
        self,
        media_path: str,
        language: str,
        preset: Optional[str] = None,
        pc_impact: Optional[str] = None,
        output_base: Optional[str] = None,
        num_speakers: Optional[int] = None,
    ) -> Optional[dict]:
        job = self._store.enqueue(
            media_path,
            language,
            preset=preset,
            pc_impact=pc_impact,
            output_base=output_base,
            num_speakers=num_speakers,
        )
        if job:
            label = get_preset(job.preset).label_es
            self._emit(job, stage=f"En cola ({label})")
            self._wake.set()
            return job.snapshot()
        return None

    def retry(self, job_id: str) -> None:
        job = self._store.retry(job_id)
        if job:
            label = get_preset(job.preset).label_es
            self._emit(job, stage=f"En cola (reintento · {label})")
            self._wake.set()

    def cancel(self, job_id: str) -> bool:
        """Cancela un job activo/pendiente y mata el CLI hijo si esta instancia lo posee."""
        target = self._store._load(self._store._path(job_id))
        current = self._current
        pid = None
        if current and target and current.id == job_id:
            pid = current.pid
        job = self._store.cancel(job_id)
        if not job:
            return False
        if pid:
            self._terminate_pid(pid)
            for other in self._store.all():
                if other.id == job_id:
                    continue
                if other.pid != pid:
                    continue
                if other.status not in (J.RUNNING, J.PENDING, J.EXTRACTING):
                    continue
                other.status = J.PENDING
                other.pid = None
                other.error = ""
                self._store.save(other)
                self._emit(other, stage="En cola")
        self._emit(job, stage="Cancelada")
        self._wake.set()
        return True

    def clear_failed(self) -> int:
        return self._store.clear_failed()

    def apply_pc_impact(self, pc_impact: object) -> int:
        """Retarget cola/en curso y sube/baja prioridad del proceso vivo."""
        impact = normalize_pc_impact(pc_impact)
        n = self._store.set_pc_impact_on_open(impact)
        current = self._current
        if current:
            current.pc_impact = impact
            apply_priority_to_pid(current.pid, impact)
        return n

    def has_active_job(self) -> bool:
        return self._current is not None

    def shutdown(self, wait: float = 0.0) -> None:
        """No mata el subproceso (es independiente); solo detiene el hilo.

        Con `wait` espera a que el hilo salga y suelta el lock de instancia (solo
        si salió de verdad): así una cola temporal —verify_transcription— puede
        borrar su carpeta al terminar. Sin `wait`, el SO libera el lock al morir.
        """
        self._stop = True
        self._wake.set()
        hilo = self._thread
        if wait > 0 and hilo is not None:
            hilo.join(wait)
            if not hilo.is_alive():
                self._release_lock()

    def _release_lock(self) -> None:
        if self._lock_handle is None:
            return
        try:
            self._lock_handle.close()
        except OSError:
            pass
        self._lock_handle = None

    @staticmethod
    def _terminate_pid(pid: int) -> None:
        try:
            proc = psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # --- bucle principal (hilo propio) ---------------------------------------------
    def _run(self) -> None:
        try:
            self._reconcile()
            while not self._stop:
                job = self._next_job()
                if job is None or self._is_recording():
                    _keep_awake(False)
                    self._wake.wait(timeout=self.IDLE_SECONDS)
                    self._wake.clear()
                    continue
                self._current = job
                try:
                    self._execute(job)
                except Exception as e:  # noqa: BLE001 — el worker no debe morir jamás
                    self._fail(job, f"{type(e).__name__}: {e}")
                finally:
                    self._current = None
        finally:
            _keep_awake(False)

    def _next_job(self) -> Optional[TranscriptionJob]:
        pendientes = self._store.pending()
        return pendientes[0] if pendientes else None

    # --- ejecución de un trabajo ----------------------------------------------------
    def _execute(self, job: TranscriptionJob) -> None:
        if self._job_cancelled(job.id):
            return
        cfg = self._get_config()
        if not is_available(cfg.transcriptor_dir):
            self._fail(job, "No se encontró el proyecto Transcriptor (revisa transcriptor_dir)", retry=False)
            return

        group = compatible_batch(job, self._store.pending())
        ready: list[TranscriptionJob] = []
        pistas: list[str] = []
        wavs: list[Path] = []

        for idx, item in enumerate(group):
            if self._job_cancelled(item.id):
                continue
            media = Path(item.media_path)
            if not media.exists():
                self._fail(item, "El archivo ya no existe", retry=False)
                continue
            item.status = J.EXTRACTING
            item.started_at = item.started_at or J._now()
            self._store.save(item)
            self._emit(item, stage="Preparando audio…")
            try:
                wav, pista = extract_audio_for_transcription(
                    media, self._store.work_dir / item.id
                )
            except Exception as e:  # noqa: BLE001
                self._fail(item, f"No se pudo extraer el audio: {e}", retry=False)
                continue
            item.work_wav = str(wav)
            self._store.save(item)
            if idx == 0:
                existing = adopt_transcribe_process(wav)
                if existing is not None:
                    item.status = J.RUNNING
                    item.pid = existing.pid
                    self._store.save(item)
                    self._events.append(
                        "adopted",
                        pid=existing.pid,
                        file=Path(item.media_path).stem,
                        log=item.log_path,
                    )
                    self._emit(item, stage="Retomando transcripción en curso…", progress=0)
                    rc = self._monitor(
                        item, existing, owned=None, cohort=self._cohort(item)
                    )
                    for other in self._cohort(item):
                        self._settle(self._reload(other), rc if other.id == item.id else None)
                    return
            if self._job_cancelled(item.id):
                self._cleanup_wav(item)
                continue
            ready.append(item)
            pistas.append(pista)
            wavs.append(Path(wav))

        if not ready:
            return

        lead = ready[0]
        fresh = self._store._load(self._store._path(lead.id))
        if fresh is not None:
            lead.pc_impact = fresh.pc_impact
        impact = normalize_pc_impact(getattr(lead, "pc_impact", DEFAULT_PC_IMPACT))
        extra = ["--threads", str(cpu_threads_for_job(impact))]
        extra.extend(
            cli_args_from_job_fields(
                model=lead.model,
                beam_size=lead.beam_size,
                no_diarize=bool(lead.no_diarize),
                num_speakers=int(getattr(lead, "num_speakers", 0) or 0),
            )
        )
        cmd = build_command(
            cfg.transcriptor_dir,
            wavs,
            lead.language,
            output_dir_for(
                Path(lead.media_path),
                output_base=getattr(lead, "output_base", "") or None,
            ),
            tuple(extra),
        )

        log = open(lead.log_path, "ab")
        try:
            log.write(
                f"--- intento {lead.attempts + 1} · {len(ready)} archivo(s) · {pistas[0]} ---\n".encode(
                    "utf-8"
                )
            )
            log.flush()
            proc = subprocess.Popen(
                cmd,
                cwd=cfg.transcriptor_dir,
                env=subprocess_env(impact),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=creationflags_for_job(impact),
            )
        finally:
            log.close()

        if self._job_cancelled(lead.id):
            self._terminate_pid(proc.pid)
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            for item in ready:
                self._cleanup_wav(item)
            return

        for item in ready:
            item.pid = proc.pid
            item.log_path = lead.log_path
            item.status = J.RUNNING if item.id == lead.id else J.PENDING
            self._store.save(item)
        self._current = lead
        self._events.append(
            "run_start",
            pid=proc.pid,
            files=[Path(i.media_path).stem for i in ready],
            track=pistas[0],
            model=lead.model,
            beam=lead.beam_size,
            no_diarize=bool(lead.no_diarize),
            num_speakers=int(getattr(lead, "num_speakers", 0) or 0),
            pc_impact=impact,
            attempt=lead.attempts + 1,
            log=lead.log_path,
        )
        self._emit(lead, stage="Transcribiendo…", progress=0)

        rc = self._monitor(
            lead, psutil.Process(proc.pid), owned=proc, cohort=list(ready)
        )
        for item in ready:
            self._settle(self._reload(item), rc if len(ready) == 1 else None)

    def _job_cancelled(self, job_id: str) -> bool:
        path = self._store._path(job_id)
        job = self._store._load(path)
        return bool(job and job.status == J.CANCELLED)

    def _reload(self, job: TranscriptionJob) -> TranscriptionJob:
        return self._store._load(self._store._path(job.id)) or job

    def _cohort(self, seed: TranscriptionJob) -> list[TranscriptionJob]:
        """Miembros vivos del lote que comparte este proceso, en orden de cola.

        Solo estados abiertos: los jobs terminados conservan su `pid` en la cola
        histórica y los PID se reciclan (la máquina auditada tenía 10 `done` con
        el mismo pid), así que incluirlos inflaría el "archivo N de M".
        """
        abiertos = [
            j
            for j in self._store.all()
            if j.status in (J.PENDING, J.EXTRACTING, J.RUNNING)
        ]
        if seed.pid:
            same = [j for j in abiertos if j.pid == seed.pid]
            if same:
                same.sort(key=lambda j: (j.created_at, j.id))
                return same
        return [j for j in abiertos if j.id == seed.id] or [seed]

    def _output_ready(self, job: TranscriptionJob) -> bool:
        txt = result_dir_for(
            Path(job.media_path),
            output_base=getattr(job, "output_base", "") or None,
        ) / "transcripcion.txt"
        return txt.exists()

    def _harvest_ready(self, cohort: list[TranscriptionJob]) -> None:
        """Marca DONE en cuanto existe transcripcion.txt, sin esperar al exit del lote."""
        for item in cohort:
            fresh = self._reload(item)
            if fresh.status in (J.DONE, J.CANCELLED, J.ERROR):
                continue
            if self._output_ready(fresh):
                self._events.append("harvest", file=Path(fresh.media_path).stem)
                self._settle(fresh, None)

    def _activate_live(
        self, live: TranscriptionJob, previous: Optional[TranscriptionJob] = None
    ) -> Optional[TranscriptionJob]:
        """Marca `live` como el archivo en curso. None si no es promovible.

        Cerrar el anterior primero: si ya tiene resultado queda listo, y si no
        (el CLI pasó de largo) vuelve a la cola para reintento.
        """
        if previous is not None and previous.id != live.id:
            prev = self._reload(previous)
            if prev.status == J.RUNNING:
                if self._output_ready(prev):
                    self._settle(prev, None)
                else:
                    prev.status = J.PENDING
                    self._store.save(prev)
                    self._events.append(
                        "requeued",
                        file=Path(prev.media_path).stem,
                        why="el CLI pasó de largo sin dejar transcripción",
                    )
        fresh = self._reload(live)
        # Cancelado/fallido/listo NO revive por el hecho de que el CLI lo toque.
        if fresh.status in (J.CANCELLED, J.ERROR, J.DONE):
            self._events.append(
                "not_promoted",
                file=Path(fresh.media_path).stem,
                status=fresh.status,
            )
            return None
        if fresh.status != J.RUNNING:
            fresh.status = J.RUNNING
            self._store.save(fresh)
        self._current = fresh
        self._events.append(
            "live",
            file=Path(fresh.media_path).stem,
            after=Path(previous.media_path).stem if previous is not None else "",
        )
        return fresh

    def _next_in_cohort(self, cohort: list[TranscriptionJob]) -> Optional[TranscriptionJob]:
        for item in cohort:
            fresh = self._reload(item)
            if fresh.status in (J.PENDING, J.RUNNING, J.EXTRACTING):
                return fresh
        return None

    @staticmethod
    def _ui_progress(pct: int) -> Optional[int]:
        return None if pct < 0 else pct

    @staticmethod
    def _batch_position(
        job: TranscriptionJob, group: Sequence[TranscriptionJob]
    ) -> Optional[Tuple[int, int]]:
        """(posición, total) del archivo dentro del lote; None si es uno solo.

        `group` va en el orden del argv del CLI, que es el orden en que los
        procesa: la posición es la que el usuario ve avanzar.
        """
        if len(group) < 2:
            return None
        for idx, item in enumerate(group):
            if item.id == job.id:
                return idx + 1, len(group)
        return None

    def _batch_eta(
        self,
        group: Sequence[TranscriptionJob],
        live: TranscriptionJob,
        tracker: ProgressTracker,
        now: float,
    ) -> float:
        """Hora estimada de término de TODO el lote (0 si va un solo archivo)."""
        if len(group) < 2:
            return 0.0
        restante = tracker.remaining()
        if not restante:
            return 0.0
        for item in group:
            if item.id == live.id:
                continue
            fresco = self._reload(item)
            if fresco.status not in (J.PENDING, J.EXTRACTING, J.RUNNING):
                continue
            audio = wav_duration_seconds(fresco.work_wav)
            if not audio:
                return 0.0  # falta un dato: mejor no dar un total a medias
            # Los pendientes de este argv entran en un CLI con los modelos ya
            # cargados: solo suman trabajo (spec 025). Cobrar el arranque a cada
            # uno inventaba minutos de espera en lotes largos.
            restante += estimate_total_seconds(
                audio,
                self._speed.factor_for(key_for_job(fresco)),
                load_models=False,
            )
        return now + restante

    def _monitor(
        self,
        job: TranscriptionJob,
        proc: psutil.Process,
        owned: Optional[subprocess.Popen] = None,
        cohort: Optional[list[TranscriptionJob]] = None,
    ) -> Optional[int]:
        """Vigila el proceso: progreso desde el log, pausa al grabar, anti-suspensión.

        Devuelve el exit code si el proceso era nuestro (owned), None si fue
        re-adoptado (el resultado se valida igual por archivos).
        """
        offset = 0
        fase = PHASE_ASR
        stage = label_for_phase(fase)
        pct = -1
        suspended = False
        applied_impact = normalize_pc_impact(getattr(job, "pc_impact", DEFAULT_PC_IMPACT))
        group = list(cohort) if cohort else self._cohort(job)
        tracker = ProgressTracker(self._speed)
        # Solo el primer archivo de un CLI que acabamos de lanzar espera la carga
        # de modelos; uno re-adoptado entra en un proceso que ya la pagó.
        tracker.reset(job, load_models=owned is not None)
        ultimo_emit = 0.0
        try:
            while True:
                vivo = (owned.poll() is None) if owned else proc.is_running()
                job = self._reload(job)
                wanted = normalize_pc_impact(job.pc_impact)
                if wanted != applied_impact:
                    apply_priority_to_pid(job.pid or getattr(proc, "pid", None), wanted)
                    applied_impact = wanted
                # Pausa total mientras se graba (la grabación manda en la CPU).
                cfg = self._get_config()
                debe_pausar = self._is_recording() and cfg.pause_transcription_while_recording
                try:
                    if debe_pausar and not suspended and vivo:
                        proc.suspend()
                        suspended = True
                        self._events.append(
                            "paused",
                            file=Path(job.media_path).stem,
                            why="empezó una grabación",
                            active_seconds=round(tracker.active, 1),
                        )
                        self._emit(
                            job,
                            stage="⏸ En pausa (grabando)…",
                            progress=tracker.progress,
                            paused=True,
                        )
                    elif not debe_pausar and suspended:
                        proc.resume()
                        suspended = False
                        self._events.append(
                            "resumed",
                            file=Path(job.media_path).stem,
                            active_seconds=round(tracker.active, 1),
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                _keep_awake(vivo and not suspended)
                # El reloj de la estimación solo corre mientras se trabaja.
                tracker.tick(vivo and not suspended)

                offset, nuevo_stage, nuevo_pct, nota, nuevo_cli, nueva_fase = (
                    self._parse_log(job.log_path, offset)
                )
                if nota and not job.note:
                    job.note = nota
                    self._store.save(job)
                if nuevo_cli:
                    matched = job_for_cli_name(group, nuevo_cli)
                    if matched is not None and matched.id != job.id:
                        promoted = self._activate_live(matched, previous=job)
                        if promoted is not None:
                            job = promoted
                            tracker.reset(job, load_models=False)
                if nueva_fase:
                    fase = nueva_fase
                if nuevo_stage:
                    stage = nuevo_stage
                if nuevo_pct is not None:
                    pct = nuevo_pct
                elif fase in PHASES_WITHOUT_ASR_PERCENT:
                    # Sin cifra del CLI: manda la estimación por tiempo, nunca
                    # el % anterior (era el 90 % congelado de antes de spec 021).
                    pct = -1

                self._active_seconds[job.id] = tracker.active
                self._harvest_ready(group)
                live = self._reload(job)
                if live.status == J.DONE:
                    nxt = self._next_in_cohort(group)
                    promoted = (
                        self._activate_live(nxt, previous=live) if nxt else None
                    )
                    if promoted is not None:
                        # Archivo nuevo del lote: vuelve a transcripción desde 0.
                        job, fase, pct = promoted, PHASE_ASR, 0
                        stage = label_for_phase(fase)
                        tracker.reset(job, load_models=False)
                    else:
                        job = live
                        self._current = job
                else:
                    job = live
                    self._current = job

                ahora = time.time()
                progreso, eta = tracker.compute(self._ui_progress(pct))
                # La diarización no imprime nada durante horas: la barra y la
                # hora estimada se refrescan por tiempo, no solo por el log.
                should_emit = bool(
                    nuevo_stage
                    or nuevo_pct is not None
                    or nuevo_cli
                    or live.status == J.DONE
                    or ahora - ultimo_emit >= self.PROGRESS_EMIT_SECONDS
                )
                if job.status == J.RUNNING and not suspended and should_emit:
                    ultimo_emit = ahora
                    self._emit(
                        job,
                        stage=stage,
                        progress=progreso,
                        batch=self._batch_position(job, group),
                        eta=eta,
                        batch_eta=self._batch_eta(group, job, tracker, now=ahora),
                    )

                if not vivo:
                    return owned.returncode if owned else None
                time.sleep(self.POLL_SECONDS)
        finally:
            if suspended:
                try:
                    proc.resume()
                except Exception:
                    pass
            _keep_awake(False)

    def _parse_log(self, log_path: str, offset: int):
        """Lee el log desde `offset`; (offset, stage, pct, nota, cli_name, phase)."""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                texto = f.read()
                offset = f.tell()
        except OSError:
            return offset, None, None, None, None, None
        stage, pct, cli_name, nota, phase = parse_plain_chunk(texto)
        return offset, stage, pct, nota, cli_name, phase

    # --- resolución -----------------------------------------------------------------
    def _settle(self, job: TranscriptionJob, rc: Optional[int]) -> None:
        """Decide done/error por exit code + archivos (nunca solo por el log)."""
        job = self._reload(job)
        if job.status == J.DONE:
            return
        if self._job_cancelled(job.id) or job.status == J.CANCELLED:
            job.status = J.CANCELLED
            job.error = job.error or "Cancelado por el usuario"
            job.finished_at = job.finished_at or J._now()
            job.pid = None
            self._store.save(job)
            self._cleanup_wav(job)
            self._emit(job, stage="Cancelada")
            return

        resultado = result_dir_for(
            Path(job.media_path),
            output_base=getattr(job, "output_base", "") or None,
        )
        txt = resultado / "transcripcion.txt"
        # En un CLI con varios archivos el exit code es global; el éxito es por artefactos.
        exito = txt.exists()

        if exito:
            job.note = job.note or self._check_speakers(resultado)
            job.status = J.DONE
            job.result_dir = str(resultado)
            job.finished_at = J._now()
            job.error = ""
            job.pid = None
            self._store.save(job)
            self._events.append(
                "settled",
                file=Path(job.media_path).stem,
                status=J.DONE,
                note=job.note or "",
                attempts=job.attempts,
                started_at=job.started_at,
                finished_at=job.finished_at,
                result=str(resultado),
            )
            self._learn_speed(job)
            self._cleanup_wav(job)
            self._emit(job, stage="Listo", progress=100)
            return

        # Atribución POR ARCHIVO: en un lote el log es compartido, y el error de
        # otro archivo no debe degradar ni marcar como fallido a este.
        seccion = self._log_section(job)
        err_line = error_in_section(seccion)
        oom = log_looks_like_oom(seccion) or log_looks_like_oom(err_line)
        if oom and apply_oom_degrade(job):
            job.status = J.PENDING
            job.pid = None
            job.error = err_line or "poca memoria"
            self._store.save(job)
            self._events.append(
                "degraded",
                file=Path(job.media_path).stem,
                why="poca memoria",
                note=job.note or "",
                model=job.model,
                pc_impact=job.pc_impact,
                no_diarize=bool(job.no_diarize),
                detail=(err_line or "")[:200],
            )
            self._emit(
                job,
                stage=job.note or "Poca memoria; reintento más ligero…",
            )
            return

        # Falló: ¿fue en la diarización? → reintento degradado sin diarizar
        # (no repetir horas de ASR para volver a morir en la misma fase).
        fallo_en_diarizacion = section_ended_in_diarization(seccion)
        job.attempts += 1
        if fallo_en_diarizacion and not job.no_diarize:
            job.no_diarize = True
            job.note = "sin hablantes (la diarización falló)"
            job.status = J.PENDING
            self._store.save(job)
            self._events.append(
                "degraded",
                file=Path(job.media_path).stem,
                why="la diarización falló",
                note=job.note,
                attempts=job.attempts,
            )
            self._emit(job, stage="Reintentando sin identificación de hablantes…")
        elif job.attempts < job.max_attempts:
            job.status = J.PENDING
            self._store.save(job)
            self._events.append(
                "retry",
                file=Path(job.media_path).stem,
                attempts=job.attempts,
                detail=(err_line or self._why_no_result(seccion, rc))[:200],
            )
            self._emit(job, stage=f"Falló; reintento {job.attempts + 1} en cola")
        else:
            self._fail(job, err_line or self._why_no_result(seccion, rc), retry=False)

    @staticmethod
    def _why_no_result(seccion: str, rc: Optional[int]) -> str:
        """Motivo legible cuando no hay transcripción y el log no dice nada.

        En un lote el exit code es global (rc=None), así que "exit code None"
        no le decía nada al usuario en la fila de la cola.
        """
        if not seccion:
            return "el proceso terminó antes de llegar a este archivo"
        if rc is None:
            return "terminó sin generar la transcripción"
        return f"terminó sin generar la transcripción (código {rc})"

    def _check_speakers(self, resultado: Path) -> str:
        """Sin token HF (o token caído) el CLI termina con exit 0 y sin hablantes."""
        try:
            data = json.loads((resultado / "transcripcion.json").read_text(encoding="utf-8"))
            if not data.get("hablantes"):
                return "sin hablantes"
        except OSError:
            pass  # json no generado (formatos personalizados): no concluimos nada
        except Exception:
            return "resultado JSON ilegible"
        return ""

    def _learn_speed(self, job: TranscriptionJob) -> None:
        """Guarda cuánto tardó de verdad este archivo (antes de borrar su WAV)."""
        activo = self._active_seconds.pop(job.id, 0.0)
        audio = wav_duration_seconds(job.work_wav)
        if activo > 0 and audio > 0:
            clave = key_for_job(job)
            self._speed.record(clave, audio, activo)
            self._events.append(
                "speed",
                file=Path(job.media_path).stem,
                key=clave,
                audio_seconds=round(audio, 1),
                active_seconds=round(activo, 1),
                factor=round(activo / audio, 3),
                learned_factor=round(self._speed.factor_for(clave), 3),
            )

    def _log_section(self, job: TranscriptionJob) -> str:
        """Parte del log que corresponde a ESTE archivo (vacía si nunca empezó)."""
        try:
            texto = Path(job.log_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return log_section_for(texto, cli_name_for_job(job))

    def _fail(self, job: TranscriptionJob, mensaje: str, retry: bool = True) -> None:
        job.attempts += 1
        if retry and job.attempts < job.max_attempts:
            job.status = J.PENDING
        else:
            job.status = J.ERROR
            job.finished_at = J._now()
            self._cleanup_wav(job)
        job.error = mensaje
        self._store.save(job)
        self._events.append(
            "failed",
            file=Path(job.media_path).stem,
            status=job.status,
            attempts=job.attempts,
            error=mensaje[:300],
        )
        self._emit(job, stage="Error" if job.status == J.ERROR else "Reintento en cola")

    def _cleanup_wav(self, job: TranscriptionJob) -> None:
        try:
            if job.work_wav and Path(job.work_wav).exists():
                Path(job.work_wav).unlink()
                Path(job.work_wav).parent.rmdir()
        except OSError:
            pass

    # --- reconciliación al arrancar ----------------------------------------------
    def _reconcile(self) -> None:
        """Retoma el estado real tras un cierre de la app, crash o apagado."""
        for job in self._store.all():
            job = self._reload(job)
            if job.status == J.EXTRACTING:
                job.status = J.PENDING
                self._store.save(job)
            elif job.status == J.RUNNING:
                wav = Path(job.work_wav) if job.work_wav else None
                proc = adopt_transcribe_process(wav)
                if proc is None and job.pid:
                    proc = _is_transcription_pid(job.pid)
                if proc is not None:
                    # El subproceso siguió trabajando solo: re-adoptarlo.
                    self._current = job
                    try:
                        self._emit(job, stage="Retomando transcripción en curso…")
                        cohort = self._cohort(job)
                        self._monitor(job, proc, owned=None, cohort=cohort)
                        for other in self._cohort(job):
                            self._settle(self._reload(other), None)
                    finally:
                        self._current = None
                else:
                    txt = result_dir_for(
                        Path(job.media_path),
                        output_base=getattr(job, "output_base", "") or None,
                    ) / "transcripcion.txt"
                    if txt.exists():
                        self._settle(job, None)  # terminó mientras la app no estaba
                    else:
                        job.attempts += 1
                        job.status = J.PENDING if job.attempts < job.max_attempts else J.ERROR
                        if job.status == J.ERROR:
                            job.error = "interrumpida (apagado o cierre del proceso)"
                        self._store.save(job)
            if job.status == J.PENDING:
                self._emit(job, stage="En cola")
        self._store.purge_orphan_work_dirs()
        # Histórico acotado (spec 023): sin aviso, es limpieza, no noticia.
        podado = self._store.prune_history()
        counts = self._store.queue_counts()
        self._events.append(
            "startup",
            pending=counts.get("pending"),
            running=counts.get("running"),
            failed=counts.get("failed"),
            pruned=podado,
        )

    # --- utilidades -----------------------------------------------------------------
    def _emit(
        self,
        job: TranscriptionJob,
        stage: str = "",
        progress: Optional[int] = None,
        batch: Optional[Tuple[int, int]] = None,
        eta: float = 0.0,
        batch_eta: float = 0.0,
        paused: bool = False,
    ) -> None:
        snap = job.snapshot()
        snap["stage"] = stage
        snap["progress"] = progress
        snap["batch_pos"], snap["batch_total"] = batch if batch else (0, 0)
        snap["eta_epoch"] = float(eta or 0.0)
        snap["batch_eta_epoch"] = float(batch_eta or 0.0)
        snap["eta_paused"] = bool(paused)
        self._events.snapshot(snap)
        try:
            self._on_update(snap)
        except Exception:
            pass

    def _acquire_lock(self) -> bool:
        """Una sola instancia procesa la cola (el SO libera el lock si morimos)."""
        if sys.platform != "win32":
            return True
        import msvcrt

        try:
            self._lock_handle = open(self._store.base / "worker.lock", "w")
            msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            if self._lock_handle:
                self._lock_handle.close()
                self._lock_handle = None
            return False

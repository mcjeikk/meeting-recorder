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
- El éxito se decide por exit code + archivos de salida; el parseo del log es
  solo para mostrar progreso. La diarización se valida leyendo el campo
  "hablantes" de transcripcion.json (el CLI degrada en silencio con exit 0 si
  falta el token de HuggingFace).
"""
from __future__ import annotations

import ctypes
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import psutil

from app.core.config import AppConfig
from app.transcription import jobs as J
from app.transcription.integration import (
    BELOW_NORMAL,
    NO_WINDOW,
    build_command,
    cpu_threads_for_job,
    extract_audio_for_transcription,
    is_available,
    output_dir_for,
    result_dir_for,
    subprocess_env,
)
from app.transcription.jobs import JobStore, TranscriptionJob
from app.transcription.presets import cli_args_from_job_fields, get_preset

# Patrones de las líneas que imprime transcribe.py en modo TRANSCRIPTOR_PLAIN.
_RE_ASR_PCT = re.compile(r"transcribiendo\.\.\. (\d+)%")
_RE_CONVERT = re.compile(r"Convirtiendo audio")
_RE_DIARIZE = re.compile(r"Identificando hablantes")
_RE_DEVICE = re.compile(r"-> dispositivo: (\w+)")
_RE_ERROR = re.compile(r"\[X\] Error con .*?: (.+)")

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
    ) -> Optional[dict]:
        job = self._store.enqueue(media_path, language, preset=preset)
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
        current = self._current
        pid = None
        if current and current.id == job_id:
            pid = current.pid
        job = self._store.cancel(job_id)
        if not job:
            return False
        if pid:
            self._terminate_pid(pid)
        self._emit(job, stage="Cancelada")
        self._wake.set()
        return True

    def clear_failed(self) -> int:
        return self._store.clear_failed()

    def has_active_job(self) -> bool:
        return self._current is not None

    def shutdown(self) -> None:
        """No mata el subproceso (es independiente); solo detiene el hilo."""
        self._stop = True
        self._wake.set()

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
        media = Path(job.media_path)
        if not media.exists():
            self._fail(job, "El archivo ya no existe", retry=False)
            return

        job.status = J.EXTRACTING
        job.started_at = job.started_at or J._now()
        self._store.save(job)
        self._emit(job, stage="Preparando audio…")

        if self._job_cancelled(job.id):
            return

        wav, pista = extract_audio_for_transcription(media, self._store.work_dir / job.id)
        job.work_wav = str(wav)

        if self._job_cancelled(job.id):
            self._cleanup_wav(job)
            return

        # Snapshot del job (no el preset vivo de AppConfig). --no-diarize una sola
        # vez: preset Rápido o reintento degradado tras fallo de diarización.
        extra = ["--threads", str(cpu_threads_for_job())]
        extra.extend(
            cli_args_from_job_fields(
                model=job.model,
                beam_size=job.beam_size,
                no_diarize=bool(job.no_diarize),
            )
        )
        cmd = build_command(cfg.transcriptor_dir, wav, job.language, output_dir_for(media), tuple(extra))

        # stdout/stderr al archivo de log: el hijo nunca se bloquea por un pipe
        # sin lector y sobrevive si el Recorder se cierra.
        log = open(job.log_path, "ab")
        try:
            log.write(f"--- intento {job.attempts + 1} · {pista} ---\n".encode("utf-8"))
            log.flush()
            proc = subprocess.Popen(
                cmd,
                cwd=cfg.transcriptor_dir,
                env=subprocess_env(),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=NO_WINDOW | BELOW_NORMAL,
            )
        finally:
            log.close()

        if self._job_cancelled(job.id):
            self._terminate_pid(proc.pid)
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            self._cleanup_wav(job)
            return

        job.status = J.RUNNING
        job.pid = proc.pid
        self._store.save(job)
        self._emit(job, stage="Transcribiendo…", progress=0)

        rc = self._monitor(job, psutil.Process(proc.pid), owned=proc)
        self._settle(job, rc)

    def _job_cancelled(self, job_id: str) -> bool:
        path = self._store._path(job_id)
        job = self._store._load(path)
        return bool(job and job.status == J.CANCELLED)

    def _monitor(self, job: TranscriptionJob, proc: psutil.Process, owned: Optional[subprocess.Popen] = None) -> Optional[int]:
        """Vigila el proceso: progreso desde el log, pausa al grabar, anti-suspensión.

        Devuelve el exit code si el proceso era nuestro (owned), None si fue
        re-adoptado (el resultado se valida igual por archivos).
        """
        offset = 0
        stage = "Transcribiendo…"
        pct = -1
        suspended = False
        try:
            while True:
                vivo = (owned.poll() is None) if owned else proc.is_running()
                # Pausa total mientras se graba (la grabación manda en la CPU).
                cfg = self._get_config()
                debe_pausar = self._is_recording() and cfg.pause_transcription_while_recording
                try:
                    if debe_pausar and not suspended and vivo:
                        proc.suspend()
                        suspended = True
                        self._emit(job, stage="⏸ En pausa (grabando)…", progress=max(pct, 0))
                    elif not debe_pausar and suspended:
                        proc.resume()
                        suspended = False
                        self._emit(job, stage=stage, progress=max(pct, 0))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                _keep_awake(vivo and not suspended)

                offset, nuevo_stage, nuevo_pct, nota = self._parse_log(job.log_path, offset)
                if nota and not job.note:
                    job.note = nota
                    self._store.save(job)
                if nuevo_stage:
                    stage = nuevo_stage
                if not suspended and (nuevo_stage or (nuevo_pct is not None and nuevo_pct != pct)):
                    if nuevo_pct is not None:
                        pct = nuevo_pct
                    self._emit(job, stage=stage, progress=max(pct, 0))

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
        """Lee el log desde `offset`; devuelve (offset, stage, pct, nota)."""
        stage = pct = nota = None
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                texto = f.read()
                offset = f.tell()
        except OSError:
            return offset, None, None, None
        for linea in texto.splitlines():
            if _RE_CONVERT.search(linea):
                stage, pct = "Preparando audio…", None
            m = _RE_ASR_PCT.search(linea)
            if m:
                stage, pct = "Transcribiendo…", int(m.group(1))
            m = _RE_DEVICE.search(linea)
            if m and m.group(1) == "cuda":
                stage = "Transcribiendo (GPU)…"
            if _RE_DIARIZE.search(linea):
                stage, pct = "Identificando hablantes… (la fase más lenta)", None
            if "La diarizacion no se completo" in linea or "Diarizacion solicitada pero no hay" in linea:
                nota = "sin hablantes"
        return offset, stage, pct, nota

    # --- resolución -----------------------------------------------------------------
    def _settle(self, job: TranscriptionJob, rc: Optional[int]) -> None:
        """Decide done/error por exit code + archivos (nunca solo por el log)."""
        if self._job_cancelled(job.id):
            job.status = J.CANCELLED
            job.error = job.error or "Cancelado por el usuario"
            job.finished_at = job.finished_at or J._now()
            job.pid = None
            self._store.save(job)
            self._cleanup_wav(job)
            self._emit(job, stage="Cancelada")
            return

        resultado = result_dir_for(Path(job.media_path))
        txt = resultado / "transcripcion.txt"
        exito = (rc in (0, None)) and txt.exists()

        if exito:
            job.note = job.note or self._check_speakers(resultado)
            job.status = J.DONE
            job.result_dir = str(resultado)
            job.finished_at = J._now()
            job.error = ""
            self._store.save(job)
            self._cleanup_wav(job)
            self._emit(job, stage="Listo", progress=100)
            return

        # Falló: ¿fue en la diarización? → reintento degradado sin diarizar
        # (no repetir horas de ASR para volver a morir en la misma fase).
        fallo_en_diarizacion = self._last_stage_was_diarization(job.log_path)
        job.attempts += 1
        if fallo_en_diarizacion and not job.no_diarize:
            job.no_diarize = True
            job.note = "sin hablantes (la diarización falló)"
            job.status = J.PENDING
            self._store.save(job)
            self._emit(job, stage="Reintentando sin identificación de hablantes…")
        elif job.attempts < job.max_attempts:
            job.status = J.PENDING
            self._store.save(job)
            self._emit(job, stage=f"Falló; reintento {job.attempts + 1} en cola")
        else:
            self._fail(job, self._last_error_line(job.log_path) or f"exit code {rc}", retry=False)

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

    def _last_stage_was_diarization(self, log_path: str) -> bool:
        try:
            texto = Path(log_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        ultimo = texto.rfind("Identificando hablantes")
        return ultimo != -1 and "OK en" not in texto[ultimo:]

    def _last_error_line(self, log_path: str) -> str:
        try:
            texto = Path(log_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        m = None
        for m in _RE_ERROR.finditer(texto):
            pass
        return m.group(1).strip()[:300] if m else ""

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
            if job.status == J.EXTRACTING:
                job.status = J.PENDING
                self._store.save(job)
            elif job.status == J.RUNNING:
                proc = _is_transcription_pid(job.pid) if job.pid else None
                if proc is not None:
                    # El subproceso siguió trabajando solo: re-adoptarlo.
                    self._current = job
                    try:
                        self._emit(job, stage="Retomando transcripción en curso…")
                        self._monitor(job, proc, owned=None)
                        self._settle(job, None)
                    finally:
                        self._current = None
                else:
                    txt = result_dir_for(Path(job.media_path)) / "transcripcion.txt"
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

    # --- utilidades -----------------------------------------------------------------
    def _emit(self, job: TranscriptionJob, stage: str = "", progress: Optional[int] = None) -> None:
        snap = job.snapshot()
        snap["stage"] = stage
        snap["progress"] = progress
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

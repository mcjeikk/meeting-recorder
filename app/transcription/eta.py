"""Cuánto falta y a qué hora termina (spec 021).

El CLI solo informa el % de la fase de transcripción, y la identificación de
hablantes —la fase larga— no tiene cifra: por eso la barra corría al 90 % y se
quedaba horas ahí. Aquí el progreso sale del TIEMPO: duración del audio × factor
medido para esa configuración. Medido en esta máquina sobre 22 reuniones:
1,08× con más CPU (n=18) y 1,45× dejando el PC usable (n=2); el viejo "2–2,5×"
de la documentación estaba al doble de la realidad.

Todo es asesor: ninguna decisión de cola, reintento o proceso lee esto.
"""
from __future__ import annotations

import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.transcription.pc_impact import DEFAULT_PC_IMPACT, normalize_pc_impact

# WAV de trabajo: 16 kHz mono PCM s16le → 32000 bytes por segundo (+44 de cabecera).
_WAV_BYTES_PER_SECOND = 16000 * 2
_WAV_HEADER = 44

# Carga de modelos antes del primer segundo de audio (un lote la paga una vez).
STARTUP_SECONDS = 40.0

# Mínimo de muestras para creerle al historial de la máquina antes del default.
MIN_SAMPLES = 3
MAX_SAMPLES = 20
# Audios muy cortos: domina la carga de modelos y ensuciarían el factor.
MIN_SAMPLE_AUDIO_SECONDS = 60.0
# Un trabajo real nunca dura segundos; medidas así vienen de un job adoptado
# a mitad o de un reloj raro.
MIN_SAMPLE_ACTIVE_SECONDS = 30.0
# Rango creíble del factor (medido 1.00–1.89; margen amplio por si acaso).
PLAUSIBLE_FACTORS = (0.1, 8.0)

_SPEAKERS = "speakers"
_NO_SPEAKERS = "nospeakers"

# Factores por configuración. Los dos primeros son medidos; los demás se derivan
# (Rápido omite la diarización, ~mitad del trabajo; large-v3 duplica el ASR) y
# el historial los corrige en cuanto haya muestras.
DEFAULT_FACTORS: Dict[str, float] = {
    f"large-v3-turbo|{_SPEAKERS}|full": 1.10,
    f"large-v3-turbo|{_SPEAKERS}|usable": 1.45,
    f"large-v3-turbo|{_NO_SPEAKERS}|full": 0.55,
    f"large-v3-turbo|{_NO_SPEAKERS}|usable": 0.75,
    f"large-v3|{_SPEAKERS}|full": 1.60,
    f"large-v3|{_SPEAKERS}|usable": 2.10,
    f"large-v3|{_NO_SPEAKERS}|full": 0.90,
    f"large-v3|{_NO_SPEAKERS}|usable": 1.20,
}
FALLBACK_FACTOR = 1.10

# La barra no llega a 100 por tiempo: el 100 lo da el archivo de transcripción.
MAX_WORKING_PROGRESS = 99
# Al alcanzar este tramo del estimado sin terminar, el estimado se estira.
STRETCH_AT = 0.95
# Margen mínimo al estirar: la barra puede llegar a 99 pero nunca a 100 por tiempo.
MIN_SLACK = 0.005


def wav_duration_seconds(path: object) -> float:
    """Duración del WAV de trabajo por tamaño (exacto, sin abrir procesos)."""
    if not path:
        return 0.0
    try:
        size = Path(str(path)).stat().st_size
    except OSError:
        return 0.0
    if size <= _WAV_HEADER:
        return 0.0
    return (size - _WAV_HEADER) / _WAV_BYTES_PER_SECOND


def speed_key(model: object, no_diarize: object, pc_impact: object) -> str:
    modelo = str(model or "large-v3-turbo").strip() or "large-v3-turbo"
    hablantes = _NO_SPEAKERS if bool(no_diarize) else _SPEAKERS
    return f"{modelo}|{hablantes}|{normalize_pc_impact(pc_impact or DEFAULT_PC_IMPACT)}"


def key_for_job(job: object) -> str:
    return speed_key(
        getattr(job, "model", ""),
        getattr(job, "no_diarize", False),
        getattr(job, "pc_impact", DEFAULT_PC_IMPACT),
    )


def default_factor(key: str) -> float:
    if key in DEFAULT_FACTORS:
        return DEFAULT_FACTORS[key]
    partes = key.split("|")
    if len(partes) == 3:
        # Configuración desconocida: mismo modelo con hablantes.
        alterno = f"{partes[0]}|{_SPEAKERS}|{partes[2]}"
        if alterno in DEFAULT_FACTORS:
            return DEFAULT_FACTORS[alterno]
    return FALLBACK_FACTOR


class SpeedStore:
    """Historial de velocidad de ESTA máquina (local, nunca sale de aquí)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        if path is None:
            from app.transcription.integration import transcripts_base

            path = transcripts_base() / "speed.json"
        self.path = Path(path)
        self._samples: Dict[str, List[Tuple[float, float]]] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return  # sin historial: se usan los defaults medidos
        crudo = data.get("samples") if isinstance(data, dict) else None
        if not isinstance(crudo, dict):
            return
        for key, muestras in crudo.items():
            limpias = []
            if not isinstance(muestras, list):
                continue
            for m in muestras:
                try:
                    audio, activo = float(m[0]), float(m[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if audio > 0 and activo > 0:
                    limpias.append((audio, activo))
            if limpias:
                self._samples[str(key)] = limpias[-MAX_SAMPLES:]

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(
                    {"version": 1, "samples": {k: [list(s) for s in v] for k, v in self._samples.items()}},
                    indent=2,
                ),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except OSError:
            pass  # el historial es un lujo: nunca debe romper una transcripción

    def keys(self) -> List[str]:
        return sorted(self._samples)

    def record(self, key: str, audio_seconds: float, active_seconds: float) -> None:
        if audio_seconds < MIN_SAMPLE_AUDIO_SECONDS:
            return
        if active_seconds < MIN_SAMPLE_ACTIVE_SECONDS:
            return
        # Una medición imposible (reloj raro, trabajo adoptado a medias) no debe
        # envenenar el factor para siempre.
        if not PLAUSIBLE_FACTORS[0] <= active_seconds / audio_seconds <= PLAUSIBLE_FACTORS[1]:
            return
        muestras = self._samples.setdefault(key, [])
        muestras.append((float(audio_seconds), float(active_seconds)))
        del muestras[:-MAX_SAMPLES]
        self._save()

    def factor_for(self, key: str) -> float:
        muestras = self._samples.get(key, [])
        if len(muestras) >= MIN_SAMPLES:
            return statistics.median(activo / audio for audio, activo in muestras)
        return default_factor(key)


def estimate_total_seconds(audio_seconds: float, factor: float) -> float:
    """Segundos de trabajo para ese audio (0 si no se conoce la duración)."""
    if audio_seconds <= 0 or factor <= 0:
        return 0.0
    return audio_seconds * factor + STARTUP_SECONDS


def weighted_progress(
    *,
    total_seconds: float,
    active_elapsed: float,
    asr_pct: Optional[int] = None,
    previous: Optional[int] = None,
    done: bool = False,
    now: Optional[float] = None,
) -> Tuple[Optional[int], float, float]:
    """(progreso, hora estimada de término, total usado).

    El progreso sale del tiempo activo sobre el estimado, con piso en el % real
    del ASR y techo en 99 hasta que exista la transcripción. Si el tiempo activo
    alcanza el estimado sin terminar, el estimado se estira: la hora de término
    se corre, nunca queda en el pasado.
    """
    ahora = time.time() if now is None else now
    if done:
        return 100, 0.0, max(total_seconds, active_elapsed)
    if total_seconds <= 0:
        # Sin duración de audio no hay hora de término, y el único dato cierto es
        # el % del ASR. Ojo: NO se arrastra el anterior — en la diarización debe
        # quedar indeterminado, no congelado en el 90 % del ASR (spec 020 FR-004).
        return (asr_pct if asr_pct is not None and asr_pct >= 0 else None), 0.0, 0.0

    total = float(total_seconds)
    if active_elapsed >= total * STRETCH_AT:
        # Se pasó del estimado: estirar el total en vez de prometer el pasado.
        # El margen se encoge conforme se alarga, así la barra sigue subiendo
        # (95 → 99) en vez de clavarse, que es la misma mentira de antes.
        margen = max(MIN_SLACK, (1.0 - STRETCH_AT) * total / max(active_elapsed, 1.0))
        total = max(total, active_elapsed * (1.0 + margen))

    pct = int(active_elapsed / total * 100)
    if asr_pct is not None and asr_pct >= 0:
        # El ASR va primero: su % real es un piso (máquina más rápida que el estimado).
        pct = max(pct, int(asr_pct * _asr_share(total)))
    pct = min(pct, MAX_WORKING_PROGRESS)
    if previous is not None:
        pct = max(pct, min(int(previous), MAX_WORKING_PROGRESS))

    restante = max(total - active_elapsed, 60.0)
    return pct, ahora + restante, total


class ProgressTracker:
    """Progreso del archivo en curso, contando solo tiempo ACTIVO.

    Si se suspende la transcripción porque empezó una grabación, el reloj de
    pared sigue pero el trabajo no: contar esa espera correría la estimación
    tanto como dure la reunión que se está grabando.
    """

    def __init__(self, store: "SpeedStore") -> None:
        self._store = store
        self.reset(None)

    def reset(self, job: object) -> None:
        self.job_id = str(getattr(job, "id", "") or "")
        self.audio_seconds = (
            wav_duration_seconds(getattr(job, "work_wav", "")) if job is not None else 0.0
        )
        self.factor = (
            self._store.factor_for(key_for_job(job)) if job is not None else FALLBACK_FACTOR
        )
        self.total = estimate_total_seconds(self.audio_seconds, self.factor)
        self.active = 0.0
        self.progress: Optional[int] = None
        self._last_tick: Optional[float] = None

    def tick(self, working: bool, now: Optional[float] = None) -> None:
        ahora = time.time() if now is None else now
        if not working:
            self._last_tick = None
            return
        if self._last_tick is not None:
            self.active += max(0.0, ahora - self._last_tick)
        self._last_tick = ahora

    def compute(
        self,
        asr_pct: Optional[int] = None,
        done: bool = False,
        now: Optional[float] = None,
    ) -> Tuple[Optional[int], float]:
        pct, eta, total = weighted_progress(
            total_seconds=self.total,
            active_elapsed=self.active,
            asr_pct=asr_pct,
            previous=self.progress,
            done=done,
            now=now,
        )
        if total:
            self.total = total
        self.progress = pct
        return pct, eta

    def remaining(self) -> float:
        return max(self.total - self.active, 0.0) if self.total else 0.0


def _asr_share(total_seconds: float) -> float:
    """Tramo de la barra que cubre la transcripción antes de los hablantes.

    Sin marcas de tiempo por línea en el log no se puede medir el reparto real;
    se usa un tramo conservador para que el piso del ASR no adelante la barra.
    """
    return 0.45


def format_finish(eta_epoch: float, now: Optional[float] = None) -> str:
    """"listo ~21:40" / "listo mañana ~03:20" / "listo el vie ~09:15"."""
    if not eta_epoch:
        return ""
    ahora = time.time() if now is None else now
    if eta_epoch <= ahora:
        eta_epoch = ahora + 60.0
    # Redondeo a 5 min hacia arriba: la precisión al minuto sería falsa.
    bloque = 5 * 60
    redondeado = ((int(eta_epoch) + bloque - 1) // bloque) * bloque
    fin = datetime.fromtimestamp(redondeado)
    hoy = datetime.fromtimestamp(ahora).date()
    dias = (fin.date() - hoy).days
    hora = fin.strftime("%H:%M")
    if dias <= 0:
        return f"listo ~{hora}"
    if dias == 1:
        return f"listo mañana ~{hora}"
    return f"listo el {_DIAS[fin.weekday()]} ~{hora}"


_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")

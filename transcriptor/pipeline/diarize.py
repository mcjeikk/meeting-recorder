"""Diarización de hablantes con pyannote.audio (modelo community-1)."""
from __future__ import annotations

import warnings
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import torch

# pyannote 4.x avisa de torchcodec (que NO usamos: pasamos el audio en memoria) y
# de un std() con pocos grados de libertad. Ambos son inofensivos; los silenciamos.
warnings.filterwarnings("ignore", message=r"(?s).*torchcodec.*")
warnings.filterwarnings("ignore", message=r".*degrees of freedom.*")

_MODELO = "pyannote/speaker-diarization-community-1"
_pipeline_cache: dict[str, object] = {}


def cargar_pipeline(hf_token: str):
    """Carga el pipeline de diarización (en GPU si torch la tiene disponible)."""
    token = hf_token or ""
    cached = _pipeline_cache.get(token)
    if cached is not None:
        return cached
    from pyannote.audio import Pipeline
    try:
        pipeline = Pipeline.from_pretrained(_MODELO, token=hf_token)
    except TypeError:
        # Versiones antiguas de pyannote usan 'use_auth_token' en lugar de 'token'.
        pipeline = Pipeline.from_pretrained(_MODELO, use_auth_token=hf_token)
    # Con el torch +cpu actual esto es un no-op; cuando el equipo tenga GPU y se
    # instale torch con CUDA, la diarización (la fase más lenta) la usará sola.
    if torch.cuda.is_available():
        try:
            pipeline.to(torch.device("cuda"))
        except Exception:
            pass  # cualquier problema con la GPU → se sigue en CPU
    _pipeline_cache[token] = pipeline
    return pipeline


def _cargar_waveform(wav_path: Path):
    """Lee un WAV PCM con la librería estándar y lo deja en memoria.

    Pasamos la onda ya cargada a pyannote para NO depender de torchcodec, cuyas
    DLLs no cargan de forma fiable en Windows. Como nuestro `audio.py` siempre
    genera WAV PCM 16 bit mono a 16 kHz, esta lectura es suficiente.
    """
    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())

    # Conversión a float32 en sitio (in-place) para no duplicar el array en RAM,
    # importante en audios largos (p. ej. una reunión de 3 h ≈ 0.66 GB).
    if sampwidth == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        data /= 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32)
        data /= 2147483648.0
    elif sampwidth == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        data -= 128.0
        data /= 128.0
    else:
        raise RuntimeError(f"Ancho de muestra WAV no soportado: {sampwidth} bytes")
    del raw

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    waveform = torch.from_numpy(np.ascontiguousarray(data)).unsqueeze(0)  # (1, tiempo)
    return waveform, sample_rate


def diarizar(
    wav_path: Path,
    hf_token: str,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
) -> list[dict]:
    """Devuelve una lista de turnos {start, end, speaker} ordenados temporalmente."""
    pipeline = cargar_pipeline(hf_token)

    kwargs: dict = {}
    if num_speakers:
        kwargs["num_speakers"] = num_speakers
    else:
        if min_speakers:
            kwargs["min_speakers"] = min_speakers
        if max_speakers:
            kwargs["max_speakers"] = max_speakers

    waveform, sample_rate = _cargar_waveform(wav_path)
    entrada = {"waveform": waveform, "sample_rate": sample_rate}

    # Barra de progreso de pyannote si está disponible.
    try:
        from pyannote.audio.pipelines.utils.hook import ProgressHook
        with ProgressHook() as hook:
            salida = pipeline(entrada, hook=hook, **kwargs)
    except (ImportError, TypeError):
        salida = pipeline(entrada, **kwargs)

    return _extraer_turnos(salida)


def _anotacion_para_asr(salida):
    """community-1: exclusive (un hablante por instante) alinea mejor con Whisper.

    La anotación regular permite solapes; al fusionar por tiempo eso mete el
    hablante equivocado en frases en español. Si exclusive no existe (pyannote
    3.x o pipeline sin el campo), se usa speaker_diarization / la Annotation.
    """
    exclusive = getattr(salida, "exclusive_speaker_diarization", None)
    if exclusive is not None:
        return exclusive
    return getattr(salida, "speaker_diarization", salida)


def _extraer_turnos(salida) -> list[dict]:
    # pyannote 4.x: DiarizeOutput; 3.x devuelve la Annotation directa.
    diar = _anotacion_para_asr(salida)
    turnos: list[dict] = []
    if hasattr(diar, "itertracks"):
        for turn, _, speaker in diar.itertracks(yield_label=True):
            turnos.append({"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)})
    else:
        for turn, speaker in diar:
            turnos.append({"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)})
    return turnos

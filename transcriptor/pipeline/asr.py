"""Transcripción con faster-whisper (CTranslate2): GPU si existe, CPU si no."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from faster_whisper import WhisperModel

_model_cache: dict[tuple, WhisperModel] = {}

# Si el alias "large-v3-turbo" no está disponible en la versión instalada de
# faster-whisper, se usa este repositorio ya convertido a CTranslate2.
_TURBO_FALLBACK = "deepdml/faster-whisper-large-v3-turbo-ct2"
_TURBO_ALIASES = {"large-v3-turbo", "turbo"}


def detectar_device() -> str:
    """Devuelve "cuda" si hay una GPU utilizable por CTranslate2, "cpu" si no.

    La detección se hace en cada ejecución (no se fija en config): el mismo
    equipo puede ganar una GPU más adelante sin tocar nada.
    """
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def cargar_modelo(
    modelo: str,
    compute_type: str = "int8",
    cpu_threads: int = 0,
    device: str = "auto",
) -> WhisperModel:
    """Carga el modelo en GPU si la hay, con caída automática a CPU.

    device: "auto" (detectar), "cuda" o "cpu". Con GPU, el compute_type "int8"
    (pensado para CPU) se sustituye por "float16"; cualquier otro valor
    explícito se respeta. Si la carga en GPU falla (drivers, memoria, libs
    CUDA ausentes), se reintenta en CPU sin intervención del usuario.
    """
    dev = detectar_device() if device in (None, "", "auto") else device
    ct = "float16" if (dev == "cuda" and compute_type == "int8") else compute_type

    nombres = [modelo] + ([_TURBO_FALLBACK] if modelo in _TURBO_ALIASES else [])
    intentos = [(dev, ct)]
    if dev == "cuda":
        intentos.append(("cpu", compute_type))

    ultimo_error: Optional[Exception] = None
    for d, c in intentos:
        cache_key = (modelo, d, c, int(cpu_threads or 0))
        cached = _model_cache.get(cache_key)
        if cached is not None:
            return cached
        for nombre in nombres:
            try:
                model = WhisperModel(nombre, device=d, compute_type=c, cpu_threads=cpu_threads)
                _model_cache[cache_key] = model
                return model
            except Exception as e:  # noqa: BLE001
                ultimo_error = e
    raise ultimo_error


def transcribir(
    wav_path: Path,
    modelo: str = "large-v3-turbo",
    idioma: Optional[str] = "es",
    compute_type: str = "int8",
    cpu_threads: int = 0,
    beam_size: int = 5,
    vad_filter: bool = True,
    on_progress: Optional[Callable[[float, float], None]] = None,
    device: str = "auto",
) -> dict:
    """Transcribe un WAV y devuelve segmentos y palabras con marcas de tiempo.

    on_progress(actual_seg, duracion_total) se llama tras cada segmento para
    poder mostrar una barra de progreso.
    """
    model = cargar_modelo(modelo, compute_type=compute_type, cpu_threads=cpu_threads, device=device)
    device_usado = str(getattr(getattr(model, "model", None), "device", None) or "cpu")
    lang = None if (idioma in (None, "auto", "")) else idioma

    segmentos_gen, info = model.transcribe(
        str(wav_path),
        language=lang,
        beam_size=beam_size,
        vad_filter=vad_filter,
        vad_parameters=dict(min_silence_duration_ms=500),
        word_timestamps=True,
        condition_on_previous_text=False,
    )

    segmentos: list[dict] = []
    palabras: list[dict] = []
    for seg in segmentos_gen:
        segmentos.append({"start": seg.start, "end": seg.end, "text": seg.text})
        if seg.words:
            for w in seg.words:
                if w.start is None or w.end is None:
                    continue
                palabras.append({"start": w.start, "end": w.end, "word": w.word})
        if on_progress is not None:
            on_progress(seg.end, info.duration)

    return {
        "segmentos": segmentos,
        "palabras": palabras,
        "idioma": info.language,
        "duracion": info.duration,
        "device": device_usado,
    }

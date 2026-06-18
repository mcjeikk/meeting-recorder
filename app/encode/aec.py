"""Cancelación de eco acústico (AEC) usando el audio del sistema como referencia.

Cuando grabas con ALTAVOCES, tu micrófono capta lo que suena por los parlantes
(el audio del sistema) y se produce ECO. Como grabamos el audio del sistema por
separado (la "referencia" o far-end), podemos estimar el eco que aparece en el
micrófono y restarlo.

Algoritmo: MDF (Multi-Delay block Frequency-domain adaptive filter) — el mismo
enfoque que usa Speex/WebRTC — implementado en numpy, sin dependencias nativas.

Uso típico:
    cleaned = cancel_echo(mic, system_ref, sr)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def cancel_echo(
    mic: np.ndarray,
    ref: np.ndarray,
    filter_len: int = 8192,
    mu: float = 0.1,
    passes: int = 2,
    eps: float = 1e-6,
) -> np.ndarray:
    """Resta de `mic` el eco del `ref` (audio del sistema) con un filtro adaptativo
    en frecuencia (overlap-save FDAF, restringido a causal).

    `mic` y `ref` deben estar a la MISMA frecuencia de muestreo y razonablemente
    alineados en el tiempo (el `ref` un poco adelantado al eco, que es lo normal:
    el loopback se toma antes de que el sonido salga por el parlante).

    `filter_len` = longitud del filtro (cola de eco modelable); 8192 ≈ 0.5 s a 16 kHz.
    Como el procesamiento es OFFLINE y la sala no cambia, hacemos varias `passes`
    para que el filtro converja mejor (2 suele ser el punto óptimo).
    Devuelve el micrófono "limpio" (mismo largo que `mic`).
    """
    mic = np.asarray(mic, dtype=np.float64).reshape(-1)
    ref = np.asarray(ref, dtype=np.float64).reshape(-1)
    n = min(len(mic), len(ref))
    L = int(filter_len)
    if n < L:
        return mic.astype(np.float32)
    mic = mic[:n]
    ref = ref[:n]

    N = 2 * L
    nfreq = N // 2 + 1
    W = np.zeros(nfreq, dtype=np.complex128)   # filtro adaptativo (freq)
    P = np.full(nfreq, eps)                    # potencia suavizada del far-end
    zeros_L = np.zeros(L)
    out = mic.copy()
    nblocks = n // L

    for _ in range(max(1, passes)):
        xbuf = np.zeros(N)
        for m in range(nblocks):
            sl = slice(m * L, (m + 1) * L)
            xbuf = np.concatenate([xbuf[L:], ref[sl]])   # deslizar (overlap-save)
            X = np.fft.rfft(xbuf, n=N)

            y = np.fft.irfft(W * X, n=N)[L:]             # eco estimado (parte válida)
            e = mic[sl] - y                              # señal limpia
            out[sl] = e

            E = np.fft.rfft(np.concatenate([zeros_L, e]), n=N)
            P = 0.9 * P + 0.1 * np.abs(X) ** 2
            g = np.fft.irfft(np.conj(X) * E / (P + eps), n=N)
            g[L:] = 0.0                                  # restricción causal
            W += mu * np.fft.rfft(g, n=N)

    return out.astype(np.float32)


def _read_wav_mono(path: str):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        data = w.readframes(w.getnframes())
    a = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    return a, sr


def _write_wav_mono(path: str, samples: np.ndarray, sr: int) -> None:
    i16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(i16.tobytes())


def apply_aec_to_file(input_path: str, output_path: str, sample_rate: int = 16000) -> str:
    """Aplica AEC a un MP4 ya grabado (con pistas 'Sistema' y 'Microfono').

    Extrae la pista de Sistema (referencia) y la de Microfono, cancela el eco, y
    re-multiplexa: Sistema (original) + Microfono limpio + Mezcla nueva.
    Requiere que el archivo tenga al menos 2 pistas de audio (a:0=Sistema, a:1=Microfono).
    Devuelve `output_path`.
    """
    from app.encode.ffmpeg import get_ffmpeg_exe

    ff = get_ffmpeg_exe()
    tmp = tempfile.mkdtemp(prefix="aec_")
    try:
        sys_wav = os.path.join(tmp, "sys.wav")
        mic_wav = os.path.join(tmp, "mic.wav")
        clean_wav = os.path.join(tmp, "clean.wav")

        def _run(args):
            p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=_NO_WINDOW)
            if p.returncode != 0:
                raise RuntimeError(p.stderr.decode("utf-8", "replace"))

        common = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", input_path,
                  "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le"]
        _run(common + ["-map", "0:a:0", sys_wav])
        _run(common + ["-map", "0:a:1", mic_wav])

        ref, _ = _read_wav_mono(sys_wav)
        mic, _ = _read_wav_mono(mic_wav)
        cleaned = cancel_echo(mic, ref)
        _write_wav_mono(clean_wav, cleaned, sample_rate)

        fc = (
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo,asplit=2[sa][sb];"
            "[1:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[ma][mb];"
            "[sb][mb]amix=inputs=2:duration=longest:normalize=0[mix]"
        )
        _run([
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path, "-i", clean_wav,
            "-filter_complex", fc,
            "-map", "0:v:0", "-map", "[sa]", "-map", "[ma]", "-map", "[mix]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-metadata:s:a:0", "title=Sistema",
            "-metadata:s:a:1", "title=Microfono",
            "-metadata:s:a:2", "title=Mezcla",
            "-movflags", "+faststart", output_path,
        ])
        return output_path
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def erle_db(echo_ref: np.ndarray, residual: np.ndarray) -> float:
    """Echo Return Loss Enhancement (dB): cuánto se redujo el eco. Mayor = mejor."""
    e0 = float(np.mean(np.square(echo_ref))) + 1e-12
    e1 = float(np.mean(np.square(residual))) + 1e-12
    return 10.0 * np.log10(e0 / e1)


# --- Prueba con eco sintético -----------------------------------------------
def _self_test() -> int:
    rng = np.random.RandomState(42)
    sr = 16000
    dur = 6
    n = sr * dur

    # Far-end (audio del sistema): ruido con algo de estructura (voz simulada).
    x = rng.randn(n)
    x = np.convolve(x, np.hanning(200), mode="same")
    x /= np.max(np.abs(x)) + 1e-9

    # Respuesta de la sala (parlante->mic): retardo + cola que decae.
    delay = int(0.02 * sr)                       # 20 ms de retardo acústico
    tail = int(0.15 * sr)                        # 150 ms de reverberación
    h = np.zeros(delay + tail)
    h[delay:] = rng.randn(tail) * np.exp(-np.linspace(0, 5, tail))
    h *= 0.6 / (np.max(np.abs(h)) + 1e-9)
    echo = np.convolve(x, h)[:n]

    # Voz cercana (tu micrófono) solo en la 2a mitad -> probar double-talk.
    near = np.zeros(n)
    half = n // 2
    near[half:] = np.convolve(rng.randn(n - half), np.hanning(150), mode="same")
    near[half:] /= np.max(np.abs(near[half:])) + 1e-9

    mic = echo + near                            # lo que capta el micrófono

    cleaned = cancel_echo(mic, x)

    # ERLE en la región de SOLO eco (1a mitad, sin voz cercana).
    region = slice(sr, half)                      # tras converger
    erle = erle_db(echo[region], cleaned[region])
    # ¿Se preservó la voz cercana? (no debe destruirla)
    near_keep = erle_db(near[half:], cleaned[half:] - near[half:])

    print(f"ERLE (reducción de eco, solo-eco): {erle:.1f} dB  (bueno: >12 dB)")
    print(f"Preservación de voz cercana:       {near_keep:.1f} dB  (mayor = mejor)")
    ok = erle > 12.0
    print("RESULTADO:", "OK" if ok else "INSUFICIENTE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())

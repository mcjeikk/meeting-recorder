"""Wrapper de FFmpeg: localizar el binario, elegir encoder y multiplexar (mux).

Usamos el FFmpeg que viene empaquetado con `imageio-ffmpeg` para no obligar al
usuario a instalar nada. Si no está, se intenta el `ffmpeg` del PATH.

Responsabilidades:
1. `detect_h264_encoder()`: prueba de verdad qué encoder H.264 funciona en esta
   máquina (NVENC/QSV/AMF por hardware, o libx264 por software como respaldo).
2. `mux_recording()`: combina el video + varias PISTAS de audio en un MP4 final.
   Cada pista puede estar formada por uno o varios SEGMENTOS temporizados (esto
   permite, por ejemplo, cambiar de micrófono a mitad de la grabación: cada mic
   es un segmento que FFmpeg normaliza y coloca en su instante correcto).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# En Windows, evita que se abran ventanas de consola al lanzar FFmpeg.
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Orden de preferencia: hardware primero (mucho más liviano para grabar pantalla),
# software (libx264) como red de seguridad universal.
_H264_CANDIDATES = ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"]

_cached_encoder: Optional[str] = None


def get_ffmpeg_exe() -> str:
    """Ruta al ejecutable de FFmpeg (empaquetado o del PATH)."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # se asume disponible en el PATH


def _run(args: List[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=_NO_WINDOW,
        **kwargs,
    )


def _run_with_progress(
    args: List[str], total_seconds: float, progress_cb: Callable[[int], None]
):
    """Ejecuta FFmpeg leyendo `-progress` (stdout) y reporta el avance en %.

    Devuelve (returncode, stderr_text). `args` debe incluir `-progress pipe:1`.
    """
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=_NO_WINDOW, text=True, encoding="utf-8", errors="replace",
    )
    stderr_chunks: List[str] = []

    def _drain_stderr():
        try:
            for line in proc.stderr:
                stderr_chunks.append(line)
        except Exception:
            pass

    t = threading.Thread(target=_drain_stderr, daemon=True)
    t.start()

    last_pct = -1
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_us=") and total_seconds > 0:
                value = line.split("=", 1)[1]
                try:
                    pct = int(min(99, max(0, int(value) / 1e6 / total_seconds * 100)))
                except (ValueError, ZeroDivisionError):
                    continue
                if pct != last_pct:
                    last_pct = pct
                    try:
                        progress_cb(pct)
                    except Exception:
                        pass
    except Exception:
        pass
    proc.wait()
    t.join(timeout=1)
    return proc.returncode, "".join(stderr_chunks)


def _encoder_works(encoder: str) -> bool:
    """Prueba funcional: codifica 1 fotograma de prueba con el encoder dado."""
    ff = get_ffmpeg_exe()
    args = [
        ff, "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=160x120:r=5:d=0.2",
        "-frames:v", "1", "-c:v", encoder, "-f", "null", os.devnull,
    ]
    try:
        return _run(args).returncode == 0
    except Exception:
        return False


def detect_h264_encoder() -> str:
    """Devuelve el primer encoder H.264 que realmente funciona. Cachea el resultado."""
    global _cached_encoder
    if _cached_encoder:
        return _cached_encoder
    for enc in _H264_CANDIDATES:
        if _encoder_works(enc):
            _cached_encoder = enc
            return enc
    # Último recurso: confiar en libx264 aunque la prueba haya fallado.
    _cached_encoder = "libx264"
    return _cached_encoder


def probe_duration(path: str) -> float:
    """Duración en segundos de un archivo, leída de `ffmpeg -i` (sin ffprobe)."""
    if not os.path.exists(path):
        return 0.0
    proc = _run([get_ffmpeg_exe(), "-hide_banner", "-i", path])
    text = proc.stderr.decode("utf-8", "replace")
    for ln in text.splitlines():
        if "Duration:" in ln:
            try:
                hms = ln.split("Duration:")[1].split(",")[0].strip()
                h, m, s = hms.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                return 0.0
    return 0.0


@dataclass
class Segment:
    """Un trozo de audio grabado de forma continua, con su instante de inicio."""
    path: str            # archivo WAV (en su formato nativo)
    offset: float = 0.0  # segundos desde el inicio de la grabación (para sincronía)


@dataclass
class Track:
    """Una pista lógica de audio (p. ej. 'Sistema' o 'Microfono').

    Puede tener varios segmentos: si el usuario cambia de micrófono a mitad de la
    grabación, cada micrófono es un segmento con su propio instante de inicio.
    """
    label: str
    segments: List[Segment] = field(default_factory=list)


def _segment_filter(input_index: int, seg: Segment, out_pad: str, sample_rate: int) -> str:
    """Normaliza un segmento a 48 kHz estéreo y lo coloca en su instante (adelay)."""
    chain = f"aresample={sample_rate},aformat=channel_layouts=stereo"
    delay_ms = int(round(max(0.0, seg.offset) * 1000))
    if delay_ms > 0:
        chain += f",adelay={delay_ms}:all=1"
    return f"[{input_index}:a]{chain}[{out_pad}]"


def mux_recording(
    video_path: str,
    tracks: List[Track],
    output_path: str,
    sample_rate: int = 48_000,
    add_mixed_master: bool = True,
    total_seconds: float = 0.0,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> str:
    """Combina video + pistas de audio (cada una con 1+ segmentos) en un MP4.

    - El video ya viene en H.264 (MKV): se copia sin recodificar.
    - Cada pista se incluye por separado, normalizada a 48 kHz estéreo.
    - Si hay 2+ pistas con contenido, se añade una pista 'Mezcla' para reproducir
      normal en cualquier reproductor.
    Devuelve la ruta final. Lanza RuntimeError si FFmpeg falla.
    """
    ff = get_ffmpeg_exe()

    # Solo pistas que realmente tengan algún segmento.
    tracks = [t for t in tracks if t.segments]

    args: List[str] = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", video_path]

    # Entradas: todos los segmentos de todas las pistas, en orden.
    input_index = 1
    seg_inputs: List[tuple] = []  # (track_idx, input_index, segment)
    for ti, track in enumerate(tracks):
        for seg in track.segments:
            args += ["-i", seg.path]
            seg_inputs.append((ti, input_index, seg))
            input_index += 1

    filters: List[str] = []
    track_pads: List[str] = []  # pad de salida [trkN] de cada pista

    # 1) Normalizar cada segmento; 2) combinar los segmentos de una pista en [trkN].
    for ti, track in enumerate(tracks):
        seg_pads = []
        for (t_idx, in_idx, seg) in seg_inputs:
            if t_idx != ti:
                continue
            pad = f"t{ti}s{len(seg_pads)}"
            filters.append(_segment_filter(in_idx, seg, pad, sample_rate))
            seg_pads.append(pad)

        trk_pad = f"trk{ti}"
        if len(seg_pads) == 1:
            filters.append(f"[{seg_pads[0]}]anull[{trk_pad}]")
        else:
            joined = "".join(f"[{p}]" for p in seg_pads)
            filters.append(
                f"{joined}amix=inputs={len(seg_pads)}:duration=longest:normalize=0[{trk_pad}]"
            )
        track_pads.append(trk_pad)

    make_mix = add_mixed_master and len(track_pads) >= 2

    # Si vamos a mezclar, cada pista debe usarse 2 veces (salida + mezcla) -> asplit.
    map_pads: List[str] = []
    if make_mix:
        mix_inputs = []
        for ti, trk_pad in enumerate(track_pads):
            out_pad, mix_pad = f"m{ti}", f"x{ti}"
            filters.append(f"[{trk_pad}]asplit=2[{out_pad}][{mix_pad}]")
            map_pads.append(out_pad)
            mix_inputs.append(f"[{mix_pad}]")
        filters.append(
            "".join(mix_inputs)
            + f"amix=inputs={len(mix_inputs)}:duration=longest:normalize=0[mix]"
        )
    else:
        map_pads = list(track_pads)

    # Construir mapeos
    args += ["-map", "0:v"]
    if filters:
        args += ["-filter_complex", ";".join(filters)]
        for pad in map_pads:
            args += ["-map", f"[{pad}]"]
        if make_mix:
            args += ["-map", "[mix]"]

    # Códecs
    args += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(sample_rate)]

    # Títulos de pista. El muxer MP4 descarta `title` (verificado con este
    # binario): el nombre visible de una pista MP4 vive en el átomo hdlr, que
    # ffmpeg expone como `handler_name`. Se escriben ambos por compatibilidad.
    out_index = 0
    for track in tracks:
        args += [f"-metadata:s:a:{out_index}", f"title={track.label}"]
        args += [f"-metadata:s:a:{out_index}", f"handler_name={track.label}"]
        out_index += 1
    if make_mix:
        args += [f"-metadata:s:a:{out_index}", "title=Mezcla"]
        args += [f"-metadata:s:a:{out_index}", "handler_name=Mezcla"]

    # (Sin `+faststart`: reescribiría todo el archivo. Innecesario para archivos
    # locales y duplica el tiempo de guardado en videos largos.)
    if progress_cb is not None and total_seconds > 0:
        args += ["-progress", "pipe:1", "-nostats", output_path]
        rc, err = _run_with_progress(args, total_seconds, progress_cb)
        if rc != 0:
            raise RuntimeError("FFmpeg falló al multiplexar:\n" + err)
    else:
        args += [output_path]
        proc = _run(args)
        if proc.returncode != 0:
            raise RuntimeError(
                "FFmpeg falló al multiplexar:\n" + proc.stderr.decode("utf-8", "replace")
            )
    return output_path


def concat_videos(paths: List[str], output_path: str) -> str:
    """Concatena varios segmentos de video (mismo formato) en uno solo, sin recodificar.

    Se usa cuando hubo PAUSAS: cada tramo activo es un MKV; se unen back-to-back.
    Si solo hay un segmento, se devuelve tal cual.
    """
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        raise RuntimeError("No hay segmentos de video para concatenar.")
    if len(paths) == 1:
        return paths[0]

    ff = get_ffmpeg_exe()
    list_path = output_path + ".concat.txt"
    # El demuxer concat necesita un archivo de lista con rutas escapadas.
    with open(list_path, "w", encoding="utf-8") as fh:
        for p in paths:
            safe = p.replace("\\", "/").replace("'", "'\\''")
            fh.write(f"file '{safe}'\n")

    args = [
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path,
    ]
    proc = _run(args)
    try:
        os.remove(list_path)
    except Exception:
        pass
    if proc.returncode != 0:
        raise RuntimeError(
            "FFmpeg falló al concatenar segmentos de video:\n"
            + proc.stderr.decode("utf-8", "replace")
        )
    return output_path


def remux_to_mp4(input_path: str, output_path: str) -> str:
    """Remux sin recodificar (copia de streams) de un contenedor a MP4."""
    ff = get_ffmpeg_exe()
    args = [
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-i", input_path, "-c", "copy", output_path,
    ]
    proc = _run(args)
    if proc.returncode != 0:
        raise RuntimeError(
            "FFmpeg falló al remuxar a MP4:\n" + proc.stderr.decode("utf-8", "replace")
        )
    return output_path


def render_track_mono_wav(track: Track, output_wav: str, sample_rate: int = 16_000) -> str:
    """Renderiza una pista (sus segmentos alineados) a un WAV MONO. Solo audio.

    Se usa para alimentar la cancelación de eco (AEC): necesita el micrófono y el
    sistema alineados y a la misma frecuencia. Es rápido (no toca el video).
    """
    ff = get_ffmpeg_exe()
    segments = [s for s in track.segments if os.path.exists(s.path)]
    if not segments:
        raise RuntimeError(f"La pista '{track.label}' no tiene segmentos.")

    args: List[str] = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    for seg in segments:
        args += ["-i", seg.path]

    filters: List[str] = []
    pads: List[str] = []
    for i, seg in enumerate(segments):
        pad = f"s{i}"
        chain = f"aresample={sample_rate},aformat=channel_layouts=mono"
        delay_ms = int(round(max(0.0, seg.offset) * 1000))
        if delay_ms > 0:
            chain += f",adelay={delay_ms}:all=1"
        filters.append(f"[{i}:a]{chain}[{pad}]")
        pads.append(pad)

    if len(pads) == 1:
        filters.append(f"[{pads[0]}]anull[out]")
    else:
        joined = "".join(f"[{p}]" for p in pads)
        filters.append(
            f"{joined}amix=inputs={len(pads)}:duration=longest:normalize=0[out]"
        )

    args += ["-filter_complex", ";".join(filters), "-map", "[out]",
             "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", output_wav]
    proc = _run(args)
    if proc.returncode != 0:
        raise RuntimeError(
            "FFmpeg falló al renderizar la pista de audio:\n"
            + proc.stderr.decode("utf-8", "replace")
        )
    return output_wav

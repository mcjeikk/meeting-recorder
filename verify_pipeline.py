"""Verificación de extremo a extremo del pipeline de grabación.

A) Mux sintético: genera un video de prueba + dos tonos (a 48k y 44.1k) y comprueba
   que el MP4 final tiene 1 video + 3 audios (Sistema, Micrófono, Mezcla), probando
   también el resampleo del `amix`.
B) Captura real corta: graba 3 s de PANTALLA + AUDIO DEL SISTEMA (sin micrófono) y
   verifica que el MP4 tenga video + 1 audio. Borra los archivos al terminar.

Ejecuta:  python verify_pipeline.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from app.encode.ffmpeg import Segment, Track, get_ffmpeg_exe, mux_recording

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_NO_WINDOW)


def probe_streams(path: str):
    """Cuenta streams de video/audio usando `ffmpeg -i` (no requiere ffprobe)."""
    ff = get_ffmpeg_exe()
    proc = _run([ff, "-hide_banner", "-i", path])
    text = proc.stderr.decode("utf-8", "replace")
    video = sum(1 for ln in text.splitlines() if "Stream #" in ln and "Video:" in ln)
    audio = sum(1 for ln in text.splitlines() if "Stream #" in ln and "Audio:" in ln)
    return video, audio


def probe_duration(path: str) -> float:
    """Duración en segundos, parseada de `ffmpeg -i` (Duration: HH:MM:SS.xx)."""
    ff = get_ffmpeg_exe()
    proc = _run([ff, "-hide_banner", "-i", path])
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


def test_synthetic_mux(tmp: Path) -> bool:
    print("== A) Mux sintético (video + 2 audios -> 3 pistas) ==")
    ff = get_ffmpeg_exe()
    video = str(tmp / "v.mkv")
    tone1 = str(tmp / "t1.wav")
    tone2 = str(tmp / "t2.wav")
    out = str(tmp / "sintetico.mp4")

    _run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "testsrc=size=320x240:rate=15:duration=3",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", video])
    _run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "sine=frequency=440:duration=3", "-ar", "48000", tone1])
    _run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "sine=frequency=880:duration=3", "-ar", "44100", tone2])

    mux_recording(
        video_path=video,
        tracks=[
            Track("Sistema", [Segment(tone1, 0.0)]),
            Track("Microfono", [Segment(tone2, 0.05)]),
        ],
        output_path=out,
        sample_rate=48_000,
    )
    v, a = probe_streams(out)
    print(f"   resultado: {v} video, {a} audio  (esperado: 1 video, 3 audio)")
    ok = v == 1 and a == 3
    print("   ", "OK" if ok else "FALLÓ")
    return ok


def test_live_capture(tmp: Path) -> bool:
    print("== B) Captura real: 3 s de pantalla + audio del sistema ==")
    from app.core.config import RecordingSettings, VideoSource
    from app.core.orchestrator import Recorder

    done = threading.Event()
    result = {}

    rec = Recorder(
        on_status=lambda m: print("   estado:", m),
        on_finished=lambda p: (result.update(path=p), done.set()),
        on_error=lambda m: (result.update(err=m), done.set()),
    )
    settings = RecordingSettings(
        video_source=VideoSource(kind="screen"),
        mic_device=None,
        capture_system_audio=True,
        output_dir=tmp,
    )
    try:
        rec.start(settings)
    except Exception as exc:
        print("   no se pudo iniciar:", exc)
        return False

    time.sleep(3.0)
    rec.stop()
    if not done.wait(timeout=40):
        print("   FALLÓ: el procesamiento no terminó a tiempo")
        return False
    if "err" in result:
        print("   FALLÓ:", result["err"])
        return False

    path = result["path"]
    v, a = probe_streams(path)
    size = os.path.getsize(path)
    print(f"   archivo: {os.path.basename(path)} ({size} bytes)")
    print(f"   resultado: {v} video, {a} audio  (esperado: 1 video, 1 audio)")
    ok = v == 1 and a >= 1 and size > 1000
    print("   ", "OK" if ok else "FALLÓ")
    try:
        os.remove(path)  # no dejamos basura
    except Exception:
        pass
    return ok


def test_live_capture_with_mic(tmp: Path) -> bool:
    print("== C) Captura real: 3 s de pantalla + sistema + MICRÓFONO (3 pistas) ==")
    from app.capture.windows_audio import list_microphones
    from app.core.config import RecordingSettings, VideoSource
    from app.core.orchestrator import Recorder

    mics = list_microphones()
    if not mics:
        print("   (omitido: no hay micrófonos)")
        return True

    done = threading.Event()
    result = {}
    rec = Recorder(
        on_status=lambda m: print("   estado:", m),
        on_finished=lambda p: (result.update(path=p), done.set()),
        on_error=lambda m: (result.update(err=m), done.set()),
    )
    settings = RecordingSettings(
        video_source=VideoSource(kind="screen"),
        mic_device=mics[0],
        capture_system_audio=True,
        output_dir=tmp,
    )
    try:
        rec.start(settings)
    except Exception as exc:
        print("   no se pudo iniciar:", exc)
        return False
    time.sleep(3.0)
    rec.stop()
    if not done.wait(timeout=40):
        print("   FALLÓ: el procesamiento no terminó a tiempo")
        return False
    if "err" in result:
        print("   FALLÓ:", result["err"])
        return False
    path = result["path"]
    v, a = probe_streams(path)
    print(f"   resultado: {v} video, {a} audio  (esperado: 1 video, 3 audio)")
    ok = v == 1 and a == 3
    print("   ", "OK" if ok else "FALLÓ")
    try:
        os.remove(path)
    except Exception:
        pass
    return ok


def test_synthetic_mic_switch(tmp: Path) -> bool:
    """Mic con 2 SEGMENTOS (simula cambio de micrófono) -> 1 pista continua."""
    print("== A2) Mux: mic con 2 segmentos (cambio de mic) -> 3 pistas ==")
    ff = get_ffmpeg_exe()
    video = str(tmp / "v2.mkv")
    sysw = str(tmp / "sys.wav")
    seg0 = str(tmp / "m0.wav")  # mic 1: 0-2s
    seg1 = str(tmp / "m1.wav")  # mic 2: 2-4s (formato distinto, a 16k mono)
    out = str(tmp / "switch.mp4")

    _run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "testsrc=size=320x240:rate=15:duration=4", "-c:v", "libx264",
          "-pix_fmt", "yuv420p", video])
    _run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "sine=frequency=300:duration=4", "-ar", "48000", sysw])
    _run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "sine=frequency=600:duration=2", "-ar", "48000", "-ac", "2", seg0])
    _run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "sine=frequency=900:duration=2", "-ar", "16000", "-ac", "1", seg1])

    mux_recording(
        video_path=video,
        tracks=[
            Track("Sistema", [Segment(sysw, 0.0)]),
            Track("Microfono", [Segment(seg0, 0.0), Segment(seg1, 2.0)]),
        ],
        output_path=out,
        sample_rate=48_000,
    )
    v, a = probe_streams(out)
    print(f"   resultado: {v} video, {a} audio  (esperado: 1 video, 3 audio)")
    ok = v == 1 and a == 3
    print("   ", "OK" if ok else "FALLÓ")
    return ok


def test_live_mic_switch(tmp: Path) -> bool:
    """Graba 4 s cambiando de micrófono a la mitad (requiere 2 micrófonos)."""
    print("== D) Captura real: cambio de MICRÓFONO a mitad de grabación ==")
    from app.capture.windows_audio import list_microphones
    from app.core.config import RecordingSettings, VideoSource
    from app.core.orchestrator import Recorder

    mics = list_microphones()
    if not mics:
        print("   (omitido: no hay micrófonos)")
        return True
    # Si solo hay un micrófono, ejercitamos igual el cambio en caliente reabriendo
    # el mismo dispositivo (genera 2 segmentos reales).
    second = mics[1] if len(mics) >= 2 else mics[0]

    done = threading.Event()
    result = {}
    rec = Recorder(
        on_status=lambda m: print("   estado:", m),
        on_finished=lambda p: (result.update(path=p), done.set()),
        on_error=lambda m: (result.update(err=m), done.set()),
    )
    settings = RecordingSettings(
        video_source=VideoSource(kind="screen"),
        mic_device=mics[0],
        capture_system_audio=True,
        output_dir=tmp,
    )
    try:
        rec.start(settings)
    except Exception as exc:
        print("   no se pudo iniciar:", exc)
        return False
    print(f"   mic inicial: {mics[0].name}")
    time.sleep(2.0)
    print(f"   cambiando a: {second.name}")
    rec.change_mic(second)
    time.sleep(2.0)
    rec.stop()
    if not done.wait(timeout=40):
        print("   FALLÓ: el procesamiento no terminó a tiempo")
        return False
    if "err" in result:
        print("   FALLÓ:", result["err"])
        return False
    path = result["path"]
    v, a = probe_streams(path)
    print(f"   resultado: {v} video, {a} audio  (esperado: 1 video, 3 audio)")
    ok = v == 1 and a == 3
    print("   ", "OK" if ok else "FALLÓ")
    try:
        os.remove(path)
    except Exception:
        pass
    return ok


def test_live_pause(tmp: Path) -> bool:
    """Graba 2 s, PAUSA 1.5 s, reanuda 2 s -> la duración final debe ser ~4 s."""
    print("== E) Captura real: PAUSAR / REANUDAR (la pausa no cuenta) ==")
    from app.core.config import RecordingSettings, VideoSource
    from app.core.orchestrator import Recorder

    done = threading.Event()
    result = {}
    rec = Recorder(
        on_status=lambda m: print("   estado:", m),
        on_finished=lambda p: (result.update(path=p), done.set()),
        on_error=lambda m: (result.update(err=m), done.set()),
    )
    settings = RecordingSettings(
        video_source=VideoSource(kind="screen"),
        mic_device=None,
        capture_system_audio=True,
        output_dir=tmp,
    )
    pause_secs = 2.0
    t0 = time.perf_counter()
    try:
        rec.start(settings)
    except Exception as exc:
        print("   no se pudo iniciar:", exc)
        return False
    time.sleep(3.0)
    print("   pausando…")
    rec.pause()
    time.sleep(pause_secs)
    print("   reanudando…")
    rec.resume()
    time.sleep(3.0)
    rec.stop()
    wall_record = time.perf_counter() - t0  # incluye la pausa
    if not done.wait(timeout=40):
        print("   FALLÓ: el procesamiento no terminó a tiempo")
        return False
    if "err" in result:
        print("   FALLÓ:", result["err"])
        return False
    path = result["path"]
    v, a = probe_streams(path)
    dur = probe_duration(path)
    # La pausa NO debe contar: (pared - duración) debe ser ~= la pausa.
    excluded = wall_record - dur
    print(f"   resultado: {v} video, {a} audio, duración={dur:.1f}s, "
          f"pared={wall_record:.1f}s -> pausa excluida={excluded:.1f}s (esperado ~{pause_secs:.0f}s)")
    ok = v == 1 and a >= 1 and 1.0 <= excluded <= 3.2
    print("   ", "OK" if ok else "FALLÓ")
    try:
        os.remove(path)
    except Exception:
        pass
    return ok


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    with_mic = "--mic" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="verify_"))
    results = []
    try:
        results.append(test_synthetic_mux(tmp))
        results.append(test_synthetic_mic_switch(tmp))
        results.append(test_live_capture(tmp))
        results.append(test_live_pause(tmp))
        if with_mic:
            results.append(test_live_capture_with_mic(tmp))
            results.append(test_live_mic_switch(tmp))
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("RESULTADO:", "TODO OK" if all(results) else "HAY FALLOS")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

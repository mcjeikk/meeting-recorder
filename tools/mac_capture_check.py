"""Diagnóstico de captura en macOS (spec 030).

Dice qué permisos tiene el proceso, qué pantallas y ventanas ve
ScreenCaptureKit y si llega un fotograma; luego graba clips reales con
`verify_pipeline.py` (el mismo camino que la app: orquestador + mux).

    python tools/mac_capture_check.py
    python tools/mac_capture_check.py --probe-only   # sin grabar clips

Sin el permiso de «Grabación de pantalla» para la Terminal (o el proceso que lo
lance) ScreenCaptureKit no entrega nada: el informe lo dice en vez de colgarse.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def probe() -> bool:
    from app.capture import sources
    from app.core import mac_permissions as perms

    pantalla = perms.screen_allowed(request=False)
    mic = perms.microphone_allowed(request=False)
    print(f"  permiso de pantalla: {'sí' if pantalla else 'NO'}")
    print(f"  permiso de micrófono: {'sí' if mic else 'no (solo hace falta con micrófono)'}")
    monitores = sources.list_monitors()
    ventanas = sources.list_windows()
    print(f"  pantallas: {len(monitores)} · ventanas: {len(ventanas)}")
    for m in monitores:
        print(f"    🖥  {m.label}")
    for w in ventanas[:8]:
        print(f"    🪟  {w.title}")
    from app.encode.ffmpeg import detect_h264_encoder, get_ffmpeg_exe

    encoders = subprocess.run(
        [get_ffmpeg_exe(), "-hide_banner", "-encoders"], capture_output=True, text=True
    ).stdout
    vt = "h264_videotoolbox" in encoders
    print(f"  ffmpeg trae h264_videotoolbox: {'sí' if vt else 'no'} · encoder elegido: {detect_h264_encoder()}")
    frame = sources.grab_monitor_frame(1) if monitores else None
    if frame is None:
        print("  fotograma de la pantalla 1: NO llegó")
        return False
    print(f"  fotograma de la pantalla 1: {frame.shape[1]}×{frame.shape[0]}")
    return pantalla and record_probe(monitores[0])


def record_probe(source) -> bool:
    """3 s de video y de audio del sistema con los backends reales, sin orquestador."""
    import tempfile
    import time

    from app.capture.mac_sck import SCKSystemAudioCapture, SCKVideoCapture

    ok = True
    with tempfile.TemporaryDirectory(prefix="mac_cap_") as tmp:
        video = Path(tmp) / "v.mkv"
        audio = Path(tmp) / "a.wav"
        cap, aud = SCKVideoCapture(source, fps=30), SCKSystemAudioCapture()
        try:
            t0 = time.monotonic()
            cap.start(str(video))
            print(f"  video: arrancó en {time.monotonic() - t0:.1f} s")
            aud.start(str(audio))
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            print(f"  grabación directa FALLÓ: {e}")
            ok = False
        finally:
            for c in (aud, cap):
                try:
                    c.stop()
                except Exception as e:  # noqa: BLE001
                    print(f"  al detener: {e}")
        for p in (video, audio):
            tam = p.stat().st_size if p.exists() else 0
            print(f"  {p.name}: {tam} bytes")
            ok = ok and tam > 0
    if not ok:
        dump_capture_log()
    return ok


def dump_capture_log() -> None:
    from app.core.platform_paths import local_dir

    log = local_dir() / "logs" / "mac_capture.log"
    if log.exists():
        print(f"---- {log}")
        print(log.read_text(encoding="utf-8", errors="replace")[-5000:])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--probe-only", action="store_true")
    args = p.parse_args()
    if sys.platform != "darwin":
        print("Este diagnóstico es para macOS.")
        return 2
    print("==> ScreenCaptureKit")
    ok = probe()
    if args.probe_only or not ok:
        if not ok:
            print("Da permiso de «Grabación de pantalla» al proceso que lanza esto y repite.")
        return 0 if ok else 1
    print("==> Clips reales (verify_pipeline.py)")
    return subprocess.run([sys.executable, str(ROOT / "verify_pipeline.py")], cwd=str(ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())

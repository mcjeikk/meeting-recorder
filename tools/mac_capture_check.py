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
    frame = sources.grab_monitor_frame(1) if monitores else None
    if frame is None:
        print("  fotograma de la pantalla 1: NO llegó")
        return False
    print(f"  fotograma de la pantalla 1: {frame.shape[1]}×{frame.shape[0]}")
    return pantalla


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

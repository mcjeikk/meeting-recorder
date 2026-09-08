"""Verificación end-to-end de la integración Recorder → Transcriptor.

Ejecuta el MISMO código que usa la app (cola + worker + subproceso CLI) sobre
un MP4 real, con una cola temporal aislada. Sirve como prueba de humo del
contrato (comando, --output absoluto, parseo de progreso, exit codes) cada vez
que se actualice el Transcriptor.

Uso:
    python verify_transcription.py                       # última grabación, completo
    python verify_transcription.py "C:\\ruta\\video.mp4"   # archivo concreto
    python verify_transcription.py --quick               # sin diarización (<1 min)
    python verify_transcription.py --force               # sobreescribir resultado previo

Con --quick se salta la identificación de hablantes (la fase lenta): valida
todo el cableado en un minuto en vez de horas.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

from app.core.config import AppConfig
from app.transcription.integration import result_dir_for
from app.transcription.jobs import DONE, ERROR, JobStore
from app.transcription.worker import TranscriptionWorker


def ultima_grabacion(cfg: AppConfig) -> Path:
    carpeta = Path(cfg.output_dir or ".")
    candidatos = sorted(carpeta.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not candidatos:
        raise SystemExit(f"No hay grabaciones .mp4 en {carpeta}")
    return candidatos[-1]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mp4", nargs="?", help="Grabación a transcribir (default: la más reciente).")
    p.add_argument("--quick", action="store_true", help="Sin diarización (rápido).")
    p.add_argument("--force", action="store_true", help="Sobreescribir un resultado existente.")
    p.add_argument("--timeout", type=int, default=0, help="Máximo en segundos (0 = sin límite).")
    args = p.parse_args()

    cfg = AppConfig.load()
    media = Path(args.mp4) if args.mp4 else ultima_grabacion(cfg)
    if not media.exists():
        raise SystemExit(f"No existe: {media}")

    destino = result_dir_for(media)
    if destino.exists() and not args.force:
        raise SystemExit(
            f"Ya existe una transcripción en {destino}\n"
            "Usa --force para sobreescribirla (ojo: --quick la dejaría sin hablantes)."
        )

    base = Path(tempfile.mkdtemp(prefix="verify_tx_"))
    store = JobStore(base)
    job = store.enqueue(str(media), cfg.transcription_language)
    if args.quick:
        job.no_diarize = True
        store.save(job)

    def on_update(snap: dict) -> None:
        pct = snap.get("progress")
        extra = f" {pct}%" if pct is not None else ""
        print(f"[{time.strftime('%H:%M:%S')}] {snap['status']:<10} {snap.get('stage', '')}{extra}", flush=True)

    worker = TranscriptionWorker(store, lambda: cfg, on_update, is_recording=lambda: False)
    worker.start()
    print(f"Transcribiendo {media.name}" + (" (modo rápido, sin hablantes)" if args.quick else ""))

    t0 = time.time()
    try:
        while True:
            actual = store.find_by_media(str(media))
            if actual and actual.status in (DONE, ERROR):
                break
            if args.timeout and time.time() - t0 > args.timeout:
                print("TIMEOUT — el job sigue en:", actual.status if actual else "?")
                print("Log:", actual.log_path if actual else "?")
                return 2
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nInterrumpido. El subproceso (si arrancó) sigue solo; log en", job.log_path)
        return 130

    if actual.status == ERROR:
        print("\nFALLÓ:", actual.error)
        print("Log:", actual.log_path)
        return 1

    print(f"\nOK en {time.time() - t0:0.0f}s — resultados en {actual.result_dir}")
    for f in sorted(Path(actual.result_dir).iterdir()):
        print("   -", f.name)
    if actual.note:
        print("Nota:", actual.note)
    shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

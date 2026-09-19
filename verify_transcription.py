"""Verificación end-to-end de la integración Recorder → Transcriptor.

Ejecuta el MISMO código que usa la app (cola + worker + subproceso CLI) para
comprobar el cableado completo: elección de pista, extracción de audio, comando,
progreso, hora estimada, artefactos y hablantes.

Uso:
    python verify_transcription.py                        # completo: última grabación entera
    python verify_transcription.py "C:\\ruta\\video.mp4"  # completo, archivo concreto
    python verify_transcription.py --quick                # muestra de 60 s, con hablantes
    python verify_transcription.py --quick --no-speakers  # lo más rápido (sin hablantes)
    python verify_transcription.py --quick --seconds 30   # muestra más corta

`--quick` trabaja SIEMPRE en una carpeta desechable (cola, logs, WAVs, historial
de velocidad y destino): no toca tus transcripciones, tu cola ni lo que la app
aprendió. Antes obligaba a `--force` sobre una transcripción real y por eso no se
podía usar (spec 022).

Códigos de salida: 0 ok · 1 falla de cableado · 2 timeout · 3 entorno · 130 corte.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from app.core.config import AppConfig
from app.encode.ffmpeg import get_ffmpeg_exe
from app.transcription.integration import NO_WINDOW, is_available, result_dir_for
from app.transcription.jobs import DONE, ERROR, JobStore
from app.transcription.worker import TranscriptionWorker

EXIT_OK = 0
EXIT_WIRING = 1
EXIT_TIMEOUT = 2
EXIT_ENV = 3
EXIT_INTERRUPTED = 130

DEFAULT_SAMPLE_SECONDS = 60
ARTIFACTS = ("transcripcion.txt", "transcripcion.srt", "transcripcion.json")


def pick_recording(cfg: AppConfig, explicit: Optional[str] = None) -> Path:
    """Grabación a verificar: la indicada o la más reciente de la carpeta."""
    if explicit:
        media = Path(explicit)
        if not media.exists():
            raise FileNotFoundError(f"No existe: {media}")
        return media
    carpeta = Path(cfg.output_dir or ".")
    candidatos = sorted(carpeta.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not candidatos:
        raise FileNotFoundError(f"No hay grabaciones .mp4 en {carpeta}")
    return candidatos[-1]


def slice_args(media: Path, destino: Path, seconds: int) -> List[str]:
    """ffmpeg para recortar la muestra SIN recodificar.

    `-map 0 -c copy` conserva las pistas y sus nombres: así la verificación
    ejercita de verdad la elección de la pista "Mezcla" (la trampa histórica).
    """
    return [
        get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "0", "-t", str(int(seconds)),
        "-i", str(media), "-map", "0", "-c", "copy", str(destino),
    ]


def build_sample(media: Path, sandbox: Path, seconds: int) -> Path:
    """Crea la muestra dentro del sandbox y devuelve su ruta."""
    sandbox.mkdir(parents=True, exist_ok=True)
    destino = sandbox / f"{media.stem} [muestra {int(seconds)}s]{media.suffix}"
    proc = subprocess.run(
        slice_args(media, destino, seconds),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW,
    )
    if proc.returncode != 0 or not destino.exists() or destino.stat().st_size < 1024:
        detalle = proc.stderr.decode("utf-8", "replace").strip()[-400:]
        raise RuntimeError(f"No se pudo recortar la muestra: {detalle}")
    return destino


def sandbox_paths(sandbox: Path) -> Tuple[Path, Path]:
    """(base de la cola, carpeta de salida) — ambas desechables."""
    return sandbox / "tx", sandbox / "salida"


def speakers_in_result(result_dir: Path) -> int:
    """Hablantes del resultado. El CLI escribe un MAPA {SPEAKER_00: ...}; también
    se aceptan lista o número por si el formato cambia."""
    try:
        data = json.loads((result_dir / "transcripcion.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    hablantes = data.get("hablantes")
    if isinstance(hablantes, (dict, list, tuple, set)):
        return len(hablantes)
    try:
        return int(hablantes or 0)
    except (TypeError, ValueError):
        return 0


def verdict(
    *,
    status: str,
    result_dir: Path,
    updates: Sequence[dict],
    media_name: str,
    want_speakers: bool,
) -> Tuple[int, str, dict]:
    """Veredicto del run: (exit code, motivo, detalles).

    No basta con que exista la transcripción: las fallas reales de este proyecto
    fueron silenciosas (hablantes perdidos con exit 0, estado que dejó de seguir
    la realidad), así que el progreso y los hablantes también se verifican.
    """
    faltantes = [a for a in ARTIFACTS if not (result_dir / a).exists()]
    con_nombre = [u for u in updates if Path(u.get("media_path", "")).name == media_name]
    con_eta = [u for u in updates if float(u.get("eta_epoch") or 0.0) > 0.0]
    hablantes = speakers_in_result(result_dir)
    detalles = {
        "artefactos": [a for a in ARTIFACTS if (result_dir / a).exists()],
        "updates": len(updates),
        "updates_del_archivo": len(con_nombre),
        "con_estimacion": len(con_eta),
        "hablantes": hablantes,
    }
    if status != DONE:
        return EXIT_WIRING, f"el trabajo terminó en estado '{status}'", detalles
    if faltantes:
        return EXIT_WIRING, f"faltan artefactos: {', '.join(faltantes)}", detalles
    if not con_nombre:
        return EXIT_WIRING, "no llegó ningún avance del archivo verificado", detalles
    if not con_eta:
        return EXIT_WIRING, "no llegó ninguna hora estimada de término", detalles
    if want_speakers and hablantes < 1:
        return EXIT_WIRING, "se pidieron hablantes y el resultado no trae ninguno", detalles
    return EXIT_OK, "", detalles


def cleanup_sandbox(sandbox: Path, tries: int = 5) -> bool:
    """Borra el sandbox. Windows tarda en soltar el lock/los logs: reintenta."""
    for intento in range(tries):
        shutil.rmtree(sandbox, ignore_errors=True)
        if not sandbox.exists():
            return True
        time.sleep(0.4 * (intento + 1))
    return not sandbox.exists()


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("mp4", nargs="?", help="Grabación a verificar (default: la más reciente).")
    p.add_argument("--quick", action="store_true",
                   help="Muestra corta en carpeta desechable (no toca tus datos).")
    p.add_argument("--seconds", type=int, default=DEFAULT_SAMPLE_SECONDS,
                   help=f"Duración de la muestra con --quick (default {DEFAULT_SAMPLE_SECONDS}).")
    p.add_argument("--no-speakers", action="store_true",
                   help="Sin identificación de hablantes (más rápido).")
    p.add_argument("--force", action="store_true",
                   help="Solo en modo completo: sobreescribir una transcripción existente.")
    p.add_argument("--timeout", type=int, default=0, help="Máximo en segundos (0 = sin límite).")
    args = p.parse_args(argv)
    if args.force and args.quick:
        p.error("--force no aplica con --quick: el sandbox nunca choca con tus datos.")
    if args.seconds < 5:
        p.error("--seconds mínimo 5.")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    cfg = AppConfig.load()

    if not is_available(cfg.transcriptor_dir):
        print(
            "No encuentro el Transcriptor con su venv en:",
            cfg.transcriptor_dir or "(sin configurar)",
        )
        return EXIT_ENV

    try:
        original = pick_recording(cfg, args.mp4)
    except FileNotFoundError as e:
        print(e)
        return EXIT_ENV

    sandbox = Path(tempfile.mkdtemp(prefix="verify_tx_"))
    worker: Optional[TranscriptionWorker] = None
    ok = False
    try:
        if args.quick:
            try:
                media = build_sample(original, sandbox / "muestra", args.seconds)
            except RuntimeError as e:
                print(e)
                return EXIT_ENV
            queue_base, output_base = sandbox_paths(sandbox)
            print(f"Muestra de {args.seconds}s de {original.name} → sandbox {sandbox}")
        else:
            media = original
            queue_base, output_base = sandbox / "tx", Path(cfg.output_dir or ".")
            destino = result_dir_for(media, output_base=str(output_base))
            if destino.exists() and not args.force:
                print(
                    f"Ya existe una transcripción en {destino}\n"
                    "Usa --force para sobreescribirla, o --quick para verificar sin tocar nada."
                )
                return EXIT_ENV

        store = JobStore(queue_base)
        job = store.enqueue(
            str(media), cfg.transcription_language, output_base=str(output_base)
        )
        if job is None:
            print("No se pudo encolar la muestra.")
            return EXIT_ENV
        if args.no_speakers:
            job.no_diarize = True
            store.save(job)

        updates: List[dict] = []

        def on_update(snap: dict) -> None:
            updates.append(snap)
            pct = snap.get("progress")
            extra = f" {pct}%" if pct is not None else ""
            print(f"[{time.strftime('%H:%M:%S')}] {snap['status']:<10} {snap.get('stage', '')}{extra}",
                  flush=True)

        worker = TranscriptionWorker(store, lambda: cfg, on_update, is_recording=lambda: False)
        worker.start()
        etiqueta = "sin hablantes" if args.no_speakers else "con hablantes"
        print(f"Verificando {media.name} ({etiqueta})")

        t0 = time.time()
        actual = None
        try:
            while True:
                actual = store.find_by_media(str(media))
                if actual and actual.status in (DONE, ERROR):
                    break
                if args.timeout and time.time() - t0 > args.timeout:
                    print("TIMEOUT — el trabajo sigue en:", actual.status if actual else "?")
                    print("Log:", actual.log_path if actual else "?")
                    print("Sandbox conservado:", sandbox)
                    return EXIT_TIMEOUT
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nInterrumpido. El subproceso (si arrancó) sigue solo; log en", job.log_path)
            print("Sandbox conservado:", sandbox)
            return EXIT_INTERRUPTED

        resultado = Path(actual.result_dir) if actual.result_dir else result_dir_for(
            Path(actual.media_path), output_base=actual.output_base or None
        )
        code, motivo, detalles = verdict(
            status=actual.status,
            result_dir=resultado,
            updates=updates,
            media_name=Path(media).name,
            want_speakers=not args.no_speakers,
        )
        elapsed = time.time() - t0
        print()
        if code == EXIT_OK:
            ok = True
            print(f"OK en {elapsed:0.0f}s — cableado completo verificado")
        else:
            print(f"FALLÓ tras {elapsed:0.0f}s — {motivo}")
            if actual.error:
                print("Error del trabajo:", actual.error)
            print("Log:", actual.log_path)
            print("Sandbox conservado:", sandbox)
        print("  Grabación:   ", original.name)
        if args.quick:
            print("  Muestra:     ", f"{args.seconds}s")
        print("  Artefactos:  ", ", ".join(detalles["artefactos"]) or "ninguno")
        print("  Avances:     ", f"{detalles['updates_del_archivo']} del archivo, "
                                 f"{detalles['con_estimacion']} con hora estimada")
        print("  Hablantes:   ", detalles["hablantes"] if not args.no_speakers else "no solicitados")
        if actual.note:
            print("  Nota:        ", actual.note)
        print("  Resultados:  ", resultado)
        return code
    finally:
        if worker is not None:
            worker.shutdown(wait=5.0)  # suelta el lock de la cola temporal
        if ok and not cleanup_sandbox(sandbox):
            print("  (no pude borrar el sandbox:", sandbox, ")")


if __name__ == "__main__":
    sys.exit(main())

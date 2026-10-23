"""Prueba de punta a punta del motor en macOS (spec 030, CI).

1. Instala el motor como lo hace la app al primer uso (`EngineInstaller`).
2. Genera una "reunión" corta: voz de `say` + video negro → MP4.
3. La transcribe por el camino real del worker con `verify_transcription.py`
   (cola, extracción de la pista, CLI, cosecha), en sandbox y sin hablantes.

    python tools/mac_engine_check.py            # instala si hace falta y verifica
    python tools/mac_engine_check.py --skip-install
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.encode.ffmpeg import get_ffmpeg_exe  # noqa: E402
from app.transcription import engine_setup as es  # noqa: E402

TEXTO_ES = (
    "Hola a todos. Esta es una prueba del grabador de reuniones en Mac. "
    "Revisamos el presupuesto del proyecto y acordamos enviar el informe el viernes."
)


def install(timeout: float) -> bool:
    listo = threading.Event()
    resultado = {"ok": False, "error": ""}

    def progreso(paso: int, total: int, etiqueta: str) -> None:
        print(f"  [{paso}/{total}] {etiqueta}", flush=True)

    def fin(ok: bool, error: str) -> None:
        resultado.update(ok=ok, error=error)
        listo.set()

    inicio = time.monotonic()
    es.EngineInstaller(progreso, fin).start()
    if not listo.wait(timeout):
        print("La instalación no terminó a tiempo.")
        return False
    print(f"  instalación: {'OK' if resultado['ok'] else 'FALLÓ'} en {time.monotonic() - inicio:.0f} s")
    if not resultado["ok"]:
        print("  error:", resultado["error"])
        try:
            print(es.setup_log_path().read_text(encoding="utf-8")[-4000:])
        except OSError:
            pass
    return bool(resultado["ok"])


def make_meeting(folder: Path) -> Path:
    aiff = folder / "voz.aiff"
    voces = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    voz = next((v for v in ("Paulina", "Monica", "Mónica", "Jorge", "Juan") if v in voces), None)
    cmd = ["say", "-o", str(aiff)] + (["-v", voz] if voz else []) + [TEXTO_ES]
    subprocess.run(cmd, check=True)
    mp4 = folder / "reunion de prueba.mp4"
    subprocess.run(
        [get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30",
         "-i", str(aiff), "-shortest",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
         str(mp4)],
        check=True,
    )
    print(f"  reunión de prueba: {mp4.name} (voz: {voz or 'por defecto'})")
    return mp4


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--skip-install", action="store_true")
    p.add_argument("--timeout", type=int, default=3600)
    args = p.parse_args()

    if sys.platform != "darwin":
        print("Esta prueba es para macOS.")
        return 2

    print("==> Motor")
    if not args.skip_install and not es.status().ready:
        if not install(args.timeout):
            return 1
    st = es.status()
    print(f"  estado: {st.state} · listo={st.ready} · desactualizado={st.outdated}")
    if not st.ready:
        return 1

    print("==> CLI del motor (--help)")
    from app.core.platform_paths import venv_python

    raiz = es.engine_root()
    ayuda = subprocess.run(
        [str(venv_python(raiz / ".venv")), "-X", "utf8", str(raiz / "transcribe.py"), "--help"],
        cwd=str(raiz), capture_output=True, text=True,
    )
    print(f"  exit {ayuda.returncode}")
    if ayuda.returncode != 0:
        print(ayuda.stdout[-2000:], ayuda.stderr[-4000:])
        return 1

    print("==> Transcripción por el worker (sandbox)")
    with tempfile.TemporaryDirectory(prefix="mac_engine_") as tmp:
        mp4 = make_meeting(Path(tmp))
        cmd = [sys.executable, str(ROOT / "verify_transcription.py"), str(mp4),
               "--quick", "--no-speakers", "--seconds", "15", "--timeout", "1800"]
        code = subprocess.run(cmd, cwd=str(ROOT)).returncode
    if code != 0:
        dump_sandbox_logs()
    print("==> Resultado:", "OK" if code == 0 else f"FALLÓ ({code})")
    return code


def dump_sandbox_logs() -> None:
    """verify_transcription conserva el sandbox si falla: mostrar el log del CLI."""
    base = Path(tempfile.gettempdir())
    for sandbox in sorted(base.glob("verify_tx_*"), key=lambda p: p.stat().st_mtime)[-1:]:
        for log in sorted(sandbox.rglob("*.log")):
            print(f"---- {log.name}")
            try:
                print(log.read_text(encoding="utf-8", errors="replace")[-6000:])
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

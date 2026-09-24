"""Verificación rápida del entorno (sin grabar nada).

Ejecuta:  python smoke_test.py

Comprueba que:
- La app se puede cargar (todas sus dependencias están instaladas).
- FFmpeg está disponible y detecta un encoder H.264.
- Se enumeran ventanas y micrófonos.
- Existe un dispositivo de loopback (audio del sistema).
- (Informativo) si la transcripción está lista: Transcriptor y token de Hugging Face.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _hf_token_configured(transcriptor_dir: str) -> bool:
    """True si el .env del Transcriptor trae un token que no es el de ejemplo."""
    try:
        texto = (Path(transcriptor_dir) / ".env").read_text(encoding="utf-8")
    except OSError:
        return False
    for linea in texto.splitlines():
        clave, _, valor = linea.partition("=")
        if clave.strip() == "HUGGINGFACE_TOKEN":
            valor = valor.strip().strip('"').strip("'")
            return valor.startswith("hf_") and "xxxx" not in valor
    return False


def check_transcription() -> None:
    """Estado de la transcripción. Es opcional: nunca hace fallar el smoke test."""
    print("== Transcripción (opcional) ==")
    try:
        from app.core.config import AppConfig
        from app.transcription.integration import is_available

        cfg = AppConfig.load()
        if not is_available(cfg.transcriptor_dir):
            print("  Sin Transcriptor: la app grabará pero no transcribirá.")
            print("  Instálalo junto a esta carpeta (README, paso B).")
            return
        print("  Transcriptor:", cfg.transcriptor_dir)
        if _hf_token_configured(cfg.transcriptor_dir):
            print("  Token de Hugging Face: configurado")
        else:
            print("  AVISO: sin token de Hugging Face en su .env -> transcribirá SIN hablantes.")
    except Exception as exc:
        print("  AVISO:", exc)


def main() -> int:
    # La consola de Windows usa cp1252 por defecto; forzamos UTF-8 para acentos.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ok = True

    print("== App ==")
    try:
        import app.ui.main_window  # noqa: F401 — carga toda la app, sin abrir ventana

        print("  OK: la app carga con todas sus dependencias")
    except Exception as exc:
        ok = False
        print("  ERROR:", exc)
        print("  Reinstala las dependencias: python -m pip install -r requirements.txt")

    print("== FFmpeg ==")
    try:
        from app.encode.ffmpeg import detect_h264_encoder, get_ffmpeg_exe

        print("  ffmpeg:", get_ffmpeg_exe())
        print("  encoder H.264 detectado:", detect_h264_encoder())
    except Exception as exc:
        ok = False
        print("  ERROR:", exc)

    print("== Ventanas (fuentes de video) ==")
    try:
        from app.capture.windows_video import list_windows

        wins = list_windows()
        print(f"  {len(wins)} ventanas encontradas")
        for w in wins[:8]:
            print("   -", w.title)
    except Exception as exc:
        ok = False
        print("  ERROR:", exc)

    print("== Micrófonos ==")
    try:
        from app.capture.windows_audio import list_microphones

        mics = list_microphones()
        print(f"  {len(mics)} micrófonos encontrados")
        for m in mics[:8]:
            print(f"   - [{m.index}] {m.name} ({m.channels}ch @ {m.sample_rate}Hz)")
    except Exception as exc:
        ok = False
        print("  ERROR:", exc)

    print("== Audio del sistema (loopback WASAPI) ==")
    if sys.platform == "win32":
        try:
            import pyaudiowpatch as pyaudio

            pa = pyaudio.PyAudio()
            wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            speakers = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
            loop = None
            if speakers.get("isLoopbackDevice", False):
                loop = speakers
            else:
                for lb in pa.get_loopback_device_info_generator():
                    if speakers["name"] in lb["name"]:
                        loop = lb
                        break
            if loop:
                print(
                    f"  OK: '{loop['name']}' "
                    f"({loop['maxInputChannels']}ch @ {int(loop['defaultSampleRate'])}Hz)"
                )
            else:
                ok = False
                print("  ERROR: no se encontró dispositivo de loopback")
            pa.terminate()
        except Exception as exc:
            ok = False
            print("  ERROR:", exc)
    else:
        print("  (omitido: solo Windows en la Fase 1)")

    check_transcription()

    print()
    print("RESULTADO:", "OK" if ok else "HAY ERRORES")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

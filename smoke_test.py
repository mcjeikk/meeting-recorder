"""Verificación rápida del entorno (sin grabar nada).

Ejecuta:  python smoke_test.py

Comprueba que:
- FFmpeg está disponible y detecta un encoder H.264.
- Se enumeran ventanas y micrófonos.
- Existe un dispositivo de loopback (audio del sistema).
"""
from __future__ import annotations

import sys


def main() -> int:
    # La consola de Windows usa cp1252 por defecto; forzamos UTF-8 para acentos.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ok = True

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

    print()
    print("RESULTADO:", "OK" if ok else "HAY ERRORES")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Entrada del .app de macOS (spec 030).

`--self-check` no abre ventanas: comprueba que el paquete trae todo lo que la
app necesita (módulos nativos, ffmpeg con su encoder, el código y los locks del
Transcriptor y `uv`) e imprime un JSON. Lo usa el CI sobre el .app ya armado,
que es lo que el usuario descarga — no sobre el árbol de fuentes.
"""
from __future__ import annotations

import json
import os
import sys


def _self_check() -> int:
    informe: dict = {"ok": True}

    def falla(clave: str, valor) -> None:
        informe[clave] = valor
        informe["ok"] = False

    try:
        import AVFoundation  # noqa: F401
        import CoreMedia  # noqa: F401
        import Quartz  # noqa: F401
        import ScreenCaptureKit  # noqa: F401
        import libdispatch  # noqa: F401
        import numpy  # noqa: F401
        import objc  # noqa: F401
        import psutil  # noqa: F401
        import sounddevice  # noqa: F401
        from PySide6 import QtWidgets  # noqa: F401

        import app.capture.mac_sck  # noqa: F401
        import app.ui.main_window  # noqa: F401

        informe["imports"] = "ok"
    except Exception as e:  # noqa: BLE001
        falla("imports", repr(e))

    try:
        from app.encode.ffmpeg import detect_h264_encoder, get_ffmpeg_exe

        ff = get_ffmpeg_exe()
        informe["ffmpeg"] = ff
        if not os.path.exists(ff):
            falla("ffmpeg", f"no existe: {ff}")
        informe["encoder"] = detect_h264_encoder()
    except Exception as e:  # noqa: BLE001
        falla("ffmpeg", repr(e))

    try:
        from app.transcription import engine_setup as es

        src = es.bundled_source_dir()
        informe["transcriptor"] = str(src)
        if not (src / "transcribe.py").exists():
            falla("transcriptor", f"falta transcribe.py en {src}")
        faltan = [n for n in (es.LOCK_MACOS, es.LOCK_MACOS13) if not (src / n).exists()]
        if faltan:
            falla("locks", faltan)
        if (src / ".env").exists():
            falla("secreto", "el paquete trae un .env (token): no debe viajar")
        uv = es.uv_executable()
        informe["uv"] = uv
        if not uv:
            falla("uv", "no viene en el paquete")
    except Exception as e:  # noqa: BLE001
        falla("engine", repr(e))

    texto = json.dumps(informe, ensure_ascii=False, indent=1)
    print(texto)
    destino = os.environ.get("MR_SELF_CHECK_OUT")
    if destino:
        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto)
    return 0 if informe["ok"] else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(_self_check())
    from app.main import main

    raise SystemExit(main())

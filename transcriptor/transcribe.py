#!/usr/bin/env python
"""
Transcriptor de Reuniones (local, CPU) con identificación de hablantes.

Ejemplos:
    python transcribe.py "reunion.m4a"
    python transcribe.py "C:\\audios" --batch
    python transcribe.py audio.mp3 --speakers 4 --names "Ana,Carlos"
    python transcribe.py audio.wav --no-diarize
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from pipeline import asr as asr_mod
from pipeline import audio as audio_mod
from pipeline import merge as merge_mod
from pipeline import output as output_mod

RAIZ = Path(__file__).resolve().parent

# ---- consola (rich es opcional) ----
try:
    from rich.console import Console
    _RICH = True
    _con = Console()
except Exception:  # pragma: no cover
    _RICH = False
    _con = None

# Modo plano para integraciones (p. ej. el Grabador lanza este script con la
# salida redirigida a un archivo de log): sin rich, el fallback imprime líneas
# estables tipo "transcribiendo... NN%" que un programa puede parsear.
if os.environ.get("TRANSCRIPTOR_PLAIN") == "1":
    _RICH = False
    _con = None


def info(msg: str) -> None:
    if _RICH:
        _con.print(msg)
    else:
        print(msg)


def cargar_config() -> dict:
    cfg_path = RAIZ / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def parsear_args():
    p = argparse.ArgumentParser(
        description="Transcribe reuniones e identifica hablantes (local, CPU).",
    )
    p.add_argument("entrada", help="Archivo de audio o carpeta (con --batch).")
    p.add_argument("--batch", action="store_true", help="Procesar todos los audios de una carpeta.")
    p.add_argument("--model", dest="modelo", help="Modelo Whisper (large-v3-turbo, large-v3, medium, small).")
    p.add_argument("--language", dest="idioma", help="Idioma ISO (es, en, ...) o 'auto'.")
    p.add_argument("--speakers", type=int, help="Número exacto de hablantes (si lo conoces).")
    p.add_argument("--min-speakers", dest="min_speakers", type=int)
    p.add_argument("--max-speakers", dest="max_speakers", type=int)
    p.add_argument("--no-diarize", action="store_true", help="Solo transcribir (sin identificar hablantes).")
    p.add_argument("--names", help="Nombres de hablantes separados por coma, en orden de aparición.")
    p.add_argument("--compute-type", dest="compute_type")
    p.add_argument("--device", choices=["auto", "cuda", "cpu"], help="auto = GPU si existe, si no CPU.")
    p.add_argument("--beam-size", dest="beam_size", type=int)
    p.add_argument("--threads", dest="cpu_threads", type=int, help="Nº de hilos de CPU (0 = todos).")
    p.add_argument("--no-vad", action="store_true", help="Desactivar el filtro de silencios (VAD).")
    p.add_argument("--formats", dest="formatos", help="Formatos de salida separados por coma (txt,srt,json).")
    p.add_argument("--output", dest="carpeta_salida", help="Carpeta de salida.")
    return p.parse_args()


def opciones_efectivas(args, cfg: dict) -> dict:
    return {
        "modelo": args.modelo or cfg.get("modelo", "large-v3-turbo"),
        "idioma": args.idioma or cfg.get("idioma", "es"),
        "compute_type": args.compute_type or cfg.get("compute_type", "int8"),
        "device": args.device or cfg.get("device", "auto"),
        "cpu_threads": args.cpu_threads if args.cpu_threads is not None else cfg.get("cpu_threads", 0),
        "beam_size": args.beam_size if args.beam_size is not None else cfg.get("beam_size", 5),
        "vad_filter": (not args.no_vad) and cfg.get("vad_filter", True),
        "diarizar": (not args.no_diarize) and cfg.get("diarizar", True),
        "num_speakers": args.speakers if args.speakers is not None else cfg.get("num_speakers"),
        "min_speakers": args.min_speakers if args.min_speakers is not None else cfg.get("min_speakers"),
        "max_speakers": args.max_speakers if args.max_speakers is not None else cfg.get("max_speakers"),
        "formatos": (
            [s.strip() for s in args.formatos.split(",")]
            if args.formatos else cfg.get("formatos", ["txt", "srt", "json"])
        ),
        "carpeta_salida": args.carpeta_salida or cfg.get("carpeta_salida", "output"),
        "nombres": (
            [s.strip() for s in args.names.split(",")]
            if args.names else cfg.get("nombres_hablantes", [])
        ),
    }


def listar_entradas(entrada: Path, batch: bool) -> list[Path]:
    if entrada.is_dir() or batch:
        if not entrada.is_dir():
            raise SystemExit(f"No es una carpeta: {entrada}")
        archivos = sorted(
            p for p in entrada.iterdir() if p.suffix.lower() in audio_mod.AUDIO_EXTS
        )
        if not archivos:
            raise SystemExit(f"No se encontraron audios en {entrada}")
        return archivos
    if not entrada.exists():
        raise SystemExit(f"No existe el archivo: {entrada}")
    return [entrada]


def _transcribir_con_progreso(wav: Path, o: dict) -> dict:
    kwargs = dict(
        modelo=o["modelo"], idioma=o["idioma"], compute_type=o["compute_type"],
        cpu_threads=o["cpu_threads"], beam_size=o["beam_size"], vad_filter=o["vad_filter"],
        device=o["device"],
    )
    if _RICH:
        from rich.progress import (
            BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn,
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(), TaskProgressColumn(), TimeElapsedColumn(),
            console=_con, transient=True,
        ) as prog:
            task = prog.add_task("    transcribiendo", total=None)

            def cb(actual: float, total: float):
                prog.update(task, total=total, completed=min(actual, total) if total else actual)

            return asr_mod.transcribir(wav, on_progress=cb, **kwargs)
    else:
        estado = {"pct": -10}

        def cb(actual: float, total: float):
            if total:
                pct = int(100 * actual / total)
                if pct >= estado["pct"] + 10:
                    estado["pct"] = pct
                    print(f"    transcribiendo... {pct}%")

        return asr_mod.transcribir(wav, on_progress=cb, **kwargs)


def procesar_archivo(archivo: Path, o: dict, hf_token: str | None) -> Path:
    info(f"\n> Procesando: {archivo.name}")
    t0 = time.time()
    turnos: list[dict] = []

    with tempfile.TemporaryDirectory() as tmp:
        info("  - Convirtiendo audio a WAV 16 kHz...")
        wav = audio_mod.convertir_a_wav16k(archivo, Path(tmp))

        info(f"  - Transcribiendo (modelo {o['modelo']}, idioma {o['idioma']})...")
        asr = _transcribir_con_progreso(wav, o)
        info(f"    -> dispositivo: {asr.get('device', 'cpu')}")

        if o["diarizar"] and hf_token:
            info("  - Identificando hablantes (diarizacion)...")
            try:
                from pipeline import diarize as diarize_mod
                turnos = diarize_mod.diarizar(
                    wav, hf_token,
                    num_speakers=o["num_speakers"],
                    min_speakers=o["min_speakers"],
                    max_speakers=o["max_speakers"],
                )
                n = len({t["speaker"] for t in turnos})
                info(f"    -> {n} hablante(s) detectado(s)")
            except Exception as e:  # noqa: BLE001
                # Si la diarizacion falla (p. ej. memoria), no perdemos la
                # transcripcion: se guarda solo el texto, sin etiquetas de hablante.
                info(f"  [!] La diarizacion no se completo ({type(e).__name__}: {e}).")
                info("      Se guardara SOLO la transcripcion (sin etiquetas de hablante).")
                turnos = []

    segmentos = asr["segmentos"]
    palabras = asr["palabras"]

    if turnos:
        if palabras:
            merge_mod.asignar_hablantes(palabras, turnos)
            bloques = merge_mod.agrupar_en_bloques(palabras, "word", separador="")
        else:
            merge_mod.asignar_hablantes(segmentos, turnos)
            bloques = merge_mod.agrupar_en_bloques(segmentos, "text", separador=" ")
        mapa = output_mod.construir_mapa_hablantes(bloques, o["nombres"])
    else:
        bloques = [
            {"speaker": None, "start": s["start"], "end": s["end"], "text": s["text"].strip()}
            for s in segmentos
        ]
        mapa = {}

    encabezado = {"archivo": archivo.name, "idioma": asr["idioma"], "duracion": asr["duracion"]}
    carpeta = RAIZ / o["carpeta_salida"] / archivo.stem
    generados = output_mod.escribir_salidas(carpeta, o["formatos"], bloques, mapa, segmentos, encabezado)

    info(f"  OK en {time.time() - t0:0.0f}s  ->  {carpeta}")
    for g in generados:
        info(f"      - {g.name}")
    return carpeta


def main():
    args = parsear_args()
    cfg = cargar_config()
    o = opciones_efectivas(args, cfg)

    load_dotenv(RAIZ / ".env")
    load_dotenv()  # también un .env del directorio actual, si existe
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if hf_token and hf_token.startswith("hf_xxx"):
        hf_token = None  # placeholder del .env.example

    if o["diarizar"] and not hf_token:
        info("[!] Diarizacion solicitada pero no hay HUGGINGFACE_TOKEN configurado.")
        info("    Se hara SOLO la transcripcion (sin identificar hablantes).")
        info("    Para activar hablantes: crea un token en huggingface.co/settings/tokens,")
        info("    acepta la licencia de 'pyannote/speaker-diarization-community-1' y ponlo en .env")
        o["diarizar"] = False

    if not audio_mod.ffmpeg_disponible():
        info("[!] No se encontro ffmpeg en el PATH. Instalalo con: winget install Gyan.FFmpeg")

    entrada = Path(args.entrada)
    archivos = listar_entradas(entrada, args.batch)
    info(f"Archivos a procesar: {len(archivos)}")

    errores = 0
    for f in archivos:
        try:
            procesar_archivo(f, o, hf_token)
        except Exception as e:  # noqa: BLE001
            errores += 1
            info(f"  [X] Error con {f.name}: {e}")

    info(f"\nFinalizado. {len(archivos) - errores}/{len(archivos)} archivo(s) correctos.")
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()

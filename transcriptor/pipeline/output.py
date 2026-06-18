"""Escritura de resultados: .txt legible, .srt y .json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _hms(segundos: float) -> str:
    s = int(round(segundos))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _srt_ts(segundos: float) -> str:
    ms = int(round(segundos * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def construir_mapa_hablantes(bloques: list[dict], nombres: Optional[list[str]]) -> dict:
    """Mapea los IDs de pyannote (SPEAKER_00...) a 'Hablante N' o a nombres reales."""
    nombres = nombres or []
    orden: list[str] = []
    for b in bloques:
        spk = b.get("speaker")
        if spk is not None and spk not in orden:
            orden.append(spk)
    mapa = {}
    for i, spk in enumerate(orden):
        mapa[spk] = nombres[i] if i < len(nombres) else f"Hablante {i + 1}"
    return mapa


def _etiqueta(spk, mapa: dict) -> str:
    if spk is None:
        return ""
    return mapa.get(spk, str(spk))


def escribir_txt(path: Path, bloques, mapa, encabezado: Optional[dict] = None):
    lineas: list[str] = []
    if encabezado:
        lineas.append(f"# Transcripción: {encabezado.get('archivo', '')}")
        if encabezado.get("duracion"):
            lineas.append(
                f"# Duración: {_hms(encabezado['duracion'])}   Idioma: {encabezado.get('idioma', '')}"
            )
        if mapa:
            lineas.append(f"# Hablantes: {', '.join(dict.fromkeys(mapa.values()))}")
        lineas.append("")
    for b in bloques:
        etq = _etiqueta(b.get("speaker"), mapa)
        rango = f"[{_hms(b['start'])} -> {_hms(b['end'])}]"
        lineas.append(f"{rango} {etq}: {b['text']}" if etq else f"{rango} {b['text']}")
    path.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def escribir_srt(path: Path, bloques, mapa):
    out: list[str] = []
    for i, b in enumerate(bloques, 1):
        etq = _etiqueta(b.get("speaker"), mapa)
        texto = f"{etq}: {b['text']}" if etq else b["text"]
        out.append(str(i))
        out.append(f"{_srt_ts(b['start'])} --> {_srt_ts(b['end'])}")
        out.append(texto)
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8")


def escribir_json(path: Path, bloques, mapa, segmentos, encabezado):
    data = {
        "archivo": encabezado.get("archivo"),
        "idioma": encabezado.get("idioma"),
        "duracion_seg": encabezado.get("duracion"),
        "hablantes": mapa,
        "bloques": [
            {
                "inicio": b["start"],
                "fin": b["end"],
                "hablante": _etiqueta(b.get("speaker"), mapa),
                "hablante_id": b.get("speaker"),
                "texto": b["text"],
            }
            for b in bloques
        ],
        "segmentos": segmentos,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def escribir_salidas(carpeta: Path, formatos, bloques, mapa, segmentos, encabezado) -> list[Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    generados: list[Path] = []
    if "txt" in formatos:
        p = carpeta / "transcripcion.txt"
        escribir_txt(p, bloques, mapa, encabezado)
        generados.append(p)
    if "srt" in formatos:
        p = carpeta / "transcripcion.srt"
        escribir_srt(p, bloques, mapa)
        generados.append(p)
    if "json" in formatos:
        p = carpeta / "transcripcion.json"
        escribir_json(p, bloques, mapa, segmentos, encabezado)
        generados.append(p)
    return generados

"""Fusión de transcripción y diarización por solape temporal."""
from __future__ import annotations


def _solape(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def asignar_hablantes(items: list[dict], turnos: list[dict], por_defecto: str = "SPEAKER_00") -> list[dict]:
    """Asigna a cada item (palabra o segmento) el hablante con mayor solape temporal.

    Modifica los items en sitio añadiendo la clave 'speaker'.
    """
    ultimo = por_defecto
    for it in items:
        s, e = it.get("start"), it.get("end")
        if s is None or e is None:
            it["speaker"] = ultimo
            continue
        mejor, mejor_ov = None, 0.0
        for t in turnos:
            ov = _solape(s, e, t["start"], t["end"])
            if ov > mejor_ov:
                mejor_ov, mejor = ov, t["speaker"]
        it["speaker"] = mejor if mejor is not None else ultimo
        ultimo = it["speaker"]
    return items


def agrupar_en_bloques(items: list[dict], clave_texto: str, separador: str = "") -> list[dict]:
    """Agrupa items consecutivos del mismo hablante en bloques (turnos de habla)."""
    bloques: list[dict] = []
    for it in items:
        spk = it.get("speaker")
        pieza = it[clave_texto]
        if bloques and bloques[-1]["speaker"] == spk:
            bloques[-1]["end"] = it["end"]
            bloques[-1]["_piezas"].append(pieza)
        else:
            bloques.append({
                "speaker": spk,
                "start": it["start"],
                "end": it["end"],
                "_piezas": [pieza],
            })
    for b in bloques:
        texto = separador.join(b.pop("_piezas"))
        # normaliza espacios (evita dobles espacios al concatenar)
        b["text"] = " ".join(texto.split())
    return bloques


def fusionar_segmentos_cercanos(
    segmentos: list[dict],
    max_gap: float = 0.8,
    max_block: float = 28.0,
) -> list[dict]:
    """Une segmentos ASR consecutivos cuando la pausa es corta.

    Sin diarización, faster-whisper deja cientos/miles de micro-frases
    ("O sea...", "Entonces...") que parecen una transcripción incompleta.
    Agrupar por proximidad mejora la lectura del .txt/.srt sin inventar texto.
    """
    if not segmentos:
        return []
    out: list[dict] = []
    cur = {
        "start": segmentos[0]["start"],
        "end": segmentos[0]["end"],
        "text": (segmentos[0].get("text") or "").strip(),
    }
    for seg in segmentos[1:]:
        gap = float(seg["start"]) - float(cur["end"])
        nuevo_fin = float(seg["end"])
        pieza = (seg.get("text") or "").strip()
        if gap <= max_gap and (nuevo_fin - float(cur["start"])) <= max_block:
            cur["end"] = nuevo_fin
            if pieza:
                cur["text"] = f"{cur['text']} {pieza}".strip() if cur["text"] else pieza
        else:
            cur["text"] = " ".join(cur["text"].split())
            out.append(cur)
            cur = {"start": seg["start"], "end": seg["end"], "text": pieza}
    cur["text"] = " ".join(cur["text"].split())
    out.append(cur)
    return out

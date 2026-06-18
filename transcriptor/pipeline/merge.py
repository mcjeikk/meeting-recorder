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

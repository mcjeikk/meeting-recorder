"""Resumen de una cola desatendida a partir del rastro (spec 026).

Lee `%LOCALAPPDATA%\\MeetingRecorder\\transcripts\\events.jsonl` (y su rotado) y
cuenta, por archivo: en qué fases estuvo, cómo terminó, cuánto tardó de verdad y
cuánto se equivocó la hora prometida. No necesita que la app esté abierta.

Uso:
    python tools/night_report.py                 # el rastro de esta máquina
    python tools/night_report.py --hours 12      # solo las últimas 12 horas
    python tools/night_report.py otro.jsonl      # un rastro concreto
    python tools/night_report.py --raw           # además, la lista de decisiones
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.transcription.event_log import default_path, read_trail  # noqa: E402

DECISIONS = (
    "startup", "run_start", "adopted", "live", "harvest", "requeued",
    "not_promoted", "paused", "resumed", "degraded", "retry", "failed",
    "settled", "speed",
)


def hhmm(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch)).strftime("%H:%M:%S") if epoch else "--:--:--"


def mmss(seconds: float) -> str:
    seconds = int(max(0.0, float(seconds)))
    if seconds >= 3600:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"
    return f"{seconds // 60}m{seconds % 60:02d}s"


def per_file(events: Sequence[dict]) -> Dict[str, dict]:
    """Agrupa el rastro por archivo, en orden de aparición."""
    files: Dict[str, dict] = {}

    def slot(name: str) -> dict:
        if name not in files:
            files[name] = {
                "name": name, "phases": [], "first_eta": None, "first_eta_t": None,
                "last_pct": None, "status": "", "note": "", "error": "",
                "started": None, "finished": None, "batch": (0, 0),
                "pauses": 0, "degraded": [], "retries": 0, "speed": None,
            }
        return files[name]

    for e in events:
        name = str(e.get("file") or "")
        if not name:
            continue
        f = slot(name)
        kind = e.get("kind")
        t = float(e.get("t") or 0.0)
        if kind == "ui":
            fase = str(e.get("stage") or "")
            if fase and (not f["phases"] or f["phases"][-1][1] != fase):
                f["phases"].append((t, fase))
            if e.get("progress") is not None:
                f["last_pct"] = e.get("progress")
            eta = float(e.get("eta_epoch") or 0.0)
            if eta and f["first_eta"] is None and e.get("status") == "running":
                f["first_eta"], f["first_eta_t"] = eta, t
            if e.get("batch_total"):
                f["batch"] = (e.get("batch_pos"), e.get("batch_total"))
            if f["started"] is None and e.get("status") in ("extracting", "running"):
                f["started"] = t
        elif kind == "paused":
            f["pauses"] += 1
        elif kind == "degraded":
            f["degraded"].append(str(e.get("why") or ""))
        elif kind == "retry":
            f["retries"] += 1
        elif kind == "speed":
            f["speed"] = e
        elif kind in ("settled", "failed"):
            f["status"] = str(e.get("status") or "")
            f["note"] = str(e.get("note") or "") or f["note"]
            f["error"] = str(e.get("error") or "") or f["error"]
            f["finished"] = t
    return files


def report(events: List[dict], raw: bool = False) -> int:
    if not events:
        print("El rastro está vacío. ¿Se abrió la app después de instalar esto?")
        return 1

    t0, t1 = float(events[0]["t"]), float(events[-1]["t"])
    print(f"Rastro de {hhmm(t0)} a {hhmm(t1)}  ({mmss(t1 - t0)}, {len(events)} entradas)")

    runs = [e for e in events if e.get("kind") == "run_start"]
    print(f"Ejecuciones del motor: {len(runs)}")
    for r in runs:
        archivos = r.get("files") or []
        print(
            f"  {hhmm(r['t'])}  pid {r.get('pid')}  {len(archivos)} archivo(s)"
            f"  {r.get('model')}  {'sin hablantes' if r.get('no_diarize') else 'con hablantes'}"
            f"  PC {r.get('pc_impact')}"
        )
        for a in archivos:
            print(f"                 - {a}")

    files = per_file(events)
    print(f"\nArchivos vistos: {len(files)}")
    problemas = []
    for f in files.values():
        real = (f["finished"] - f["started"]) if (f["finished"] and f["started"]) else 0.0
        cabecera = f"\n  {f['name'][:70]}"
        if f["batch"][1]:
            cabecera += f"   (archivo {f['batch'][0]} de {f['batch'][1]})"
        print(cabecera)
        estado = f["status"] or "sin desenlace registrado"
        print(f"    estado:     {estado}" + (f"  · {f['note']}" if f["note"] else ""))
        if real:
            print(f"    tardó:      {mmss(real)}")
        if f["first_eta"] and f["finished"]:
            prometido = f["first_eta"] - f["first_eta_t"]
            de_verdad = f["finished"] - f["first_eta_t"]
            error = prometido - de_verdad
            signo = "+" if error >= 0 else ""
            pct = (error / de_verdad * 100) if de_verdad else 0.0
            print(
                f"    prometía:   {mmss(prometido)} y fueron {mmss(de_verdad)}"
                f"   ({signo}{int(error)}s, {signo}{pct:.0f}%)"
            )
            # En archivos de menos de 2 min manda el piso de 60 s del estimado:
            # el desvío porcentual ahí no dice nada (spec 025, hallazgo F2).
            if abs(pct) > 25 and de_verdad >= 120:
                problemas.append(f"{f['name'][:40]}: estimación {signo}{pct:.0f}%")
        if f["speed"]:
            s = f["speed"]
            print(
                f"    velocidad:  {s.get('factor')}x el audio"
                f"  (aprendido ahora: {s.get('learned_factor')}x)"
            )
        if f["pauses"]:
            print(f"    pausas por grabación: {f['pauses']}")
        if f["degraded"]:
            print(f"    degradado:  {', '.join(f['degraded'])}")
            problemas.append(f"{f['name'][:40]}: degradado ({f['degraded'][0]})")
        if f["retries"]:
            print(f"    reintentos: {f['retries']}")
            problemas.append(f"{f['name'][:40]}: {f['retries']} reintento(s)")
        if f["error"]:
            print(f"    error:      {f['error'][:150]}")
            problemas.append(f"{f['name'][:40]}: {f['error'][:60]}")
        fases = " → ".join(p[1][:34] for p in f["phases"][:8])
        if fases:
            print(f"    fases:      {fases}")

    if raw:
        print("\nDecisiones, en orden:")
        for e in events:
            if e.get("kind") in DECISIONS and e.get("kind") != "ui":
                extra = {k: v for k, v in e.items() if k not in ("t", "hora", "kind")}
                print(f"  {e.get('hora')}  {e.get('kind'):<13} {extra}")

    print()
    if problemas:
        print("Para mirar:")
        for p in problemas:
            print(f"  - {p}")
    else:
        print("Nada raro: ningún reintento, degradación ni estimación muy desviada.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("trail", nargs="?", help="Rastro a leer (default: el de esta máquina).")
    p.add_argument("--hours", type=float, default=0.0, help="Solo las últimas N horas.")
    p.add_argument("--raw", action="store_true", help="Listar también cada decisión.")
    args = p.parse_args(argv)

    destino = Path(args.trail) if args.trail else default_path()
    eventos = read_trail(destino)
    if args.hours > 0 and eventos:
        corte = float(eventos[-1]["t"]) - args.hours * 3600
        eventos = [e for e in eventos if float(e.get("t") or 0) >= corte]
    if not eventos:
        print(f"Sin entradas en {destino}")
        return 1
    return report(eventos, raw=args.raw)


if __name__ == "__main__":
    sys.exit(main())

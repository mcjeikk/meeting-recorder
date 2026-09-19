"""Rastro de lo que la app mostró y decidió, para revisar una cola desatendida.

Una línea JSON por momento, junto a la cola que describe (spec 026). Es
diagnóstico y nada más: **ninguna decisión de cola, reintento, proceso o
estimación lee esto**, y cualquier fallo al escribirlo se traga en silencio —
una noche de transcripciones no se arruina por no poder anotarla.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

# Tope por archivo; al pasarlo, el actual pasa a ".1" y se empieza uno nuevo.
# Una noche larga escribe unos cientos de KB: el tope es para años, no para noches.
MAX_BYTES = 8 * 1024 * 1024


class EventLog:
    """Escritor append-only que nunca levanta una excepción."""

    def __init__(self, path: Path, max_bytes: int = MAX_BYTES) -> None:
        self.path = Path(path)
        self.max_bytes = int(max_bytes)

    def append(self, kind: str, **fields: Any) -> None:
        """Anota un momento. Si no se puede, no pasa nada (a propósito)."""
        try:
            ahora = time.time()
            entrada: Dict[str, Any] = {
                "t": round(ahora, 3),
                "hora": datetime.fromtimestamp(ahora).strftime("%Y-%m-%d %H:%M:%S"),
                "kind": str(kind),
            }
            entrada.update(fields)
            linea = json.dumps(entrada, ensure_ascii=False, default=str)
            self._rotate_if_needed()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except Exception:  # noqa: BLE001 — el rastro jamás debe estorbar
            pass

    def snapshot(self, snap: Dict[str, Any]) -> None:
        """Anota un estado tal como lo recibió la ventana."""
        self.append(
            "ui",
            id=snap.get("id"),
            file=_stem(snap.get("media_path")),
            status=snap.get("status"),
            stage=snap.get("stage"),
            progress=snap.get("progress"),
            eta_epoch=snap.get("eta_epoch"),
            batch_pos=snap.get("batch_pos"),
            batch_total=snap.get("batch_total"),
            batch_eta_epoch=snap.get("batch_eta_epoch"),
            paused=snap.get("eta_paused"),
            note=snap.get("note") or "",
            error=(snap.get("error") or "")[:300],
        )

    def _rotate_if_needed(self) -> None:
        try:
            if self.path.stat().st_size < self.max_bytes:
                return
        except OSError:
            return  # todavía no existe: nada que rotar
        previo = self.path.with_suffix(self.path.suffix + ".1")
        try:
            self.path.replace(previo)  # el más reciente siempre sobrevive
        except OSError:
            pass


def _stem(media_path: Any) -> str:
    try:
        return Path(str(media_path or "")).stem
    except (TypeError, ValueError):
        return ""


def read_events(path: Path) -> Iterator[Dict[str, Any]]:
    """Entradas completas del rastro; una línea a medias (corte de luz) se salta."""
    try:
        with Path(path).open("r", encoding="utf-8", errors="replace") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    dato = json.loads(linea)
                except ValueError:
                    continue
                if isinstance(dato, dict):
                    yield dato
    except OSError:
        return


def read_trail(path: Path) -> list:
    """El rastro entero en orden: primero el rotado, luego el actual."""
    previo = Path(str(path) + ".1")
    return list(read_events(previo)) + list(read_events(Path(path)))


def default_path(base: Optional[Path] = None) -> Path:
    """`events.jsonl` junto a la cola (fuera de OneDrive)."""
    if base is None:
        from app.transcription.integration import transcripts_base

        base = transcripts_base()
    return Path(base) / "events.jsonl"

"""Reloj maestro para sincronizar video + audio del sistema + micrófono, con pausa.

Cada flujo (video, sistema, micrófono) arranca como un subproceso/hilo
independiente y no comienzan EXACTAMENTE en el mismo instante. Además, la app
permite PAUSAR: el tiempo en pausa NO debe contar en la grabación final.

Por eso el reloj trabaja en "tiempo grabado" = tiempo de pared menos el total
pausado. Todos los desfases de segmentos se miden en este tiempo grabado, de modo
que al unir los segmentos de video (concatenados) y colocar los de audio (adelay)
todo queda alineado y sin huecos por las pausas.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class MasterClock:
    """Mide el tiempo grabado (excluyendo pausas) y el inicio de cada flujo."""

    _t0: float = field(default_factory=time.perf_counter)
    _paused_total: float = 0.0
    _pause_started: Optional[float] = None
    _starts: Dict[str, float] = field(default_factory=dict)

    def reset(self) -> None:
        self._t0 = time.perf_counter()
        self._paused_total = 0.0
        self._pause_started = None
        self._starts.clear()

    # --- tiempo grabado ------------------------------------------------------
    def recorded_now(self) -> float:
        """Segundos grabados hasta ahora (sin contar el tiempo en pausa)."""
        now = time.perf_counter()
        paused = self._paused_total
        if self._pause_started is not None:
            paused += now - self._pause_started
        return max(0.0, now - self._t0 - paused)

    def pause(self) -> None:
        if self._pause_started is None:
            self._pause_started = time.perf_counter()

    def resume(self) -> None:
        if self._pause_started is not None:
            self._paused_total += time.perf_counter() - self._pause_started
            self._pause_started = None

    @property
    def is_paused(self) -> bool:
        return self._pause_started is not None

    # --- marcas de inicio de flujos -----------------------------------------
    def mark_start(self, stream: str) -> None:
        """Registra (en tiempo grabado) cuándo arrancó un flujo."""
        if stream not in self._starts:
            self._starts[stream] = self.recorded_now()

    def get_start(self, stream: str) -> Optional[float]:
        return self._starts.get(stream)

    def offset_seconds(self, stream: str, reference: str = "video") -> float:
        """Desfase (en tiempo grabado) de `stream` respecto a `reference`."""
        if stream not in self._starts or reference not in self._starts:
            return 0.0
        return self._starts[stream] - self._starts[reference]

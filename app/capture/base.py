"""Contratos (interfaces) comunes de captura.

La idea es que el resto de la app (orquestador y UI) NO dependa de Windows.
Cada sistema operativo implementa estas clases a su manera:
- Windows: `windows_video.py`, `windows_audio.py`
- macOS (Fase 3) y Linux (Fase 4): se añadirán implementaciones equivalentes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class VideoCapture(ABC):
    """Captura de video hacia un archivo (solo video, sin audio)."""

    @abstractmethod
    def start(self, output_path: str) -> None:
        """Comienza a grabar video en `output_path` (contenedor MKV)."""

    @abstractmethod
    def stop(self) -> None:
        """Detiene la grabación de forma ordenada (cierra el archivo)."""


class AudioCapture(ABC):
    """Captura de un flujo de audio hacia un archivo WAV."""

    @abstractmethod
    def start(self, output_path: str) -> None:
        """Comienza a grabar audio en `output_path` (WAV PCM)."""

    @abstractmethod
    def stop(self) -> None:
        """Detiene la captura y cierra el archivo."""

    def current_level(self) -> float:
        """Nivel de audio actual (0.0–1.0) para los medidores de la UI.

        Las implementaciones que no lo soporten devuelven 0.0.
        """
        return 0.0

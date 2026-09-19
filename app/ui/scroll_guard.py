"""Evita que listas desplegables cambien de valor al hacer scroll de la ventana.

Qt cambia el ítem de un QComboBox con la rueda aunque el control no tenga
foco (QTBUG-19730). En un formulario con scroll eso muta ajustes por accidente.
Patrón de la comunidad Qt: StrongFocus + ignorar Wheel si no hay foco, para
que el gesto llegue al contenedor.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QWidget


class WheelFocusFilter(QObject):
    """Rueda: solo el control enfocado cambia; si no, el evento se ignora (scroll padre)."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel and isinstance(
            watched, (QComboBox, QAbstractSpinBox)
        ):
            if not watched.hasFocus():
                event.ignore()
                return True
        return False


def guard_wheel_unless_focused(widget: QWidget, owner: QObject) -> None:
    """Instala el filtro en `widget` y lo deja vivo como hijo de `owner`."""
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    filt = getattr(owner, "_wheel_focus_filter", None)
    if filt is None:
        filt = WheelFocusFilter(owner)
        owner._wheel_focus_filter = filt  # noqa: SLF001 — un filtro por ventana
    widget.installEventFilter(filt)

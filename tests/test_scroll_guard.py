"""Rueda del mouse no debe mutar un combo sin foco."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from app.ui.scroll_guard import guard_wheel_unless_focused


def _wheel(widget: QWidget) -> QWheelEvent:
    local = QPointF(widget.rect().center())
    glob = QPointF(widget.mapToGlobal(widget.rect().center()))
    return QWheelEvent(
        local,
        glob,
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


class TestWheelGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_unfocused_combo_keeps_index(self) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["uno", "dos", "tres"])
        combo.setCurrentIndex(0)
        guard_wheel_unless_focused(combo, host)
        combo.clearFocus()
        self.assertFalse(combo.hasFocus())
        self.app.sendEvent(combo, _wheel(combo))
        self.assertEqual(combo.currentIndex(), 0)

    def test_filter_blocks_only_without_focus(self) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["uno", "dos"])
        guard_wheel_unless_focused(combo, host)
        filt = host._wheel_focus_filter
        with patch.object(combo, "hasFocus", return_value=False):
            self.assertTrue(filt.eventFilter(combo, _wheel(combo)))
        with patch.object(combo, "hasFocus", return_value=True):
            self.assertFalse(filt.eventFilter(combo, _wheel(combo)))


if __name__ == "__main__":
    unittest.main()

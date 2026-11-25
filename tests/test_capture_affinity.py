"""Checkbox: ocultar o no esta ventana en grabaciones/capturas."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from app.ui.capture_affinity import (
    WDA_EXCLUDEFROMCAPTURE,
    WDA_NONE,
    affinity_flag,
)


class TestAffinityFlag(unittest.TestCase):
    def test_checked_excludes(self) -> None:
        self.assertEqual(affinity_flag(True), WDA_EXCLUDEFROMCAPTURE)
        self.assertEqual(affinity_flag(False), WDA_NONE)


@unittest.skipUnless(os.environ.get("QT_QPA_PLATFORM") != "skip", "Qt UI")
class TestCaptureAffinityCheckbox(unittest.TestCase):
    def test_checkbox_default_on_and_persists_toggle(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from tests.qml_window import click, item, make_window

        w = make_window(self)
        click(w, "tab2")
        check = item(w, "hideSelf")
        self.assertTrue(check.property("checked"))
        check.forceActiveFocus()
        QTest.keyClick(w.view, Qt.Key_Space)
        self.app.processEvents()
        self.assertFalse(w._config.exclude_window_from_capture)
        self.assertFalse(check.property("checked"))
        w._config.save.assert_called_once()
        w._apply_capture_affinity.assert_called()

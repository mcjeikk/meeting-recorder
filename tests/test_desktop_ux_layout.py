"""Layout clásico: paneles agrupados, Grabar en el flujo, rueda no hijackea combos."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch


@unittest.skipUnless(os.environ.get("QT_QPA_PLATFORM") != "skip", "Qt UI")
class TestDesktopUxLayout(unittest.TestCase):
    def test_classic_groupboxes_and_record_label(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QGroupBox

        app = QApplication.instance() or QApplication(sys.argv)
        from app.ui.main_window import MainWindow

        with patch("app.ui.main_window.threading.Thread") as thr:
            thr.return_value = MagicMock()
            with patch.object(MainWindow, "_update_preview", lambda self: None):
                with patch("app.ui.main_window.AudioMonitor"):
                    w = MainWindow()
        try:
            self.assertTrue(w.findChildren(QGroupBox))
            self.assertIn("Grabar", w._record_btn.text())
            self.assertTrue(hasattr(w, "_hide_self_check"))
            self.assertEqual(w._source_combo.focusPolicy(), Qt.FocusPolicy.StrongFocus)
            self.assertIn("#2ecc71", w.styleSheet().lower())
            self.assertIn("Transcribir archivo", w._tx_file_btn.text())
            self.assertTrue(hasattr(w, "_tx_speakers"))
            self.assertTrue(hasattr(w, "_tx_impact"))
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()

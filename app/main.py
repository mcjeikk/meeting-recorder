"""Punto de entrada de la aplicación.

Ejecuta:  python -m app.main
"""
from __future__ import annotations

import signal
import sys


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow, app_icon

    # En Windows, declarar un AppUserModelID propio para que la barra de tareas
    # muestre NUESTRO ícono (y no el de pythonw.exe) y agrupe bien la ventana.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "MeetingRecorder.GrabadorReuniones"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Grabador de Reuniones")
    app.setWindowIcon(app_icon())
    if sys.platform == "win32":
        import ctypes

        ERROR_ALREADY_EXISTS = 183
        handle = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Local\\MeetingRecorder.Grabador.SingleInstance"
        )
        app._recorder_mutex = handle  # noqa: SLF001 — vive con el proceso
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                None,
                "Grabador de Reuniones",
                "Ya hay una ventana del Grabador abierta.\n"
                "Usa esa; una segunda copia deja la cola de transcripción a medias.",
            )
            return 0
    # Al cerrar la última ventana, salir del proceso.
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow()
    window.show()

    # Permitir cerrar con Ctrl+C desde la consola. El bucle de Qt bloquea las
    # señales de Python; un temporizador que despierta el intérprete cada 200 ms
    # deja que la señal se procese.
    def _handle_sigint(*_args):
        window._quit_after_finalize = False
        app.quit()

    try:
        signal.signal(signal.SIGINT, _handle_sigint)
    except Exception:
        pass
    keepalive = QTimer()
    keepalive.start(200)
    keepalive.timeout.connect(lambda: None)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

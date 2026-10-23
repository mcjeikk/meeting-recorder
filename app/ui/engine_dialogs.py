"""Panel del motor de transcripción en macOS (spec 030).

Vive dentro del grupo de salida/transcripción y solo existe en macOS: allí el
motor se instala al primer uso. Muestra en qué estado está, pide permiso antes
de descargar ~1,5 GB, enseña el avance, se pausa si empieza una grabación y
permite guardar el token de Hugging Face para identificar hablantes.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.transcription import engine_setup as es
from app.transcription import hf_token as hf

_CONSENT_TEXT = (
    "Para transcribir, la app necesita su motor (Whisper para el texto y "
    "pyannote para los hablantes).\n\n"
    "• Se descargan unos 1,5 GB (y la primera transcripción baja además los "
    "modelos, ~1,5 GB más).\n"
    "• Se instala en ~/Library/Application Support/MeetingRecorder/engine.\n"
    "• Todo corre en tu Mac: tus grabaciones no salen de él.\n"
    "• Si empiezas a grabar, la instalación se pausa sola.\n\n"
    "¿Instalar ahora?"
)


def _label(text: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lbl


class EnginePanel(QWidget):
    readiness_changed = Signal(bool)
    _progress_sig = Signal(int, int, str)
    _done_sig = Signal(bool, str)

    def __init__(self, is_recording: Callable[[], bool], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_recording = is_recording
        self._installer: Optional[es.EngineInstaller] = None
        self._paused_by_recording = False
        self._last_ready: Optional[bool] = None
        self._auto_update_tried = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        self._status = _label()
        lay.addWidget(self._status)
        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setMaximumHeight(8)
        self._bar.setVisible(False)
        lay.addWidget(self._bar)
        fila = QHBoxLayout()
        self._install_btn = QPushButton("Instalar motor…")
        self._install_btn.setCursor(Qt.PointingHandCursor)
        self._install_btn.clicked.connect(self._ask_and_install)
        self._token_btn = QPushButton("Hablantes (token)…")
        self._token_btn.setCursor(Qt.PointingHandCursor)
        self._token_btn.setToolTip("Token de Hugging Face para identificar quién habla.")
        self._token_btn.clicked.connect(self._edit_token)
        self._log_btn = QPushButton("Ver registro")
        self._log_btn.clicked.connect(self._open_log)
        for b in (self._install_btn, self._token_btn, self._log_btn):
            fila.addWidget(b)
        fila.addStretch(1)
        lay.addLayout(fila)

        self._progress_sig.connect(self._on_progress)
        self._done_sig.connect(self._on_done)

        try:
            if es.status().ready:
                es.sync_sources()  # código nuevo de la app, mismo entorno
        except Exception:
            pass

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._refresh()

    # --- consultas ------------------------------------------------------------------
    def is_ready(self) -> bool:
        return es.is_ready()

    def offer_install_if_needed(self) -> None:
        """Se llama cuando el usuario quiere transcribir y aún no hay motor."""
        st = es.status()
        if not st.ready and not self._busy():
            self._ask_and_install()

    def _busy(self) -> bool:
        return bool(self._installer and self._installer.is_running())

    # --- ciclo ----------------------------------------------------------------------
    def _tick(self) -> None:
        if self._busy():
            grabando = bool(self._is_recording())
            if grabando and not self._paused_by_recording:
                self._installer.pause()
                self._paused_by_recording = True
                self._status.setText("Instalación del motor en pausa: se está grabando.")
            elif not grabando and self._paused_by_recording:
                self._installer.resume()
                self._paused_by_recording = False
            return
        st = es.status()
        if (st.ready and st.outdated and st.consented and not self._auto_update_tried
                and not self._is_recording()):
            self._auto_update_tried = True  # si falla, no reintentar en bucle
            self._start_install()  # actualización: el motor actual sigue sirviendo
            return
        self._refresh(st)

    def _refresh(self, st: Optional[es.EngineStatus] = None) -> None:
        st = st or es.status()
        token = hf.read_token(es.engine_root() / ".env")
        if st.ready:
            hablantes = (
                f"hablantes activados ({hf.mask(token)})" if token
                else "sin token: transcribe, pero sin identificar hablantes"
            )
            self._status.setText(f"Motor de transcripción listo · {hablantes}.")
            self._install_btn.setVisible(False)
        elif st.state == es.FAILED:
            self._status.setText(f"La instalación del motor falló: {st.error}")
            self._install_btn.setText("Reintentar instalación")
            self._install_btn.setVisible(True)
        else:
            self._status.setText(
                "Falta el motor de transcripción (se instala una vez, ~1,5 GB). "
                "Las grabaciones que pidas transcribir esperan en la cola."
            )
            self._install_btn.setText("Instalar motor…")
            self._install_btn.setVisible(True)
        self._token_btn.setEnabled(st.ready)
        self._log_btn.setVisible(es.setup_log_path().exists())
        if st.ready != self._last_ready:
            self._last_ready = st.ready
            self.readiness_changed.emit(st.ready)

    # --- instalación ------------------------------------------------------------------
    def _ask_and_install(self) -> None:
        if self._busy():
            return
        r = QMessageBox.question(self, "Instalar el motor de transcripción", _CONSENT_TEXT)
        if r == QMessageBox.Yes:
            self._start_install()

    def _start_install(self) -> None:
        self._installer = es.EngineInstaller(self._progress_sig.emit, self._done_sig.emit)
        self._paused_by_recording = False
        self._install_btn.setVisible(False)
        self._bar.setRange(0, len(es.STEPS))
        self._bar.setValue(0)
        self._bar.setVisible(True)
        self._status.setText("Preparando la instalación del motor…")
        self._installer.start()

    def _on_progress(self, step: int, total: int, label: str) -> None:
        self._bar.setRange(0, total)
        self._bar.setValue(step - 1)
        if not self._paused_by_recording:
            self._status.setText(f"Instalando el motor ({step} de {total}): {label}…")

    def _on_done(self, ok: bool, error: str) -> None:
        self._bar.setVisible(False)
        self._installer = None
        self._refresh()
        if ok and not hf.read_token(es.engine_root() / ".env"):
            r = QMessageBox.question(
                self,
                "Motor instalado",
                "El motor ya está listo y las transcripciones pendientes empiezan solas.\n\n"
                "¿Quieres configurar ahora la identificación de hablantes? "
                "(necesita una cuenta gratuita de Hugging Face)",
            )
            if r == QMessageBox.Yes:
                self._edit_token()
        elif not ok:
            QMessageBox.warning(
                self, "No se pudo instalar el motor",
                f"{error}\n\nPuedes reintentarlo desde el panel; el detalle está en «Ver registro».",
            )

    def _open_log(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(es.setup_log_path())))

    # --- token ----------------------------------------------------------------------
    def _edit_token(self) -> None:
        TokenDialog(self).exec()
        self._refresh()


class TokenDialog(QDialog):
    _checked_sig = Signal(object, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Identificar hablantes")
        self.setMinimumWidth(460)
        self._env = es.engine_root() / ".env"
        actual = hf.read_token(self._env)

        lay = QVBoxLayout(self)
        intro = QLabel(
            "Para saber quién dijo qué, el modelo de hablantes (pyannote) pide una "
            "cuenta gratuita de Hugging Face:<br><br>"
            f"1. Crea un token de lectura en <a href='{hf.TOKENS_URL}'>huggingface.co/settings/tokens</a>.<br>"
            f"2. Abre <a href='{hf.MODEL_URL}'>el modelo de hablantes</a> y acepta sus términos "
            "(«Agree and access»).<br>"
            "3. Pega el token aquí."
        )
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)
        lay.addWidget(intro)
        self._edit = QLineEdit()
        self._edit.setEchoMode(QLineEdit.Password)
        self._edit.setPlaceholderText(f"Guardado: {hf.mask(actual)}" if actual else "hf_…")
        lay.addWidget(self._edit)
        self._result = _label("El token se guarda solo en este Mac, en la carpeta del motor.")
        lay.addWidget(self._result)

        botones = QDialogButtonBox()
        self._save_btn = botones.addButton("Comprobar y guardar", QDialogButtonBox.AcceptRole)
        self._remove_btn = botones.addButton("Quitar token", QDialogButtonBox.DestructiveRole)
        self._remove_btn.setVisible(bool(actual))
        botones.addButton("Cerrar", QDialogButtonBox.RejectRole)
        self._save_btn.clicked.connect(self._check)
        self._remove_btn.clicked.connect(self._remove)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)
        self._checked_sig.connect(self._on_checked)

    def _check(self) -> None:
        token = self._edit.text().strip()
        self._save_btn.setEnabled(False)
        self._result.setText("Comprobando con Hugging Face…")
        threading.Thread(
            target=lambda: self._checked_sig.emit(hf.validate(token), token), daemon=True
        ).start()

    def _on_checked(self, check: hf.Check, token: str) -> None:
        self._save_btn.setEnabled(True)
        if check.result == hf.INVALID:
            self._result.setText(check.message)
            return
        hf.write_token(self._env, token)
        self._edit.clear()
        self._edit.setPlaceholderText(f"Guardado: {hf.mask(token)}")
        self._remove_btn.setVisible(True)
        if check.result == hf.OK:
            quien = f" (cuenta {check.user})" if check.user else ""
            self._result.setText(f"✓ {check.message}{quien}")
        elif check.result == hf.TERMS:
            self._result.setText(f"Guardado, pero falta un paso: {check.message}")
        else:
            self._result.setText(f"Guardado sin comprobar: {check.message}")

    def _remove(self) -> None:
        hf.write_token(self._env, None)
        self._remove_btn.setVisible(False)
        self._edit.setPlaceholderText("hf_…")
        self._result.setText("Token quitado: se transcribirá sin identificar hablantes.")

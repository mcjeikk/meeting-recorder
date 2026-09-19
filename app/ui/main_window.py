"""Ventana principal (PySide6) — tema oscuro moderno.

Funciones de la interfaz:
- Selección de fuente (ventana / pantalla) con VISTA PREVIA (miniatura).
- Selección de micrófono que se puede CAMBIAR EN VIVO durante la grabación.
- Interruptor de audio del sistema, con medidores de nivel de color.
- Botón grande Grabar/Detener + Pausar/Reanudar, cronómetro e indicador de grabación.
- Ícono en la bandeja del sistema y atajos de teclado GLOBALES (Ctrl+Shift+R/P).
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QSize, QEvent
from PySide6.QtGui import (
    QAction,
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app.capture.monitor import AudioMonitor
from app.core.config import (
    AppConfig,
    AudioDevice,
    RecordingSettings,
    VideoSource,
    apply_selected_output_dir,
    default_output_dir,
    resolve_output_dir,
)
from app.core.output_path import (
    dest_file_path,
    ffmpeg_path_too_long,
    folder_looks_unusable,
    load_pending,
)
from app.core.mic_usage import (
    is_microphone_in_use_by_others,
    microphone_users,
    should_apply_follow_meeting_mute,
)
from app.core.orchestrator import Recorder
from app.transcription.import_media import (
    ALREADY_DONE,
    enqueue_imports,
    file_dialog_filter,
    summarize_import_results,
)
from app.transcription.integration import is_available as transcriptor_disponible
from app.transcription.jobs import JobStore, normalize_language, normalize_num_speakers
from app.transcription.queue_status import (
    batch_eta_text,
    batch_suffix,
    eta_suffix,
    format_queue_line,
    visible_queue_jobs,
)
from app.ui.device_watcher import DeviceChangeWatcher, hotplug_action
from app.ui.flow_layout import FlowLayout
from app.ui.scroll_guard import guard_wheel_unless_focused
from app.transcription.pc_impact import (
    PC_IMPACT_ORDER,
    get_pc_impact,
    normalize_pc_impact,
)
from app.transcription.presets import (
    PRESET_ORDER,
    get_preset,
    normalize_preset,
)
from app.transcription.worker import TranscriptionWorker
from app.ui.hotkeys import GlobalHotkeys
from app.ui.capture_affinity import apply_window_capture_affinity
from app.ui.preview_policy import (
    should_pause_idle_wgc_preview,
    transcription_status_is_open,
)
# --- Paleta y estilos (tema oscuro) -----------------------------------------
_ACCENT = "#2ecc71"
_DANGER = "#e74c3c"
_STYLE = f"""
QMainWindow, QWidget#central {{ background:#1e1f24; }}
QScrollArea {{ background:#1e1f24; border: none; }}
QLabel {{ color:#e6e6e6; }}
QLabel#muted {{ color:#9aa0a8; }}
QGroupBox {{
    background:#2a2c33; border:1px solid #34373f; border-radius:10px;
    margin-top:14px; padding:10px; color:#e6e6e6; font-weight:bold;
}}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 4px; color:#9aa0a8; }}
QComboBox, QLineEdit {{
    background:#1a1b1f; color:#e6e6e6; border:1px solid #34373f;
    border-radius:6px; padding:6px 8px; min-height:18px;
}}
QComboBox:disabled {{ color:#6b7077; }}
QComboBox QAbstractItemView {{ background:#1a1b1f; color:#e6e6e6; selection-background-color:#2ecc71; }}
QListWidget {{
    background:#1a1b1f; color:#e6e6e6; border:1px solid #34373f;
    border-radius:6px; outline: 0;
}}
QListWidget::item {{ color:#e6e6e6; padding:4px 8px; }}
QListWidget::item:selected {{ background:#34373f; }}
QPushButton {{
    background:#34373f; color:#e6e6e6; border:none; border-radius:6px; padding:8px 12px;
}}
QPushButton:hover {{ background:#3d414a; }}
QPushButton:disabled {{ color:#6b7077; background:#2a2c33; }}
QCheckBox {{ color:#e6e6e6; spacing:8px; }}
QCheckBox::indicator {{ width:16px; height:16px; }}
QProgressBar {{ background:#15161a; border:none; border-radius:4px; }}
QProgressBar::chunk {{
    border-radius:4px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #2ecc71, stop:0.6 #2ecc71, stop:0.8 #f1c40f, stop:1 #e74c3c);
}}
QFrame#banner {{ background:#163b29; border:1px solid #1e9e54; border-radius:8px; }}
QFrame#banner QLabel {{ color:#eafff2; font-weight:bold; }}
"""

_MSGBOX_QSS = (
    "QMessageBox { background:#23252b; }"
    "QMessageBox QLabel { color:#e8e8e8; font-size:13px; }"
    "QMessageBox QPushButton { background:#34373f; color:#e6e6e6; border:none;"
    " border-radius:6px; padding:7px 18px; min-width:72px; }"
    "QMessageBox QPushButton:hover { background:#3d414a; }"
)

_RECORD_BTN = (
    "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
    " stop:0 #34e07a, stop:1 #1e9e54); color:#06210f; font-size:17px; font-weight:bold;"
    " border-radius:10px; padding:15px; } QPushButton:hover { background:#33d977; }"
    " QPushButton:disabled { background:#2f5c43; color:#cfe6da; }"
)
_STOP_BTN = (
    "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
    " stop:0 #ef5b4a, stop:1 #c0392b); color:white; font-size:17px; font-weight:bold;"
    " border-radius:10px; padding:15px; } QPushButton:hover { background:#e74c3c; }"
)
_BUSY_BAR = (
    "QProgressBar { background:#15161a; border:none; border-radius:3px; }"
    "QProgressBar::chunk { background:#3b82f6; border-radius:3px; }"
)


def meter_display_levels(
    mic_level: float,
    system_level: float,
    *,
    mic_muted: bool,
    system_enabled: bool,
) -> tuple[float, float]:
    """VU levels for the UI: inactive sources show as silence (empty bars)."""
    return (
        0.0 if mic_muted else float(mic_level),
        0.0 if not system_enabled else float(system_level),
    )


def _make_dot_icon(color: str, size: int = 64) -> QIcon:
    """Genera un ícono circular (para la bandeja)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(int(size * 0.12), int(size * 0.12), int(size * 0.76), int(size * 0.76))
    p.end()
    return QIcon(pm)


def app_icon() -> QIcon:
    """Ícono de la app: usa assets/icon.ico si existe, si no uno generado."""
    ico = Path(__file__).resolve().parents[2] / "assets" / "icon.ico"
    if ico.exists():
        return QIcon(str(ico))
    return _make_dot_icon(_DANGER)


def _prep_combo(combo: QComboBox, owner=None) -> None:
    """Combo elástico; la rueda no cambia el valor si el control no tiene foco."""
    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(10)
    combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    if owner is not None:
        guard_wheel_unless_focused(combo, owner)


class _WrapLabel(QLabel):
    """QLabel con word-wrap cuyo sizeHint NO reclama el ancho del texto sin envolver."""

    def __init__(self, text: str = "", *, muted: bool = False) -> None:
        super().__init__(text)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        if muted:
            self.setObjectName("muted")

    def hasHeightForWidth(self) -> bool:
        return True

    def minimumSizeHint(self):
        # Permite encoger; la altura real la da heightForWidth en el layout.
        return QSize(0, 0)

    def sizeHint(self):
        # Ancho preferido compacto: sin esto Qt usa el texto en una sola línea
        # y la ventana "no es responsive".
        w = 160
        return QSize(w, max(16, self.heightForWidth(w)))


def _wrap_label(text: str, *, muted: bool = False) -> QLabel:
    return _WrapLabel(text, muted=muted)


def _wrapping_check(text: str) -> tuple[QWidget, QCheckBox]:
    """Casilla + etiqueta con word-wrap (QCheckBox no envuelve el texto solo)."""
    wrap = QWidget()
    wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    cb = QCheckBox()
    cb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    class _ToggleLabel(_WrapLabel):
        def mousePressEvent(self, event) -> None:  # noqa: N802
            cb.toggle()
            super().mousePressEvent(event)

    clickable = _ToggleLabel(text)
    clickable.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    row.addWidget(cb, 0, Qt.AlignTop)
    row.addWidget(clickable, 1)
    return wrap, cb


class MainWindow(QMainWindow):
    # Señales para actualizar la UI desde hilos de fondo de forma segura.
    _status_sig = Signal(str)
    _finished_sig = Signal(str)
    _error_sig = Signal(str)
    _save_failed_sig = Signal(str)
    _started_sig = Signal()
    _progress_sig = Signal(int)
    _tx_update_sig = Signal(dict)  # snapshots del worker de transcripción
    _preview_ready_sig = Signal(object, int)  # QImage, generation

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grabador de Reuniones")
        # Mínimo bajo: el QScrollArea absorbe el resto (scroll H/V).
        self.setMinimumSize(360, 320)
        self.setWindowIcon(app_icon())
        self.setStyleSheet(_STYLE)

        self._config = AppConfig.load()
        self._windows: List[VideoSource] = []
        self._mics: List[AudioDevice] = []
        self._last_output: Optional[str] = None
        self._blink_on = False
        self._preview_counter = 0
        self._preview_busy = False
        self._preview_dirty = False
        self._preview_gen = 0
        self._quit_after_finalize = False
        self._hotkeys_registered = False
        self._own_hint = os.path.basename(sys.executable)  # para excluirnos en la detección
        # Último others_using visto por auto-mute (None = aún no muestreado /
        # rearmado). Solo aplicamos mute en flancos para no pisar el mute manual.
        self._auto_mute_others_prev: Optional[bool] = None
        self._monitor = AudioMonitor()  # medidores en vivo cuando NO se graba
        self._pending_mic_hotplug_refresh = False
        self._sys_silent_ticks = 0
        self._sys_silence_warned = False
        self._hotplug_debounce = QTimer(self)
        self._hotplug_debounce.setSingleShot(True)
        self._hotplug_debounce.setInterval(800)
        self._hotplug_debounce.timeout.connect(self._on_hotplug_debounce)
        self._hotplug_followup = QTimer(self)
        self._hotplug_followup.setSingleShot(True)
        self._hotplug_followup.setInterval(2000)
        self._hotplug_followup.timeout.connect(self._on_hotplug_followup)

        self._recorder = Recorder(
            on_status=self._status_sig.emit,
            on_finished=self._finished_sig.emit,
            on_error=self._error_sig.emit,
            on_progress=self._progress_sig.emit,
            on_save_failed=self._save_failed_sig.emit,
        )
        self._status_sig.connect(self._set_status)
        self._finished_sig.connect(self._on_finished)
        self._error_sig.connect(self._on_error)
        self._save_failed_sig.connect(self._on_save_failed)
        self._started_sig.connect(self._on_started)
        self._progress_sig.connect(self._on_progress)
        self._busy = False

        # Transcripción (Fase 2): cola persistente + worker en hilo de fondo.
        # El worker emite snapshots por señal (mismo patrón que el Recorder) y
        # consulta is_recording() para no competir jamás con una grabación.
        self._tx_last: dict = {}
        self._tx_store = JobStore()
        self._tx_worker = TranscriptionWorker(
            self._tx_store,
            get_config=lambda: self._config,
            on_update=self._tx_update_sig.emit,
            is_recording=self._recorder.is_recording,
        )
        self._tx_update_sig.connect(self._on_tx_update)
        self._preview_ready_sig.connect(self._on_preview_ready)

        self._build_ui()
        self._setup_tray()
        self._setup_hotkeys()
        self._setup_device_watcher()
        self._refresh_sources()
        self._refresh_mics()
        self._apply_saved_config()
        self._update_mute_button()
        self._update_preview()

        # Tamaño inicial compacto (no forzar el ancho del sizeHint del contenido,
        # que con combos/banners largos hincha la ventana y parece "no responsive").
        avail = QGuiApplication.primaryScreen().availableGeometry()
        init_w = min(480, max(400, avail.width() // 3), avail.width() - 40)
        init_h = min(720, avail.height() - 60)
        self.resize(init_w, init_h)
        frame = self.frameGeometry()
        frame.moveCenter(avail.center())
        self.move(frame.topLeft())

        # Arranca el worker DESPUÉS de construir la UI: reconcilia trabajos
        # pendientes de sesiones anteriores y los retoma solo.
        self._tx_worker.start()
        try:
            self._tx_worker.apply_pc_impact(self._config.transcription_pc_impact)
        except Exception:
            pass

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # Pre-cargar la detección de encoder en segundo plano para que el PRIMER
        # "Grabar" sea inmediato (si no, la primera vez tardaría ~1 s probando).
        threading.Thread(target=self._prewarm_encoder, daemon=True).start()
        QTimer.singleShot(0, self._offer_pending_save)

    def _prewarm_encoder(self) -> None:
        try:
            from app.encode.ffmpeg import detect_h264_encoder

            detect_h264_encoder()
        except Exception:
            pass

    # --- construcción de la interfaz ----------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = _wrap_label("Grabador de Reuniones")
        title.setStyleSheet("font-size:18px; font-weight:bold;")
        self._rec_dot = QLabel("●")
        self._rec_dot.setStyleSheet(f"color:{_DANGER}; font-size:16px;")
        self._rec_dot.setVisible(False)
        header.addWidget(title, 1)
        header.addWidget(self._rec_dot, 0, Qt.AlignTop)
        root.addLayout(header)

        prev_box = QGroupBox("Vista previa")
        prev_lay = QVBoxLayout(prev_box)
        self._preview = QLabel("Sin vista previa")
        self._preview.setObjectName("muted")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumSize(160, 120)
        self._preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._preview.setStyleSheet("background:#15161a; border-radius:8px;")
        prev_lay.addWidget(self._preview)
        root.addWidget(prev_box, 1)

        src_box = QGroupBox("1. Fuente de captura")
        src_lay = QVBoxLayout(src_box)
        self._source_combo = QComboBox()
        _prep_combo(self._source_combo, self)
        self._source_combo.currentIndexChanged.connect(self._update_preview)
        self._refresh_btn = QPushButton("🔄 Actualizar")
        self._refresh_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._refresh_btn.clicked.connect(self._on_refresh)
        src_lay.addWidget(self._source_combo)
        src_btns = FlowLayout(h_spacing=8, v_spacing=6)
        src_btns.addWidget(self._refresh_btn)
        src_lay.addLayout(src_btns)
        hide_wrap, self._hide_self_check = _wrapping_check(
            "No capturar esta ventana"
        )
        self._hide_self_check.setToolTip(
            "Marcado: el Grabador no aparece en la grabación ni en recortes "
            "(Win+Shift+S). Desmárcalo si quieres que se vea en la imagen."
        )
        self._hide_self_check.setChecked(True)
        self._hide_self_check.toggled.connect(self._on_hide_self_toggled)
        src_lay.addWidget(hide_wrap)
        root.addWidget(src_box)

        mic_box = QGroupBox("2. Micrófono")
        mic_lay = QVBoxLayout(mic_box)
        self._mic_combo = QComboBox()
        _prep_combo(self._mic_combo, self)
        self._mic_combo.activated.connect(self._on_mic_activated)
        self._mic_refresh_btn = QPushButton("🔄 Actualizar")
        self._mic_refresh_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._mic_refresh_btn.clicked.connect(self._on_refresh_mics)
        self._mute_btn = QPushButton("🎤 Activo")
        self._mute_btn.setMaximumWidth(130)
        self._mute_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._mute_btn.clicked.connect(self._toggle_mute)
        mic_lay.addWidget(self._mic_combo)
        mic_btns = FlowLayout(h_spacing=8, v_spacing=6)
        mic_btns.addWidget(self._mic_refresh_btn)
        mic_btns.addWidget(self._mute_btn)
        mic_lay.addLayout(mic_btns)
        self._mic_meter = self._make_meter()
        mic_lay.addWidget(self._mic_meter)
        mic_lay.addWidget(
            _wrap_label("Cámbialo o siléncialo durante la grabación.", muted=True)
        )
        self._mic_usage_label = _wrap_label("Micrófono del sistema: …", muted=True)
        mic_lay.addWidget(self._mic_usage_label)
        auto_wrap, self._auto_mute_check = _wrapping_check(
            "Auto-silenciar fuera de llamada (experimental)"
        )
        self._auto_mute_check.setToolTip(
            "Si Windows no ve a Teams/Zoom (u otra app) usando el micrófono, "
            "graba silencio en tu pista. Cuando detecta una llamada, vuelve a "
            "grabar tu voz.\n\n"
            "Solo actúa al entrar/salir de llamada: un mute manual durante la "
            "llamada se respeta hasta el siguiente cambio de estado.\n\n"
            "No detecta el botón de mute DENTRO de Teams: si Teams sigue "
            "capturando el mic, Windows cree que hay llamada. Para eso usa "
            "🔇 o Ctrl+Shift+M."
        )
        self._auto_mute_check.toggled.connect(self._on_auto_mute_toggled)
        mic_lay.addWidget(auto_wrap)
        root.addWidget(mic_box)

        sys_box = QGroupBox("3. Audio del sistema")
        sys_lay = QVBoxLayout(sys_box)
        sys_lay.addWidget(
            _wrap_label("Lo que escuchas en la reunión / escritorio.", muted=True)
        )
        sys_wrap, self._sys_check = _wrapping_check("Grabar el audio del sistema")
        self._sys_check.setToolTip("Lo que escuchas en la reunión o el escritorio.")
        self._sys_check.setChecked(True)
        self._sys_meter = self._make_meter()
        sys_lay.addWidget(sys_wrap)
        sys_lay.addWidget(self._sys_meter)
        self._sys_route_label = _wrap_label("", muted=True)
        sys_lay.addWidget(self._sys_route_label)
        aec_wrap, self._aec_check = _wrapping_check(
            "Reducir eco del micrófono (útil si grabas con altavoces)"
        )
        sys_lay.addWidget(aec_wrap)
        root.addWidget(sys_box)

        out_box = QGroupBox("4. Carpeta de salida")
        out_v = QVBoxLayout(out_box)
        self._out_edit = QLineEdit()
        self._out_edit.setReadOnly(True)
        self._out_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        out_btn = QPushButton("Cambiar…")
        out_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        out_btn.clicked.connect(self._choose_output)
        out_v.addWidget(self._out_edit)
        out_btns = FlowLayout(h_spacing=8, v_spacing=6)
        out_btns.addWidget(out_btn)
        out_v.addLayout(out_btns)
        tx_wrap, self._tx_check = _wrapping_check("📝 Transcribir al terminar")
        out_v.addWidget(tx_wrap)
        self._tx_file_btn = QPushButton("Transcribir archivo…")
        self._tx_file_btn.setCursor(Qt.PointingHandCursor)
        self._tx_file_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._tx_file_btn.setToolTip(
            "El original no se mueve. La transcripción va a Carpeta de salida"
            "\\Transcripciones."
        )
        self._tx_file_btn.clicked.connect(self._choose_transcribe_files)
        out_v.addWidget(self._tx_file_btn)
        self._tx_file_hint = _wrap_label(
            "Suelta un archivo: va a Carpeta de salida\\Transcripciones.",
            muted=True,
        )
        out_v.addWidget(self._tx_file_hint)
        self._tx_import_status = _wrap_label("", muted=True)
        self._tx_import_status.setVisible(False)
        out_v.addWidget(self._tx_import_status)
        self._tx_queue_list = QListWidget()
        self._tx_queue_list.setMinimumHeight(48)
        self._tx_queue_list.setMaximumHeight(96)
        self._tx_queue_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._tx_queue_list.itemSelectionChanged.connect(self._on_tx_queue_selected)
        self._tx_queue_list.setVisible(False)
        out_v.addWidget(self._tx_queue_list)
        self._tx_queue_empty = _wrap_label("Nada en cola.", muted=True)
        self._tx_queue_empty.setVisible(False)
        out_v.addWidget(self._tx_queue_empty)
        out_v.addWidget(_wrap_label("Velocidad / calidad:", muted=True))
        self._tx_preset = QComboBox()
        _prep_combo(self._tx_preset, self)
        for pid in PRESET_ORDER:
            self._tx_preset.addItem(get_preset(pid).label_es, pid)
        self._tx_preset.currentIndexChanged.connect(self._on_preset_changed)
        out_v.addWidget(self._tx_preset)
        out_v.addWidget(_wrap_label("Uso del PC:", muted=True))
        self._tx_impact = QComboBox()
        _prep_combo(self._tx_impact, self)
        for iid in PC_IMPACT_ORDER:
            self._tx_impact.addItem(get_pc_impact(iid).label_es, iid)
        self._tx_impact.currentIndexChanged.connect(self._on_pc_impact_changed)
        out_v.addWidget(self._tx_impact)
        out_v.addWidget(_wrap_label("Idioma:", muted=True))
        self._tx_lang = QComboBox()
        _prep_combo(self._tx_lang, self)
        for label, code in (("Español", "es"), ("English", "en"), ("Auto", "auto")):
            self._tx_lang.addItem(label, code)
        self._tx_lang.currentIndexChanged.connect(self._on_language_changed)
        out_v.addWidget(self._tx_lang)
        out_v.addWidget(_wrap_label("Hablantes:", muted=True))
        self._tx_speakers = QComboBox()
        _prep_combo(self._tx_speakers, self)
        self._tx_speakers.addItem("Auto (detectar)", 0)
        for n in (2, 3, 4, 5, 6):
            self._tx_speakers.addItem(f"{n}", n)
        self._tx_speakers.currentIndexChanged.connect(self._on_speakers_changed)
        self._tx_speakers.setToolTip(
            "Si lo sabes (entrevista 1 a 1 = 2) acelera y etiqueta mejor. "
            "Si no, deja Auto. Equilibrado/Máxima identifican hablantes."
        )
        out_v.addWidget(self._tx_speakers)
        root.addWidget(out_box)

        self._btn_flow = FlowLayout(h_spacing=8, v_spacing=8)
        self._record_btn = QPushButton("●  Grabar")
        self._record_btn.setStyleSheet(_RECORD_BTN)
        self._record_btn.setCursor(Qt.PointingHandCursor)
        self._record_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._record_btn.setMinimumWidth(120)
        self._record_btn.clicked.connect(self._toggle_record)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 130))
        self._record_btn.setGraphicsEffect(shadow)
        self._pause_btn = QPushButton("⏸  Pausar")
        self._pause_btn.setCursor(Qt.PointingHandCursor)
        self._pause_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._pause_btn.setVisible(False)
        self._btn_flow.addWidget(self._record_btn)
        self._btn_flow.addWidget(self._pause_btn)
        root.addLayout(self._btn_flow)

        status_col = QVBoxLayout()
        status_col.setSpacing(2)
        self._timer_label = QLabel("00:00:00")
        self._timer_label.setStyleSheet("font-size:16px; font-weight:bold;")
        self._status_label = _wrap_label("Listo para grabar", muted=True)
        status_col.addWidget(self._timer_label)
        status_col.addWidget(self._status_label)
        root.addLayout(status_col)

        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setFixedHeight(6)
        self._busy_bar.setStyleSheet(_BUSY_BAR)
        self._busy_bar.setVisible(False)
        root.addWidget(self._busy_bar)

        self._result_banner = QFrame()
        self._result_banner.setObjectName("banner")
        bl = QVBoxLayout(self._result_banner)
        bl.setContentsMargins(12, 8, 8, 8)
        bl.setSpacing(8)
        self._result_label = _wrap_label("✓ Grabación guardada")
        bl.addWidget(self._result_label)
        result_btns = FlowLayout(h_spacing=8, v_spacing=6)
        self._open_btn = QPushButton("📂 Abrir carpeta")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._open_btn.clicked.connect(self._open_output_folder)
        close_btn = QPushButton("✕")
        close_btn.setMaximumWidth(36)
        close_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(lambda: self._result_banner.setVisible(False))
        result_btns.addWidget(self._open_btn)
        result_btns.addWidget(close_btn)
        bl.addLayout(result_btns)
        self._result_banner.setVisible(False)
        root.addWidget(self._result_banner)

        self._tx_banner = QFrame()
        self._tx_banner.setObjectName("banner")
        tx_outer = QVBoxLayout(self._tx_banner)
        tx_outer.setContentsMargins(12, 8, 8, 8)
        tx_outer.setSpacing(8)
        tx_top = QHBoxLayout()
        tx_col = QVBoxLayout()
        tx_col.setSpacing(4)
        self._tx_label = _wrap_label("")
        self._tx_queue_hint = _wrap_label("", muted=True)
        self._tx_queue_hint.setVisible(False)
        self._tx_bar = QProgressBar()
        self._tx_bar.setTextVisible(False)
        self._tx_bar.setFixedHeight(6)
        tx_col.addWidget(self._tx_label)
        tx_col.addWidget(self._tx_queue_hint)
        tx_col.addWidget(self._tx_bar)
        tx_close = QPushButton("✕")
        tx_close.setMaximumWidth(36)
        tx_close.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        tx_close.setCursor(Qt.PointingHandCursor)
        tx_close.clicked.connect(lambda: self._tx_banner.setVisible(False))
        tx_top.addLayout(tx_col, 1)
        tx_top.addWidget(tx_close, 0, Qt.AlignTop)
        tx_outer.addLayout(tx_top)
        tx_btns = FlowLayout(h_spacing=8, v_spacing=6)
        self._tx_open_btn = QPushButton("📂 Abrir")
        self._tx_open_btn.setCursor(Qt.PointingHandCursor)
        self._tx_open_btn.clicked.connect(self._open_transcription)
        self._tx_cancel_btn = QPushButton("Cancelar")
        self._tx_cancel_btn.clicked.connect(self._cancel_transcription)
        self._tx_retry_btn = QPushButton("Reintentar")
        self._tx_retry_btn.clicked.connect(self._retry_transcription)
        self._tx_clear_btn = QPushButton("Limpiar fallidos")
        self._tx_clear_btn.clicked.connect(self._clear_failed_transcriptions)
        self._tx_log_btn = QPushButton("Ver log")
        self._tx_log_btn.clicked.connect(self._open_tx_log)
        for b in (
            self._tx_open_btn,
            self._tx_cancel_btn,
            self._tx_retry_btn,
            self._tx_clear_btn,
            self._tx_log_btn,
        ):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            tx_btns.addWidget(b)
        tx_outer.addLayout(tx_btns)
        self._tx_banner.setVisible(False)
        root.addWidget(self._tx_banner)

        self._central = central
        self._scroll = QScrollArea()
        central.setMinimumWidth(0)
        central.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._scroll.setWidget(central)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setMinimumSize(0, 0)
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(self._scroll)
        self._narrow = False
        self.setAcceptDrops(True)
        self._drop_overlay = QLabel("Suelta para transcribir", self)
        self._drop_overlay.setAlignment(Qt.AlignCenter)
        self._drop_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._drop_overlay.setStyleSheet(
            "background: rgba(46, 204, 113, 0.28); color:#eafff2; "
            "font-size:18px; font-weight:bold; border:2px dashed #2ecc71;"
        )
        self._drop_overlay.hide()
        self._scroll.viewport().setAcceptDrops(True)
        self._scroll.viewport().installEventFilter(self)
        self._central.setAcceptDrops(True)
        self._central.installEventFilter(self)
        self._preview.setAcceptDrops(True)
        self._preview.installEventFilter(self)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_drop_overlay()
        narrow = event.size().width() < 480
        if narrow == getattr(self, "_narrow", False):
            return
        self._narrow = narrow
        m = 10 if narrow else 16
        if hasattr(self, "_central") and self._central.layout() is not None:
            self._central.layout().setContentsMargins(m, m, m, m)
            self._central.layout().setSpacing(10 if narrow else 12)

    def eventFilter(self, watched, event):  # noqa: N802
        et = event.type()
        if et == QEvent.DragEnter:
            self.dragEnterEvent(event)
            return event.isAccepted()
        if et == QEvent.DragMove:
            self.dragMoveEvent(event)
            return event.isAccepted()
        if et == QEvent.DragLeave:
            self.dragLeaveEvent(event)
            return True
        if et == QEvent.Drop:
            self.dropEvent(event)
            return event.isAccepted()
        return super().eventFilter(watched, event)

    def _sync_drop_overlay(self) -> None:
        overlay = getattr(self, "_drop_overlay", None)
        if overlay is None:
            return
        overlay.setGeometry(self.rect())
        overlay.raise_()

    def _local_paths_from_mime(self, mime) -> List[str]:
        if mime is None or not mime.hasUrls():
            return []
        paths: List[str] = []
        for url in mime.urls():
            if url.isLocalFile():
                local = url.toLocalFile()
                if local:
                    paths.append(local)
        return paths

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._local_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            self._sync_drop_overlay()
            self._drop_overlay.show()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._local_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._drop_overlay.hide()
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = self._local_paths_from_mime(event.mimeData())
        self._drop_overlay.hide()
        event.acceptProposedAction()
        if paths:
            self._import_media_paths(paths)

    def _make_meter(self) -> QProgressBar:
        m = QProgressBar()
        m.setRange(0, 100)
        m.setTextVisible(False)
        m.setFixedHeight(10)
        m.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return m

    # --- bandeja y atajos ---------------------------------------------------
    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("Grabador de Reuniones")
        menu = QMenu()
        act_show = QAction("Mostrar ventana", self)
        act_show.triggered.connect(self._show_from_tray)
        act_rec = QAction("Iniciar / Detener", self)
        act_rec.triggered.connect(self._toggle_record)
        act_pause = QAction("Pausar / Reanudar", self)
        act_pause.triggered.connect(self._toggle_pause)
        act_mute = QAction("Silenciar / activar micrófono", self)
        act_mute.triggered.connect(self._toggle_mute)
        act_quit = QAction("Salir", self)
        act_quit.triggered.connect(self._quit_app)
        for a in (act_show, act_rec, act_pause, act_mute):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_hotkeys(self) -> None:
        self._hotkeys = GlobalHotkeys(
            self._toggle_record, self._toggle_pause, self._toggle_mute
        )
        try:
            from PySide6.QtWidgets import QApplication

            QApplication.instance().installNativeEventFilter(self._hotkeys)
        except Exception:
            pass

    def _setup_device_watcher(self) -> None:
        """Auto-refresh de mics ante hotplug Windows (debounce en MainWindow)."""
        self._device_watcher = DeviceChangeWatcher(self._on_device_change_event)
        try:
            from PySide6.QtWidgets import QApplication

            QApplication.instance().installNativeEventFilter(self._device_watcher)
        except Exception:
            pass

    def _on_device_change_event(self) -> None:
        # Reinicia debounce: ráfagas PnP → un solo refresh.
        self._hotplug_debounce.start()

    def _on_hotplug_debounce(self) -> None:
        recording = self._recorder.is_recording()
        if hotplug_action(recording=recording) == "defer":
            self._pending_mic_hotplug_refresh = True
            return
        self._refresh_mics(auto=True)
        # Segundo pase corto: BT a menudo publica HFP después del primer evento.
        self._hotplug_followup.start()

    def _on_hotplug_followup(self) -> None:
        if self._recorder.is_recording():
            self._pending_mic_hotplug_refresh = True
            return
        self._refresh_mics(auto=True)

    def _flush_pending_mic_hotplug(self) -> None:
        if not self._pending_mic_hotplug_refresh:
            return
        if self._recorder.is_recording():
            return
        self._pending_mic_hotplug_refresh = False
        self._refresh_mics(auto=True)
        self._hotplug_followup.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._hotkeys_registered:
            # Registrar atajos globales (la ventana ya tiene HWND válido).
            try:
                self._hotkeys.register(int(self.winId()))
            except Exception:
                pass
            self._hotkeys_registered = True
        self._apply_capture_affinity()
        # Medidores en vivo mientras la ventana está visible y no se graba.
        self._start_monitor()
        self._update_system_route_hint()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._stop_monitor()  # liberar el micrófono al minimizar a la bandeja

    def _start_monitor(self) -> None:
        if self._recorder.is_recording():
            return
        try:
            self._monitor.start(self._mic_combo.currentData())
        except Exception:
            pass

    def _stop_monitor(self) -> None:
        try:
            self._monitor.stop()
        except Exception:
            pass

    def _apply_capture_affinity(self) -> None:
        """Aplica si esta ventana se oculta o no de grabaciones/capturas."""
        apply_window_capture_affinity(
            int(self.winId()) if self.winId() else None,
            bool(self._config.exclude_window_from_capture),
        )

    def _on_hide_self_toggled(self, checked: bool) -> None:
        self._config.exclude_window_from_capture = bool(checked)
        self._config.save()
        self._apply_capture_affinity()

    # --- poblar selectores ---------------------------------------------------
    def _on_refresh(self) -> None:
        self._refresh_sources()
        self._update_preview()

    def _on_refresh_mics(self) -> None:
        self._refresh_mics(manual=True)

    def _mic_selection_key(self) -> str:
        """Clave visible de identidad para conservar selección (nombre exacto)."""
        text = self._mic_combo.currentText()
        return text if text else "Sin micrófono"

    def _restore_mic_selection(self, key: str) -> bool:
        """Restaura por match exacto de texto. Fallback: «Sin micrófono».

        Returns True si se restauró la clave; False si se aplicó el fallback.
        """
        idx = self._mic_combo.findText(key)
        if idx >= 0:
            self._mic_combo.setCurrentIndex(idx)
            return True
        self._mic_combo.setCurrentIndex(0)  # "Sin micrófono"
        return False

    def _refresh_sources(self) -> None:
        from app.capture.windows_video import list_monitors, list_windows

        prev = self._source_combo.currentData()
        self._source_combo.blockSignals(True)
        self._source_combo.clear()
        monitors = list_monitors() if sys.platform == "win32" else [
            VideoSource(kind="screen", title="Pantalla 1", monitor_index=1, is_primary=True)
        ]
        for m in monitors:
            self._source_combo.addItem(f"🖥️  {m.label}", userData=m)
        if sys.platform == "win32":
            self._windows = list_windows()
            for w in self._windows:
                self._source_combo.addItem(f"🪟  {w.title}", userData=w)
        # Conservar selección: monitor por índice; ventana por título.
        if isinstance(prev, VideoSource):
            if prev.kind == "screen" and prev.monitor_index:
                for i in range(self._source_combo.count()):
                    data = self._source_combo.itemData(i)
                    if (
                        isinstance(data, VideoSource)
                        and data.kind == "screen"
                        and data.monitor_index == prev.monitor_index
                    ):
                        self._source_combo.setCurrentIndex(i)
                        break
            elif prev.kind == "window" and prev.title:
                idx = self._source_combo.findText(f"🪟  {prev.title}")
                if idx >= 0:
                    self._source_combo.setCurrentIndex(idx)
        self._source_combo.blockSignals(False)

    def _refresh_mics(self, *, manual: bool = False, auto: bool = False) -> None:
        """Repuebla el combo de micrófonos.

        En arranque (`manual=False`, `auto=False`) no aplica last_mic_name (lo
        hace `_apply_saved_config`). En refresh manual/auto conserva la
        selección por nombre exacto y reengancha el medidor si no se graba.

        Fuera de grabación reinicia PortAudio (vía ``list_microphones(refresh=True)``)
        para que micrófonos Bluetooth/USB recién conectados aparezcan. Durante
        grabación solo consulta la lista cacheada (Recording Always Wins).
        """
        user_driven = bool(manual or auto)
        had_items = self._mic_combo.count() > 0
        prev_key = self._mic_selection_key() if had_items else None
        prev_names = {m.name for m in (self._mics or [])}

        recording = self._recorder.is_recording()
        # Re-init PortAudio solo idle: corta streams sounddevice (medidor / captura).
        do_reinit = bool(user_driven and not recording)
        if do_reinit and self._monitor.is_running():
            self._monitor.set_mic(None)

        self._mic_combo.blockSignals(True)
        self._mic_combo.clear()
        self._mic_combo.addItem("Sin micrófono", userData=None)
        try:
            from app.capture.windows_audio import list_microphones

            self._mics = list_microphones(refresh=do_reinit)
        except Exception as exc:
            self._mics = []
            self._mic_combo.blockSignals(False)
            if user_driven:
                self._status_label.setText(
                    f"No se pudieron listar micrófonos ({exc})"
                )
            if do_reinit and self._monitor.is_running():
                self._monitor.set_mic(None)
            return

        for m in self._mics:
            self._mic_combo.addItem(m.name, userData=m)

        if prev_key is None:
            # Primer populate: preferir el primer mic hardware si existe.
            if self._mics:
                self._mic_combo.setCurrentIndex(1)
            restored = True
        else:
            restored = self._restore_mic_selection(prev_key)

        self._mic_combo.blockSignals(False)

        if user_driven:
            n = len(self._mics)
            new_names = {m.name for m in self._mics}
            added = new_names - prev_names
            if not restored and prev_key not in (None, "Sin micrófono"):
                self._status_label.setText(
                    f"«{prev_key}» ya no disponible — seleccionado Sin micrófono"
                )
            elif added:
                self._status_label.setText(f"{n} micrófonos encontrados")
            elif recording:
                self._status_label.setText(
                    f"{n} micrófonos — sin cambios. Bluetooth nuevo: detén la "
                    "grabación y pulsa Actualizar"
                )
            else:
                self._status_label.setText(
                    f"{n} micrófonos encontrados — sin cambios. Si es Bluetooth, "
                    "espera el perfil Hands-Free (no solo Stereo)"
                )
            if not recording:
                # Reiniciar medidor completo: el loopback debe seguir la salida
                # por defecto (p. ej. tras conectar Bluetooth).
                try:
                    self._monitor.restart(self._mic_combo.currentData())
                except Exception:
                    pass
                self._update_system_route_hint()

    def _update_system_route_hint(self) -> None:
        """Aviso si la salida actual (p. ej. BT) suele dejar Sistema en silencio."""
        if not hasattr(self, "_sys_route_label"):
            return
        try:
            from app.capture.windows_audio import describe_system_audio_route

            info = describe_system_audio_route()
        except Exception:
            self._sys_route_label.setText("")
            return
        if info.get("warning"):
            text = "⚠ " + info["warning"]
            self._sys_route_label.setText(text)
            self._sys_route_label.setToolTip(text)
        elif info.get("ok") and info.get("output_name"):
            text = f"Capturando loopback de: {info['output_name']}"
            self._sys_route_label.setText(text)
            self._sys_route_label.setToolTip(text)
        else:
            self._sys_route_label.setText(info.get("warning") or "")
            self._sys_route_label.setToolTip(self._sys_route_label.text())

    def _apply_saved_config(self) -> None:
        shown = self._config.output_dir or str(default_output_dir())
        try:
            shown = str(resolve_output_dir(shown))
        except ValueError:
            shown = str(Path.home())
        self._out_edit.setText(shown)
        self._sys_check.setChecked(self._config.capture_system_audio)
        self._aec_check.setChecked(self._config.reduce_echo)
        self._hide_self_check.blockSignals(True)
        self._hide_self_check.setChecked(bool(self._config.exclude_window_from_capture))
        self._hide_self_check.blockSignals(False)
        disponible = transcriptor_disponible(self._config.transcriptor_dir)
        self._tx_check.setEnabled(disponible)
        self._tx_check.setChecked(self._config.transcribe_after_recording and disponible)
        self._tx_preset.setEnabled(disponible)
        self._tx_impact.setEnabled(disponible)
        self._tx_lang.setEnabled(disponible)
        self._tx_speakers.setEnabled(disponible)
        self._tx_file_btn.setEnabled(disponible)
        self._set_preset_ui(self._config.transcription_preset, save=False)
        self._set_pc_impact_ui(self._config.transcription_pc_impact, save=False)
        self._set_language_ui(self._config.transcription_language, save=False)
        self._set_speakers_ui(self._config.transcription_num_speakers, save=False)
        if not disponible:
            tip = (
                "No se encontró el proyecto Transcriptor.\n"
                "Revisa 'transcriptor_dir' en %APPDATA%\\MeetingRecorder\\config.json"
            )
            for w in (
                self._tx_check,
                self._tx_preset,
                self._tx_impact,
                self._tx_lang,
                self._tx_speakers,
                self._tx_file_btn,
            ):
                w.setToolTip(tip)
        else:
            self._tx_check.setToolTip("")
            self._tx_file_btn.setToolTip(
                "Transcribe un audio o vídeo que ya tengas; no hace falta grabar una reunión."
            )
        self._refresh_tx_queue()
        self._auto_mute_check.blockSignals(True)
        self._auto_mute_check.setChecked(bool(self._config.auto_mute_follow_meeting))
        self._auto_mute_check.blockSignals(False)
        if self._config.last_mic_name:
            idx = self._mic_combo.findText(self._config.last_mic_name)
            if idx >= 0:
                self._mic_combo.setCurrentIndex(idx)

    def _set_preset_ui(self, preset_id: object, *, save: bool) -> None:
        pid = normalize_preset(preset_id)
        idx = self._tx_preset.findData(pid)
        self._tx_preset.blockSignals(True)
        if idx >= 0:
            self._tx_preset.setCurrentIndex(idx)
        self._tx_preset.blockSignals(False)
        p = get_preset(pid)
        self._tx_preset.setToolTip(p.hint_es)
        self._config.transcription_preset = pid
        if save:
            self._config.save()

    def _on_preset_changed(self, _index: int = 0) -> None:
        pid = self._tx_preset.currentData()
        if pid is None:
            return
        self._set_preset_ui(pid, save=True)

    def _set_pc_impact_ui(self, profile_id: object, *, save: bool) -> None:
        iid = normalize_pc_impact(profile_id)
        idx = self._tx_impact.findData(iid)
        self._tx_impact.blockSignals(True)
        if idx >= 0:
            self._tx_impact.setCurrentIndex(idx)
        self._tx_impact.blockSignals(False)
        self._tx_impact.setToolTip(get_pc_impact(iid).hint_es)
        self._config.transcription_pc_impact = iid
        if save:
            self._config.save()

    def _on_pc_impact_changed(self, _index: int = 0) -> None:
        iid = self._tx_impact.currentData()
        if iid is None:
            return
        self._set_pc_impact_ui(iid, save=True)
        try:
            self._tx_worker.apply_pc_impact(iid)
        except Exception:
            pass

    def _set_language_ui(self, language: object, *, save: bool) -> None:
        code = normalize_language(language)
        idx = self._tx_lang.findData(code)
        self._tx_lang.blockSignals(True)
        if idx >= 0:
            self._tx_lang.setCurrentIndex(idx)
        self._tx_lang.blockSignals(False)
        self._config.transcription_language = code
        if save:
            self._config.save()

    def _on_language_changed(self, _index: int = 0) -> None:
        code = self._tx_lang.currentData()
        if code is None:
            return
        self._set_language_ui(code, save=True)

    def _set_speakers_ui(self, count: object, *, save: bool) -> None:
        n = normalize_num_speakers(count)
        idx = self._tx_speakers.findData(n)
        self._tx_speakers.blockSignals(True)
        if idx >= 0:
            self._tx_speakers.setCurrentIndex(idx)
        else:
            self._tx_speakers.setCurrentIndex(0)
        self._tx_speakers.blockSignals(False)
        self._config.transcription_num_speakers = n
        if save:
            self._config.save()

    def _on_speakers_changed(self, _index: int = 0) -> None:
        self._set_speakers_ui(self._tx_speakers.currentData(), save=True)

    # --- vista previa --------------------------------------------------------
    def _transcription_open(self) -> bool:
        if self._tx_worker.has_active_job():
            return True
        return transcription_status_is_open(self._tx_last.get("status"))

    def _update_preview(self) -> None:
        """Actualiza la miniatura sin bloquear el hilo Qt en grabs WGC."""
        try:
            source = self._source_combo.currentData()
            # Idle WGC + Intel GPU + transcripción = APPCRASH en igd10um64xe.DLL.
            if should_pause_idle_wgc_preview(
                recording=self._recorder.is_recording(),
                transcription_open=self._transcription_open(),
            ):
                self._preview_dirty = False
                return
            # Durante grabación el backend ya tiene el frame — barato, síncrono.
            # No abrir otra sesión WGC de preview encima de la captura activa.
            if self._recorder.is_recording():
                frame = self._recorder.current_video_frame()
                if frame is not None:
                    self._set_preview_pixmap(self._bgra_to_pixmap(frame))
                return

            if not isinstance(source, VideoSource):
                return

            if self._preview_busy:
                self._preview_dirty = True
                return

            hwnd = None
            mon_idx = None
            if source.kind == "window" and source.hwnd:
                hwnd = int(source.hwnd)
            elif source.kind == "screen":
                mon_idx = int(source.monitor_index or 1)
            else:
                return

            self._preview_busy = True
            self._preview_dirty = False
            self._preview_gen += 1
            gen = self._preview_gen
            threading.Thread(
                target=self._preview_grab_worker,
                args=(hwnd, mon_idx, gen),
                daemon=True,
            ).start()
        except Exception:
            self._preview_busy = False

    def _preview_grab_worker(
        self, hwnd: Optional[int], mon_idx: Optional[int], gen: int
    ) -> None:
        frame = None
        try:
            from app.capture.windows_video import grab_monitor_frame, grab_window_frame

            if hwnd is not None:
                frame = grab_window_frame(hwnd)
            elif mon_idx is not None:
                frame = grab_monitor_frame(mon_idx)
        except Exception:
            frame = None
        img = None
        if frame is not None:
            try:
                img = self._bgra_to_qimage(frame)
            except Exception:
                img = None
        self._preview_ready_sig.emit(img, gen)

    def _on_preview_ready(self, img: object, gen: int) -> None:
        self._preview_busy = False
        try:
            if gen == self._preview_gen and isinstance(img, QImage) and not img.isNull():
                self._set_preview_pixmap(QPixmap.fromImage(img))
        except Exception:
            pass
        if self._preview_dirty:
            self._preview_dirty = False
            self._update_preview()

    def _set_preview_pixmap(self, pm: QPixmap) -> None:
        tw = max(1, self._preview.width())
        th = max(1, self._preview.height())
        self._preview.setPixmap(
            pm.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _bgra_to_qimage(self, frame) -> QImage:
        """Convierte un fotograma BGRA (numpy) a QImage opaco (seguro off-thread)."""
        h, w = frame.shape[:2]
        return QImage(frame.data, w, h, w * 4, QImage.Format_RGB32).copy()

    def _bgra_to_pixmap(self, frame) -> QPixmap:
        return QPixmap.fromImage(self._bgra_to_qimage(frame))

    # --- acciones ------------------------------------------------------------
    def _choose_output(self) -> None:
        current = self._out_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Elige la carpeta de salida", current)
        if folder:
            resolved = apply_selected_output_dir(self._config, folder)
            self._out_edit.setText(str(resolved))
            self._config.save()

    def _ensure_output_folder_for_record(self) -> bool:
        """Exige carpeta de salida; si la ruta es larga, ofrece corregirla."""
        raw = (self._out_edit.text() or self._config.output_dir or "").strip()
        bad = folder_looks_unusable(raw)
        if bad:
            self._dialog(QMessageBox.Warning, "Carpeta de salida", bad).exec()
            self._choose_output()
            raw = (self._out_edit.text() or "").strip()
            if folder_looks_unusable(raw):
                self._dialog(
                    QMessageBox.Critical,
                    "Carpeta de salida",
                    "No se puede grabar sin una carpeta de salida. Elige una y vuelve a intentar.",
                ).exec()
                return False
        try:
            folder = resolve_output_dir(raw)
        except Exception as exc:
            self._dialog(QMessageBox.Critical, "Carpeta de salida", str(exc)).exec()
            return False
        probe = dest_file_path(folder, "Grabacion_2099-12-31_23-59-59")
        if ffmpeg_path_too_long(probe) or ffmpeg_path_too_long(folder):
            box = self._dialog(
                QMessageBox.Warning,
                "Ruta demasiado larga",
                "Esta carpeta es demasiado larga para Windows y puede impedir guardar el MP4 "
                "(pasó el 9-sep-2026 con una ruta de OneDrive).\n\n"
                "¿Elegir ahora una carpeta más corta (Escritorio o Videos)?\n"
                "Si continúas, la grabación se guarda primero en una copia local segura "
                "y al final te pediré una carpeta válida.",
                QMessageBox.Yes | QMessageBox.No,
            )
            yes = box.button(QMessageBox.Yes)
            no = box.button(QMessageBox.No)
            if yes is not None:
                yes.setText("Elegir carpeta")
            if no is not None:
                no.setText("Grabar igual")
            if box.exec() == QMessageBox.Yes:
                self._choose_output()
        return True

    def _offer_pending_save(self) -> None:
        pending = load_pending()
        if pending is None:
            return
        box = self._dialog(
            QMessageBox.Warning,
            "Grabación sin guardar",
            "Hay una grabación que no llegó a la carpeta de salida.\n"
            "Los archivos NO se han borrado.\n\n"
            "¿Elegir ahora una carpeta para guardar el MP4?",
            QMessageBox.Yes | QMessageBox.No,
        )
        box.button(QMessageBox.Yes).setText("Elegir carpeta")
        box.button(QMessageBox.No).setText("Más tarde")
        if box.exec() != QMessageBox.Yes:
            self._set_status("Grabación pendiente de guardar (no se ha borrado).")
            return
        self._pick_folder_and_retry_save()

    def _pick_folder_and_retry_save(self) -> None:
        start = self._out_edit.text() or self._config.output_dir or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Elige una carpeta CORTA para guardar", start
        )
        if not folder:
            self._set_status("Grabación pendiente de guardar (no se ha borrado).")
            return
        try:
            resolved = apply_selected_output_dir(self._config, folder)
            self._out_edit.setText(str(resolved))
            self._config.save()
        except Exception:
            resolved = Path(folder)
        self._enter_busy("Guardando la grabación pendiente…", "Guardando…")
        threading.Thread(
            target=self._recorder.retry_save, args=(resolved,), daemon=True
        ).start()

    def _choose_transcribe_files(self) -> None:
        start = self._out_edit.text() or self._config.output_dir or str(Path.home())
        files, _ok = QFileDialog.getOpenFileNames(
            self,
            "Transcribir archivo",
            start,
            file_dialog_filter(),
        )
        if files:
            self._import_media_paths(files)

    def _tx_output_base(self) -> str:
        raw = self._out_edit.text() or self._config.output_dir or str(default_output_dir())
        return str(resolve_output_dir(raw))

    def _recording_output_base(self, media_path: str) -> str:
        try:
            return str(Path(media_path).expanduser().resolve().parent)
        except OSError:
            return str(Path(media_path).parent)

    def _import_media_paths(self, paths: List[str]) -> None:
        results = enqueue_imports(
            paths,
            store=self._tx_store,
            enqueue=lambda media, language, preset: self._tx_worker.enqueue(
                media,
                language,
                preset=preset,
                pc_impact=normalize_pc_impact(
                    self._tx_impact.currentData()
                    or self._config.transcription_pc_impact
                ),
                output_base=self._tx_output_base(),
                num_speakers=normalize_num_speakers(self._tx_speakers.currentData()),
            ),
            language=normalize_language(
                self._tx_lang.currentData() or self._config.transcription_language
            ),
            preset=normalize_preset(
                self._tx_preset.currentData() or self._config.transcription_preset
            ),
            tool_available=transcriptor_disponible(self._config.transcriptor_dir),
            output_base=self._tx_output_base(),
        )
        summary = summarize_import_results(results)
        if summary:
            self._tx_import_status.setText(summary)
            self._tx_import_status.setVisible(True)
            if not self._recorder.is_recording():
                self._set_status(summary)
        done = next((r for r in results if r.kind == ALREADY_DONE and r.job), None)
        if done and done.job and not self._tx_store.active():
            self._on_tx_update(done.job)
        else:
            first = next((r.job for r in results if r.kind == OK and r.job), None)
            if first and not (
                transcription_status_is_open(self._tx_last.get("status"))
                and self._tx_last.get("status") in ("running", "extracting")
            ):
                self._on_tx_update(first)
            else:
                self._refresh_tx_queue()

    def _build_settings(self) -> RecordingSettings:
        source = self._source_combo.currentData()
        if not isinstance(source, VideoSource):
            source = VideoSource(kind="screen", monitor_index=1, is_primary=True)
        raw = self._out_edit.text() or self._config.output_dir or str(default_output_dir())
        return RecordingSettings(
            video_source=source,
            mic_device=self._mic_combo.currentData(),
            capture_system_audio=self._sys_check.isChecked(),
            reduce_echo=self._aec_check.isChecked(),
            output_dir=resolve_output_dir(raw),
        )

    def _toggle_record(self) -> None:
        if self._busy:
            return  # ya está iniciando o procesando

        if self._recorder.is_recording():
            # DETENER: el cierre de FFmpeg + mux pueden tardar -> en segundo plano.
            self._rec_dot.setVisible(False)
            self._enter_busy("Deteniendo y guardando…", "Guardando…")
            threading.Thread(target=self._recorder.stop, daemon=True).start()
            return

        if not self._sys_check.isChecked() and self._mic_combo.currentData() is None:
            box = self._dialog(
                QMessageBox.Question, "Sin audio",
                "No seleccionaste micrófono ni audio del sistema. ¿Grabar solo video?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if box.exec() != QMessageBox.Yes:
                return
        if not self._ensure_output_folder_for_record():
            return
        if self._sys_check.isChecked():
            try:
                from app.capture.windows_audio import describe_system_audio_route

                route = describe_system_audio_route()
            except Exception:
                route = {}
            if route.get("bluetooth"):
                box = self._dialog(
                    QMessageBox.Warning,
                    "Audio del sistema y Bluetooth",
                    route.get("warning")
                    or (
                        "La salida por defecto es Bluetooth. Windows suele dejar "
                        "la pista Sistema en silencio. ¿Grabar igual?"
                    ),
                    QMessageBox.Yes | QMessageBox.No,
                )
                if box.exec() != QMessageBox.Yes:
                    return
        try:
            settings = self._build_settings()
            self._save_config(settings)
        except Exception as exc:
            self._dialog(QMessageBox.Critical, "Error", str(exc)).exec()
            return
        # INICIAR: lanzar FFmpeg/streams puede tardar -> en segundo plano.
        self._stop_monitor()
        self._result_banner.setVisible(False)
        self._sys_silent_ticks = 0
        self._sys_silence_warned = False
        self._enter_busy("Iniciando grabación…", "Iniciando…")
        threading.Thread(target=self._do_start, args=(settings,), daemon=True).start()

    def _dialog(self, icon, title: str, text: str, buttons=QMessageBox.Ok):
        """Crea un QMessageBox con estilo legible sobre el tema oscuro."""
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        box.setStyleSheet(_MSGBOX_QSS)
        return box

    def _do_start(self, settings) -> None:
        try:
            self._recorder.start(settings)
            self._started_sig.emit()
        except Exception as exc:
            self._error_sig.emit(str(exc))

    def _on_started(self) -> None:
        self._exit_busy()
        self._hotplug_followup.stop()
        self._set_recording_ui(True)

    def _enter_busy(self, status_msg: str, btn_text: str) -> None:
        self._busy = True
        self._busy_bar.setRange(0, 0)  # indeterminado hasta que haya % real
        self._busy_bar.setVisible(True)
        self._status_label.setText(status_msg)
        self._record_btn.setText(btn_text)
        self._record_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)

    def _exit_busy(self) -> None:
        self._busy = False
        self._busy_bar.setVisible(False)
        self._busy_bar.setRange(0, 0)  # volver a indeterminado para la próxima vez
        self._record_btn.setEnabled(True)

    def _on_progress(self, pct: int) -> None:
        if not self._busy:
            return
        self._busy_bar.setRange(0, 100)  # barra determinada con %
        self._busy_bar.setValue(pct)
        self._status_label.setText(f"Guardando… {pct}%")

    def _toggle_pause(self) -> None:
        if not self._recorder.is_recording():
            return
        if self._recorder.is_paused():
            self._recorder.resume()
            self._pause_btn.setText("⏸ Pausar")
        else:
            self._recorder.pause()
            self._pause_btn.setText("▶ Reanudar")

    def _on_mic_activated(self, _index: int) -> None:
        device = self._mic_combo.currentData()
        if self._recorder.is_recording():
            self._recorder.change_mic(device)  # cambio EN VIVO
        else:
            self._monitor.set_mic(device)  # actualizar el medidor en vivo

    def _toggle_mute(self) -> None:
        self._recorder.set_mic_muted(not self._recorder.is_mic_muted())
        self._update_mute_button()

    def _on_auto_mute_toggled(self, checked: bool) -> None:
        self._config.auto_mute_follow_meeting = bool(checked)
        self._config.save()
        # Rearmar: al (re)activar, aplicar una vez; al desactivar, olvidar flanco.
        self._auto_mute_others_prev = None
        if checked:
            self._update_mic_usage()

    def _update_mute_button(self) -> None:
        muted = self._recorder.is_mic_muted()
        if muted:
            self._mute_btn.setText("🔇 Silenciado")
            self._mute_btn.setStyleSheet(
                f"QPushButton {{ background:{_DANGER}; color:white; border-radius:6px; padding:8px; }}"
            )
        else:
            self._mute_btn.setText("🎤 Activo")
            self._mute_btn.setStyleSheet("")

    def _save_config(self, settings: RecordingSettings) -> None:
        self._config.output_dir = str(resolve_output_dir(settings.output_dir))
        self._config.capture_system_audio = settings.capture_system_audio
        self._config.reduce_echo = settings.reduce_echo
        self._config.last_mic_name = settings.mic_device.name if settings.mic_device else ""
        self._config.transcribe_after_recording = self._tx_check.isChecked()
        self._config.transcription_preset = normalize_preset(self._tx_preset.currentData())
        self._config.transcription_pc_impact = normalize_pc_impact(self._tx_impact.currentData())
        self._config.transcription_language = normalize_language(self._tx_lang.currentData())
        self._config.transcription_num_speakers = normalize_num_speakers(
            self._tx_speakers.currentData()
        )
        self._config.auto_mute_follow_meeting = self._auto_mute_check.isChecked()
        self._config.exclude_window_from_capture = self._hide_self_check.isChecked()
        self._config.save()

    # --- callbacks del orquestador (vía señales) ----------------------------
    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_finished(self, path: str) -> None:
        self._last_output = path
        self._exit_busy()
        self._set_recording_ui(False)
        self._record_btn.setEnabled(True)
        self._status_label.setText("Listo ✓")
        # Encolar la transcripción ANTES del posible cierre de la app: el job
        # queda persistido en disco y se procesa ahora o al siguiente arranque.
        encolada = False
        if self._tx_check.isChecked() and transcriptor_disponible(self._config.transcriptor_dir):
            try:
                encolada = self._tx_worker.enqueue(
                    path,
                    normalize_language(self._config.transcription_language),
                    preset=normalize_preset(self._config.transcription_preset),
                    pc_impact=normalize_pc_impact(self._config.transcription_pc_impact),
                    output_base=self._recording_output_base(path),
                    num_speakers=normalize_num_speakers(
                        self._config.transcription_num_speakers
                    ),
                ) is not None
            except Exception:
                pass
        sufijo = " · transcripción en cola" if encolada else ""
        self._result_label.setText(f"✓ Grabación guardada{sufijo}:  {os.path.basename(path)}")
        self._result_banner.setVisible(True)
        self._update_preview()
        if self._quit_after_finalize:
            self._finish_quit()
            return
        self._start_monitor()  # reanudar medidores en vivo
        self._flush_pending_mic_hotplug()
        # Notificación nativa solo si la ventana está minimizada/en bandeja.
        if self._tray.isVisible() and not self.isActiveWindow():
            self._tray.showMessage("Grabación lista", os.path.basename(path),
                                   QSystemTrayIcon.Information, 4000)

    def _on_error(self, msg: str) -> None:
        self._exit_busy()
        self._set_recording_ui(False)
        self._record_btn.setEnabled(True)
        self._status_label.setText("Error")
        if self._quit_after_finalize:
            if self._recorder.has_unsaved_session() or load_pending() is not None:
                self._quit_after_finalize = False
                self.show()
                self._on_save_failed(msg)
                return
            self._finish_quit()
            return
        self._start_monitor()
        self._flush_pending_mic_hotplug()
        self._dialog(QMessageBox.Critical, "Error al procesar", msg).exec()

    def _on_save_failed(self, msg: str) -> None:
        """El mux/copia falló: la sesión sigue en disco. Pedir carpeta, no salir."""
        self._exit_busy()
        self._set_recording_ui(False)
        self._record_btn.setEnabled(True)
        self._status_label.setText("Grabación pendiente de guardar")
        if self._quit_after_finalize:
            self._quit_after_finalize = False
            self.show()
            self.raise_()
        self._start_monitor()
        self._flush_pending_mic_hotplug()
        box = self._dialog(
            QMessageBox.Critical,
            "No se pudo guardar",
            msg,
            QMessageBox.Retry | QMessageBox.Cancel,
        )
        retry_btn = box.button(QMessageBox.Retry)
        if retry_btn is not None:
            retry_btn.setText("Elegir carpeta")
        cancel_btn = box.button(QMessageBox.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText("Más tarde")
        if box.exec() == QMessageBox.Retry:
            self._pick_folder_and_retry_save()
        else:
            self._set_status("Grabación pendiente de guardar (no se ha borrado).")

    # --- transcripción (vía señal del worker) --------------------------------
    def _tx_live_id(self) -> str:
        if self._tx_last.get("status") in ("pending", "extracting", "running"):
            return str(self._tx_last.get("id") or "")
        return ""

    def _notify_tx_done(self, snap: dict) -> None:
        nombre = Path(snap.get("media_path", "")).stem
        if self._tray.isVisible() and not self.isActiveWindow():
            self._tray.showMessage(
                "Transcripción lista", nombre, QSystemTrayIcon.Information, 5000
            )

    def _on_tx_update(self, snap: dict) -> None:
        if snap.get("status") == "done":
            job_id = str(snap.get("id") or "")
            rest = any(
                j.id != job_id and j.status in ("pending", "extracting", "running")
                for j in self._tx_store.all()
            )
            if rest:
                # El lote sigue: el aviso se queda en el archivo en curso, pero
                # cada archivo terminado sí se notifica.
                self._notify_tx_done(snap)
                self._refresh_tx_queue()
                return
        self._tx_last = snap
        self._apply_tx_snapshot(snap)
        self._refresh_tx_queue()

    def _apply_tx_snapshot(self, snap: dict) -> None:
        self._tx_last = snap
        nombre = Path(snap.get("media_path", "")).stem
        estado = snap.get("status", "")
        stage = snap.get("stage") or estado
        pct = snap.get("progress")

        es_done = estado == "done"
        es_error = estado == "error"
        es_cancelado = estado == "cancelled"
        es_activo = estado in ("pending", "extracting", "running")
        hay_fallidos = self._tx_store.count_clearable() > 0
        self._tx_open_btn.setVisible(es_done)
        self._tx_cancel_btn.setVisible(es_activo)
        self._tx_retry_btn.setVisible(es_error)
        self._tx_clear_btn.setVisible(hay_fallidos or es_error or es_cancelado)
        self._tx_log_btn.setVisible(es_error or es_cancelado)
        self._tx_bar.setVisible(es_activo)
        if es_done or es_error or es_cancelado or es_activo:
            self._tx_banner.setVisible(True)

        if es_done:
            nota = f"  ({snap['note']})" if snap.get("note") else ""
            self._tx_label.setText(f"✓ Transcripción lista{nota}:  {nombre}")
            self._notify_tx_done(snap)
        elif es_cancelado:
            self._tx_label.setText(f"⛔ Transcripción cancelada:  {nombre}")
        elif es_error:
            detalle = (snap.get("error") or "")[:140]
            self._tx_label.setText(f"⚠ Transcripción falló:  {nombre}\n{detalle}")
        elif es_activo:
            # La pausa ya trae su propio ⏸: no duplicar iconos.
            icono = "" if stage.startswith("⏸") else "🎙 "
            self._tx_label.setText(
                f"{icono}{stage}  ·  {nombre}{batch_suffix(snap)}{eta_suffix(snap)}"
            )
            if pct is not None and pct > 0:
                self._tx_bar.setRange(0, 100)
                self._tx_bar.setValue(pct)
            else:
                self._tx_bar.setRange(0, 0)
        else:
            self._tx_label.setText("")

    def _refresh_tx_queue(self) -> None:
        live_id = self._tx_live_id()
        c = self._tx_store.queue_counts(live_id)
        parts = []
        if c["running"]:
            parts.append(f"{c['running']} en curso")
        if c["pending"]:
            parts.append(f"{c['pending']} en espera")
        if c["failed"]:
            parts.append(f"{c['failed']} fallida(s)")
        lote = batch_eta_text(self._tx_last)
        if lote:
            parts.append(lote)
        hint = ("Resumen: " + " · ".join(parts)) if parts else ""
        self._tx_queue_hint.setText(hint)
        self._tx_queue_hint.setVisible(bool(hint))
        if c["running"]:
            self._tx_import_status.setVisible(False)

        jobs = visible_queue_jobs(self._tx_store.all())
        current_id = str(self._tx_last.get("id") or "")
        stage = str(self._tx_last.get("stage") or "")
        pct = self._tx_last.get("progress")
        progress = pct if isinstance(pct, int) else None

        self._tx_queue_list.blockSignals(True)
        selected = live_id or current_id
        prev = self._tx_queue_list.currentItem()
        if prev is not None:
            prev_id = str(prev.data(Qt.UserRole) or "")
            prev_job = (
                self._tx_store._load(self._tx_store._path(prev_id)) if prev_id else None
            )
            if prev_job is not None and prev_job.status in ("error", "cancelled"):
                selected = prev_id
        self._tx_queue_list.clear()
        for job in jobs:
            line = format_queue_line(
                job,
                stage=stage if job.id == current_id else "",
                progress=progress if job.id == current_id else None,
                live_id=live_id or current_id,
            )
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, job.id)
            self._tx_queue_list.addItem(item)
            if job.id == selected:
                item.setSelected(True)
                self._tx_queue_list.setCurrentItem(item)
        self._tx_queue_list.blockSignals(False)
        empty = not jobs
        self._tx_queue_empty.setVisible(False)
        self._tx_queue_list.setVisible(not empty)
        if jobs:
            self._tx_banner.setVisible(True)

    def _on_tx_queue_selected(self) -> None:
        item = self._tx_queue_list.currentItem()
        if item is None:
            return
        job_id = item.data(Qt.UserRole)
        job = self._tx_store._load(self._tx_store._path(str(job_id)))
        if job is None:
            return
        live = self._tx_live_id()
        if live and job.id != live and job.status in ("pending", "extracting", "running"):
            return
        snap = job.snapshot()
        if job.id == self._tx_last.get("id"):
            if self._tx_last.get("stage"):
                snap["stage"] = self._tx_last["stage"]
            if self._tx_last.get("progress") is not None:
                snap["progress"] = self._tx_last["progress"]
        self._apply_tx_snapshot(snap)

    def _open_transcription(self) -> None:
        carpeta = self._tx_last.get("result_dir")
        if carpeta and os.path.isdir(carpeta):
            try:
                os.startfile(carpeta)  # type: ignore[attr-defined]
            except OSError:
                pass

    def _open_tx_log(self) -> None:
        log = self._tx_last.get("log_path")
        if log and os.path.exists(log):
            try:
                os.startfile(log)  # type: ignore[attr-defined]
            except OSError:
                pass

    def _retry_transcription(self) -> None:
        job_id = self._tx_last.get("id")
        if job_id:
            self._tx_worker.retry(job_id)
            self._refresh_tx_queue()

    def _cancel_transcription(self) -> None:
        job_id = self._tx_last.get("id")
        if job_id:
            self._tx_worker.cancel(job_id)
            self._refresh_tx_queue()

    def _clear_failed_transcriptions(self) -> None:
        n = self._tx_worker.clear_failed()
        if n and self._tx_last.get("status") in ("error", "cancelled"):
            self._tx_banner.setVisible(False)
            self._tx_last = {}
        elif self._tx_last:
            self._on_tx_update(self._tx_last)
        self._refresh_tx_queue()

    # --- estado de la UI -----------------------------------------------------
    def _set_recording_ui(self, recording: bool) -> None:
        # Fuente de video bloqueada durante grabación; mic + refresh de mics
        # permanecen activos (cambio/refresh en vivo). C-RECORDING-GATES.
        # Transcribir archivo… / drop siguen disponibles: solo se encola;
        # el worker cede CPU (Recording Always Wins).
        for w in (self._source_combo, self._refresh_btn, self._sys_check):
            w.setEnabled(not recording)
        self._mic_combo.setEnabled(True)
        self._mic_refresh_btn.setEnabled(True)
        self._pause_btn.setVisible(recording)
        self._pause_btn.setEnabled(recording)
        self._rec_dot.setVisible(recording)
        if recording:
            self._record_btn.setText("■ Detener")
            self._record_btn.setStyleSheet(_STOP_BTN)
            self._pause_btn.setText("⏸ Pausar")
        else:
            self._record_btn.setText("● Grabar")
            self._record_btn.setStyleSheet(_RECORD_BTN)

    def _tick(self) -> None:
        secs = int(self._recorder.elapsed_seconds())
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        self._timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

        # Medidores: del grabador si graba; del monitor en vivo si está inactivo.
        # Mute / casilla de sistema apagan la barra aunque el monitor siga muestreando.
        system_enabled = self._sys_check.isChecked()
        if self._recorder.is_recording():
            raw_sys = self._recorder.system_level()
            raw_mic = self._recorder.mic_level()
            # Si Sistema sigue en silencio varios segundos, avisar (BT / salida mala).
            if (
                system_enabled
                and not self._recorder.is_paused()
                and not self._sys_silence_warned
            ):
                if raw_sys < 0.01:
                    self._sys_silent_ticks += 1
                else:
                    self._sys_silent_ticks = 0
                # ~5 s a 100 ms/tick
                if self._sys_silent_ticks >= 50:
                    self._sys_silence_warned = True
                    self._status_label.setText(
                        "Audio del sistema en silencio — si usas Bluetooth, "
                        "cambia la salida a Altavoces"
                    )
        else:
            raw_sys = self._monitor.system_level()
            raw_mic = self._monitor.mic_level()
        mic_lvl, sys_lvl = meter_display_levels(
            raw_mic,
            raw_sys,
            mic_muted=self._recorder.is_mic_muted(),
            system_enabled=system_enabled,
        )
        self._mic_meter.setValue(int(mic_lvl * 100))
        self._sys_meter.setValue(int(sys_lvl * 100))

        self._preview_counter += 1
        if self._recorder.is_recording():
            if self._recorder.is_paused():
                self._rec_dot.setVisible(True)  # sólido en pausa
            elif self._preview_counter % 5 == 0:  # parpadeo cada ~500 ms
                self._blink_on = not self._blink_on
                self._rec_dot.setVisible(self._blink_on)
            # Vista previa EN VIVO durante la grabación (cada ~1 s).
            if not self._recorder.is_paused() and self._preview_counter % 10 == 0:
                self._update_preview()
        elif self._preview_counter % 15 == 0:
            # No abrir WGC en bucle: el driver Intel crashea pythonw (c0000005
            # en igd10um64xe.DLL) si se crea/destruye captura cada ~1.5 s.
            if not should_pause_idle_wgc_preview(
                recording=False,
                transcription_open=self._transcription_open(),
                periodic=True,
            ):
                self._update_preview()

        # Detección de uso del micrófono por otras apps (~cada 1.5 s).
        if self._preview_counter % 15 == 0:
            self._update_mic_usage()
            if not self._recorder.is_recording():
                self._update_system_route_hint()

    def _update_mic_usage(self) -> None:
        try:
            users = microphone_users((self._own_hint, "python"))
        except Exception:
            users = []
        names = sorted({u.name for u in users})
        in_meeting = bool(names)
        if in_meeting:
            msg = "En llamada — " + ", ".join(names) + " está usando el micrófono"
            self._mic_usage_label.setText(msg)
            self._mic_usage_label.setToolTip(msg)
        else:
            self._mic_usage_label.setText("Sin llamada activa")
            self._mic_usage_label.setToolTip("")

        if self._auto_mute_check.isChecked():
            try:
                others = is_microphone_in_use_by_others((self._own_hint, "python"))
            except Exception:
                return
            # Edge-triggered: solo aplicar al entrar/salir de llamada (o al
            # armar), para que un mute manual durante la llamada no se pise
            # cada ~1.5 s.
            want_mute = should_apply_follow_meeting_mute(
                others, self._auto_mute_others_prev
            )
            self._auto_mute_others_prev = bool(others)
            if want_mute is not None and want_mute != self._recorder.is_mic_muted():
                self._recorder.set_mic_muted(want_mute)
                self._update_mute_button()

    def _open_output_folder(self) -> None:
        if not self._last_output:
            return
        folder = os.path.dirname(self._last_output)
        try:
            if sys.platform == "win32":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')
        except Exception:
            pass

    # --- bandeja: mostrar/ocultar/salir -------------------------------------
    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app(self) -> None:
        # Salir desde el menú de la bandeja = mismo flujo que cerrar la ventana.
        self.close()

    def _teardown_native_filters(self) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        for filt in (getattr(self, "_device_watcher", None), getattr(self, "_hotkeys", None)):
            if filt is None:
                continue
            try:
                app.removeNativeEventFilter(filt)
            except Exception:
                pass

    def _finish_quit(self) -> None:
        """Limpia recursos y cierra la aplicación de verdad."""
        from PySide6.QtWidgets import QApplication

        self._hotplug_debounce.stop()
        self._hotplug_followup.stop()
        self._stop_monitor()
        try:
            self._hotkeys.unregister()
        except Exception:
            pass
        self._teardown_native_filters()
        try:
            self._tray.hide()
        except Exception:
            pass
        QApplication.quit()

    def closeEvent(self, event) -> None:
        # Si hay una grabación en curso, ofrecer finalizarla antes de salir.
        if self._recorder.is_recording():
            box = self._dialog(
                QMessageBox.Question, "Grabación en curso",
                "Hay una grabación en curso.\n¿Detenerla, guardar el archivo y salir?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if box.exec() != QMessageBox.Yes:
                event.ignore()
                return
            # Detener y salir SOLO si el guardado termina bien (_on_finished).
            # Si falla, _on_save_failed cancela este flag y pide carpeta.
            self._quit_after_finalize = True
            self._enter_busy("Guardando antes de salir…", "Guardando…")
            threading.Thread(target=self._recorder.stop, daemon=True).start()
            event.ignore()  # seguimos vivos hasta que el mux termine
            self.hide()
            return
        if self._recorder.has_unsaved_session() or load_pending() is not None:
            box = self._dialog(
                QMessageBox.Warning,
                "Grabación sin guardar",
                "Hay una grabación que aún no está en la carpeta de salida.\n"
                "Si sales ahora, los archivos NO se borran; al volver a abrir podrás guardarlos.\n\n"
                "¿Salir sin copiar el MP4 a tu carpeta?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if box.exec() != QMessageBox.Yes:
                event.ignore()
                return
        # Si hay una transcripción en marcha, avisar que continúa sola: el
        # subproceso es independiente (su salida va a un archivo, no a un pipe)
        # y al reabrir la app la reconciliación lo retoma o recoge el resultado.
        if self._tx_worker.has_active_job():
            self._dialog(
                QMessageBox.Information, "Transcripción en curso",
                "La transcripción continúa en segundo plano aunque cierres la app.\n"
                "Verás el resultado al volver a abrir el Grabador.",
            ).exec()

        # Sin grabación: cerrar limpio y asegurar que el proceso termina.
        from PySide6.QtWidgets import QApplication

        self._hotplug_debounce.stop()
        self._hotplug_followup.stop()
        self._stop_monitor()
        try:
            self._hotkeys.unregister()
        except Exception:
            pass
        self._teardown_native_filters()
        try:
            self._tray.hide()
        except Exception:
            pass
        super().closeEvent(event)
        QApplication.quit()

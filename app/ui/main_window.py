"""Ventana nativa de escritorio. Las tres pantallas viven en app/ui/qml."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Property, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QMainWindow, QMenu,
                               QMessageBox, QSystemTrayIcon, QVBoxLayout)

from app.core.config import AppConfig, RecordingSettings
from app.core.mic_usage import microphone_users, should_apply_follow_meeting_mute, is_microphone_in_use_by_others
from app.core.output_path import dest_file_path, ffmpeg_path_too_long, folder_looks_unusable, load_pending
from app.transcription.import_media import file_dialog_filter
from app.transcription.integration import is_available
from app.ui.audio_inputs import AudioInputs
from app.ui.capture_affinity import apply_window_capture_affinity
from app.ui.device_watcher import DeviceChangeWatcher
from app.ui.hotkeys import GlobalHotkeys
from app.ui.preferences import Preferences
from app.ui.preview import Preview
from app.ui.session import RecordingSession
from app.ui.source_picker import SourcePicker
from app.ui.transcriptions import Transcriptions, open_local

_MAC = sys.platform == "darwin"

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
    return _make_dot_icon("#e74c3c")


def qml_entry() -> Path:
    if _MAC and getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parents[1] / "Resources" / "app" / "ui" / "qml" / "Main.qml"
    return Path(__file__).with_name("qml") / "Main.qml"


class MainWindow(QMainWindow):
    statusChanged = Signal()
    metricsChanged = Signal()
    resultsChanged = Signal()
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grabador de Reuniones")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(360, 320)
        self.setAcceptDrops(True)
        self._status = "Listo para grabar"
        self._last_output = ""
        self._quit_after_finalize = False
        self._hotkeys_registered = self._pending_hotplug = False
        self._tick_count = self._silent_ticks = 0
        self._silence_warned = False
        self._metrics = {"time": "00:00:00", "mic": 0., "system": 0., "muted": False}
        self._usage = ""
        self._auto_mute_previous = None
        self._config = AppConfig.load()
        self.pref = Preferences(self._config, self)
        self.session = RecordingSession(self)
        self.picker = SourcePicker(self.session.priority, self)
        self.audio = AudioInputs(self.session, self._config, self)
        self.library = Transcriptions(self.pref, self.session,
                _MAC or is_available(self._config.transcriptor_dir),
                self._engine_ready if _MAC else None, self)
        self.preview = Preview(self.picker, self.session, self.library, self)
        self._engine_dialog = self._engine_panel = None
        self._wire_services()
        self._build_ui()
        self._setup_tray()
        self._setup_hotkeys()
        self._setup_device_watcher()
        self._hotplug_debounce = self._once(800, self._refresh_hotplug)
        self._hotplug_followup = self._once(2000, self._refresh_hotplug_followup)
        self.picker.refresh()
        self.audio.refresh()
        self.library.worker.start()
        self.library.worker.apply_pc_impact(self._config.transcription_pc_impact)
        self.preview.refresh()
        self._timer = QTimer(self, interval=100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        QTimer.singleShot(0, self._offer_pending_save)
        threading.Thread(target=self._prewarm_encoder, daemon=True).start()
        available = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(480, available.width()-40), min(720, available.height()-60))
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _wire_services(self):
        self.pref.edited.connect(self._preference_changed)
        self.picker.message.connect(self._set_status)
        self.audio.message.connect(self._set_status)
        self.library.message.connect(self._set_status)
        self.library.requestEngine.connect(self._offer_engine)
        self.library.completed.connect(self._notify_transcript)
        self.session.status.connect(self._set_status)
        self.session.changed.connect(self._session_changed)
        self.session.saved.connect(self._on_saved)
        self.session.failed.connect(self._on_error)
        self.session.recovery.connect(self._on_recovery)
        self.session.progress.connect(lambda percent: self._set_status(f"Guardando… {percent}%"))

    def _build_ui(self):
        self.view = QQuickWidget(self)
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.view.setClearColor(QColor("#191c20"))
        context = self.view.rootContext()
        for name, obj in (("desk", self), ("session", self.session), ("picker", self.picker),
                          ("inputs", self.audio), ("prefs", self.pref), ("library", self.library),
                          ("previewImage", self.preview)):
            context.setContextProperty(name, obj)
        self.view.engine().addImageProvider("preview", self.preview.provider)
        self.view.setSource(QUrl.fromLocalFile(str(qml_entry())))
        if self.view.status() == QQuickWidget.Error:
            raise RuntimeError("\n".join(error.toString() for error in self.view.errors()))
        self.setCentralWidget(self.view)
        self.setFocusProxy(self.view)

    def _once(self, ms, action):
        timer = QTimer(self, singleShot=True, interval=ms)
        timer.timeout.connect(action)
        return timer

    @staticmethod
    def _prewarm_encoder():
        from app.encode.ffmpeg import detect_h264_encoder
        detect_h264_encoder()

    @staticmethod
    def _engine_ready():
        from app.transcription.engine_setup import is_ready
        return is_ready()

    @Property(bool, constant=True)
    def platformMac(self):
        return _MAC

    @Property(str, notify=statusChanged)
    def statusText(self):
        return self._status

    @Property(str, notify=statusChanged)
    def micUsage(self):
        return self._usage

    @Property("QVariantMap", notify=metricsChanged)
    def metrics(self):
        return self._metrics

    @Property(str, notify=resultsChanged)
    def lastFile(self):
        return Path(self._last_output).name if self._last_output else ""

    @Slot(str)
    def _set_status(self, msg):
        self._status = msg
        self.statusChanged.emit()

    @Slot()
    def refreshSource(self):
        old = self.picker.selected
        self.picker.refresh()
        if not self.session.priority() and self.picker.selected and old and self.picker.selected.selection_key == old.selection_key:
            self.preview.refresh()

    @Slot()
    def recordAction(self):
        if self.session.phase == "recovery":
            self.chooseRecovery()
            return
        if self.session.phase in ("recording", "paused"):
            self._set_status("Guardando la grabación…")
            self.session.stop()
            return
        if self.session.phase != "idle" or self.audio.busy or not self.picker.selected:
            return
        if not self._config.capture_system_audio and self.audio.selected is None:
            if not self._confirm("Grabar solo video", "El micrófono y el audio del sistema están desactivados. ¿Grabar solo video?"):
                return
        if not self._ensure_output_folder_for_record() or (_MAC and not self._mac_permissions_ok()):
            return
        if self._config.capture_system_audio and self.audio.route.get("bluetooth"):
            if not self._confirm("Audio del sistema y Bluetooth", self.audio.route.get("warning", "") + "\n¿Continuar con esta salida?"):
                return
        self._last_output = ""
        self.resultsChanged.emit()
        self._silent_ticks = 0
        self._silence_warned = False
        self._set_status("Iniciando grabación…")
        self.session.start(self._build_settings(), self.audio.release_monitor)

    def _build_settings(self):
        return RecordingSettings(video_source=self.picker.selected, mic_device=self.audio.selected,
                                 capture_system_audio=self._config.capture_system_audio,
                                 reduce_echo=self._config.reduce_echo, output_dir=self.pref.directory)

    @Slot()
    def toggleMute(self):
        rec = self.session.recorder
        rec.set_mic_muted(not rec.is_mic_muted())
        self._update_metrics()

    @Slot()
    def chooseOutput(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de salida", str(self.pref.directory))
        if folder:
            self.pref.set_directory(folder)

    def _ensure_output_folder_for_record(self):
        folder = self.pref.directory
        problem = folder_looks_unusable(folder)
        if problem:
            self._dialog(QMessageBox.Warning, "Carpeta de salida", problem).exec()
            self.chooseOutput()
            return not folder_looks_unusable(self.pref.directory)
        probe = dest_file_path(folder, "Grabacion_2099-12-31_23-59-59")
        if ffmpeg_path_too_long(probe) and self._confirm("Carpeta de salida",
                "La longitud de la ruta puede impedir guardar el MP4. ¿Elegir una carpeta más corta?"):
            self.chooseOutput()
        return True

    def _confirm(self, title, message):
        return self._dialog(QMessageBox.Question, title, message, QMessageBox.Yes | QMessageBox.No).exec() == QMessageBox.Yes

    def _mac_permissions_ok(self) -> bool:
        """macOS: sin permiso de pantalla (o de micrófono, si hay uno elegido) no
        se graba; se explica qué falta y se abre Ajustes en el sitio exacto."""
        from app.core import mac_permissions as perms

        faltan = perms.missing_for_recording(
            needs_screen=True,
            needs_microphone=self.audio.selected is not None,
        )
        if not faltan:
            return True
        box = self._dialog(
            QMessageBox.Warning, "Faltan permisos de macOS", perms.explanation(faltan),
            QMessageBox.Open | QMessageBox.Cancel,
        )
        if box.exec() == QMessageBox.Open:
            for m in faltan:
                perms.open_settings(m.kind)
        return False

    def _dialog(self, icon, title: str, text: str, buttons=QMessageBox.Ok):
        """Crea un QMessageBox con estilo legible sobre el tema oscuro."""
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        return box


    @Slot()
    def importFiles(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Transcribir archivo", str(self.pref.directory), file_dialog_filter())
        if files:
            self.library.import_paths(files)

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.library.import_paths(paths)
            self.view.rootObject().setProperty("page", 1)
            event.acceptProposedAction()

    @Slot()
    def openRecordingFolder(self):
        if self._last_output and not open_local(Path(self._last_output).parent):
            self._set_status("No se pudo abrir la carpeta de la grabación.")

    def _offer_pending_save(self):
        pending = load_pending()
        if pending and self.session.phase == "idle":
            self.session.adopt(pending)
            self._set_status("Hay una grabación pendiente de guardar.")

    @Slot()
    def chooseRecovery(self):
        folder = QFileDialog.getExistingDirectory(self, "Guardar la grabación pendiente", str(self.pref.directory))
        if folder:
            self._set_status("Guardando la grabación pendiente…")
            self.session.retry(self.pref.set_directory(folder))

    @Slot()
    def _session_changed(self):
        if self.session.phase == "recording":
            self._hotplug_followup.stop()
        if self._quit_after_finalize and self.session.phase in ("paused", "recording"):
            QTimer.singleShot(0, self.session.stop)
        self._update_metrics()

    def _after_session(self):
        self.audio.update_monitor()
        if self._pending_hotplug:
            self._pending_hotplug = False
            self._refresh_hotplug()

    @Slot(str)
    def _on_saved(self, path):
        self._last_output = path
        self.resultsChanged.emit()
        message = "Grabación guardada"
        if self._config.transcribe_after_recording and self.library.available:
            try:
                if self.library.enqueue_recording(path):
                    message += " · transcripción en cola"
            except (OSError, RuntimeError, ValueError) as exc:
                message += f". No se pudo encolar la transcripción. {exc}"
        self._set_status(message)
        if self._quit_after_finalize:
            self.close()
            return
        self._after_session()
        self.preview.refresh()
        if not self.isActiveWindow() and self._tray.isVisible():
            self._tray.showMessage("Grabación lista", Path(path).name, QSystemTrayIcon.Information, 4000)

    @Slot(str)
    def _on_error(self, message):
        self._set_status(message)
        if self._quit_after_finalize:
            self._quit_after_finalize = False
            self.show()
        self._after_session()

    @Slot(str)
    def _on_recovery(self, message):
        self._on_error(message)
        self._set_status("Grabación pendiente de guardar. " + message)

    @Slot(str)
    def _notify_transcript(self, name):
        if self._tray.isVisible() and not self.isActiveWindow():
            self._tray.showMessage("Transcripción lista", name, QSystemTrayIcon.Information, 4000)

    @Slot()
    def showEngine(self):
        if not _MAC:
            return
        if self._engine_dialog is None:
            from app.ui.engine_dialogs import EnginePanel
            self._engine_dialog = QDialog(self)
            self._engine_dialog.setWindowTitle("Motor de transcripción")
            self._engine_panel = EnginePanel(self.session.priority, self._engine_dialog)
            QVBoxLayout(self._engine_dialog).addWidget(self._engine_panel)
        self._engine_dialog.show()
        self._engine_dialog.raise_()

    @Slot()
    def _offer_engine(self):
        if _MAC and not self._engine_ready():
            self.showEngine()
            self._engine_panel.offer_install_if_needed()

    def _preference_changed(self, key):
        if key == "exclude_window_from_capture":
            self._apply_capture_affinity()
        elif key == "transcription_pc_impact":
            self.library.worker.apply_pc_impact(self._config.transcription_pc_impact)
        elif key == "auto_mute_follow_meeting":
            self._auto_mute_previous = None
            self._update_usage()
        self._update_metrics()

    def _tick(self):
        self._tick_count += 1
        self._update_metrics()
        if self._tick_count % 10 == 0 and self.session.phase == "recording" and self.isVisible():
            self.preview.refresh()
        if self._tick_count % 15 == 0:
            self._update_usage()

    def _update_metrics(self):
        rec = self.session.recorder
        recording = rec.is_recording()
        levels = rec if recording else self.audio.monitor
        muted = rec.is_mic_muted()
        mic, system = meter_display_levels(levels.mic_level(), levels.system_level(),
                    mic_muted=muted, system_enabled=self._config.capture_system_audio)
        seconds = int(rec.elapsed_seconds())
        hours, minutes = divmod(seconds, 3600)
        minutes, seconds = divmod(minutes, 60)
        metrics = dict(time=f"{hours:02}:{minutes:02}:{seconds:02}", mic=round(mic, 2),
                       system=round(system, 2), muted=muted)
        if metrics != self._metrics:
            self._metrics = metrics
            self.metricsChanged.emit()
        if not _MAC and self.session.phase == "recording" and self._config.capture_system_audio:
            self._silent_ticks = self._silent_ticks + 1 if system < .01 else 0
            if self._silent_ticks >= 50 and not self._silence_warned:
                self._silence_warned = True
                self._set_status("El audio del sistema está en silencio. Comprueba la salida de sonido.")

    def _update_usage(self):
        if _MAC:
            return
        own = (os.path.basename(sys.executable), "python")
        try:
            names = sorted({u.name for u in microphone_users(own)})
            usage = "En llamada · " + ", ".join(names) if names else ""
            if self._usage != usage:
                self._usage = usage
                self.statusChanged.emit()
            if self._config.auto_mute_follow_meeting:
                others = is_microphone_in_use_by_others(own)
                mute = should_apply_follow_meeting_mute(others, self._auto_mute_previous)
                self._auto_mute_previous = others
                if mute is not None:
                    self.session.recorder.set_mic_muted(mute)
                    self._update_metrics()
        except OSError:
            pass

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("Grabador de Reuniones")
        menu = QMenu(self)
        act_show = QAction("Mostrar ventana", self)
        act_show.triggered.connect(self._show_from_tray)
        act_rec = QAction("Iniciar / Detener", self)
        act_rec.triggered.connect(self.recordAction)
        act_pause = QAction("Pausar / Reanudar", self)
        act_pause.triggered.connect(self.session.togglePause)
        act_mute = QAction("Silenciar / activar micrófono", self)
        act_mute.triggered.connect(self.toggleMute)
        act_quit = QAction("Salir", self)
        act_quit.triggered.connect(self.close)
        for a in (act_show, act_rec, act_pause, act_mute):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_hotkeys(self) -> None:
        if _MAC:
            from app.ui.hotkeys_mac import MacGlobalHotkeys

            hotkeys_cls = MacGlobalHotkeys
        else:
            hotkeys_cls = GlobalHotkeys
        self._hotkeys = hotkeys_cls(
            self.recordAction, self.session.togglePause, self.toggleMute
        )
        QApplication.instance().installNativeEventFilter(self._hotkeys)

    def _setup_device_watcher(self) -> None:
        """Auto-refresh de mics ante hotplug Windows (debounce en MainWindow)."""
        if _MAC:
            # Sin WM_DEVICECHANGE: se compara la lista de entradas cada 3 s.
            from app.ui import mac_devices

            self._mac_inputs = mac_devices.audio_input_names()
            self._mac_device_poll = QTimer(self)
            self._mac_device_poll.setInterval(3000)
            self._mac_device_poll.timeout.connect(self._poll_mac_devices)
            self._mac_device_poll.start()
            return
        self._device_watcher = DeviceChangeWatcher(self._on_device_change_event)
        QApplication.instance().installNativeEventFilter(self._device_watcher)


    def _poll_mac_devices(self):
        from app.ui import mac_devices
        names = mac_devices.audio_input_names()
        if mac_devices.changed(self._mac_inputs, names):
            self._mac_inputs = names
            self._on_device_change_event()

    def _on_device_change_event(self):
        self._hotplug_debounce.start()

    def _refresh_hotplug(self):
        if self.session.priority():
            self._pending_hotplug = True
        else:
            self.audio.refresh()
            self._hotplug_followup.start()

    def _refresh_hotplug_followup(self):
        if self.session.priority():
            self._pending_hotplug = True
        else:
            self.audio.refresh()

    def _apply_capture_affinity(self):
        apply_window_capture_affinity(int(self.winId()), self._config.exclude_window_from_capture)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._hotkeys_registered:
            self._hotkeys.register(int(self.winId()))
            self._hotkeys_registered = True
        self._apply_capture_affinity()
        self.audio.visible(True)

    def hideEvent(self, event):
        self.audio.visible(False)
        super().hideEvent(event)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.session.priority():
            if self.session.phase == "saving" or self._confirm("Grabación en curso",
                        "¿Guardar la grabación y salir cuando termine?"):
                self._quit_after_finalize = True
                self.session.stop()
                self.hide()
            event.ignore()
            return
        if self.session.phase == "recovery" and not self._confirm("Grabación pendiente",
                "Los archivos están en la carpeta de recuperación. ¿Salir y guardarlos en el próximo inicio?"):
            event.ignore()
            return
        if not self._quit_after_finalize and self.library.worker.has_active_job():
            self._dialog(QMessageBox.Information, "Transcripción en curso",
                         "La transcripción continúa en segundo plano. Puedes consultar el resultado al volver.").exec()
        self._timer.stop()
        self._hotplug_debounce.stop()
        self._hotplug_followup.stop()
        if _MAC:
            self._mac_device_poll.stop()
        self._hotkeys.unregister()
        for native_filter in (self._hotkeys, getattr(self, "_device_watcher", None)):
            if native_filter is not None:
                QApplication.instance().removeNativeEventFilter(native_filter)
        self.library.worker.shutdown()
        self.preview.close()
        self.audio.close()
        self._tray.hide()
        self.view.setSource(QUrl())
        super().closeEvent(event)
        self.closed.emit()

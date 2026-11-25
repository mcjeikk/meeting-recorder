"""Inventario y medidores de preparación. Un solo hilo accede a PortAudio."""
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.capture import sources
from app.capture.monitor import AudioMonitor
from app.capture.windows_audio import list_microphones


class AudioInputs(QObject):
    changed = Signal()
    message = Signal(str)
    _loaded = Signal(object, dict, str)

    def __init__(self, session, config, parent=None):
        super().__init__(parent)
        self.session = session
        self.config = config
        self.monitor = AudioMonitor()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recorder-audio")
        self.devices = []
        self._index = 0
        self._busy = False
        self._visible = False
        self._initialized = False
        self._closed = False
        self.route = {}
        self._loaded.connect(self._apply)

    @Property("QStringList", notify=changed)
    def names(self):
        return ["Sin micrófono"] + [d.name for d in self.devices]

    @Property(int, notify=changed)
    def index(self):
        return self._index

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def routeHint(self):
        return self.route.get("warning") or self.route.get("output_name") or ""

    @property
    def selected(self):
        return self.devices[self._index - 1] if self._index else None

    @Slot()
    def refresh(self):
        if self._closed or self._busy or self.session.busy:
            return
        self._busy = True
        self.changed.emit()
        idle = not self.session.priority()
        reinitialize = idle and self._initialized

        def enumerate_devices():
            if reinitialize:
                self.monitor.stop()
            try:
                devices = list_microphones(refresh=reinitialize)
                error = ""
            except Exception as exc:
                devices, error = [], f"No se pudieron listar los micrófonos. {exc}"
            try:
                route = sources.describe_system_audio_route() if idle else self.route
            except Exception:
                route = {}
            if not self._closed:
                self._loaded.emit(devices, route, error)

        self.executor.submit(enumerate_devices)

    @Slot(object, dict, str)
    def _apply(self, devices, route, error):
        if self._closed:
            return
        previous = self.names[self.index] if self._initialized else self.config.last_mic_name
        self._busy = False
        self.route = route
        if not error:
            self.devices = devices
            self._index = self.names.index(previous) if previous in self.names else int(bool(devices) and not previous)
            if self._initialized and previous not in self.names:
                self.message.emit(f"El micrófono «{previous}» ya no está disponible.")
        else:
            self.message.emit(error)
        self._initialized = True
        self.changed.emit()
        self.update_monitor()

    @Slot(int)
    def choose(self, index):
        if self.session.busy or not 0 <= index <= len(self.devices) or self._index == index:
            return
        self._index = index
        self.config.last_mic_name = self.names[index]
        self.config.save()
        self.changed.emit()
        if self.session.recorder.is_recording():
            self.session.change_mic(self.selected)
        else:
            self.update_monitor(restart=True)

    def visible(self, value):
        self._visible = value
        self.update_monitor()

    def update_monitor(self, restart=False):
        if self._closed or not self._initialized:
            return
        if self._visible and not self.session.priority():
            fn = self.monitor.restart if restart else self.monitor.start
            self.executor.submit(fn, self.selected)
        else:
            self.executor.submit(self.monitor.stop)

    def release_monitor(self):
        self.executor.submit(self.monitor.stop).result()

    def close(self):
        self._closed = True
        self.executor.submit(self.monitor.stop)
        self.executor.shutdown(wait=False)

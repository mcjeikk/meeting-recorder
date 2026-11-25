"""Las filas de la lista pueden cambiar de sitio. La fuente conserva su identidad nativa."""
from collections import Counter

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.capture import sources
from app.core.config import VideoSource


class SourcePicker(QObject):
    changed = Signal()
    selectionChanged = Signal()
    message = Signal(str)

    def __init__(self, locked, parent=None):
        super().__init__(parent)
        self._locked = locked
        self.items = []
        self._labels = []
        self._index = 0

    @Property("QStringList", notify=changed)
    def labels(self):
        return self._labels

    @Property(int, notify=changed)
    def index(self):
        return self._index

    @property
    def selected(self):
        return self.items[self._index] if self.items else None

    @Slot(int)
    def select(self, index):
        if not self._locked() and 0 <= index < len(self.items) and self._index != index:
            self._index = index
            self.changed.emit()
            self.selectionChanged.emit()

    @Slot()
    def refresh(self):
        if self._locked():
            return
        previous = self.selected
        try:
            monitors = sources.list_monitors()
        except Exception:
            monitors = [source for source in self.items if source.kind == "screen"]
        if not monitors:
            monitors = [VideoSource("screen", monitor_index=1, is_primary=True)]
        try:
            windows = sources.list_windows()
        except Exception:
            self.message.emit("No se pudo actualizar la lista de ventanas. Vuelve a intentar.")
            if self.items:
                return
            windows = []
        counts = Counter(w.title for w in windows)
        seen = Counter()
        labels = [m.label for m in monitors]
        for w in windows:
            seen[w.title] += 1
            prefix = f"({seen[w.title]}/{counts[w.title]}) " if counts[w.title] > 1 else ""
            labels.append(prefix + w.title)
        self.items = list(monitors) + list(windows)
        self._index = next((i for i, s in enumerate(self.items)
                            if previous and s.selection_key == previous.selection_key), 0)
        self._labels = labels
        self.changed.emit()
        if previous and self.selected.selection_key != previous.selection_key:
            self.message.emit(f"La fuente anterior ya no está disponible. Se seleccionó {self.selected.label}.")
            self.selectionChanged.emit()

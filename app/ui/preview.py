from threading import Thread

from PySide6.QtCore import QObject, Property, Signal, Slot, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

from app.capture import sources
from app.ui.preview_policy import should_pause_idle_wgc_preview


class PreviewImages(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self.frame = QImage()

    def requestImage(self, image_id, size, requested_size):
        frame = self.frame
        if size is not None:
            size.setWidth(frame.width())
            size.setHeight(frame.height())
        return frame


def frame_image(frame):
    height, width = frame.shape[:2]
    image = QImage(frame.data, width, height, frame.strides[0], QImage.Format_RGB32)
    return image.scaled(QSize(800, 450), Qt.KeepAspectRatio, Qt.SmoothTransformation).copy()


class Preview(QObject):
    changed = Signal()
    _ready = Signal(object, int)

    def __init__(self, picker, session, library, parent=None):
        super().__init__(parent)
        self.picker, self.session, self.library = picker, session, library
        self.provider = PreviewImages()
        self._generation = 0
        self._revision = 0
        self._busy = self._dirty = self._closed = False
        self._ready.connect(self.receive)
        picker.selectionChanged.connect(self.invalidate)

    @Property(str, notify=changed)
    def url(self):
        return "" if self.provider.frame.isNull() else f"image://preview/{self._revision}"

    @Slot()
    def invalidate(self):
        self._generation += 1
        self.provider.frame = QImage()
        self.changed.emit()
        self.refresh()

    def _publish(self, image):
        self._revision += 1
        self.provider.frame = image
        self.changed.emit()

    @Slot()
    def refresh(self):
        if self._closed or self.session.busy:
            return
        rec = self.session.recorder
        if rec.is_recording():
            frame = rec.current_video_frame()
            if frame is not None:
                self._publish(frame_image(frame))
            return
        if should_pause_idle_wgc_preview(recording=False, transcription_open=self.library.open_job()):
            return
        source = self.picker.selected
        if source is None:
            return
        if self._busy:
            self._dirty = True
            return
        self._busy = True
        self._dirty = False
        gen = self._generation

        def grab():
            try:
                frame = (sources.grab_window_frame(source.hwnd) if source.kind == "window"
                         else sources.grab_monitor_frame(source.monitor_index or 1))
                image = frame_image(frame) if frame is not None else None
            except Exception:
                image = None
            if not self._closed:
                self._ready.emit(image, gen)

        Thread(target=grab, daemon=True).start()

    @Slot(object, int)
    def receive(self, image, generation):
        self._busy = False
        if self._closed:
            return
        if generation == self._generation and isinstance(image, QImage) and not image.isNull():
            self._publish(image)
        if self._dirty:
            self._dirty = False
            self.refresh()

    def close(self):
        self._closed = True

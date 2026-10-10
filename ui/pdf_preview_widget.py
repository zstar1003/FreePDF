"""Compatible PDF pane with automatic native recovery on browser failure."""

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from utils.diagnostics import get_logger
from utils.preview_backend import use_native_preview
from ui.native_pdf_widget import NativePdfWidget


class PdfPreviewWidget(QWidget):
    scrollChanged = pyqtSignal(str, int, int)
    previewFailed = pyqtSignal(str, str)
    previewReady = pyqtSignal(str)

    def __init__(self, name, profile=None, locale="zh-cn", parent=None):
        super().__init__(parent)
        self._name = name
        self._path = None
        self._recovery = None
        self._switching = False
        self._recovery_timer = QTimer(self)
        self._recovery_timer.setSingleShot(True)
        self._recovery_timer.timeout.connect(self._recover)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if use_native_preview():
            self._viewer = NativePdfWidget(name, parent=self)
        else:
            from ui.pdfjs_widget import PdfJsWidget
            self._viewer = PdfJsWidget(name, profile, locale, self)
        self._connect()
        layout.addWidget(self._viewer)

    @property
    def view(self):
        return self._viewer.view

    @property
    def pdf_view(self):
        return self.view

    def _connect(self):
        self._viewer.scrollChanged.connect(self.scrollChanged)
        self._viewer.previewReady.connect(self.previewReady)
        self._viewer.previewFailed.connect(self._on_failure)

    def _on_failure(self, name, message):
        if isinstance(self._viewer, NativePdfWidget) or not self._path:
            self.previewFailed.emit(name, message)
        elif not self._switching:
            self._switching = True
            self._recovery = {"reason": message, "previous_backend": "webengine"}
            get_logger("preview").warning("view=%s event=native_recovery details=%s", name, self._recovery)
            self._recovery_timer.start(0)

    def _recover(self):
        if not self._path:
            self._switching = False
            return
        old = self._viewer
        old.previewFailed.disconnect(self._on_failure)
        old.previewReady.disconnect(self.previewReady)
        old.scrollChanged.disconnect(self.scrollChanged)
        self.layout().removeWidget(old)
        old.cleanup()
        old.deleteLater()
        self._viewer = NativePdfWidget(self._name, parent=self)
        self._connect()
        self.layout().addWidget(self._viewer)
        self._switching = False
        if self._path:
            self._viewer.load_pdf(self._path)

    def load_pdf(self, path, preserve_position=False):
        preserve_position = preserve_position and self._path is not None
        self._path = None if path == "about:blank" else path
        self._viewer.load_pdf(path, preserve_position=preserve_position)

    def show_message(self, message):
        self._path = None
        self._viewer.show_message(message)

    def show_loading(self, message):
        self.show_message(message)

    def hide_loading(self):
        self._viewer.hide_loading()

    def set_scroll_position(self, top, left):
        self._viewer.set_scroll_position(top, left)

    def zoom_in(self):
        self._viewer.zoom_in()

    def zoom_out(self):
        self._viewer.zoom_out()

    def diagnostic_state(self):
        state = self._viewer.diagnostic_state()
        if self._recovery:
            state["recovery"] = self._recovery
        return state

    def cleanup(self):
        self._recovery_timer.stop()
        self._path = None
        self._viewer.cleanup()

"""Continuous native PDF reader. No browser process, JavaScript or WebEngine DLL."""

import json
import os
import time
import uuid

from PyQt6.QtCore import QPointF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget

from utils.diagnostics import get_logger


class PaintedPdfView(QPdfView):
    painted = pyqtSignal()

    def paintEvent(self, event):
        super().paintEvent(event)
        self.painted.emit()


class NativePdfWidget(QWidget):
    scrollChanged = pyqtSignal(str, int, int)
    previewFailed = pyqtSignal(str, str)
    previewReady = pyqtSignal(str)

    def __init__(self, name, profile=None, locale=None, parent=None):
        super().__init__(parent)
        self._name = name
        self._state = {"view": name, "backend": "qt_pdf", "stage": "empty"}
        self._started_at = 0
        self._path = None
        self._syncing = False
        self._closed = False
        self._logger = get_logger("preview")
        self.document = QPdfDocument(self)
        self.view = PaintedPdfView(self)
        from PyQt6.QtGui import QPalette, QColor
        palette = self.view.palette()
        palette.setColor(QPalette.ColorRole.Dark, QColor("#d4e0e4"))
        palette.setColor(QPalette.ColorRole.Mid, QColor("#e5edef"))
        self.view.setPalette(palette)
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.view.setPageSpacing(12)
        self.view.painted.connect(self._on_painted)
        self.document.statusChanged.connect(self._on_status)
        self.view.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.view.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        self.view.pageNavigator().currentPageChanged.connect(self._page_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 8, 12, 8)
        previous = QPushButton()
        previous.setToolTip("上一页")
        from ui.theme import style_button
        style_button(previous, "previous")
        previous.clicked.connect(lambda: self._jump(self.page.value() - 2))
        next_page = QPushButton()
        next_page.setToolTip("下一页")
        style_button(next_page, "next")
        next_page.clicked.connect(lambda: self._jump(self.page.value()))
        self.page = QSpinBox()
        self.page.setMinimum(1)
        self.page.setMaximum(1)
        self.page.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.page.setFixedWidth(62)
        self.page.editingFinished.connect(lambda: self._jump(self.page.value() - 1))
        self.pages_label = QLabel("/ 0")
        for item in (previous, self.page, self.pages_label, next_page):
            toolbar.addWidget(item)
        toolbar.addStretch()
        fit = QPushButton("适合宽度")
        fit.clicked.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth))
        toolbar.addWidget(fit)
        layout.addLayout(toolbar)
        self.stack = QStackedWidget()
        self.message = QLabel("打开 PDF，开始阅读与翻译")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setObjectName("emptyState")
        self.stack.addWidget(self.message)
        self.stack.addWidget(self.view)
        layout.addWidget(self.stack)

    def _log(self, event, **details):
        self._logger.info("view=%s load=%s elapsed=%.3f event=%s details=%s", self._name,
                          self._state.get("load_id"), time.monotonic() - self._started_at if self._started_at else 0,
                          event, json.dumps(details, ensure_ascii=False))

    def load_pdf(self, path, preserve_position=False):
        if path == "about:blank":
            self.show_message("打开 PDF，开始阅读与翻译")
            return
        current_page = self.view.pageNavigator().currentPage() if preserve_position else 0
        scroll_top = self.view.verticalScrollBar().value() if preserve_position else 0
        self._closed = False
        self._path = os.path.abspath(path)
        self.document.close()
        self._started_at = time.monotonic()
        self._state = {"view": self._name, "backend": "qt_pdf", "load_id": uuid.uuid4().hex[:10],
                       "pdf_path": self._path, "stage": "requested", "first_page_rendered": False}
        self._log("native_load_requested", path=self._path)
        error = self.document.load(self._path)
        if preserve_position and error == QPdfDocument.Error.None_:
            self._jump(min(current_page, max(0, self.document.pageCount() - 1)))
            QTimer.singleShot(0, lambda: self.view.verticalScrollBar().setValue(scroll_top) if not self._closed else None)
        if error != QPdfDocument.Error.None_ and not self._state.get("failure"):
            self._fail(error.name)

    def _on_status(self, status):
        if self._closed:
            return
        self._log("native_document_status", status=status.name, error=self.document.error().name)
        if status == QPdfDocument.Status.Ready:
            count = self.document.pageCount()
            if not count:
                self._fail("PDF 没有可显示的页面")
                return
            self._state.update(stage="document_loaded", pages=count)
            self._log("document_loaded", backend="qt_pdf", pages=count)
            self.page.setMaximum(count)
            self.page.setValue(1)
            self.pages_label.setText(f"/ {count}")
            self.stack.setCurrentWidget(self.view)
            self.view.viewport().update()
        elif status == QPdfDocument.Status.Error:
            self._fail(self.document.error().name)

    def _on_painted(self):
        if (self._closed or self.document.status() != QPdfDocument.Status.Ready
                or self._state.get("first_page_rendered") or self._state.get("verification_pending")):
            return
        self._state["verification_pending"] = True
        load_id = self._state.get("load_id")
        QTimer.singleShot(0, lambda: self._verify_render(load_id))

    def _verify_render(self, load_id):
        if self._closed or load_id != self._state.get("load_id"):
            return
        self._state.pop("verification_pending", None)
        if self.document.status() != QPdfDocument.Status.Ready:
            return
        points = self.document.pagePointSize(0)
        image = self.document.render(0, QSize(384, max(1, min(2048, round(384 * points.height() / max(1, points.width()))))))
        if image.isNull():
            self._fail("页面渲染失败")
            return
        self._state.update(stage="first_page_rendered", first_page_rendered=True,
                           rendered_size=[image.width(), image.height()])
        self._state.pop("failure", None)
        self._log("first_page_rendered", backend="qt_pdf", width=image.width(), height=image.height())
        self.previewReady.emit(self._name)

    def _fail(self, reason):
        if self._state.get("failure"):
            return
        message = "无法显示 PDF：" + reason
        self._state.update(stage="failed", failure=message)
        self._log("native_document_error", error=reason)
        self.message.setText(message)
        self.stack.setCurrentWidget(self.message)
        self.previewFailed.emit(self._name, message)

    def _jump(self, page):
        if self.document.pageCount():
            self.view.pageNavigator().jump(max(0, min(self.document.pageCount() - 1, page)), QPointF(), self.view.zoomFactor())

    def _page_changed(self, page):
        self.page.setValue(page + 1)

    def _on_scroll(self, *_):
        if not self._syncing:
            self.scrollChanged.emit(self._name, self.view.verticalScrollBar().value(), self.view.horizontalScrollBar().value())

    def set_scroll_position(self, top, left):
        self._syncing = True
        try:
            self.view.verticalScrollBar().setValue(top)
            self.view.horizontalScrollBar().setValue(left)
        finally:
            self._syncing = False

    def _zoom(self, factor):
        width = self.document.pagePointSize(max(0, self.view.pageNavigator().currentPage())).width() if self.document.pageCount() else 600
        current = self.view.zoomFactor()
        if self.view.zoomMode() == QPdfView.ZoomMode.FitToWidth:
            current = max(0.1, (self.view.viewport().width() - 24) / max(1, width))
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.2, min(5.0, current * factor)))

    def zoom_in(self):
        self._zoom(1.2)

    def zoom_out(self):
        self._zoom(1 / 1.2)

    def show_message(self, message):
        self.document.close()
        self._path = None
        self._state = {"view": self._name, "backend": "qt_pdf", "stage": "message"}
        self.message.setText(message)
        self.stack.setCurrentWidget(self.message)

    def show_loading(self, message):
        self.show_message(message)

    def hide_loading(self):
        pass

    def set_locale(self, locale):
        pass

    def diagnostic_state(self):
        return dict(self._state, visible=self.isVisible(), width=self.width(), height=self.height())

    def cleanup(self):
        self._closed = True
        self.document.close()
        self.view.setDocument(None)

"""One export sheet, with a background worker for large PDF documents."""
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ui.theme import style_button
from utils.diagnostics import get_logger
from utils.pdf_export import ExportDestination, export_pdf


class ExportThread(QThread):
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, original, translated, destination, layout, parent, destination_guard=None):
        super().__init__(parent)
        self.paths = (original, translated, destination)
        self.export_layout = layout
        self.destination_guard = destination_guard

    def run(self):
        try:
            export_pdf(*self.paths, layout=self.export_layout, destination_guard=self.destination_guard)
            get_logger("export").info("PDF export completed layout=%s destination=%s", self.export_layout, self.paths[2])
            self.completed.emit(str(self.paths[2]))
        except Exception as error:  # noqa: BLE001 - report all worker failures to the UI
            get_logger("export").exception("PDF export failed")
            self.failed.emit(str(error))


class ExportDialog(QDialog):
    def __init__(self, original, translated, parent=None):
        super().__init__(parent)
        self.original, self.translated = original, translated
        self.worker = None
        self.setWindowTitle("导出 PDF")
        self.resize(510, 290)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("选择你的阅读版本")
        title.setObjectName("brandTitle")
        layout.addWidget(title)
        note = QLabel("本地译文已保存，导出会创建一份新的 PDF。")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        self.format = QComboBox()
        self.format.addItem("左右对照 · 原文在左，译文在右", "side_by_side")
        self.format.addItem("仅译文 · 保留原始版式", "translation")
        layout.addWidget(self.format)
        self.status = QLabel("左右对照每页对应同一页原文与译文，文字保持清晰。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.reject)
        self.export_button = QPushButton("导出 PDF")
        style_button(self.export_button, "export", primary=True)
        self.export_button.clicked.connect(self._export)
        buttons.addWidget(self.close_button)
        buttons.addStretch()
        buttons.addWidget(self.export_button)
        layout.addLayout(buttons)

    def _export(self):
        if self.worker is not None and self.worker.isRunning():
            return
        suffix = "-bilingual" if self.format.currentData() == "side_by_side" else "-translated"
        name = str(Path(self.translated).parent / (Path(self.original).stem + suffix + ".pdf"))
        path, _ = QFileDialog.getSaveFileName(self, "导出 PDF", name, "PDF 文档 (*.pdf)")
        if not path:
            return
        if not path.lower().endswith('.pdf'):
            path += '.pdf'
        try:
            guard = ExportDestination.capture(self.original, self.translated, path)
        except (OSError, ValueError) as error:
            self.status.setText("导出失败：" + str(error))
            return
        if guard.signature is not None:
            answer = QMessageBox.question(
                self, "确认覆盖 PDF",
                f"文件已存在：\n{guard.path}\n\n是否替换此文件？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        path = str(guard.path)
        self.export_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.format.setEnabled(False)
        self.status.setText("正在生成 PDF…")
        self.worker = ExportThread(self.original, self.translated, path, self.format.currentData(), self, destination_guard=guard)
        self.worker.completed.connect(lambda destination: self._finished("已导出：" + destination))
        self.worker.failed.connect(lambda message: self._finished("导出失败：" + message))
        self.worker.start()

    def _finished(self, message):
        self.status.setText(message)
        self.export_button.setEnabled(True)
        self.close_button.setEnabled(True)
        self.format.setEnabled(True)

    def reject(self):
        if self.worker is None or not self.worker.isRunning():
            super().reject()

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
        else:
            event.accept()

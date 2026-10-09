"""Support tools kept inside the settings dialog."""

from datetime import datetime

from PyQt6.QtWidgets import QCheckBox, QDialog, QFileDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from utils.diagnostics import export_diagnostics, get_logger, read_preferences, set_software_rendering


class DiagnosticsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("诊断与日志")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        description = QLabel("日志自动保存在本机。遇到预览空白或翻译问题时，\n请先重现问题，再导出日志供开发者分析。")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.software_checkbox = QCheckBox("使用软件渲染（更改后需重启软件）")
        self.software_checkbox.setToolTip("用于排查显卡驱动导致的空白或崩溃，可能降低预览性能。")
        self.software_checkbox.setChecked(bool(read_preferences().get("software_rendering")))
        self.software_checkbox.toggled.connect(self._save_rendering)
        layout.addWidget(self.software_checkbox)
        self.export_button = QPushButton("导出日志…")
        self.export_button.clicked.connect(self._export)
        layout.addWidget(self.export_button)
        view_logs = QPushButton("查看翻译日志…")
        view_logs.clicked.connect(self._view_translation_logs)
        layout.addWidget(view_logs)
        note = QLabel("导出包包含运行环境、预览状态和近期日志，不包含 PDF 或配置文件。\n日志中可能包含文件名和路径，常见密钥字段会脱敏。")
        note.setWordWrap(True)
        layout.addWidget(note)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _view_translation_logs(self):
        from ui.log_dialog import LogDialog

        LogDialog(self).exec()

    def _save_rendering(self, enabled):
        try:
            set_software_rendering(enabled)
        except OSError:
            get_logger("settings").exception("Cannot save rendering preference")
            self.software_checkbox.blockSignals(True)
            self.software_checkbox.setChecked(not enabled)
            self.software_checkbox.blockSignals(False)
            QMessageBox.warning(self, "保存失败", "无法保存设置，请检查用户目录的写入权限。")

    def _export(self):
        filename = "FreePDF-logs-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip"
        path, _ = QFileDialog.getSaveFileName(self, "导出诊断日志", filename, "ZIP 压缩文件 (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        window = self.parentWidget()
        while window is not None and not hasattr(window, "left_pdf_widget"):
            window = window.parentWidget()
        states = {}
        if window is not None:
            states = {"left": window.left_pdf_widget.diagnostic_state(),
                      "right": window.right_pdf_widget.diagnostic_state()}
        try:
            export_diagnostics(path, states)
        except (OSError, ValueError):
            get_logger("export").exception("Diagnostic export failed")
            QMessageBox.warning(self, "导出失败", "无法写入日志文件，请选择其他保存位置。")
            return
        QMessageBox.information(self, "导出成功", f"日志已保存到：\n{path}")

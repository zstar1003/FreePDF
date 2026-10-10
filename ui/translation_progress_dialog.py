"""A compact, live view of real worker events and committed output."""

import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextBrowser, QVBoxLayout
from utils.translation_logger import get_translation_logger
from ui.theme import style_button


class TranslationProgressDialog(QDialog):
    def __init__(self, window):
        super().__init__(window, Qt.WindowType.Tool)
        self.setWindowTitle("翻译进度详情")
        self.resize(500, 470)
        self.setMinimumSize(460, 430)
        self.window = window
        self.logger = get_translation_logger()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)
        self.stage = QLabel()
        self.stage.setObjectName("dialogTitle")
        self.stage.setWordWrap(True)
        layout.addWidget(self.stage)
        self.filename = QLabel()
        self.filename.setObjectName("muted")
        self.filename.setWordWrap(True)
        layout.addWidget(self.filename)
        self.progress = QProgressBar()
        self.progress.setMinimumHeight(26)
        layout.addWidget(self.progress)
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)
        self.values = {}
        for row, (key, caption) in enumerate((("pages", "已保存页面"), ("current", "当前页面"),
                                             ("paragraphs", "段落处理"), ("elapsed", "已用时间"), ("waiting", "距最近进展"))):
            label = QLabel(caption)
            label.setObjectName("muted")
            value = QLabel()
            self.values[key] = value
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
        layout.addLayout(grid)
        self.notice = QLabel()
        self.notice.setObjectName("muted")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.events = QTextBrowser()
        self.events.setMinimumHeight(100)
        self.events.setReadOnly(True)
        layout.addWidget(self.events, 1)
        footer = QHBoxLayout()
        self.stop_button = QPushButton("停止并保留")
        style_button(self.stop_button)
        self.stop_button.clicked.connect(self.stop_translation)
        footer.addWidget(self.stop_button)
        self.resume_button = QPushButton("继续翻译")
        style_button(self.resume_button, primary=True)
        self.resume_button.clicked.connect(self.resume_translation)
        footer.addWidget(self.resume_button)
        footer.addStretch()
        close_button = QPushButton("关闭")
        style_button(close_button, quiet=True)
        close_button.clicked.connect(self.close)
        footer.addWidget(close_button)
        layout.addLayout(footer)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self.logger.state_updated.connect(self.refresh)
        self.refresh()

    def refresh(self, state=None):
        state = self.logger.get_state()
        running = state.get("status") == "running"
        completed, total = state.get("completed", 0), state.get("total", 0)
        self.stage.setText(state.get("stage", "尚未开始翻译"))
        self.filename.setText(Path(state.get("file", "")).name or "导入 PDF 后将显示实时进度")
        self.progress.setRange(0, total or 1)
        self.progress.setValue(completed)
        self.progress.setFormat(f"{completed} / {total} 页已保存" if total else "等待文档信息")
        self.values["pages"].setText(f"{completed} / {total}" if total else "—")
        self.values["current"].setText(f"第 {state['page']} 页 / 共 {state.get('document_pages', total)} 页" if state.get("page") else "—")
        self.values["paragraphs"].setText(f"已处理 {state.get('finished', 0)} · 进行中 {state.get('active', 0)}")
        elapsed = int(state.get("elapsed", 0))
        self.values["elapsed"].setText(f"{elapsed // 60} 分 {elapsed % 60:02d} 秒")
        waiting = int(max(0, time.monotonic() - state.get("last_activity", time.monotonic()))) if running else 0
        self.values["waiting"].setText(f"{waiting} 秒" if running else "—")
        self.notice.setText(state.get("message") or ("已完成的页面会立即保存并显示。尚未翻译的页面暂时保留原文。" if running else
                            "所有选定页面已完成，可导出 PDF。" if state.get("status") == "completed" else "完成的页面会保留；进度按实际保存的页面计算。"))
        lines = [line for line in self.logger.get_all_logs() if any(token in line for token in ("[阶段开始]", "[PROGRESS]", "[ERROR]", "[WARN]"))][-8:]
        text = "\n".join(lines)
        if self.events.toPlainText() != text:
            self.events.setPlainText(text)
            self.events.verticalScrollBar().setValue(self.events.verticalScrollBar().maximum())
        current_file = str(Path(self.window.current_file).resolve()) if self.window.current_file else ""
        same_file = current_file == str(Path(state.get("file", "")).resolve())
        self.stop_button.setVisible(running and same_file and self.window.translation_manager.is_translating())
        self.resume_button.setVisible(state.get("status") in ("partial", "failed"))
        self.resume_button.setEnabled(same_file and not self.window.translation_manager.is_translating())

    def stop_translation(self):
        self.stop_button.setEnabled(False)
        self.window.translation_manager.stop_current_translation()
        self.stop_button.setEnabled(True)
        self.window.progress_bar.hide()
        self.window.progress_percent.hide()
        self.window.status_label.set_status("翻译已停止 · 已完成页面已保留", "warning")
        self.refresh()

    def resume_translation(self):
        if self.window.current_file:
            self.window.start_translation(self.window.current_file)
        self.refresh()

    def showEvent(self, event):
        self.refresh()
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

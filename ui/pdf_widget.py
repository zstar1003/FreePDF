"""PDF显示组件 - 基于Web渲染"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWebChannel import QWebChannel

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class PDFViewCommunicator(QObject):
    """用于与JavaScript通信的对象"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_position = 0.0
        
    @pyqtSlot(float)
    def setScrollPosition(self, position):
        """从JavaScript接收滚动位置"""
        self._scroll_position = position
        if self.parent():
            self.parent().on_scroll_changed(position)
    
    @pyqtSlot(float)
    def updateScrollPosition(self, position):
        """更新JavaScript的滚动位置"""
        self._scroll_position = position


class PDFWidget(QWidget):
    """PDF显示组件"""
    scroll_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.page_loaded = False
        self.js_ready = False
        self.error_label = None
        self.web_view = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建堆叠部件用于显示错误信息
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # 错误标签
        self.error_label = QLabel()
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                padding: 20px;
                background: #fde7e7;
                border: 1px solid #ffa4a4;
                border-radius: 4px;
                font-family: system-ui, -apple-system, sans-serif;
            }
        """)
        self.stacked_widget.addWidget(self.error_label)

        # Web视图
        self.web_view = QWebEngineView()
        
        # 禁用GPU加速和WebGL
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AcceleratedCompositingEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
        
        self.stacked_widget.addWidget(self.web_view)
        self.stacked_widget.setCurrentWidget(self.web_view)

        # 设置通信通道
        self.channel = QWebChannel()
        self.communicator = PDFViewCommunicator(self)
        self.channel.registerObject("communicator", self.communicator)
        self.web_view.page().setWebChannel(self.channel)

        # 加载HTML模板
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "pdf_viewer.html")
        logger.debug(f"加载HTML模板: {template_path}")
        
        if not os.path.exists(template_path):
            self.show_error(f"HTML模板不存在: {template_path}")
            return
            
        self.web_view.setUrl(QUrl.fromLocalFile(template_path))
        
        # 连接信号
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.page().windowCloseRequested.connect(self._on_window_close_requested)
        self.web_view.page().console_message_received.connect(self._on_console_message)

    def _on_console_message(self, level, message, line, source):
        """处理来自JavaScript的控制台消息"""
        logger.debug(f"JS Console ({level}): {message} (line {line}, source: {source})")

    def _on_window_close_requested(self):
        """处理窗口关闭请求"""
        logger.debug("Window close requested")

    def _on_load_finished(self, ok):
        """处理页面加载完成事件"""
        if not ok:
            self.show_error("PDF查看器加载失败")
            return

        logger.info("PDF查看器页面加载完成")
        self.page_loaded = True
        
        # 检查PDF.js状态
        self.web_view.page().runJavaScript(
            "checkPDFJS()",
            self._check_pdfjs_callback
        )

    def _check_pdfjs_callback(self, result):
        """检查PDF.js加载状态的回调"""
        try:
            if isinstance(result, str):
                result = json.loads(result)
            
            logger.debug(f"PDF.js状态检查结果: {result}")
            
            if not result.get("pdfjsLoaded"):
                self.show_error("PDF.js库加载失败")
                return
                
            logger.info(f"PDF.js加载成功，版本: {result.get('version', '未知')}")
            self.js_ready = True
            
            # 如果有待加载的文件，现在加载它
            if self.current_file:
                self._load_current_file()
                
        except Exception as e:
            logger.error(f"检查PDF.js状态时出错: {e}")
            self.show_error(f"检查PDF.js状态时出错: {e}")

    def show_error(self, message):
        """显示错误消息"""
        logger.error(f"错误: {message}")
        self.error_label.setText(message)
        self.stacked_widget.setCurrentWidget(self.error_label)

    def _load_current_file(self):
        """加载当前PDF文件"""
        if not self.current_file:
            return
            
        if not self.page_loaded or not self.js_ready:
            logger.warning("页面或PDF.js尚未准备好")
            return
            
        try:
            file_url = QUrl.fromLocalFile(self.current_file).toString()
            logger.info(f"正在加载PDF文件: {file_url}")
            
            # 使用JavaScript加载PDF
            script = f"loadPDF('{file_url}')"
            self.web_view.page().runJavaScript(
                script,
                self._load_pdf_callback
            )
            
        except Exception as e:
            logger.error(f"加载PDF文件时出错: {e}")
            self.show_error(f"加载PDF文件时出错: {e}")

    def _load_pdf_callback(self, result):
        """PDF加载回调"""
        if result is not None:
            logger.debug(f"PDF加载结果: {result}")

    def load_pdf(self, file_path: str):
        """加载PDF文件"""
        if not os.path.isfile(file_path):
            self.show_error(f"文件不存在: {file_path}")
            return
            
        logger.info(f"准备加载PDF文件: {file_path}")
        self.current_file = file_path
        
        if self.page_loaded and self.js_ready:
            self._load_current_file()

    def on_scroll_changed(self, position):
        """处理滚动位置改变"""
        self.scroll_changed.emit(position)
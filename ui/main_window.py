"""主窗口"""

from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QLabel, QScrollArea, QPushButton, QFileDialog, 
    QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import QApplication
from core.pdf_document import PDFDocument
from ui.pdf_widget import VirtualPDFWidget
from utils.constants import *  # noqa: F403


DEFAULT_ZOOM = 1.0
MAX_ZOOM = 10.0
MIN_ZOOM = 0.1
ZOOM_STEP = 1.1
SCROLL_RESTORE_DELAY = 100


class PDFViewer(QMainWindow):
    """PDF查看器主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高性能连续PDF预览器")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化
        self.pdf_doc = PDFDocument()
        self.zoom_factor = DEFAULT_ZOOM
        self.current_page = 0
        self.selected_text = ""
        self._closing = False
        
        self._setup_ui()
        
    def _setup_ui(self):
        """设置界面"""
        self._create_menu()
        self._create_toolbar()
        self._create_pdf_area()
        self._create_status_bar()
        
    def _create_menu(self):
        """创建菜单"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        open_action = QAction('打开PDF', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')
        
        copy_action = QAction('复制', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(self.copy_text)
        edit_menu.addAction(copy_action)
        
    def _create_toolbar(self):
        """创建工具栏"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.main_layout = QVBoxLayout(central_widget)
        
        toolbar = QHBoxLayout()
        
        # 页面信息
        self.page_label = QLabel('页面: 0 / 0')
        toolbar.addWidget(self.page_label)
        
        toolbar.addStretch()
        
        # 缩放控制
        zoom_out_btn = QPushButton('缩小 (-)')
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        self.zoom_label = QLabel(f'{int(DEFAULT_ZOOM * 100)}%')
        toolbar.addWidget(self.zoom_label)
        
        zoom_in_btn = QPushButton('放大 (+)')
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        reset_btn = QPushButton('重置')
        reset_btn.clicked.connect(self.reset_zoom)
        toolbar.addWidget(reset_btn)
        
        self.main_layout.addLayout(toolbar)
        
    def _create_pdf_area(self):
        """创建PDF显示区域"""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.pdf_widget = VirtualPDFWidget()
        self.pdf_widget.text_selected.connect(self.on_text_selected)
        self.pdf_widget.page_changed.connect(self.on_page_changed)
        
        # 占位符
        placeholder = QLabel(
            "请打开PDF文件\n\n功能特点：\n• 连续滚动浏览\n• 虚拟渲染技术\n• 精确文本选择\n• Ctrl+滚轮缩放"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "QLabel { background: #f8f9fa; padding: 50px; font-size: 16px; color: #666; }"
        )
        
        self.scroll_area.setWidget(placeholder)
        self.main_layout.addWidget(self.scroll_area)
        
        # 绑定事件
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.scroll_area.wheelEvent = self.wheel_event
        
    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
    def open_file(self):
        """打开文件"""
        if self._closing:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF文件 (*.pdf)"
        )
        
        if file_path:
            self.load_pdf(file_path)
            
    def load_pdf(self, file_path):
        """加载PDF"""
        if self._closing:
            return
            
        success, message = self.pdf_doc.load(file_path)
        
        if success:
            self.status_bar.showMessage("正在初始化PDF显示...")
            
            # 设置PDF widget
            self.pdf_widget.set_document(self.pdf_doc, self.zoom_factor)
            self.scroll_area.setWidget(self.pdf_widget)
            
            # 更新界面
            self.page_label.setText(f'页面: 1 / {self.pdf_doc.total_pages}')
            self.zoom_label.setText(f'{int(self.zoom_factor * 100)}%')
            
            # 触发初始加载
            QApplication.processEvents()
            self.on_scroll(0)
            
            filename = file_path.split('/')[-1]
            self.status_bar.showMessage(f"已载入: {filename} ({self.pdf_doc.total_pages} 页)")
        else:
            QMessageBox.critical(self, "错误", f"无法打开PDF:\n{message}")
            
    def wheel_event(self, event):
        """滚轮事件"""
        if self._closing:
            return
            
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            QScrollArea.wheelEvent(self.scroll_area, event)
            
    def zoom_in(self):
        """放大"""
        if self._closing or self.zoom_factor >= MAX_ZOOM:
            return
            
        old_ratio = self._get_scroll_ratio()
        self.zoom_factor *= ZOOM_STEP
        self._refresh_view(old_ratio)
            
    def zoom_out(self):
        """缩小"""
        if self._closing or self.zoom_factor <= MIN_ZOOM:
            return
            
        old_ratio = self._get_scroll_ratio()
        self.zoom_factor /= ZOOM_STEP
        self._refresh_view(old_ratio)
    
    def reset_zoom(self):
        """重置缩放"""
        if self._closing:
            return
            
        old_ratio = self._get_scroll_ratio()
        self.zoom_factor = DEFAULT_ZOOM
        self._refresh_view(old_ratio)
            
    def _get_scroll_ratio(self):
        """获取滚动比例"""
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() > 0:
            return scrollbar.value() / scrollbar.maximum()
        return 0
        
    def _refresh_view(self, scroll_ratio=0):
        """刷新视图"""
        if self._closing or not self.pdf_doc.doc:
            return
            
        self.status_bar.showMessage(f"正在重新渲染 (缩放: {int(self.zoom_factor * 100)}%)...")
        
        self.pdf_widget.set_document(self.pdf_doc, self.zoom_factor)
        self.zoom_label.setText(f'{int(self.zoom_factor * 100)}%')
        
        QApplication.processEvents()
        
        # 恢复滚动位置
        QTimer.singleShot(SCROLL_RESTORE_DELAY, lambda: self._restore_scroll_position(scroll_ratio))
        
        self.status_bar.showMessage(f"缩放完成: {int(self.zoom_factor * 100)}%")
    
    def _restore_scroll_position(self, scroll_ratio):
        """恢复滚动位置"""
        if self._closing:
            return
            
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() > 0:
            new_value = int(scroll_ratio * scrollbar.maximum())
            scrollbar.setValue(new_value)
            
    def on_scroll(self, value):
        """滚动事件"""
        if self._closing or not self.pdf_doc.doc:
            return
            
        viewport_height = self.scroll_area.viewport().height()
        self.pdf_widget.update_viewport(value, viewport_height)
            
    def on_page_changed(self, page_num):
        """页面改变"""
        if not self._closing:
            self.current_page = page_num
            self.page_label.setText(f'页面: {page_num + 1} / {self.pdf_doc.total_pages}')
        
    def on_text_selected(self, text):
        """文本选择"""
        if not self._closing:
            self.selected_text = text
            word_count = len(text.split())
            self.status_bar.showMessage(f"已选择: {word_count} 词 - Ctrl+C复制")
        
    def copy_text(self):
        """复制文本"""
        if self._closing:
            return
            
        if self.selected_text:
            QApplication.clipboard().setText(self.selected_text)
            self.status_bar.showMessage("已复制到剪贴板")
        else:
            self.status_bar.showMessage("没有选中文本")
            
    def closeEvent(self, event: QCloseEvent):
        """关闭事件"""
        print("开始关闭主窗口...")
        self._closing = True
        
        # 显示关闭进度
        self.status_bar.showMessage("正在关闭，请稍候...")
        QApplication.processEvents()
        
        # 清理PDF widget
        if hasattr(self, 'pdf_widget'):
            self.pdf_widget.cleanup_threads()
        
        # 关闭PDF文档
        self.pdf_doc.close()
        
        # 确保所有事件处理完成
        QApplication.processEvents()
        
        print("主窗口关闭完成")
        event.accept() 
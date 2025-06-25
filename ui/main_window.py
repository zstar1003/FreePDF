"""主窗口模块"""

import os

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.translation import TranslationManager
from ui.components import LoadingWidget, StatusLabel, SyncScrollArea
from ui.pdf_widget import PDFWidget
from utils.constants import (
    DEFAULT_ZOOM,
    MAX_ZOOM,
    MIN_ZOOM,
)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FreePDF")
        self.setWindowIcon(QIcon("ui/logo/logo.ico"))
        self.setGeometry(100, 100, 1600, 900)
        self.showMaximized()
        
        # 初始化组件
        self.current_file = None
        self.translation_manager = TranslationManager()
        
        # 创建UI
        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        self.setup_connections()
        
    def setup_ui(self):
        """设置UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 文件操作按钮
        self.open_btn = QPushButton("打开PDF文件")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        toolbar_layout.addWidget(self.open_btn)
        
        toolbar_layout.addStretch()
        
        # 缩放控制
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("缩放:"))
        
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setFixedSize(30, 30)
        zoom_layout.addWidget(self.zoom_out_btn)
        
        self.zoom_spinbox = QSpinBox()
        self.zoom_spinbox.setRange(int(MIN_ZOOM * 100), int(MAX_ZOOM * 100))
        self.zoom_spinbox.setValue(int(DEFAULT_ZOOM * 100))
        self.zoom_spinbox.setSuffix("%")
        self.zoom_spinbox.setFixedWidth(80)
        zoom_layout.addWidget(self.zoom_spinbox)
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(30, 30)
        zoom_layout.addWidget(self.zoom_in_btn)
        
        toolbar_layout.addLayout(zoom_layout)
        main_layout.addLayout(toolbar_layout)
        
        # 分割器 - 左右两个预览区
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧预览区（原始PDF）
        left_frame = QFrame()
        left_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(2, 2, 2, 2)
        
        # 左侧标题
        left_title = QLabel("原始文档")
        left_title.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
                font-weight: bold;
                color: #495057;
            }
        """)
        left_layout.addWidget(left_title)
        
        # 左侧PDF查看器
        self.left_pdf_widget = PDFWidget()
        left_layout.addWidget(self.left_pdf_widget)
        
        # 右侧预览区（翻译PDF）
        right_frame = QFrame()
        right_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(2, 2, 2, 2)
        
        # 右侧标题
        right_title = QLabel("翻译文档")
        right_title.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
                font-weight: bold;
                color: #495057;
            }
        """)
        right_layout.addWidget(right_title)
        
        # 右侧PDF查看器
        self.right_pdf_widget = PDFWidget()
        right_layout.addWidget(self.right_pdf_widget)
        
        # 创建加载动画，但不添加到布局中！
        self.loading_widget = LoadingWidget("等待上传PDF文件...")
        # 设置parent为right_frame，但不添加到layout
        self.loading_widget.setParent(right_frame)
        self.loading_widget.hide()
        
        # 保存right_frame的引用，用于后续定位
        self.right_frame = right_frame
        
        # 添加到分割器
        self.splitter.addWidget(left_frame)
        self.splitter.addWidget(right_frame)
        self.splitter.setSizes([800, 800])  # 初始均分
        
        main_layout.addWidget(self.splitter)
        
        # 设置同步滚动
        self.sync_scroll = SyncScrollArea(
            self.left_pdf_widget.scroll_area, 
            self.right_pdf_widget.scroll_area
        )
        
    def setup_menu(self):
        """设置菜单"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        open_action = QAction("打开PDF", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图")
        
        sync_action = QAction("同步滚动", self)
        sync_action.setCheckable(True)
        sync_action.setChecked(True)
        sync_action.triggered.connect(self.toggle_sync_scroll)
        view_menu.addAction(sync_action)
        
    def setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = StatusLabel()
        self.status_bar.addWidget(self.status_label)
        
        # 页面信息
        self.page_info_label = QLabel("无文档")
        self.status_bar.addPermanentWidget(self.page_info_label)
        
    def setup_connections(self):
        """设置信号连接"""
        # 文件操作
        self.open_btn.clicked.connect(self.open_file)
        
        # 缩放控制
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_spinbox.valueChanged.connect(self.on_zoom_changed)
        
        # PDF查看器信号
        self.left_pdf_widget.page_changed.connect(self.on_page_changed)
        self.left_pdf_widget.text_selected.connect(self.on_text_selected)
        
        # 翻译管理器信号
        self.translation_manager.current_thread = None
        
    @pyqtSlot()
    def open_file(self):
        """打开PDF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF files (*.pdf)"
        )
        
        if file_path:
            self.load_pdf_file(file_path)
            
    def load_pdf_file(self, file_path):
        """加载PDF文件"""
        try:
            # 加载到左侧预览器
            if self.left_pdf_widget.load_pdf(file_path):
                self.current_file = file_path
                
                # 更新状态
                filename = os.path.basename(file_path)
                self.status_label.set_status(f"已加载: {filename}", "success")
                
                # 更新页面信息
                if self.left_pdf_widget.doc:
                    total_pages = self.left_pdf_widget.doc.page_count
                    self.page_info_label.setText(f"共 {total_pages} 页")
                
                # 隐藏右侧占位符并显示加载动画
                self.right_pdf_widget.placeholder.hide()
                self.show_loading_centered("正在准备翻译...")
                
                # 开始翻译
                self.start_translation(file_path)
                
            else:
                QMessageBox.warning(self, "错误", "无法打开PDF文件")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件时出错: {str(e)}")

    def show_loading_centered(self, message):
        """显示居中的加载动画"""
        self.loading_widget.set_message(message)
        self.loading_widget.show()
        
        # 使用QTimer延迟执行居中定位，确保布局已完成
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, self.center_loading_widget)

    def center_loading_widget(self):
        """将loading widget居中在PDF widget区域"""
        try:
            # 获取PDF widget的几何信息
            pdf_widget_rect = self.right_pdf_widget.geometry()
            
            # 计算居中位置（相对于right_frame）
            x = pdf_widget_rect.x() + (pdf_widget_rect.width() - self.loading_widget.width()) // 2
            y = pdf_widget_rect.y() + (pdf_widget_rect.height() - self.loading_widget.height()) // 2
            
            self.loading_widget.move(x, y)
            self.loading_widget.raise_()  # 确保在最上层
            
        except Exception as e:
            print(f"居中loading widget时出错: {e}")

    def hide_loading(self):
        """隐藏加载动画"""
        self.loading_widget.hide()

    def start_translation(self, file_path):
        """开始翻译PDF"""
        try:
            self.translation_manager.start_translation(
                file_path,
                progress_callback=self.on_translation_progress,
                completed_callback=self.on_translation_completed,
                failed_callback=self.on_translation_failed
            )
        except Exception as e:
            self.on_translation_failed(f"启动翻译失败: {str(e)}")
        
    @pyqtSlot(str)
    def on_translation_progress(self, message):
        """翻译进度更新"""
        try:
            self.loading_widget.set_message(message)
            self.status_label.set_status(message, "info")
        except Exception as e:
            print(f"更新翻译进度时出错: {e}")
        
    @pyqtSlot(str)
    def on_translation_completed(self, translated_file):
        """翻译完成"""
        try:
            # 检查翻译文件是否存在
            if not os.path.exists(translated_file):
                self.on_translation_failed("翻译文件不存在")
                return
            
            # 记录翻译文件
            self.translation_manager.set_translated_file(self.current_file, translated_file)
            
            # 加载翻译后的文件到右侧
            if self.right_pdf_widget.load_pdf(translated_file):
                # 隐藏加载动画
                self.loading_widget.hide()
                
                # 同步缩放
                zoom_factor = self.left_pdf_widget.zoom_factor
                self.right_pdf_widget.set_zoom(zoom_factor)
                
                # 启用同步滚动
                self.sync_scroll.set_enabled(True)
                
                filename = os.path.basename(translated_file)
                self.status_label.set_status(f"翻译完成: {filename}", "success")
            else:
                self.on_translation_failed("无法加载翻译后的文件")
                
        except Exception as e:
            self.on_translation_failed(f"加载翻译文件时出错: {str(e)}")
            
    @pyqtSlot(str)
    def on_translation_failed(self, error_message):
        """翻译失败"""
        try:
            # 隐藏加载动画
            self.loading_widget.hide()
            
            # 恢复显示右侧占位符
            self.right_pdf_widget.placeholder.show()
            self.right_pdf_widget.scroll_area.setWidget(self.right_pdf_widget.placeholder)
            
            # 显示错误状态
            self.status_label.set_status(f"翻译失败: {error_message}", "error")
            
            # 显示错误对话框（非阻塞）
            error_dialog = QMessageBox(self)
            error_dialog.setWindowTitle("翻译失败")
            error_dialog.setText("PDF翻译过程中出现错误")
            error_dialog.setDetailedText(error_message)
            error_dialog.setIcon(QMessageBox.Icon.Warning)
            error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_dialog.show()
            
        except Exception as e:
            print(f"处理翻译失败时出错: {e}")
        
    @pyqtSlot()
    def zoom_in(self):
        """放大"""
        current_zoom = self.zoom_spinbox.value()
        new_zoom = min(current_zoom + 25, int(MAX_ZOOM * 100))
        self.zoom_spinbox.setValue(new_zoom)
        
    @pyqtSlot()
    def zoom_out(self):
        """缩小"""
        current_zoom = self.zoom_spinbox.value()
        new_zoom = max(current_zoom - 25, int(MIN_ZOOM * 100))
        self.zoom_spinbox.setValue(new_zoom)
        
    @pyqtSlot(int)
    def on_zoom_changed(self, value):
        """缩放改变"""
        zoom_factor = value / 100.0
        self.left_pdf_widget.set_zoom(zoom_factor)
        if self.right_pdf_widget.doc:  # 只有加载了文档才同步缩放
            self.right_pdf_widget.set_zoom(zoom_factor)
            
    @pyqtSlot(int)
    def on_page_changed(self, page_num):
        """页面改变"""
        if self.left_pdf_widget.doc:
            total_pages = self.left_pdf_widget.doc.page_count
            self.page_info_label.setText(f"第 {page_num + 1} 页 / 共 {total_pages} 页")
            
    @pyqtSlot(str)
    def on_text_selected(self, text):
        """文本选中"""
        if text.strip():
            self.status_label.set_status(f"已选择文本: {text[:50]}...", "info")
            
    @pyqtSlot(bool)
    def toggle_sync_scroll(self, enabled):
        """切换同步滚动"""
        self.sync_scroll.set_enabled(enabled)
        
    def closeEvent(self, event):
        """关闭事件"""
        # 清理翻译管理器
        self.translation_manager.cleanup()
        
        # 清理PDF查看器
        self.left_pdf_widget.cleanup()
        self.right_pdf_widget.cleanup()
        
        super().closeEvent(event)

    def resizeEvent(self, event):
        """窗口大小改变时重新调整loading widget位置"""
        super().resizeEvent(event)
        if hasattr(self, 'loading_widget') and self.loading_widget.isVisible():
            # 延迟执行居中，确保布局调整完成
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self.center_loading_widget) 
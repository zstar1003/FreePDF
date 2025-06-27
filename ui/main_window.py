"""主窗口模块"""

import os

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QIcon, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.translation import TranslationManager
from ui.components import StatusLabel, DragDropOverlay
from ui.pdf_widget import PDFWidget


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FreePDF")
        self.setWindowIcon(QIcon("ui/logo/logo.ico"))
        self.setGeometry(100, 100, 1600, 900)
        self.showMaximized()
        
        # 启用拖拽功能
        self.setAcceptDrops(True)
        
        # 初始化组件
        self.current_file = None
        self.translation_manager = TranslationManager()
        self._pending_zoom_value = None
        
        # 创建拖拽提示覆盖层
        self.drag_overlay = DragDropOverlay(self)
        
        # 创建UI
        self.setup_ui()
        self.setup_status_bar()
        self.setup_connections()
        
        # 预热PDF组件，确保WebEngine提前初始化
        self._preheat_pdf_components()
        
    def setup_ui(self):
        """设置UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)  # 设置主布局元素间距为5px，保持紧凑
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)  # 减少外边距
        toolbar_layout.setSpacing(10)  # 控制元素间距
        
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
        left_title.setFixedHeight(35)  # 设置固定高度
        left_title.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 居中对齐
        left_title.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
                font-weight: bold;
                color: #495057;
                font-size: 14px;
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
        right_title.setFixedHeight(35)  # 设置固定高度
        right_title.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 居中对齐
        right_title.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
                font-weight: bold;
                color: #495057;
                font-size: 14px;
            }
        """)
        right_layout.addWidget(right_title)
        
        # 右侧PDF查看器
        self.right_pdf_widget = PDFWidget()
        right_layout.addWidget(self.right_pdf_widget)
        
        # 保存right_frame的引用，用于后续定位
        self.right_frame = right_frame
        
        # 添加到分割器
        self.splitter.addWidget(left_frame)
        self.splitter.addWidget(right_frame)
        self.splitter.setSizes([800, 800])  # 初始均分
        
        main_layout.addWidget(self.splitter)
        

        
    def setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = StatusLabel()
        self.status_bar.addWidget(self.status_label)
        
        # 页面信息已移除，使用更简洁的状态栏
        
    def setup_connections(self):
        """设置信号连接"""
        # 文件操作
        self.open_btn.clicked.connect(self.open_file)
        
        # PDF查看器信号
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
                
                # 显示加载动画（不需要隐藏占位符，会被QStackedWidget自动管理）
                self.show_loading_centered("正在准备翻译...")
                
                # 开始翻译
                self.start_translation(file_path)
                
            else:
                QMessageBox.warning(self, "错误", "无法打开PDF文件")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件时出错: {str(e)}")

    def show_loading_centered(self, message):
        """显示居中的加载动画"""
        self.right_pdf_widget.show_loading(message)

    def center_loading_widget(self):
        """将loading widget居中在PDF widget区域"""
        # 不再需要手动居中，因为加载页面已集成在QStackedWidget中
        pass

    def hide_loading(self):
        """隐藏加载动画"""
        self.right_pdf_widget.hide_loading()

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
            self.right_pdf_widget.set_loading_message(message)
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
            
            # 额外验证PDF文件
            if not self._validate_pdf_file(translated_file):
                self.on_translation_failed("翻译后的PDF文件格式无效或损坏")
                return
            
            # 记录翻译文件
            self.translation_manager.set_translated_file(self.current_file, translated_file)
            
            # 先隐藏加载动画，然后加载翻译后的文件到右侧
            self.hide_loading()
            
            # 重试机制加载PDF
            retry_count = 3
            loaded = False
            
            for i in range(retry_count):
                if self.right_pdf_widget.load_pdf(translated_file):
                    loaded = True
                    break
                else:
                    if i < retry_count - 1:  # 不是最后一次尝试
                        print(f"加载PDF失败，正在重试... ({i+1}/{retry_count})")
                        # 短暂等待后重试
                        import time
                        time.sleep(0.5)
            
            if loaded:
                # 确保PDF视图显示
                self.right_pdf_widget.pdf_view.show()
                
                # 强制刷新显示
                QTimer.singleShot(100, self._force_pdf_display)
                
                filename = os.path.basename(translated_file)
                file_size = os.path.getsize(translated_file) / (1024 * 1024)  # MB
                self.status_label.set_status(f"翻译完成: {filename} ({file_size:.1f}MB)", "success")
                print(f"翻译成功，文件保存在: {translated_file}")
            else:
                self.on_translation_failed("多次尝试后仍无法加载翻译后的文件")
                
        except Exception as e:
            self.on_translation_failed(f"加载翻译文件时出错: {str(e)}")
            
    def _validate_pdf_file(self, file_path):
        """验证PDF文件是否有效"""
        try:
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size < 1024:  # 小于1KB
                print(f"PDF文件太小: {file_size} bytes")
                return False
            
            # 检查PDF文件头
            with open(file_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF-'):
                    print(f"无效的PDF文件头: {header}")
                    return False
            
            # 尝试使用fitz验证
            try:
                import fitz
                doc = fitz.open(file_path)
                page_count = doc.page_count
                doc.close()
                
                if page_count == 0:
                    print("PDF文件没有页面")
                    return False
                    
                print(f"PDF文件验证成功，共{page_count}页，大小{file_size/1024/1024:.1f}MB")
                return True
                
            except Exception as e:
                print(f"fitz验证PDF失败: {e}")
                return False
                
        except Exception as e:
            print(f"验证PDF文件时出错: {e}")
            return False
    
    def _force_pdf_display(self):
        """强制显示PDF视图"""
        try:
            # 确保右侧PDF容器可见
            self.right_pdf_widget.show()
            
            # 确保QStackedWidget显示PDF视图（索引2）
            if hasattr(self.right_pdf_widget, 'stacked_widget'):
                self.right_pdf_widget.stacked_widget.setCurrentIndex(2)
                print("已切换到PDF视图页面")
            
            # 显示PDF视图
            self.right_pdf_widget.pdf_view.show()
            
            # 强制更新整个右侧区域
            self.right_pdf_widget.update()
            self.right_pdf_widget.repaint()
            
            # 激活PDF视图
            self.right_pdf_widget.pdf_view.setFocus()
            
            # 触发整个窗口重绘
            self.update()
            self.repaint()
            
            print("PDF显示已强制刷新")
        except Exception as e:
            print(f"强制显示PDF时出错: {e}")
            

            
    @pyqtSlot(str)
    def on_translation_failed(self, error_message):
        """翻译失败"""
        try:
            # 隐藏加载动画
            self.hide_loading()
            
            # 使用新的重置方法，平滑切换回占位符
            self.right_pdf_widget.reset_to_placeholder()
            
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
            
    @pyqtSlot(str)
    def on_text_selected(self, text):
        """文本选中"""
        if text.strip():
            self.status_label.set_status(f"已选择文本: {text[:50]}...", "info")
        
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
        # 不再需要手动调整加载组件位置，因为它已集成在QStackedWidget中

    def _preheat_pdf_components(self):
        """预热PDF组件，确保WebEngine提前初始化"""
        try:
            # 提前触发左右两个PDF组件的WebEngine初始化
            # 这会启动预加载过程，让WebEngine提前准备好
            
            # 强制触发WebEngine的初始化，但不显示
            temp_geometry = self.left_pdf_widget.pdf_view.geometry()
            temp_geometry2 = self.right_pdf_widget.pdf_view.geometry()
            
            # 设置一个很小的大小来触发渲染管道初始化，但不影响用户界面
            self.left_pdf_widget.pdf_view.resize(1, 1)
            self.right_pdf_widget.pdf_view.resize(1, 1)
            
            # 延迟恢复正常大小
            def restore_size():
                self.left_pdf_widget.pdf_view.resize(temp_geometry.size())
                self.right_pdf_widget.pdf_view.resize(temp_geometry2.size())
            
            QTimer.singleShot(500, restore_size)
            
            print("PDF组件预热已启动，WebEngine初始化中...")
            
        except Exception as e:
            print(f"PDF组件预热失败: {e}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            # 检查是否包含PDF文件
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith('.pdf'):
                        event.acceptProposedAction()
                        # 显示拖拽提示覆盖层
                        self.drag_overlay.show_overlay(self)
                        # 更新状态提示
                        self.status_label.set_status("松开鼠标以导入PDF文件", "info")
                        return
        event.ignore()
        
    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        """拖拽离开事件"""
        # 隐藏拖拽提示覆盖层
        self.drag_overlay.hide_overlay()
        # 恢复原始状态
        if self.current_file:
            filename = os.path.basename(self.current_file)
            self.status_label.set_status(f"已加载: {filename}", "success")
        else:
            self.status_label.set_status("就绪", "info")
        
    def dropEvent(self, event: QDropEvent):
        """拖拽放下事件"""
        # 隐藏拖拽提示覆盖层
        self.drag_overlay.hide_overlay()
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith('.pdf'):
                        # 加载第一个找到的PDF文件
                        self.load_pdf_file(file_path)
                        event.acceptProposedAction()
                        return
        event.ignore() 
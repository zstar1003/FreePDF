"""主窗口模块"""

import os
import webbrowser

import requests

# 应用版本信息
__version__ = "3.0.0"

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.translation import TranslationManager
from ui.components import (
    DragDropOverlay,
    EmbeddedQAWidget,
    QADialog,
    StatusLabel,
    TranslationConfigDialog,
)
from ui.pdfjs_widget import PdfJsWidget  # Use the new widget


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FreePDF")
        self.setWindowIcon(QIcon("ui/logo/logo.ico"))
        self.setGeometry(100, 100, 1600, 900)
        
        self.setAcceptDrops(True)
        
        self.current_file = None
        self.translation_manager = TranslationManager()
        self._is_syncing = False
        self._scroll_sync_enabled = True
        self.qa_panel_visible = True

        # Create a single, shared profile for all web views
        self.web_profile = QWebEngineProfile("shared_profile", self)
        self.web_profile.setCachePath(os.path.join("cache", "web_engine_cache"))
        self.web_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        
        self.drag_overlay = DragDropOverlay(self)
        self.qa_dialog = QADialog(self) # Keep for compatibility if needed
        self.embedded_qa = EmbeddedQAWidget(self)
        
        self.setup_ui()
        self.setup_status_bar()
        self.setup_connections()

        # Install the global event filter
        QApplication.instance().installEventFilter(self)
        
    def setup_ui(self):
        """设置UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
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
        
        # 配置按钮
        self.config_btn = QPushButton("引擎配置")
        self.config_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        toolbar_layout.addWidget(self.config_btn)
        
        # 滚动同步按钮
        self.sync_btn = QPushButton("关闭滚动同步")
        self.sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        toolbar_layout.addWidget(self.sync_btn)
        
        toolbar_layout.addStretch()
        
        # 关于软件按钮
        self.about_btn = QPushButton("关于软件")
        self.about_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        toolbar_layout.addWidget(self.about_btn)
        
        # 智能问答按钮 - 放到最右边，默认显示状态
        self.qa_btn = QPushButton("关闭问答")
        self.qa_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        toolbar_layout.addWidget(self.qa_btn)
        
        main_layout.addLayout(toolbar_layout)
        
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel (Original PDF)
        left_frame = QFrame()
        left_frame.setFrameStyle(QFrame.Shape.NoFrame)
        left_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(1, 1, 1, 1) # Add a small margin to prevent content from touching the border
        left_layout.setSpacing(0)
        left_title = QLabel("原始文档")
        left_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_title.setFixedHeight(35) # Restore fixed height
        left_title.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        left_layout.addWidget(left_title)
        self.left_pdf_widget = PdfJsWidget(name="left_view", profile=self.web_profile)
        self.left_pdf_widget.setStyleSheet("border: none; border-bottom-left-radius: 7px; border-bottom-right-radius: 7px;")
        left_layout.addWidget(self.left_pdf_widget)
        
        # Middle panel (Translated PDF)
        middle_frame = QFrame()
        middle_frame.setFrameStyle(QFrame.Shape.NoFrame)
        middle_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        middle_layout = QVBoxLayout(middle_frame)
        middle_layout.setContentsMargins(1, 1, 1, 1) # Add a small margin
        middle_layout.setSpacing(0)
        middle_title = QLabel("翻译文档")
        middle_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        middle_title.setFixedHeight(35) # Restore fixed height
        middle_title.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        middle_layout.addWidget(middle_title)
        self.right_pdf_widget = PdfJsWidget(name="right_view", profile=self.web_profile)
        self.right_pdf_widget.setStyleSheet("border: none; border-bottom-left-radius: 7px; border-bottom-right-radius: 7px;")
        middle_layout.addWidget(self.right_pdf_widget)
        
        # Right panel (QA) - Restoring to a stable state with a visible title bar and content
        self.qa_panel = QFrame()
        self.qa_panel.setFrameStyle(QFrame.Shape.NoFrame)
        self.qa_panel.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        qa_panel_layout = QVBoxLayout(self.qa_panel)
        qa_panel_layout.setContentsMargins(1, 1, 1, 1)
        qa_panel_layout.setSpacing(0)
        
        # 1. Restore the external, styled title bar.
        qa_title = QLabel("智能问答")
        qa_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qa_title.setFixedHeight(35)
        qa_title.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        qa_panel_layout.addWidget(qa_title)
        
        # 2. Restore the QA content widget below the title.
        # 3. Hide the widget's internal title to prevent duplicates.
        self.embedded_qa.hide_title_bar()
        self.embedded_qa.setStyleSheet("border: none; border-bottom-left-radius: 7px; border-bottom-right-radius: 7px;")
        qa_panel_layout.addWidget(self.embedded_qa)
        
        self.main_splitter.addWidget(left_frame)
        self.main_splitter.addWidget(middle_frame)
        self.main_splitter.addWidget(self.qa_panel)
        self.main_splitter.setSizes([300, 450, 250])
        self.main_splitter.setChildrenCollapsible(False)
        
        main_layout.addWidget(self.main_splitter)
        
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
        self.config_btn.clicked.connect(self.open_config)
        self.about_btn.clicked.connect(self.show_about_dialog)
        self.qa_btn.clicked.connect(self.toggle_qa_widget)
        
        # 滚动同步相关的连接
        self.sync_btn.clicked.connect(self.toggle_scroll_sync)
        
        # PDF查看器信号
        # self.left_pdf_widget.text_selected.connect(self.on_text_selected) # REMOVED: Feature not available in new widget
        
        # 翻译管理器信号
        self.translation_manager.current_thread = None
        
        # 连接PDF组件的滚动信号
        # self.left_pdf_widget.scroll_changed.connect(self.on_left_scroll_changed) # This line was removed by the user's edit, so it's commented out.
        # self.right_pdf_widget.scroll_changed.connect(self.on_right_scroll_changed) # This line was removed by the user's edit, so it's commented out.
        # Connect the scroll signals from both new widgets
        self.left_pdf_widget.scrollChanged.connect(self.on_scroll_changed)
        self.right_pdf_widget.scrollChanged.connect(self.on_scroll_changed)
    
    def toggle_scroll_sync(self):
        """切换滚动同步状态"""
        self._scroll_sync_enabled = not self._scroll_sync_enabled
        self.sync_btn.setText("关闭滚动同步" if self._scroll_sync_enabled else "开启滚动同步")
        self.status_label.set_status(f"滚动同步已{'启用' if self._scroll_sync_enabled else '禁用'}", "info")
    
    def on_scroll_changed(self, view_name, top, left):
        if not self._scroll_sync_enabled or self._is_syncing:
            return
        
        self._is_syncing = True
        target_widget = None
        if view_name == "left_view":
            target_widget = self.right_pdf_widget
        elif view_name == "right_view":
            target_widget = self.left_pdf_widget
        
        if target_widget:
            target_widget.set_scroll_position(top, left)
        
        # Use a short timer to reset the sync flag, preventing immediate re-triggering.
        QTimer.singleShot(50, lambda: setattr(self, '_is_syncing', False))
    
    def _reset_sync_flag(self):
        """重置同步标志"""
        if self._is_syncing:
            print("重置同步标志")
            self._is_syncing = False
    
    @pyqtSlot()
    def open_file(self):
        """打开PDF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF files (*.pdf)"
        )
        
        if file_path:
            self.load_pdf_file(file_path)
            
    @pyqtSlot()
    def open_config(self):
        """打开翻译配置对话框"""
        dialog = TranslationConfigDialog(self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            # 配置已保存，可以在这里添加其他处理逻辑
            self.status_label.set_status("翻译配置已更新", "success")
            
    @pyqtSlot()
    def show_about_dialog(self):
        """显示关于软件对话框"""
        dialog = AboutDialog(self)
        dialog.exec()
            
    @pyqtSlot()
    def toggle_qa_widget(self):
        """切换智能问答面板显示/隐藏"""
        if self.qa_panel_visible:
            # 隐藏问答面板
            self.qa_panel_visible = False
            self.qa_btn.setText("智能问答")
            
            # 直接隐藏面板
            self.qa_panel.setVisible(False)
            
            # 调整二栏分割器：左侧40%，中间60%
            total_width = self.main_splitter.width()
            if total_width > 100:
                sizes = [int(total_width * 0.4), int(total_width * 0.6)]
            else:
                sizes = [400, 600]
            
            # 只设置前两栏的大小
            current_sizes = self.main_splitter.sizes()
            new_sizes = [sizes[0], sizes[1], current_sizes[2]]  # 保持第三栏原样
            self.main_splitter.setSizes(new_sizes)
            
            print("隐藏面板 - 设置可见性: False")
        else:
            # 显示问答面板
            self.qa_panel_visible = True
            self.qa_btn.setText("关闭问答")
            
            # 直接显示面板
            self.qa_panel.setVisible(True)
            
            # 检查当前状态并更新提示信息
            self._update_qa_panel_status()
            
            # 调整三栏分割器：左侧37.5%，中间37.5%，右侧25%（左边两个容器宽度一致）
            total_width = self.main_splitter.width()
            if total_width > 100:
                sizes = [int(total_width * 0.375), int(total_width * 0.375), int(total_width * 0.25)]
            else:
                sizes = [375, 375, 250]
            self.main_splitter.setSizes(sizes)
            
            print(f"显示面板 - 设置可见性: True, 分割器大小: {sizes}")
            
        # 强制刷新布局
        self.main_splitter.update()
        
        # 延迟检查实际结果
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: print(f"实际结果 - qa_panel可见: {self.qa_panel.isVisible()}, 宽度: {self.qa_panel.width()}"))
    
    def _update_qa_panel_status(self):
        """更新问答面板的状态信息"""
        # 检查问答引擎配置
        if not self._check_qa_engine_config():
            # 配置有问题，在面板内显示提示
            self.embedded_qa.clear_chat()
            self.embedded_qa.add_message("系统", "问答引擎未配置或配置有误，请先在翻译配置中正确配置问答引擎")
        elif not self.current_file:
            # 没有PDF文件，在面板内显示提示
            self.embedded_qa.clear_chat() 
            self.embedded_qa.add_message("系统", "请先打开PDF文件，然后即可开始智能问答")
        else:
            # 提取PDF文本内容（仅在首次显示时）
            if not self.embedded_qa.pdf_content:
                pdf_text = self._extract_pdf_text()
                if not pdf_text:
                    self.embedded_qa.clear_chat()
                    self.embedded_qa.add_message("系统", "无法提取PDF文本内容，请检查PDF文件是否正常")
                else:
                    self.embedded_qa.set_pdf_content(pdf_text)
                    # 如果成功加载了PDF内容，只清空聊天记录，不显示提示
                    self.embedded_qa.clear_chat()
        
    def _check_qa_engine_config(self):
        """检查问答引擎配置"""
        import json
        import os
        
        config_file = "pdf2zh_config.json"
        if not os.path.exists(config_file):
            return False
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                qa_config = config.get("qa_engine", {})
                
                if qa_config.get("service", "关闭") == "关闭":
                    return False
                    
                # 检查必要的配置项
                service = qa_config.get("service")
                envs = qa_config.get("envs", {})
                
                if service == "silicon":
                    if not envs.get("SILICON_API_KEY") or not envs.get("SILICON_MODEL"):
                        return False
                elif service == "ollama":
                    if not envs.get("OLLAMA_HOST") or not envs.get("OLLAMA_MODEL"):
                        return False
                        
                return True
                
        except Exception:
            return False
            
    def _extract_pdf_text(self):
        """提取PDF文本内容"""
        if not self.current_file:
            return ""
            
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(self.current_file)
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text.strip():
                    text_content.append(f"第{page_num + 1}页:\n{text}")
                    
            doc.close()
            
            full_text = "\n\n".join(text_content)
            return full_text
            
        except Exception as e:
            print(f"提取PDF文本失败: {e}")
            return ""
    

    def load_pdf_file(self, file_path):
        """加载PDF文件"""
        self.current_file = file_path
        self.left_pdf_widget.load_pdf(file_path)
        self.status_label.set_status(f"已加载: {os.path.basename(file_path)}", "success")
        
        # Show a loading message in the right panel and start the actual translation
        self.right_pdf_widget.view.setHtml("<div style='display:flex;justify-content:center;align-items:center;height:100%;font-size:16px;color:grey;'>正在准备翻译...</div>")
        self.start_translation(file_path)

    def _force_left_pdf_display(self):
        """强制显示左侧PDF视图"""
        try:
            # 确保左侧PDF容器可见
            self.left_pdf_widget.show()
            
            # 确保QStackedWidget显示PDF视图（索引2）
            if hasattr(self.left_pdf_widget, 'stacked_widget'):
                self.left_pdf_widget.stacked_widget.setCurrentIndex(2)
                print("已切换到左侧PDF视图页面")
            
            # 显示PDF视图
            self.left_pdf_widget.pdf_view.show()
            
            # 强制更新整个左侧区域
            self.left_pdf_widget.update()
            self.left_pdf_widget.repaint()
            
            # 激活PDF视图
            self.left_pdf_widget.pdf_view.setFocus()
            
            # 触发整个窗口重绘
            self.update()
            self.repaint()
            
            print("左侧PDF显示已强制刷新")
        except Exception as e:
            print(f"强制显示左侧PDF时出错: {e}")

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
        self.right_pdf_widget.view.setHtml(f"<div style='display:flex;justify-content:center;align-items:center;height:100%;font-size:16px;color:grey;'>{message}</div>")
        self.status_label.set_status(message, "info")
        
    @pyqtSlot(str)
    def on_translation_completed(self, translated_file):
        """翻译完成"""
        if os.path.exists(translated_file):
            self.right_pdf_widget.load_pdf(translated_file)
            self.status_label.set_status("翻译完成", "success")
        else:
            self.on_translation_failed(f"翻译文件 '{translated_file}' 不存在")
            
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
        self.hide_loading()
        QMessageBox.critical(self, "翻译失败", f"翻译过程中出现错误:\n{error_message}")
        
    # def on_text_selected(self, text): # REMOVED: Feature not available in new widget
    #     """文本选中"""
    #     if text.strip():
    #         self.status_label.set_status(f"已选择文本: {text[:50]}...", "info")
        
    def closeEvent(self, event):
        """处理关闭事件"""
        # Clean up web engine widgets before closing to prevent shutdown errors.
        if hasattr(self, 'left_pdf_widget') and self.left_pdf_widget:
            self.left_pdf_widget.cleanup()
        if hasattr(self, 'right_pdf_widget') and self.right_pdf_widget:
            self.right_pdf_widget.cleanup()

        # Clean up translation manager threads
        if hasattr(self, 'translation_manager') and self.translation_manager:
            self.translation_manager.cleanup()
            
        reply = QMessageBox.question(self, '确认退出', '您确定要退出 FreePDF 吗？',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 不再需要手动调整加载组件位置，因为它已集成在QStackedWidget中

    def _preheat_pdf_components(self):
        """预热PDF组件，确保WebEngine提前初始化"""
        try:
            # 延迟预热，避免影响初始窗口显示
            def delayed_preheat():
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
                    
                    QTimer.singleShot(300, restore_size)
                    
                    print("PDF组件预热已启动，WebEngine初始化中...")
                    
                except Exception as e:
                    print(f"PDF组件预热失败: {e}")
            
            # 延迟1秒后执行预热，确保窗口已经稳定显示
            QTimer.singleShot(1000, delayed_preheat)
            
        except Exception as e:
            print(f"PDF组件预热启动失败: {e}")

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


class UpdateCheckThread(QThread):
    """检查更新的线程"""
    update_checked = pyqtSignal(bool, str)  # 是否有更新, 最新版本/错误信息
    
    def run(self):
        try:
            # 获取当前版本
            current_version = __version__
            
            # 请求GitHub API获取最新版本
            response = requests.get(
                "https://api.github.com/repos/zstar1003/FreePDF/releases/latest",
                timeout=10
            )
            
            if response.status_code == 200:
                release_data = response.json()
                latest_version = release_data.get("tag_name", "").lstrip("v")
                
                # 简单的版本比较
                if latest_version and latest_version != current_version:
                    self.update_checked.emit(True, latest_version)
                else:
                    self.update_checked.emit(False, "已是最新版本")
            else:
                self.update_checked.emit(False, f"检查更新失败: HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            self.update_checked.emit(False, f"网络连接失败: {str(e)}")
        except Exception as e:
            self.update_checked.emit(False, f"检查更新时出错: {str(e)}")


class AboutDialog(QDialog):
    """关于软件对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 FreePDF")
        self.setFixedSize(500, 400)
        
        # 创建检查更新线程
        self.update_thread = UpdateCheckThread()
        self.update_thread.update_checked.connect(self.on_update_checked)
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 软件标题
        title_label = QLabel("FreePDF")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #007acc;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title_label)
        
        # 版本信息
        version_label = QLabel(f"版本 {__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #666;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(version_label)
        
        # 开发者信息
        info_text = QTextBrowser()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(180)
        info_text.setHtml("""
        <div style="font-size: 14px; line-height: 1.6; color: #333;">
            <p><strong>制作者：</strong>zstar</p>
            <p><strong>微信公众号：</strong>我有一计</p>
            <p><strong>理念：</strong>一直致力于构建免费好用的软件</p>
            <p><strong>项目地址：</strong>https://github.com/zstar1003/FreePDF</p>
        </div>
        """)
        info_text.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                background-color: #f9f9f9;
            }
        """)
        layout.addWidget(info_text)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 检查更新按钮
        self.update_btn = QPushButton("检查更新")
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #fff;
            }
        """)
        self.update_btn.clicked.connect(self.check_for_updates)
        button_layout.addWidget(self.update_btn)
        
        button_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def check_for_updates(self):
        """检查更新"""
        self.update_btn.setEnabled(False)
        self.update_btn.setText("检查中...")
        self.update_thread.start()
        
    def on_update_checked(self, has_update, message):
        """更新检查完成"""
        self.update_btn.setEnabled(True)
        self.update_btn.setText("检查更新")
        
        if has_update:
            # 有新版本
            reply = QMessageBox.question(
                self,
                "发现新版本",
                f"发现新版本 {message}，是否前往下载？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                webbrowser.open("https://github.com/zstar1003/FreePDF/releases/latest")
        else:
            # 无新版本或出错
            QMessageBox.information(self, "检查更新", message) 
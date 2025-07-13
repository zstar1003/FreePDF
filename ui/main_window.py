"""主窗口模块"""

import os
import webbrowser

import requests

# 应用版本信息
__version__ = "4.0.0"

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineProfile
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
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
        self._last_pdf_file = None  # 用于追踪PDF文件变化
        self.translation_manager = TranslationManager()
        self._is_syncing = False
        self._scroll_sync_enabled = True
        self.qa_panel_visible = True

        # Use an off-the-record (incognito) profile by creating a QWebEngineProfile
        # without a persistent storage name.
        self.web_profile = QWebEngineProfile(self)
        
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
                background-color: #005a9e;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #003e6b;
            }
        """)
        toolbar_layout.addWidget(self.open_btn)
        
        # 翻译配置按钮
        self.translation_config_btn = QPushButton("翻译配置")
        self.translation_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #005a9e;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #003e6b;
            }
        """)
        toolbar_layout.addWidget(self.translation_config_btn)
        
        # 配置按钮
        self.config_btn = QPushButton("引擎配置")
        self.config_btn.setStyleSheet("""
            QPushButton {
                background-color: #005a9e;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #003e6b;
            }
        """)
        toolbar_layout.addWidget(self.config_btn)
        
        # 滚动同步按钮
        self.sync_btn = QPushButton("关闭滚动同步")
        self.sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #005a9e;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #003e6b;
            }
        """)
        toolbar_layout.addWidget(self.sync_btn)
        
        toolbar_layout.addStretch()
        
        # 批量翻译按钮
        self.batch_translate_btn = QPushButton("批量翻译")
        self.batch_translate_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff8c00;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e07b00;
            }
        """)
        self.batch_translate_btn.clicked.connect(self.open_batch_translate)
        toolbar_layout.addWidget(self.batch_translate_btn)
        
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
        # Set initial sizes to be equal for the first two panels
        self.main_splitter.setSizes([375, 375, 250])
        self.main_splitter.setChildrenCollapsible(False)
        
        main_layout.addWidget(self.main_splitter)
        
    def setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = StatusLabel()
        # 标签可拉伸，进度条固定
        self.status_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.status_label.setMaximumWidth(400)
        self.status_bar.addWidget(self.status_label)

        # 进度条（放在状态标签右侧）
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)  # 百分比单独显示
        # 美化样式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 3px;
                background-color: #eee;
                height: 12px;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        self.status_bar.addWidget(self.progress_bar)

        # 百分比标签
        self.progress_percent = QLabel("0%")
        self.progress_percent.setStyleSheet("color: #28a745; font-weight: bold; margin-left: 4px;")
        self.progress_percent.setVisible(False)
        self.status_bar.addWidget(self.progress_percent)
        
        # 页面信息已移除，使用更简洁的状态栏
        
    def setup_connections(self):
        """设置信号连接"""
        # 文件操作
        self.open_btn.clicked.connect(self.open_file)
        self.translation_config_btn.clicked.connect(self.open_translation_config)
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
        
        # Handle download requests from the web engine
        self.web_profile.downloadRequested.connect(self.on_download_requested)
    
    def on_download_requested(self, download):
        """Handle file download requests from the web view."""
        # Get the original file name, if available
        original_filename = "downloaded_file.pdf"
        if self.current_file:
            base, _ = os.path.splitext(os.path.basename(self.current_file))
            # Suggest a name for the saved file (e.g., original_saved.pdf)
            original_filename = f"{base}-mono.pdf"

        # Open a "Save As" dialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            original_filename,
            "PDF Documents (*.pdf)"
        )

        # If the user cancels the dialog, path will be empty.
        if not path:
            download.cancel()
            return
        
        # Set the download path and accept the request.
        download.setDownloadFileName(path)
        download.accept()
        print(f"开始下载到: {path}")

        # Connect the isFinishedChanged signal to the completion handler.
        # This signal is emitted when the download state changes, including completion.
        download.isFinishedChanged.connect(lambda: self.on_download_finished(download))

    def on_download_finished(self, download):
        """Handles the completion of a download request."""
        # This handler might be called multiple times, ensure we only act once it's truly finished.
        if not download.isFinished():
            return

        # It's good practice to disconnect the signal to avoid multiple calls,
        # especially if the download object persists.
        try:
            download.isFinishedChanged.disconnect()
        except TypeError:
            # Signal may have already been disconnected.
            pass

        path = download.downloadFileName()
        state = download.state()

        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            QMessageBox.information(self, "下载完成", f"文件已成功保存到:\n{path}")
            print(f"下载完成: {path}")
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            print(f"下载已取消: {path}")
        else:
            QMessageBox.warning(self, "下载失败", f"无法下载文件。\n状态: {state}")
            print(f"下载失败: {path}, 状态: {state}")

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
    def open_translation_config(self):
        """打开翻译配置对话框"""
        from ui.translation_dialog import TranslationSettingsDialog
        dialog = TranslationSettingsDialog(self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.status_label.set_status("翻译配置已更新", "success")
            
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
    def open_batch_translate(self):
        """打开批量翻译对话框"""
        from ui.batch_translation_dialog import BatchTranslationDialog
        dialog = BatchTranslationDialog(self)
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
            
            # The sizes are treated as proportions. Set the first two to equal
            # proportions (50/50 split) and the hidden one to zero.
            self.main_splitter.setSizes([1, 1, 0])
            
            print("隐藏面板 - 设置可见性: False")
        else:
            # 显示问答面板
            self.qa_panel_visible = True
            self.qa_btn.setText("关闭问答")
            
            # 直接显示面板
            self.qa_panel.setVisible(True)
            
            # 检查当前状态并更新提示信息
            self._update_qa_panel_status()
            
            # 调整三栏分割器：左右两个视图等宽
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
            # 检查是否已经有PDF内容，避免重复提取和清空聊天记录
            if not self.embedded_qa.pdf_content:
                # 第一次加载PDF，需要提取文本内容
                print("首次加载PDF，开始提取文本内容...")
                pdf_text = self._extract_pdf_text()
                if not pdf_text:
                    self.embedded_qa.clear_chat()
                    self.embedded_qa.add_message("系统", "无法提取PDF文本内容，请检查PDF文件是否正常")
                else:
                    print(f"PDF文本提取成功，长度: {len(pdf_text)} 字符")
                    self.embedded_qa.set_pdf_content(pdf_text)
                    # 只在首次加载时清空聊天记录并显示提示
                    self.embedded_qa.clear_chat()
                    self.embedded_qa.add_message("系统", f"PDF文档已加载完成（{len(pdf_text)}字符），现在可以开始智能问答了！")
            else:
                # PDF内容已存在，不需要清空聊天记录，只需确保内容是最新的
                print("PDF内容已存在，保持历史对话记录")
                # 如果当前文件与之前不同，则重新提取（比如用户换了PDF文件）
                if hasattr(self, '_last_pdf_file') and self._last_pdf_file != self.current_file:
                    print("检测到PDF文件变化，重新提取文本内容...")
                    pdf_text = self._extract_pdf_text()
                    if pdf_text:
                        self.embedded_qa.set_pdf_content(pdf_text)
                        self.embedded_qa.add_message("系统", f"新PDF文档已加载（{len(pdf_text)}字符），可以继续问答")
                        
            # 记录当前PDF文件路径
            self._last_pdf_file = self.current_file
        
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
        """提取PDF文本内容 - 优先使用支持页面分割的方法"""
        if not self.current_file:
            return ""
            
        try:
            # 首先检查PDF的实际页数
            actual_page_count = 0
            try:
                import pikepdf
                with pikepdf.open(self.current_file) as pdf:
                    actual_page_count = len(pdf.pages)
                print(f"PDF实际页数: {actual_page_count}")
            except Exception as e:
                print(f"无法获取PDF页数: {e}")
                
            # 优先尝试使用pymupdf（项目中已安装且支持页面分割）
            try:
                import pymupdf  # pymupdf
                print("使用pymupdf(pymupdf )提取PDF文本...")
                doc = pymupdf .open(self.current_file)
                pdf_page_count = len(doc)
                print(f"pymupdf检测到的页数: {pdf_page_count}")
                
                text_content = []
                for page_num in range(pdf_page_count):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    
                    # 检查文本质量 - 如果包含过多单字符或乱码，认为提取失败
                    if page_text and page_text.strip():
                        # 简单的文本质量检查
                        words = page_text.split()
                        single_chars = sum(1 for word in words if len(word.strip()) == 1)
                        total_words = len(words)
                        
                        if total_words > 0 and (single_chars / total_words) > 0.7:
                            print(f"第{page_num + 1}页文本质量较差，可能是乱码")
                            text_content.append(f"=== 第{page_num + 1}页 ===\n[页面文本质量较差，可能需要使用其他提取方法]")
                        else:
                            text_content.append(f"=== 第{page_num + 1}页 ===\n{page_text.strip()}")
                    else:
                        # 即使页面为空，也添加页面标记
                        text_content.append(f"=== 第{page_num + 1}页 ===\n[页面内容为空或无法提取]")
                
                doc.close()
                        
                if text_content and len(text_content) == pdf_page_count:
                    full_text = "\n\n".join(text_content)
                    print(f"成功使用pymupdf提取PDF文本，总长度: {len(full_text)} 字符，共{len(text_content)}页")
                    return full_text
                else:
                    print(f"pymupdf页面数量不匹配，期望{pdf_page_count}页，实际提取{len(text_content)}页")
                    
            except ImportError as e:
                print(f"pymupdf导入失败: {str(e)}")
                print("尝试其他方法")
            except Exception as e:
                print(f"pymupdf处理失败: {str(e)}")
                print("尝试其他方法")
                
            # 尝试使用pdfplumber
            try:
                import pdfplumber
                print("使用pdfplumber提取PDF文本...")
                text_content = []
                with pdfplumber.open(self.current_file) as pdf:
                    pdf_page_count = len(pdf.pages)
                    print(f"pdfplumber检测到的页数: {pdf_page_count}")
                    
                    # 验证页数是否合理
                    if actual_page_count > 0 and pdf_page_count != actual_page_count:
                        print(f"页数不匹配：实际{actual_page_count}页，pdfplumber检测到{pdf_page_count}页")
                    
                    for page_num, page in enumerate(pdf.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text and page_text.strip():
                                text_content.append(f"=== 第{page_num + 1}页 ===\n{page_text.strip()}")
                            else:
                                # 即使页面为空，也添加页面标记
                                text_content.append(f"=== 第{page_num + 1}页 ===\n[页面内容为空或无法提取]")
                        except Exception as e:
                            print(f"提取第{page_num + 1}页文本失败: {e}")
                            text_content.append(f"=== 第{page_num + 1}页 ===\n[页面文本提取失败]")
                            continue
                            
                if text_content and len(text_content) == pdf_page_count:
                    full_text = "\n\n".join(text_content)
                    print(f"成功使用pdfplumber提取PDF文本，总长度: {len(full_text)} 字符，共{len(text_content)}页")
                    return full_text
                else:
                    print(f"pdfplumber页面数量不匹配，期望{pdf_page_count}页，实际提取{len(text_content)}页")
                    
            except ImportError:
                print("pdfplumber未安装")
                
            # 尝试使用PyPDF2（如果用户安装了）
            try:
                import PyPDF2
                print("使用PyPDF2提取PDF文本...")
                text_content = []
                with open(self.current_file, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    pdf_page_count = len(pdf_reader.pages)
                    print(f"PyPDF2检测到的页数: {pdf_page_count}")
                    
                    # 验证页数是否合理
                    if actual_page_count > 0 and pdf_page_count != actual_page_count:
                        print(f"页数不匹配：实际{actual_page_count}页，PyPDF2检测到{pdf_page_count}页")
                    
                    for page_num, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text and page_text.strip():
                                text_content.append(f"=== 第{page_num + 1}页 ===\n{page_text.strip()}")
                            else:
                                # 即使页面为空，也添加页面标记
                                text_content.append(f"=== 第{page_num + 1}页 ===\n[页面内容为空或无法提取]")
                        except Exception as e:
                            print(f"提取第{page_num + 1}页文本失败: {e}")
                            text_content.append(f"=== 第{page_num + 1}页 ===\n[页面文本提取失败]")
                            continue
                            
                if text_content and len(text_content) == pdf_page_count:
                    full_text = "\n\n".join(text_content)
                    print(f"成功使用PyPDF2提取PDF文本，总长度: {len(full_text)} 字符，共{len(text_content)}页")
                    return full_text
                else:
                    print(f"PyPDF2页面数量不匹配，期望{pdf_page_count}页，实际提取{len(text_content)}页")
                    
            except ImportError:
                print("PyPDF2未安装")
                
            # 使用pdfminer-six作为备用方案，增强页面分割功能
            try:
                import io

                from pdfminer.high_level import extract_text, extract_text_to_fp
                from pdfminer.layout import LAParams
                from pdfminer.pdfpage import PDFPage
                
                print("使用pdfminer-six提取PDF文本（备用方案）...")
                
                # 尝试按页面提取文本
                try:
                    text_content = []
                    with open(self.current_file, 'rb') as fp:
                        pages = list(PDFPage.get_pages(fp))
                        page_count = len(pages)
                        print(f"pdfminer-six检测到的页数: {page_count}")
                        
                        # 验证页数是否合理
                        if actual_page_count > 0 and page_count != actual_page_count:
                            print(f"页数不匹配：实际{actual_page_count}页，pdfminer-six检测到{page_count}页")
                        
                        # 按页面提取文本
                        for page_num, page in enumerate(pages):
                            try:
                                # 重新打开文件并提取特定页面
                                with open(self.current_file, 'rb') as fp2:
                                    output_string = io.StringIO()
                                    laparams = LAParams()
                                    extract_text_to_fp(fp2, output_string, 
                                                     page_numbers=[page_num], 
                                                     laparams=laparams)
                                    page_text = output_string.getvalue()
                                    
                                if page_text and page_text.strip():
                                    text_content.append(f"=== 第{page_num + 1}页 ===\n{page_text.strip()}")
                                else:
                                    text_content.append(f"=== 第{page_num + 1}页 ===\n[页面内容为空或无法提取]")
                                    
                            except Exception as e:
                                print(f"提取第{page_num + 1}页失败: {e}")
                                text_content.append(f"=== 第{page_num + 1}页 ===\n[页面文本提取失败: {str(e)}]")
                                
                    if text_content and len(text_content) == page_count:
                        full_text = "\n\n".join(text_content)
                        print(f"成功使用pdfminer-six按页面提取PDF文本，总长度: {len(full_text)} 字符，共{len(text_content)}页")
                        return full_text
                    else:
                        print("pdfminer-six页面提取不完整，回退到整体提取")
                        
                except Exception as e:
                    print(f"pdfminer-six按页面提取失败: {e}，尝试整体提取")
                
                # 回退到整体文本提取
                full_text = extract_text(self.current_file)
                if full_text and full_text.strip():
                    print(f"成功使用pdfminer-six提取PDF文本，总长度: {len(full_text)} 字符")
                    
                    # 尝试智能分页 - 基于常见的页面分隔符
                    import re
                    
                    # 常见的页面分隔符模式
                    page_break_patterns = [
                        r'\n\s*\n\s*(?=\d+\s*\n)',  # 页码后的换行
                        r'\n\s*\n\s*(?=Page\s+\d+)',  # "Page X"
                        r'\n\s*\n\s*(?=第\s*\d+\s*页)',  # "第X页"
                        r'\f',  # 换页符
                    ]
                    
                    # 尝试不同的分页模式
                    pages = None
                    for pattern in page_break_patterns:
                        try_pages = re.split(pattern, full_text)
                        if len(try_pages) > 1:
                            pages = try_pages
                            print(f"使用模式 '{pattern}' 分割出 {len(pages)} 个部分")
                            break
                    
                    if pages and len(pages) > 1:
                        text_content = []
                        for i, page_text in enumerate(pages):
                            if page_text.strip():
                                text_content.append(f"=== 第{i + 1}页 ===\n{page_text.strip()}")
                        if text_content:
                            final_text = "\n\n".join(text_content)
                            print(f"智能分页成功，共{len(text_content)}页")
                            return final_text
                    
                    # 如果无法分页，返回整个文档，但为页面过滤添加单页标记
                    print("无法自动分页，返回整个文档")
                    return f"=== 第1页 ===\n{full_text.strip()}\n\n注意：无法自动分页，所有内容作为第1页处理。"
                    
            except ImportError:
                print("pdfminer-six导入失败")
            except Exception as e:
                print(f"pdfminer-six处理失败: {e}")
                
            # 最后使用pikepdf作为最后备用方案
            print("使用pikepdf作为最后备用方案...")
            import pikepdf
            with pikepdf.open(self.current_file) as pdf:
                pdf_page_count = len(pdf.pages)
                print(f"pikepdf检测到的页数: {pdf_page_count}")
                
                text_content = []
                for page_num, page in enumerate(pdf.pages):
                    try:
                        # pikepdf主要用于结构操作，文本提取有限
                        if '/Contents' in page:
                            text_content.append(f"=== 第{page_num + 1}页 ===\n[PDF页面内容 - 文本提取功能有限，建议安装pdfminer-six、pymupdf、pdfplumber或PyPDF2]")
                        else:
                            text_content.append(f"=== 第{page_num + 1}页 ===\n[空白页面或无文本内容]")
                    except Exception as e:
                        print(f"处理第{page_num + 1}页失败: {e}")
                        text_content.append(f"=== 第{page_num + 1}页 ===\n[页面处理失败]")
                        continue
                        
            if text_content and len(text_content) == pdf_page_count:
                full_text = "\n\n".join(text_content)
                print(f"使用pikepdf提取PDF结构信息，总长度: {len(full_text)} 字符，共{len(text_content)}页")
                return full_text
            else:
                print(f"pikepdf页面数量不匹配，期望{pdf_page_count}页，实际提取{len(text_content)}页")
                if text_content:
                    full_text = "\n\n".join(text_content)
                    return full_text + "\n\n注意：当前使用的是基础PDF结构提取。为获得完整文本内容，建议确保pdfminer-six或pymupdf库正常工作。"
                else:
                    return "PDF文件已加载，但无法提取文本内容。建议检查PDF文件格式或安装更好的文本提取库。"
                
        except Exception as e:
            print(f"PDF文本提取失败: {e}")
            return f"PDF文本提取失败: {str(e)}"
    

    def load_pdf_file(self, file_path):
        """加载PDF文件"""
        # 检查是否是新的PDF文件
        is_new_file = (self.current_file != file_path)
        
        self.current_file = file_path
        self.left_pdf_widget.load_pdf(file_path)
        self.status_label.set_status(f"已加载: {os.path.basename(file_path)}", "success")

        # 如果是新文件且智能问答面板存在内容，清空它以便重新加载
        if is_new_file and hasattr(self.embedded_qa, 'pdf_content') and self.embedded_qa.pdf_content:
            print("检测到新PDF文件，清空智能问答内容以便重新加载")
            self.embedded_qa.pdf_content = None  # 清空PDF内容，但保留聊天记录

        # 如果智能问答面板可见，更新PDF内容
        if self.qa_panel_visible:
            self._update_qa_panel_status()

        # 读取配置判断是否启用翻译
        if not self._is_translation_enabled():
            # 直接在右侧加载原始文件，不进行翻译
            self.right_pdf_widget.load_pdf(file_path)
            self.status_label.set_status("翻译已禁用，直接显示原文", "info")
            return

        # 检查同目录是否已有翻译后的 -mono 文件
        existing = self._find_existing_translation(file_path)
        if existing:
            # 直接加载现有翻译版本
            self.right_pdf_widget.load_pdf(existing)
            self.status_label.set_status("已加载本地翻译版本", "success")
            return

        # 否则开始翻译
        self.right_pdf_widget.view.setHtml("<div style='display:flex;justify-content:center;align-items:center;height:100%;font-size:16px;color:grey;'>正在准备翻译...</div>")
        self.start_translation(file_path)

    def _is_translation_enabled(self):
        """从配置文件判断是否启用翻译 (默认启用)"""
        import json
        import os
        cfg_path = "pdf2zh_config.json"
        if not os.path.exists(cfg_path):
            return True
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return bool(cfg.get("translation_enabled", True))
        except Exception:
            return True

    def _find_existing_translation(self, original_path):
        """检查是否存在已翻译的 -mono 文件并验证有效性"""
        base, ext = os.path.splitext(original_path)
        mono_path = f"{base}-mono{ext}"
        if os.path.exists(mono_path) and self._validate_pdf_file(mono_path):
            return mono_path
        return None

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
        # 显示并初始化进度条
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            if hasattr(self, 'progress_percent'):
                self.progress_percent.setText("0%")
                self.progress_percent.setVisible(True)
            print(f"进度条显示状态: {self.progress_bar.isVisible()} (start_translation)")
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
        if message.startswith("PROGRESS:"):
            # 解析并更新进度条
            try:
                percent = int(message.split(":", 1)[1])
                if hasattr(self, 'progress_bar'):
                    self.progress_bar.setValue(percent)
                if hasattr(self, 'progress_percent'):
                    self.progress_percent.setText(f"{percent}%")
            except ValueError:
                pass
        else:
            sanitized = message.replace("\n", " ")
            self.right_pdf_widget.view.setHtml(
                f"<div style='display:flex;justify-content:center;align-items:center;height:100%;font-size:16px;color:grey;'>{sanitized}</div>"
            )
            self.status_label.set_status(sanitized, "info")
        
    @pyqtSlot(str)
    def on_translation_completed(self, translated_file):
        """翻译完成"""
        if os.path.exists(translated_file):
            self.right_pdf_widget.load_pdf(translated_file)
            self.status_label.set_status("翻译完成", "success")
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(False)
        if hasattr(self, 'progress_percent'):
            self.progress_percent.setVisible(False)
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
            
            # 尝试使用pikepdf验证
            try:
                import pikepdf
                with pikepdf.open(file_path) as pdf:
                    page_count = len(pdf.pages)
                
                if page_count == 0:
                    print("PDF文件没有页面")
                    return False
                    
                print(f"PDF文件验证成功，共{page_count}页，大小{file_size/1024/1024:.1f}MB")
                return True
                
            except Exception as e:
                print(f"pikepdf验证PDF失败: {e}")
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
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(False)
        if hasattr(self, 'progress_percent'):
            self.progress_percent.setVisible(False)
        QMessageBox.critical(self, "翻译失败", f"翻译过程中出现错误:\n{error_message}")
        
    # def on_text_selected(self, text): # REMOVED: Feature not available in new widget
    #     """文本选中"""
    #     if text.strip():
    #         self.status_label.set_status(f"已选择文本: {text[:50]}...", "info")
        
    def closeEvent(self, event):
        """处理关闭事件"""
        reply = QMessageBox.question(self, '确认退出', '您确定要退出 FreePDF 吗？',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # Clean up resources only when the user confirms exiting.
            if hasattr(self, 'left_pdf_widget') and self.left_pdf_widget:
                self.left_pdf_widget.cleanup()
            if hasattr(self, 'right_pdf_widget') and self.right_pdf_widget:
                self.right_pdf_widget.cleanup()
            if hasattr(self, 'translation_manager') and self.translation_manager:
                self.translation_manager.cleanup()
                
            event.accept()
        else:
            event.ignore()

    def eventFilter(self, obj, event):
        """A global event filter to capture Ctrl+Wheel for zooming."""
        if event.type() == event.Type.Wheel:
            # The object can be a QWindow, which is not a QWidget.
            # We must ensure it's a widget before using isAncestorOf.
            if not isinstance(obj, QWidget):
                return super().eventFilter(obj, event)

            # Check if the event is for one of the PDF widgets.
            # We need to check isAncestorOf because the event's source `obj`
            # might be a child widget within the QWebEngineView.
            source_widget = None
            if self.left_pdf_widget.isAncestorOf(obj) or obj is self.left_pdf_widget:
                source_widget = self.left_pdf_widget
            elif self.right_pdf_widget.isAncestorOf(obj) or obj is self.right_pdf_widget:
                source_widget = self.right_pdf_widget

            if source_widget and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                # Ctrl key is pressed, so this is a zoom event.
                if event.angleDelta().y() > 0:
                    source_widget.zoom_in()
                else:
                    source_widget.zoom_out()
                
                # Return True to consume the event, preventing it from being
                # processed as a scroll event.
                return True

        # For all other events, pass them through.
        return super().eventFilter(obj, event)

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
                padding: 10px;
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
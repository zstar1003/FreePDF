"""批量翻译对话框"""

import os
import glob
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEventLoop
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTextEdit,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QSpacerItem,
    QSizePolicy,
    QListWidget,
    QListWidgetItem,
)


class BatchTranslationThread(QThread):
    """批量翻译线程"""
    progress_updated = pyqtSignal(int, int, str)  # current, total, current_file
    file_completed = pyqtSignal(str, bool, str)  # file_path, success, message
    batch_completed = pyqtSignal(int, int)  # success_count, total_count
    
    def __init__(self, pdf_files, lang_in, lang_out, parent=None):
        super().__init__(parent)
        self.pdf_files = pdf_files
        self.lang_in = lang_in
        self.lang_out = lang_out
        self._stop_requested = False
        
    def stop(self):
        """停止翻译"""
        self._stop_requested = True
        
    def run(self):
        """执行批量翻译"""
        success_count = 0
        total_count = len(self.pdf_files)
        
        for i, pdf_file in enumerate(self.pdf_files):
            if self._stop_requested:
                break
                
            # 更新进度
            self.progress_updated.emit(i + 1, total_count, os.path.basename(pdf_file))
            
            try:
                # 导入翻译模块
                from core.translation import TranslationManager
                
                # 创建翻译管理器
                translation_manager = TranslationManager()
                
                # 设置完成回调
                event_loop = QEventLoop()
                translation_error = None
                
                def on_completed(result_file):
                    event_loop.quit()
                    
                def on_failed(error):
                    nonlocal translation_error
                    translation_error = error
                    event_loop.quit()
                
                # 开始翻译
                translation_manager.start_translation(
                    pdf_file,
                    completed_callback=on_completed,
                    failed_callback=on_failed
                )
                
                # 阻塞等待翻译线程结束
                event_loop.exec()
                
                if self._stop_requested:
                    break
                    
                if translation_error:
                    self.file_completed.emit(pdf_file, False, translation_error)
                else:
                    self.file_completed.emit(pdf_file, True, "翻译成功")
                    success_count += 1
                    
            except Exception as e:
                self.file_completed.emit(pdf_file, False, f"翻译失败: {str(e)}")
                
        self.batch_completed.emit(success_count, total_count)


class BatchTranslationDialog(QDialog):
    """批量翻译对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量翻译")
        self.setFixedSize(700, 800)
        self.setModal(True)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLabel {
                color: #333;
                font-size: 12px;
            }
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px;
                font-size: 12px;
                background-color: #fafafa;
            }
            QLineEdit:focus {
                border-color: #007acc;
                background-color: #ffffff;
            }
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px;
                font-size: 12px;
                background-color: #fafafa;
            }
            QComboBox:focus {
                border-color: #007acc;
                background-color: #ffffff;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px;
                font-size: 12px;
                background-color: #fafafa;
            }
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: #fafafa;
                font-size: 12px;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666;
            }
            QPushButton[isSecondary="true"] {
                background-color: #6c757d;
                color: white;
            }
            QPushButton[isSecondary="true"]:hover {
                background-color: #5a6268;
            }
            QPushButton[isOrange="true"] {
                background-color: #ff8c00;
                color: white;
            }
            QPushButton[isOrange="true"]:hover {
                background-color: #e07b00;
            }
            QPushButton[isRed="true"] {
                background-color: #dc3545;
                color: white;
            }
            QPushButton[isRed="true"]:hover {
                background-color: #c82333;
            }
        """)
        
        self.pdf_files = []
        self.translation_thread = None
        
        self.setup_ui()
        self.load_language_config()
        
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("批量翻译PDF文档")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #007acc;
                padding: 10px 0;
                border-bottom: 1px solid #ddd;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title_label)
        
        # 文件夹选择组
        folder_group = QGroupBox("选择文件夹")
        folder_layout = QFormLayout(folder_group)
        folder_layout.setContentsMargins(15, 20, 15, 15)
        
        # 文件夹路径
        folder_input_layout = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("选择包含PDF文件的文件夹...")
        self.folder_path.setReadOnly(True)
        folder_input_layout.addWidget(self.folder_path)
        
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.browse_folder)
        folder_input_layout.addWidget(self.browse_btn)
        
        folder_layout.addRow("文件夹:", folder_input_layout)
        layout.addWidget(folder_group)
        
        # 语言配置组
        lang_group = QGroupBox("翻译设置")
        lang_layout = QFormLayout(lang_group)
        lang_layout.setContentsMargins(15, 20, 15, 15)
        
        # 源语言
        self.lang_in_combo = QComboBox()
        lang_layout.addRow("源语言:", self.lang_in_combo)
        
        # 目标语言
        self.lang_out_combo = QComboBox()
        lang_layout.addRow("目标语言:", self.lang_out_combo)
        
        layout.addWidget(lang_group)
        
        # 文件列表组
        files_group = QGroupBox("待翻译文件")
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(15, 20, 15, 15)
        
        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(150)
        files_layout.addWidget(self.files_list)
        
        self.files_info = QLabel("请选择文件夹以显示PDF文件列表")
        self.files_info.setStyleSheet("color: #666; font-style: italic;")
        files_layout.addWidget(self.files_info)
        
        layout.addWidget(files_group)
        
        # 进度显示组
        progress_group = QGroupBox("翻译进度")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(15, 20, 15, 15)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.current_file_label = QLabel("")
        self.current_file_label.setVisible(False)
        self.current_file_label.setStyleSheet("color: #007acc; font-weight: bold;")
        progress_layout.addWidget(self.current_file_label)

        # 移除结果显示框
        # self.result_text = QTextEdit()
        # self.result_text.setMaximumHeight(100)
        # self.result_text.setVisible(False)
        # self.result_text.setReadOnly(True)
        # progress_layout.addWidget(self.result_text)

        layout.addWidget(progress_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch()
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setProperty("isSecondary", True)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        # 停止按钮
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setProperty("isRed", True)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_translation)
        button_layout.addWidget(self.stop_btn)
        
        # 开始翻译按钮
        self.start_btn = QPushButton("开始翻译")
        self.start_btn.setProperty("isOrange", True)
        self.start_btn.clicked.connect(self.start_translation)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        
        layout.addLayout(button_layout)
        
    def load_language_config(self):
        """加载语言配置"""
        # 语言映射
        languages = {
            "英文": "en",
            "中文": "zh", 
            "日语": "ja",
            "韩语": "ko",
            "繁体中文": "zh-TW"
        }
        
        for lang_name in languages.keys():
            self.lang_in_combo.addItem(lang_name)
            self.lang_out_combo.addItem(lang_name)
            
        # 设置默认值
        self.lang_in_combo.setCurrentText("英文")
        self.lang_out_combo.setCurrentText("中文")
        
    def browse_folder(self):
        """浏览文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "选择包含PDF文件的文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.folder_path.setText(folder)
            self.scan_pdf_files(folder)
            
    def scan_pdf_files(self, folder):
        """扫描PDF文件"""
        try:
            # 查找所有PDF文件
            pdf_pattern = os.path.join(folder, "*.pdf")
            all_pdfs = glob.glob(pdf_pattern)
            
            # 过滤掉dual和mono后缀的文件
            self.pdf_files = []
            for pdf_file in all_pdfs:
                filename = os.path.basename(pdf_file)
                # 检查是否包含dual或mono后缀
                if not (filename.lower().endswith('.dual.pdf') or 
                        filename.lower().endswith('.mono.pdf') or
                        '.dual.' in filename.lower() or 
                        '.mono.' in filename.lower()):
                    self.pdf_files.append(pdf_file)
            
            # 更新文件列表显示
            self.files_list.clear()
            for pdf_file in self.pdf_files:
                item = QListWidgetItem(os.path.basename(pdf_file))
                item.setToolTip(pdf_file)  # 显示完整路径作为提示
                self.files_list.addItem(item)
                
            # 更新信息标签
            if self.pdf_files:
                self.files_info.setText(f"找到 {len(self.pdf_files)} 个PDF文件（已排除dual和mono文件）")
                self.start_btn.setEnabled(True)
            else:
                self.files_info.setText("未找到可翻译的PDF文件")
                self.start_btn.setEnabled(False)
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"扫描文件时出错：\n{str(e)}")
            
    def start_translation(self):
        """开始批量翻译"""
        if not self.pdf_files:
            QMessageBox.warning(self, "警告", "没有找到可翻译的PDF文件！")
            return
            
        # 获取语言设置
        lang_map = {
            "英文": "en",
            "中文": "zh", 
            "日语": "ja",
            "韩语": "ko",
            "繁体中文": "zh-TW"
        }
        
        lang_in = lang_map[self.lang_in_combo.currentText()]
        lang_out = lang_map[self.lang_out_combo.currentText()]
        
        # 显示进度组件
        self.progress_bar.setVisible(True)
        self.current_file_label.setVisible(True)
        # self.result_text.setVisible(True) # Removed as per edit hint
        # self.result_text.clear() # Removed as per edit hint
        
        # 更新按钮状态
        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.cancel_btn.setEnabled(False)
        
        # 设置进度条
        self.progress_bar.setRange(0, len(self.pdf_files))
        self.progress_bar.setValue(0)
        # 记录已完成数
        self._completed_count = 0
        
        # 创建并启动翻译线程
        self.translation_thread = BatchTranslationThread(self.pdf_files, lang_in, lang_out, self)
        self.translation_thread.progress_updated.connect(self.update_progress)
        self.translation_thread.file_completed.connect(self.file_completed)
        self.translation_thread.batch_completed.connect(self.batch_completed)
        self.translation_thread.start()
        
    def stop_translation(self):
        """停止翻译"""
        if self.translation_thread and self.translation_thread.isRunning():
            self.translation_thread.stop()
            self.translation_thread.wait(3000)  # 等待3秒
            
        self.reset_ui()
        # self.result_text.append("翻译已停止。") # Removed as per edit hint
        
    def update_progress(self, current, total, current_file):
        """更新进度"""
        # 修正进度条显示：当前处理第N个文件时，进度条应为N-1
        self.progress_bar.setValue(current - 1)
        self.current_file_label.setText(f"正在翻译: {current_file} ({current}/{total})")
        
    def file_completed(self, file_path, success, message):
        """文件翻译完成"""
        # 统计已完成数
        if not hasattr(self, '_completed_count'):
            self._completed_count = 0
        self._completed_count += 1
        # 进度条+1
        self.progress_bar.setValue(self._completed_count)
        # 可选：弹窗或label显示结果
        # filename = os.path.basename(file_path)
        # if success:
        #     self.result_text.append(f"✓ {filename}: {message}")
        # else:
        #     self.result_text.append(f"✗ {filename}: {message}")
        # 滚动到底部（已移除result_text）
            
    def batch_completed(self, success_count, total_count):
        """批量翻译完成"""
        self.reset_ui()
        # 进度条100%
        self.progress_bar.setValue(total_count)
        # 显示完成信息
        self.current_file_label.setText(f"批量翻译完成: {success_count}/{total_count} 成功")
        # 可选：弹窗提示
        if success_count == total_count:
            QMessageBox.information(self, "完成", f"批量翻译成功完成！\n共翻译 {total_count} 个文件。")
        else:
            QMessageBox.warning(self, "完成", f"批量翻译完成，但有部分失败。\n成功: {success_count}, 失败: {total_count - success_count}")
        
    def reset_ui(self):
        """重置UI状态"""
        self.start_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)
        self.start_btn.setEnabled(len(self.pdf_files) > 0)
        
    def closeEvent(self, event):
        """关闭事件"""
        if self.translation_thread and self.translation_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "确认", 
                "翻译正在进行中，确定要关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.translation_thread.stop()
                self.translation_thread.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
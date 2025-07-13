"""QA配置对话框"""

import json
import os

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class QASettingsDialog(QDialog):
    """QA配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("智能问答配置")
        self.setFixedSize(500, 450)
        self.setModal(True)
        
        # 设置对话框样式 - 与应用其他对话框保持一致
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
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
                background-color: #f5f5f5;
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
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px;
                font-size: 12px;
                background-color: #fafafa;
            }
            QTextEdit:focus {
                border-color: #007acc;
                background-color: #ffffff;
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
            QPushButton[isSecondary="true"] {
                background-color: #6c757d;
                color: white;
            }
            QPushButton[isSecondary="true"]:hover {
                background-color: #5a6268;
            }
        """)
        
        # 加载当前配置
        self.config = self._load_config()
        
        self.setup_ui()
        self.load_current_settings()
        
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # PDF页面范围配置组
        page_group = QGroupBox("PDF内容配置")
        page_layout = QFormLayout(page_group)
        page_layout.setContentsMargins(15, 20, 15, 15)
        
        # 页面范围输入
        self.pages_input = QLineEdit()
        self.pages_input.setPlaceholderText("例如: 1-5,8,10-15 (留空表示所有页面)")
        page_layout.addRow("页面范围:", self.pages_input)
        
        # 格式说明
        format_label = QLabel("格式说明：输入要分析的页面范围，用逗号分隔\n例如：1-5,8,10-15 表示第1-5页、第8页、第10-15页")
        format_label.setWordWrap(True)
        format_label.setStyleSheet("color: #666; font-style: italic; margin-top: 5px;")
        page_layout.addRow("", format_label)
        
        layout.addWidget(page_group)
        
        # 系统提示词配置组
        prompt_group = QGroupBox("系统提示词配置")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.setContentsMargins(15, 20, 15, 15)
        
        # 提示词输入框
        self.prompt_input = QTextEdit()
        self.prompt_input.setMaximumHeight(150)
        self.prompt_input.setPlaceholderText("例如：你是一个专业的文档分析助手，请用简洁明了的语言回答问题...")
        prompt_layout.addWidget(self.prompt_input)
        
        layout.addWidget(prompt_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("isSecondary", True)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # 添加按钮间距
        button_layout.addSpacing(10)
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
    def _load_config(self):
        """加载配置文件"""
        config_file = "pdf2zh_config.json"
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"读取配置文件失败: {e}")
        return {}
        
    def load_current_settings(self):
        """加载当前设置到界面"""
        # 加载页面范围设置
        qa_config = self.config.get("qa_settings", {})
        pages = qa_config.get("pages", "")
        self.pages_input.setText(pages)
        
        # 加载系统提示词设置
        system_prompt = qa_config.get("system_prompt", "")
        self.prompt_input.setPlainText(system_prompt)
        
    def save_settings(self):
        """保存设置"""
        try:
            # 获取用户输入
            pages = self.pages_input.text().strip()
            system_prompt = self.prompt_input.toPlainText().strip()
            
            # 验证页面范围格式
            if pages and not self._validate_page_range(pages):
                QMessageBox.warning(self, "格式错误", "页面范围格式不正确！\n\n正确格式例如：1-5,8,10-15")
                return
                
            # 更新配置
            if "qa_settings" not in self.config:
                self.config["qa_settings"] = {}
                
            self.config["qa_settings"]["pages"] = pages
            self.config["qa_settings"]["system_prompt"] = system_prompt
            
            # 保存到文件
            config_file = "pdf2zh_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
                
            # 使用简单的成功提示，不带白色背景
            self._show_success_message("QA配置已保存！")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存配置时出错：\n{str(e)}")
            
    def _show_success_message(self, message):
        """显示成功消息，不带白色背景"""
        # 创建自定义的成功提示对话框
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("保存成功")
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        # 设置样式，去掉白色背景
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f5f5f5;
            }
            QMessageBox QLabel {
                color: #333;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 60px;
            }
            QMessageBox QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        
        msg_box.exec()
            
    def _validate_page_range(self, page_range):
        """验证页面范围格式"""
        if not page_range:
            return True
            
        try:
            # 分割逗号分隔的部分
            parts = page_range.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # 验证范围格式
                    start, end = part.split('-', 1)
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    if start_num < 1 or end_num < 1 or start_num > end_num:
                        return False
                else:
                    # 验证单个页面
                    page_num = int(part)
                    if page_num < 1:
                        return False
            return True
        except (ValueError, IndexError):
            return False
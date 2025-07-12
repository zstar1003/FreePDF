"""翻译设置对话框"""

import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class TranslationSettingsDialog(QDialog):
    """翻译设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("翻译配置")
        self.setFixedSize(500, 520)
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
            QCheckBox, QRadioButton {
                color: #333;
                font-size: 12px;
                spacing: 8px;
            }
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
            QLineEdit:disabled {
                background-color: #f8f9fa;
                color: #6c757d;
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
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 基本翻译设置组
        basic_group = QGroupBox("基本设置")
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.setContentsMargins(15, 20, 15, 15)
        
        # 是否启用翻译
        self.enable_translation = QCheckBox("启用PDF翻译")
        self.enable_translation.setChecked(True)
        basic_layout.addWidget(self.enable_translation)
        
        layout.addWidget(basic_group)
        
        # 页面设置组
        pages_group = QGroupBox("页面设置")
        pages_layout = QVBoxLayout(pages_group)
        pages_layout.setContentsMargins(15, 20, 15, 15)
        pages_layout.setSpacing(15)
        
        # 翻译模式选择 - 使用单选按钮组
        mode_label = QLabel("翻译模式:")
        mode_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        pages_layout.addWidget(mode_label)
        
        self.mode_group = QButtonGroup(self)
        
        self.translate_all = QRadioButton("翻译全部页面")
        self.translate_all.setChecked(True)
        self.mode_group.addButton(self.translate_all, 0)
        pages_layout.addWidget(self.translate_all)
        
        self.translate_custom = QRadioButton("自定义页面范围")
        self.mode_group.addButton(self.translate_custom, 1)
        pages_layout.addWidget(self.translate_custom)
        
        # 自定义页面设置
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        custom_layout.setContentsMargins(20, 10, 0, 0)
        custom_layout.setSpacing(8)
        
        # 页面范围输入
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("页面范围:"))
        self.page_range = QLineEdit()
        self.page_range.setPlaceholderText("例如: 1-5,8,10-15")
        self.page_range.setEnabled(False)
        range_layout.addWidget(self.page_range)
        custom_layout.addLayout(range_layout)
        
        pages_layout.addWidget(custom_widget)
        
        # 帮助说明
        help_label = QLabel("""页面范围格式说明:
• 单页: 1, 3, 5
• 范围: 1-5 (第1到5页)  
• 混合: 1-3,5,7-10 (第1到3页、第5页、第7到10页)
• 留空则翻译所有页面""")
        help_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                background-color: #f8f9fa;
                padding: 12px;
                border-radius: 6px;
                border: 1px solid #e9ecef;
                line-height: 18px;
            }
        """)
        pages_layout.addWidget(help_label)
        
        layout.addWidget(pages_group)
        
        # 连接信号
        self.mode_group.buttonToggled.connect(self.on_mode_changed)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 重置按钮
        reset_btn = QPushButton("重置")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        reset_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004a82;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
    def on_mode_changed(self, button, checked):
        """翻译模式改变时的处理"""
        if checked:
            if button == self.translate_all:
                self.page_range.setEnabled(False)
                self.page_range.clear()
            elif button == self.translate_custom:
                self.page_range.setEnabled(True)
                self.page_range.setFocus()
            
    def _load_config(self):
        """加载配置文件"""
        config_file = "pdf2zh_config.json"
        default_config = {
            "translation_enabled": True,
            "pages": ""
        }
        
        if not os.path.exists(config_file):
            return default_config
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {
                    "translation_enabled": config.get("translation_enabled", True),
                    "pages": config.get("pages", "")
                }
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            return default_config
            
    def load_current_settings(self):
        """加载当前设置到界面"""
        # 基本设置
        self.enable_translation.setChecked(self.config.get("translation_enabled", True))
        
        # 页面设置
        pages = self.config.get("pages", "")
        
        if pages:
            # 有自定义页面设置
            self.translate_custom.setChecked(True)
            self.page_range.setText(pages)
            self.page_range.setEnabled(True)
        else:
            # 翻译全部页面
            self.translate_all.setChecked(True)
            self.page_range.setEnabled(False)
        
    def reset_settings(self):
        """重置设置为默认值"""
        self.enable_translation.setChecked(True)
        self.translate_all.setChecked(True)
        self.page_range.setText("")
        self.page_range.setEnabled(False)
        
    def _validate_page_range(self, page_range_str):
        """验证页面范围格式"""
        if not page_range_str.strip():
            return True  # 空字符串表示所有页面
            
        try:
            # 简单的格式验证
            ranges = page_range_str.split(',')
            for range_part in ranges:
                range_part = range_part.strip()
                if '-' in range_part:
                    start, end = range_part.split('-', 1)
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    if start_num <= 0 or end_num <= 0 or start_num > end_num:
                        return False
                else:
                    page_num = int(range_part)
                    if page_num <= 0:
                        return False
            return True
        except (ValueError, AttributeError):
            return False
            
    def save_settings(self):
        """保存设置"""
        try:
            # 验证页面范围
            if self.translate_custom.isChecked():
                page_range = self.page_range.text().strip()
                if page_range and not self._validate_page_range(page_range):
                    QMessageBox.warning(self, "格式错误", 
                                      "页面范围格式不正确！\n"
                                      "正确格式示例: 1-5,8,10-15")
                    return
            
            # 加载现有配置
            config_file = "pdf2zh_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # 更新翻译设置
            config["translation_enabled"] = self.enable_translation.isChecked()
            
            if self.translate_custom.isChecked():
                config["pages"] = self.page_range.text().strip()
            else:
                config["pages"] = ""  # 空字符串表示翻译所有页面
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "保存成功", "翻译配置已保存成功！")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存配置时出错:\n{str(e)}")
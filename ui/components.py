"""UI组件模块"""

import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class AnimationOverlay(QWidget):
    """动画覆盖层 - 确保旋转动画在最上层"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.animation_center_x = 0
        self.animation_center_y = 0
        self.radius = 22  # 增大半径，让动画更明显
        
        # 设置为透明覆盖层
        self.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
        """)
        
        # 确保这个widget在最上层
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.raise_()
        
    def set_animation_center(self, x, y):
        """设置动画中心点"""
        self.animation_center_x = x
        self.animation_center_y = y
        self.update()
        
    def set_angle(self, angle):
        """设置旋转角度"""
        self.angle = angle
        self.update()
        
    def paintEvent(self, event):
        """绘制旋转动画"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = self.animation_center_x
        center_y = self.animation_center_y
        
        # 只在有效位置绘制
        if center_x > 0 and center_y > 0:
            # 绘制外圈淡色圆圈 - 增加可见性
            painter.setPen(QColor(0, 122, 204, 80))
            painter.setBrush(QColor(0, 122, 204, 30))
            painter.drawEllipse(center_x - self.radius - 8, center_y - self.radius - 8, 
                              (self.radius + 8) * 2, (self.radius + 8) * 2)
            
            # 绘制旋转的加载点 - 增强可见性
            painter.setPen(QColor(0, 122, 204, 150))
            
            for i in range(12):
                angle_rad = math.radians(self.angle + i * 30)
                x = center_x + self.radius * math.cos(angle_rad)
                y = center_y + self.radius * math.sin(angle_rad)
                
                # 计算透明度，形成尾巴效果 - 增加最小透明度
                alpha = int(255 * (1 - i * 0.06))  # 减少透明度衰减
                if alpha < 80:  # 提高最小透明度
                    alpha = 80
                
                painter.setBrush(QColor(0, 122, 204, alpha))
                
                # 绘制更大的圆点，增加可见性
                point_size = 7 - (i * 0.2)  # 增大基础尺寸，减少衰减
                if point_size < 4:  # 提高最小尺寸
                    point_size = 4
                    
                painter.drawEllipse(int(x - point_size/2), int(y - point_size/2), 
                                  int(point_size), int(point_size))


class LoadingWidget(QWidget):
    """加载动画组件"""
    
    def __init__(self, message="正在处理...", parent=None):
        super().__init__(parent)
        # 设置固定大小，确保加载框显示正确
        self.message = message
        self.angle = 0
        
        # 设置固定大小为合适的加载框尺寸
        self.setFixedSize(500, 300)
        
        # 设置大小策略为固定大小
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # 设置背景
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.98);
                border: 2px solid #007acc;
                border-radius: 15px;
            }
        """)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(25)
        
        # 创建中心容器，用于限制内容宽度
        center_container = QWidget()
        center_container.setMaximumWidth(460)  # 适应500px的固定宽度
        center_container.setMinimumHeight(220)  # 适应300px的固定高度
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(20, 20, 20, 20)
        center_layout.setSpacing(20)
        
        # 旋转动画区域 - 创建一个专门的容器
        animation_container = QWidget()
        animation_container.setFixedHeight(100)
        animation_container.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
        """)
        self.animation_container = animation_container
        center_layout.addWidget(animation_container)
        
        # 创建独立的动画覆盖层，确保动画在最上层
        self.animation_overlay = AnimationOverlay(self)
        self.animation_overlay.hide()  # 初始隐藏
        
        # 消息标签
        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 15px;
                line-height: 1.4;
            }
        """)
        center_layout.addWidget(self.message_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 无限进度条
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background-color: #e0e0e0;
                margin: 10px 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #007acc, stop: 0.5 #4fc3f7, stop: 1 #007acc
                );
                border-radius: 3px;
            }
        """)
        center_layout.addWidget(self.progress_bar)
        
        # 将中心容器添加到主布局
        main_layout.addWidget(center_container, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 动画定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(40)  # 40ms刷新一次，更流畅
        
    def update_animation(self):
        """更新动画"""
        self.angle = (self.angle + 8) % 360  # 更平滑的角度变化
        
        # 更新覆盖层的角度
        if hasattr(self, 'animation_overlay'):
            self.animation_overlay.set_angle(self.angle)
            
        # 重新计算动画中心位置
        self._update_animation_position()
        
    def set_message(self, message):
        """设置消息"""
        self.message = message
        self.message_label.setText(message)
    
    def _update_animation_position(self):
        """更新动画位置"""
        if hasattr(self, 'animation_overlay') and hasattr(self, 'animation_container'):
            # 确保覆盖层大小与LoadingWidget一致
            self.animation_overlay.setGeometry(self.rect())
            
            # 计算动画中心位置
            if self.animation_container:
                animation_rect = self.animation_container.geometry()
                center_x = self.width() // 2
                center_y = animation_rect.center().y() + 30  # 往下移动
                
                # 设置动画中心
                self.animation_overlay.set_animation_center(center_x, center_y)
                
                # 显示覆盖层并确保在最上层
                self.animation_overlay.show()
                self.animation_overlay.raise_()
        
    def paintEvent(self, event):
        """绘制背景（动画由覆盖层处理）"""
        super().paintEvent(event)
        # 确保动画位置更新
        self._update_animation_position()
        
    def show_centered(self, parent_widget):
        """在父控件中心显示"""
        if parent_widget:
            parent_rect = parent_widget.rect()
            self.move(
                parent_rect.center().x() - self.width() // 2,
                parent_rect.center().y() - self.height() // 2
            )
        self.show()
        self.raise_()
        
    def closeEvent(self, event):
        """关闭时停止定时器"""
        if hasattr(self, 'timer'):
            self.timer.stop()
        if hasattr(self, 'animation_overlay'):
            self.animation_overlay.hide()
        super().closeEvent(event)


class StatusLabel(QLabel):
    """状态标签组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 5px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 3px;
            }
        """)
        self.setText("就绪")
        
    def set_status(self, message, status_type="info"):
        """设置状态信息
        status_type: info, success, warning, error
        """
        colors = {
            "info": "#007acc",
            "success": "#28a745", 
            "warning": "#ffc107",
            "error": "#dc3545"
        }
        
        color = colors.get(status_type, "#007acc")
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 12px;
                padding: 5px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                font-weight: bold;
            }}
        """)
        self.setText(message)


class DragDropOverlay(QWidget):
    """拖拽提示覆盖层"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background: rgba(0, 122, 204, 0.15);
                border: 3px dashed #007acc;
                border-radius: 15px;
            }
            QLabel {
                color: #007acc;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)
        
        # 添加图标标签
        icon_label = QLabel("📄")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(icon_label)
        
        # 添加文本标签
        text_label = QLabel("拖拽PDF文件到此处")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(True)
        layout.addWidget(text_label)
        
        # 添加说明文字
        desc_label = QLabel("支持 .pdf 格式文件")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 16px;
                font-weight: normal;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(desc_label)
        
        # 默认隐藏
        self.hide()
        
    def show_overlay(self, parent_widget):
        """显示覆盖层"""
        if parent_widget:
            # 设置大小和位置与父控件一致
            self.setGeometry(parent_widget.rect())
            self.move(parent_widget.mapToGlobal(parent_widget.rect().topLeft()))
        self.show()
        self.raise_()
        
    def hide_overlay(self):
        """隐藏覆盖层"""
        self.hide()


class TranslationConfigDialog(QDialog):
    """翻译配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("翻译配置")
        self.setFixedSize(480, 500)
        self.setModal(True)
        
        # 加载当前配置
        self.load_current_config()
        
        # 创建UI
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("翻译引擎配置")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #333;
                padding: 10px 0;
            }
        """)
        main_layout.addWidget(title_label)
        
        # 基础配置组
        basic_group = QGroupBox("基础配置")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(10)
        
                 # 翻译引擎选择
        self.service_combo = QComboBox()
        self.service_combo.addItems(["bing", "google", "silicon", "ollama"])
        self.service_combo.currentTextChanged.connect(self.on_service_changed)
        basic_layout.addRow("翻译引擎:", self.service_combo)
        
        # 语言映射字典
        self.lang_display_map = {
            "zh": "中文",
            "en": "英文"
        }
        self.lang_code_map = {
            "中文": "zh",
            "英文": "en"
        }
        
        # 原语言
        self.lang_in_combo = QComboBox()
        self.lang_in_combo.addItems(["英文", "中文"])
        basic_layout.addRow("原语言:", self.lang_in_combo)
        
        # 目标语言
        self.lang_out_combo = QComboBox()
        self.lang_out_combo.addItems(["中文", "英文"])
        basic_layout.addRow("目标语言:", self.lang_out_combo)
        
        main_layout.addWidget(basic_group)
        
        # 环境变量配置组
        self.env_group = QGroupBox("环境变量配置")
        self.env_layout = QFormLayout(self.env_group)
        self.env_layout.setSpacing(10)
        
        # 环境变量输入框会根据服务类型动态创建
        
        main_layout.addWidget(self.env_group)
        
        # 添加弹性空间
        spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        main_layout.addItem(spacer)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("""
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
                background-color: #005a9e;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        main_layout.addLayout(button_layout)
        
        # 初始化显示
        self.on_service_changed(self.service_combo.currentText())
        
    def on_service_changed(self, service):
        """翻译引擎改变时的处理"""
        # 清除之前的环境变量输入框
        while self.env_layout.rowCount() > 0:
            self.env_layout.removeRow(0)
        
        if service == "silicon":
            # 创建Silicon配置控件
            self.silicon_api_key = QLineEdit()
            self.silicon_api_key.setPlaceholderText("请输入Silicon API Key")
            self.silicon_model = QLineEdit()
            self.silicon_model.setPlaceholderText("例如: Qwen/Qwen2.5-7B-Instruct")
            
            self.env_layout.addRow("API Key:", self.silicon_api_key)
            self.env_layout.addRow("模型:", self.silicon_model)
        elif service == "ollama":
            # 创建Ollama配置控件
            self.ollama_host = QLineEdit()
            self.ollama_host.setPlaceholderText("例如: http://127.0.0.1:11434")
            self.ollama_model = QLineEdit()
            self.ollama_model.setPlaceholderText("例如: deepseek-r1:1.5b")
            
            self.env_layout.addRow("服务地址:", self.ollama_host)
            self.env_layout.addRow("模型:", self.ollama_model)
        else:
            # Google/Bing 不需要额外配置
            info_label = QLabel("该翻译引擎无需额外配置")
            info_label.setStyleSheet("color: #6c757d; font-style: italic;")
            self.env_layout.addRow(info_label)
            
    def load_current_config(self):
        """加载当前配置"""
        import json
        import os
        
        # 默认配置
        self.current_config = {
            "service": "bing",
            "lang_in": "en", 
            "lang_out": "zh",
            "envs": {}
        }
        
        # 从统一配置文件加载
        config_file = "pdf2zh_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
                    if "translation" in full_config:
                        self.current_config.update(full_config["translation"])
            except Exception as e:
                print(f"读取配置失败: {e}")
                
    def save_config(self):
        """保存配置"""
        import json
        import os
        
        # 收集配置，将显示名称转换为代码
        config = {
            "service": self.service_combo.currentText(),
            "lang_in": self.lang_code_map.get(self.lang_in_combo.currentText(), "en"),
            "lang_out": self.lang_code_map.get(self.lang_out_combo.currentText(), "zh"),
            "envs": {}
        }
        
        # 收集环境变量
        service = config["service"]
        if service == "silicon":
            if hasattr(self, 'silicon_api_key') and self.silicon_api_key.text().strip():
                config["envs"]["SILICON_API_KEY"] = self.silicon_api_key.text().strip()
            if hasattr(self, 'silicon_model') and self.silicon_model.text().strip():
                config["envs"]["SILICON_MODEL"] = self.silicon_model.text().strip()
        elif service == "ollama":
            if hasattr(self, 'ollama_host') and self.ollama_host.text().strip():
                config["envs"]["OLLAMA_HOST"] = self.ollama_host.text().strip()
            if hasattr(self, 'ollama_model') and self.ollama_model.text().strip():
                config["envs"]["OLLAMA_MODEL"] = self.ollama_model.text().strip()
        
        # 读取现有的完整配置文件
        config_file = "pdf2zh_config.json"
        full_config = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
            except Exception as e:
                print(f"读取现有配置失败: {e}")
        
        # 更新翻译配置部分
        full_config["translation"] = config
        
        # 保存到统一配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(full_config, f, indent=4, ensure_ascii=False)
            
        self.current_config = config
        
    def apply_current_config(self):
        """应用当前配置到UI"""
        # 设置服务
        index = self.service_combo.findText(self.current_config.get("service", "bing"))
        if index >= 0:
            self.service_combo.setCurrentIndex(index)
            
        # 设置语言，将代码转换为显示名称
        lang_in_code = self.current_config.get("lang_in", "en")
        lang_in_display = self.lang_display_map.get(lang_in_code, "英文")
        index = self.lang_in_combo.findText(lang_in_display)
        if index >= 0:
            self.lang_in_combo.setCurrentIndex(index)
            
        lang_out_code = self.current_config.get("lang_out", "zh")
        lang_out_display = self.lang_display_map.get(lang_out_code, "中文")
        index = self.lang_out_combo.findText(lang_out_display)
        if index >= 0:
            self.lang_out_combo.setCurrentIndex(index)
            
        # 设置环境变量
        envs = self.current_config.get("envs", {})
        if hasattr(self, 'silicon_api_key') and "SILICON_API_KEY" in envs:
            self.silicon_api_key.setText(envs["SILICON_API_KEY"])
        if hasattr(self, 'silicon_model') and "SILICON_MODEL" in envs:
            self.silicon_model.setText(envs["SILICON_MODEL"])
        if hasattr(self, 'ollama_host') and "OLLAMA_HOST" in envs:
            self.ollama_host.setText(envs["OLLAMA_HOST"])
        if hasattr(self, 'ollama_model') and "OLLAMA_MODEL" in envs:
            self.ollama_model.setText(envs["OLLAMA_MODEL"])
            
    def showEvent(self, event):
        """显示对话框时应用配置"""
        super().showEvent(event)
        self.apply_current_config()
        
    def accept(self):
        """确定按钮处理"""
        self.save_config()
        super().accept()
        
    def get_config(self):
        """获取当前配置"""
        return self.current_config.copy() 
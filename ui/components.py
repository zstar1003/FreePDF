"""UI组件模块"""

import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget, QSizePolicy


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
        from PyQt6.QtWidgets import QHBoxLayout
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
        self.update()
        
    def set_message(self, message):
        """设置消息"""
        self.message = message
        self.message_label.setText(message)
        
    def paintEvent(self, event):
        """绘制旋转圆圈"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 基于animation_container的位置来计算动画位置
        if hasattr(self, 'animation_container') and self.animation_container:
            # 获取animation_container在LoadingWidget中的位置
            animation_rect = self.animation_container.geometry()
            
            # 在animation_container的中心绘制动画
            center_x = animation_rect.center().x()
            center_y = animation_rect.center().y()
            
            # 确保不超出边界
            radius = 18  # 固定半径，确保动画大小合适
            
            # 边界检查 - 确保动画在LoadingWidget内部
            if center_x - radius - 5 < 0 or center_x + radius + 5 > self.width():
                return  # 如果会超出边界，不绘制
            if center_y - radius - 5 < 0 or center_y + radius + 5 > self.height():
                return  # 如果会超出边界，不绘制
        else:
            # 如果没有animation_container，使用默认位置
            center_x = self.width() // 2
            center_y = self.height() // 4
            radius = 18
        
        # 绘制外圈淡色圆圈 - 增加可见性
        painter.setPen(QColor(0, 122, 204, 80))
        painter.setBrush(QColor(0, 122, 204, 30))
        painter.drawEllipse(center_x - radius - 8, center_y - radius - 8, 
                          (radius + 8) * 2, (radius + 8) * 2)
        
        # 绘制旋转的加载点 - 增强可见性
        painter.setPen(QColor(0, 122, 204, 150))
        
        for i in range(12):
            angle_rad = math.radians(self.angle + i * 30)
            x = center_x + radius * math.cos(angle_rad)
            y = center_y + radius * math.sin(angle_rad)
            
            # 计算透明度，形成尾巴效果 - 增加最小透明度
            alpha = int(255 * (1 - i * 0.06))  # 减少透明度衰减
            if alpha < 80:  # 提高最小透明度
                alpha = 80
            
            painter.setBrush(QColor(0, 122, 204, alpha))
            
            # 绘制更大的圆点，增加可见性
            point_size = 6 - (i * 0.2)  # 增大基础尺寸，减少衰减
            if point_size < 3:  # 提高最小尺寸
                point_size = 3
                
            painter.drawEllipse(int(x - point_size/2), int(y - point_size/2), 
                              int(point_size), int(point_size))
        
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
"""UI组件模块"""

import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget, QSizePolicy


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
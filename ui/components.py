"""UI组件模块"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QMovie
import math


class LoadingWidget(QWidget):
    """加载动画组件"""
    
    def __init__(self, message="正在处理...", parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 150)
        self.message = message
        self.angle = 0
        
        # 设置背景
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid #ddd;
                border-radius: 10px;
            }
        """)
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 消息标签
        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 14px;
                font-weight: bold;
                background: transparent;
                border: none;
                margin: 10px;
            }
        """)
        layout.addWidget(self.message_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 无限进度条
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ccc;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #007acc, stop: 1 #4fc3f7
                );
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 动画定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)  # 50ms刷新一次
        
    def update_animation(self):
        """更新动画"""
        self.angle = (self.angle + 10) % 360
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
        
        # 绘制旋转圆圈
        center_x = self.width() // 2
        center_y = 40
        radius = 15
        
        painter.setPen(QColor(0, 122, 204, 100))
        
        for i in range(8):
            angle_rad = math.radians(self.angle + i * 45)
            x = center_x + radius * math.cos(angle_rad)
            y = center_y + radius * math.sin(angle_rad)
            
            alpha = int(255 * (i + 1) / 8)
            painter.setBrush(QColor(0, 122, 204, alpha))
            painter.drawEllipse(int(x - 3), int(y - 3), 6, 6)
            
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


class SyncScrollArea:
    """同步滚动区域管理器"""
    
    def __init__(self, scroll_area1, scroll_area2):
        self.scroll_area1 = scroll_area1
        self.scroll_area2 = scroll_area2
        self._syncing = False
        
        # 连接滚动条信号
        self.scroll_area1.verticalScrollBar().valueChanged.connect(self._sync_scroll1)
        self.scroll_area2.verticalScrollBar().valueChanged.connect(self._sync_scroll2)
        
    def _sync_scroll1(self, value):
        """同步第一个滚动区域到第二个"""
        if not self._syncing:
            self._syncing = True
            self.scroll_area2.verticalScrollBar().setValue(value)
            self._syncing = False
            
    def _sync_scroll2(self, value):
        """同步第二个滚动区域到第一个"""
        if not self._syncing:
            self._syncing = True
            self.scroll_area1.verticalScrollBar().setValue(value)
            self._syncing = False
            
    def set_enabled(self, enabled):
        """启用或禁用同步"""
        if enabled:
            self.scroll_area1.verticalScrollBar().valueChanged.connect(self._sync_scroll1)
            self.scroll_area2.verticalScrollBar().valueChanged.connect(self._sync_scroll2)
        else:
            self.scroll_area1.verticalScrollBar().valueChanged.disconnect(self._sync_scroll1)
            self.scroll_area2.verticalScrollBar().valueChanged.disconnect(self._sync_scroll2)


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
"""PDF双语预览器主程序"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow


def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("PDF双语预览器")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PDF Tools")
    
    # PyQt6中高DPI默认启用，不需要设置这些属性
    # 如果需要禁用高DPI，可以设置环境变量 QT_ENABLE_HIGHDPI_SCALING=0
    pass
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
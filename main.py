"""FreePDF主程序"""

import os
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEngineProfile

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow


def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("FreePDF")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("FreePDF")
    
    # 预热WebEngine，提前初始化核心组件
    print("正在预热WebEngine...")
    profile = QWebEngineProfile.defaultProfile()
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    print("WebEngine核心组件预热完成")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
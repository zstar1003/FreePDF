"""PDF预览器主程序"""

import sys
from PyQt6.QtWidgets import QApplication

from ui.main_window import PDFViewer


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("PDF预览器")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("PDF Tools")
    
    # 创建并显示主窗口
    viewer = PDFViewer()
    viewer.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
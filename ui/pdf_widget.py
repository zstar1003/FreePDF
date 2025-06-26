"""PDF显示组件 - 基于Web渲染"""

import os
import urllib.parse

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)


class WebPDFView(QWebEngineView):
    """基于Web的PDF视图"""
    page_changed = pyqtSignal(int)
    text_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # 创建一个模拟的滚动条来兼容旧的API
        from PyQt6.QtWidgets import QScrollBar
        self._mock_vertical_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self._mock_horizontal_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        
        # 设置不可见
        self._mock_vertical_scrollbar.hide()
        self._mock_horizontal_scrollbar.hide()
        
        # 配置WebEngine设置
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        # 设置样式，包含强制隐藏PDF工具栏的CSS
        self.setStyleSheet("""
            QWebEngineView {
                border: none;
                background-color: #f5f5f5;
            }
        """)
        
        self.pdf_path = None
        self.current_page = 0
        self.total_pages = 0
        
        # 监听页面加载完成
        self.loadFinished.connect(self._on_load_finished)
        
        # 页面变化检测定时器
        self.page_timer = QTimer()
        self.page_timer.timeout.connect(self._check_current_page)
        self.page_timer.setInterval(500)  # 每500ms检查一次
        
    def load_pdf(self, file_path):
        """加载PDF文件"""
        try:
            if not os.path.exists(file_path):
                return False
                
            self.pdf_path = file_path
            
            # 将文件路径转换为file:// URL
            file_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            
            # 加载PDF文件
            self.load(file_url)
            
            return True
            
        except Exception as e:
            print(f"加载PDF失败: {e}")
            return False
    

    
    def _on_load_finished(self, success):
        """页面加载完成"""
        if success and self.pdf_path:
            print(f"PDF加载成功: {self.pdf_path}")
            
            # 启动页面检测
            self.page_timer.start()
            
            # 注入JavaScript来获取PDF信息和监听页面变化
            self._inject_pdf_scripts()
            
            # 延迟执行简单的适应宽度设置，让PDF先完全加载
            QTimer.singleShot(2000, self._set_fit_width)
        else:
            print("PDF加载失败")
    
    def _inject_pdf_scripts(self):
        """注入JavaScript脚本"""
        # 简化的脚本，只监听基本信息
        js_code = """
        (function() {
            function checkPDFInfo() {
                try {
                    const plugin = document.querySelector('embed[type="application/pdf"]');
                    if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {
                        const app = plugin.contentWindow.PDFViewerApplication;
                        if (app.pdfDocument) {
                            window.pdfTotalPages = app.pdfDocument.numPages;
                            window.pdfCurrentPage = app.page;
                            return true;
                        }
                    }
                    
                    // 默认值
                    window.pdfCurrentPage = 1;
                    window.pdfTotalPages = 1;
                    return false;
                } catch (e) {
                    return false;
                }
            }
            
            // 定期检查PDF信息
            setInterval(checkPDFInfo, 500);
            checkPDFInfo();
            
            // 监听文本选择
            document.addEventListener('selectionchange', function() {
                const selection = window.getSelection();
                if (selection && selection.toString().trim()) {
                    window.selectedText = selection.toString().trim();
                }
            });
        })();
        """
        
        self.page().runJavaScript(js_code)
    
    def _check_current_page(self):
        """检查当前页面"""
        # 通过JavaScript获取当前页面信息
        self.page().runJavaScript(
            "window.pdfCurrentPage || 1",
            self._on_current_page_result
        )
        
        self.page().runJavaScript(
            "window.pdfTotalPages || 1",
            self._on_total_pages_result
        )
        
        # 检查选中的文本
        self.page().runJavaScript(
            "window.selectedText || ''",
            self._on_selected_text_result
        )
    
    def _on_current_page_result(self, page):
        """当前页面结果"""
        try:
            new_page = int(page) if page else 1
            if new_page != self.current_page:
                self.current_page = new_page
                self.page_changed.emit(self.current_page - 1)  # 转换为0基索引
        except (ValueError, TypeError):
            pass
    
    def _on_total_pages_result(self, total):
        """总页数结果"""
        try:
            self.total_pages = int(total) if total else 1
        except (ValueError, TypeError):
            pass
    
    def _on_selected_text_result(self, text):
        """选中文本结果"""
        if text and text.strip():
            self.text_selected.emit(text.strip())
            # 清除JavaScript中的选中文本标记
            self.page().runJavaScript("window.selectedText = '';")
    
    def go_to_page(self, page_num):
        """跳转到指定页面"""
        # 注入JavaScript来跳转页面
        js_code = f"""
        (function() {{
            try {{
                // 尝试Chrome PDF插件方式
                const plugin = document.querySelector('embed[type="application/pdf"]');
                if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {{
                    plugin.contentWindow.PDFViewerApplication.page = {page_num + 1};
                    return true;
                }}
                
                // 尝试PDF.js方式
                const pageInput = document.querySelector('#pageNumber');
                if (pageInput) {{
                    pageInput.value = {page_num + 1};
                    pageInput.dispatchEvent(new Event('change'));
                    return true;
                }}
                
                return false;
            }} catch (e) {{
                console.log('Go to page error:', e);
                return false;
            }}
        }})();
        """
        
        self.page().runJavaScript(js_code)
    
    def zoom_in(self):
        """放大"""
        js_code = """
        (function() {
            try {
                const plugin = document.querySelector('embed[type="application/pdf"]');
                if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {
                    plugin.contentWindow.PDFViewerApplication.zoomIn();
                    return true;
                }
                return false;
            } catch (e) {
                console.log('Zoom in error:', e);
                return false;
            }
        })();
        """
        self.page().runJavaScript(js_code)
    
    def zoom_out(self):
        """缩小"""
        js_code = """
        (function() {
            try {
                const plugin = document.querySelector('embed[type="application/pdf"]');
                if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {
                    plugin.contentWindow.PDFViewerApplication.zoomOut();
                    return true;
                }
                return false;
            } catch (e) {
                console.log('Zoom out error:', e);
                return false;
            }
        })();
        """
        self.page().runJavaScript(js_code)
    
    def fit_width(self):
        """适应宽度"""
        js_code = """
        (function() {
            try {
                const plugin = document.querySelector('embed[type="application/pdf"]');
                if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {
                    plugin.contentWindow.PDFViewerApplication.pdfViewer.currentScaleValue = 'page-width';
                    return true;
                }
                return false;
            } catch (e) {
                console.log('Fit width error:', e);
                return false;
            }
        })();
        """
        self.page().runJavaScript(js_code)
    
    def fit_page(self):
        """适应页面"""
        js_code = """
        (function() {
            try {
                const plugin = document.querySelector('embed[type="application/pdf"]');
                if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {
                    plugin.contentWindow.PDFViewerApplication.pdfViewer.currentScaleValue = 'page-fit';
                    return true;
                }
                return false;
            } catch (e) {
                console.log('Fit page error:', e);
                return false;
            }
        })();
        """
        self.page().runJavaScript(js_code)
    
    def _set_fit_width(self):
        """设置PDF适应宽度"""
        js_code = """
        (function() {
            try {
                const plugin = document.querySelector('embed[type="application/pdf"]');
                if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {
                    const app = plugin.contentWindow.PDFViewerApplication;
                    
                    // 只设置适应宽度，不做其他操作
                    if (app.pdfViewer) {
                        app.pdfViewer.currentScaleValue = 'page-width';
                        console.log('PDF已设置为适应宽度');
                    }
                }
            } catch (e) {
                console.log('设置PDF适应宽度时出错:', e);
            }
        })();
        """
        self.page().runJavaScript(js_code)
    
    def verticalScrollBar(self):
        """返回模拟的垂直滚动条以兼容旧API"""
        return self._mock_vertical_scrollbar
    
    def horizontalScrollBar(self):
        """返回模拟的水平滚动条以兼容旧API"""
        return self._mock_horizontal_scrollbar
    
    def cleanup(self):
        """清理资源"""
        self.page_timer.stop()
        self.pdf_path = None


class PDFWidget(QWidget):
    """PDF显示组件包装器"""
    text_selected = pyqtSignal(str)
    page_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = None
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建PDF视图
        self.pdf_view = WebPDFView()
        
        # 占位符
        self.placeholder = QLabel(
            "请打开PDF文件"
        )
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("""
            QLabel { 
                background: #f8f9fa; 
                padding: 50px; 
                font-size: 16px; 
                color: #666;
                border: 2px dashed #ddd;
                border-radius: 10px;
                margin: 20px;
            }
        """)
        
        # 默认显示占位符
        layout.addWidget(self.placeholder)
        
        # 连接信号
        self.pdf_view.text_selected.connect(self.text_selected.emit)
        self.pdf_view.page_changed.connect(self.page_changed.emit)
        
        # 为了兼容旧代码，添加scroll_area属性指向pdf_view
        self.scroll_area = self.pdf_view
        
    def load_pdf(self, file_path):
        """加载PDF文件"""
        try:
            success = self.pdf_view.load_pdf(file_path)
            
            if success:
                # 切换到PDF视图
                layout = self.layout()
                layout.removeWidget(self.placeholder)
                self.placeholder.hide()
                layout.addWidget(self.pdf_view)
                
                # 保存文档引用以兼容旧代码
                try:
                    import fitz
                    self.doc = fitz.open(file_path)
                except Exception as e:
                    print(f"无法创建fitz文档引用: {e}")
                    self.doc = None
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"加载PDF失败: {e}")
            return False
    
    def go_to_page(self, page_num):
        """跳转到指定页面"""
        self.pdf_view.go_to_page(page_num)
    
    def zoom_in(self):
        """放大"""
        self.pdf_view.zoom_in()
    
    def zoom_out(self):
        """缩小"""
        self.pdf_view.zoom_out()
    
    def fit_width(self):
        """适应宽度"""
        self.pdf_view.fit_width()
    
    def fit_page(self):
        """适应页面"""
        self.pdf_view.fit_page()
            
    def cleanup(self):
        """清理资源"""
        if hasattr(self, 'pdf_view'):
            self.pdf_view.cleanup()
            
        if self.doc:
            self.doc.close()
            self.doc = None
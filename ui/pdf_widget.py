"""PDF显示组件 - 基于Web渲染"""

import os

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class WebPDFView(QWebEngineView):
    """基于Web的PDF视图"""
    page_changed = pyqtSignal(int)
    text_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # 配置WebEngine设置
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        # 添加更多设置来解决渲染问题
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        
        # 设置样式，包含强制隐藏PDF工具栏的CSS
        self.setStyleSheet("""
            QWebEngineView {
                border: none;
                background-color: #ffffff;
            }
        """)
        
        self.pdf_path = None
        self.current_page = 0
        self.total_pages = 0
        self._is_preloaded = False
        
        # 监听页面加载完成
        self.loadFinished.connect(self._on_load_finished)
        
        # 页面变化检测定时器
        self.page_timer = QTimer()
        self.page_timer.timeout.connect(self._check_current_page)
        self.page_timer.setInterval(1000)  # 减少检查频率到每1000ms检查一次
        
        # 启动预加载
        self._preload_webengine()
        
    def _preload_webengine(self):
        """预加载WebEngine环境"""
        # 创建一个空的HTML页面来预热WebEngine
        preload_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>PDF Viewer Ready</title>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    background: #f5f5f5;
                    font-family: Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                }
                .ready-message {
                    color: #666;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="ready-message">PDF查看器已就绪...</div>
            <script>
                // 预加载PDF相关的JavaScript环境
                window.pdfCurrentPage = 1;
                window.pdfTotalPages = 1;
                window.selectedText = '';
                
                // 定义PDF相关函数，提前准备JavaScript环境
                window.preparePDFEnvironment = function() {
                    console.log('PDF environment prepared');
                };
                
                // 调用准备函数
                window.preparePDFEnvironment();
            </script>
        </body>
        </html>
        """
        
        self.setHtml(preload_html)
        print("WebEngine预加载已启动...")
        
    
    def load_pdf(self, file_path):
        """加载PDF文件"""
        try:
            if not os.path.exists(file_path):
                return False
            
            # 如果WebEngine还未预加载完成，等待预加载
            if not self._is_preloaded:
                print("等待WebEngine预加载完成...")
                # 使用QTimer等待预加载完成
                def check_preload():
                    if self._is_preloaded:
                        self._do_load_pdf(file_path)
                    else:
                        QTimer.singleShot(100, check_preload)
                QTimer.singleShot(100, check_preload)
                return True
            else:
                return self._do_load_pdf(file_path)
                
        except Exception as e:
            print(f"加载PDF失败: {e}")
            return False
    
    def _do_load_pdf(self, file_path):
        """执行实际的PDF加载"""
        try:
            self.pdf_path = file_path
            
            # 将文件路径转换为file:// URL
            file_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            
            # 由于WebEngine已经预加载，这里的加载会更快
            self.load(file_url)
            
            return True
            
        except Exception as e:
            print(f"执行PDF加载失败: {e}")
            return False
    
    def _on_load_finished(self, success):
        """页面加载完成"""
        if success:
            if not self._is_preloaded and not self.pdf_path:
                # 预加载完成
                self._is_preloaded = True
                print("WebEngine预加载完成，组件已就绪")
            elif self.pdf_path:
                # PDF加载完成
                print(f"PDF加载成功: {self.pdf_path}")
                
                # 强制重绘和激活WebEngine
                self.update()
                self.repaint()
                self.activateWindow()
                
                # 启动页面检测
                self.page_timer.start()
                
                # 注入JavaScript来获取PDF信息和监听页面变化
                self._inject_pdf_scripts()
                
                # 减少延迟时间，让PDF更快适应宽度
                QTimer.singleShot(300, self._set_fit_width)
                
                # 再次强制重绘，确保PDF正确显示
                QTimer.singleShot(500, self._force_refresh)
        else:
            print("页面加载失败")
    
    def _inject_pdf_scripts(self):
        """注入JavaScript脚本"""
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

                            // 自动隐藏侧边栏（PDF.js）
                            if (app.pdfSidebar && app.pdfSidebar.isOpen) {
                                app.pdfSidebar.close();
                            }

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

            // 初始尝试隐藏侧边栏
            setTimeout(() => {
                try {
                    const plugin = document.querySelector('embed[type="application/pdf"]');
                    if (plugin && plugin.contentWindow && plugin.contentWindow.PDFViewerApplication) {
                        const app = plugin.contentWindow.PDFViewerApplication;
                        if (app.pdfSidebar && app.pdfSidebar.isOpen) {
                            app.pdfSidebar.close();
                        }
                    }
                } catch (e) {}
            }, 500);

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
                    
                    // 确保PDF已完全加载后再设置缩放
                    if (app.pdfDocument && app.pdfViewer) {
                        // 平滑设置适应宽度，避免突然的视觉变化
                        app.pdfViewer.currentScaleValue = 'page-width';
                        console.log('PDF已平滑设置为适应宽度');
                    } else {
                        // 如果PDF还未完全加载，再等一会儿
                        setTimeout(function() {
                            if (app.pdfDocument && app.pdfViewer) {
                                app.pdfViewer.currentScaleValue = 'page-width';
                                console.log('PDF延迟设置为适应宽度');
                            }
                        }, 200);
                    }
                }
            } catch (e) {
                console.log('设置PDF适应宽度时出错:', e);
            }
        })();
        """
        self.page().runJavaScript(js_code)
    
    def _force_refresh(self):
        """强制刷新WebEngine显示"""
        try:
            self.update()
            self.repaint()
            # 确保WebEngine获得焦点
            self.setFocus()
            # 发送一个空的JavaScript来触发重绘
            self.page().runJavaScript("void(0);")
        except Exception as e:
            print(f"强制刷新失败: {e}")
    
    def showEvent(self, event):
        """显示事件处理"""
        super().showEvent(event)
        # 当WebEngine显示时，触发重绘以解决灰色显示问题
        if self.pdf_path:
            QTimer.singleShot(50, self._force_refresh)
    
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
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用QStackedWidget来避免布局重排
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # 创建占位符页面
        self.placeholder = QLabel("请打开PDF文件")
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
        
        # 创建PDF视图页面
        self.pdf_view = WebPDFView()
        
        # 添加到堆叠组件
        self.stacked_widget.addWidget(self.placeholder)  # 索引0: 占位符
        self.stacked_widget.addWidget(self.pdf_view)      # 索引1: PDF视图
        
        # 默认显示占位符
        self.stacked_widget.setCurrentIndex(0)
        
        # 连接信号
        self.pdf_view.text_selected.connect(self.text_selected.emit)
        self.pdf_view.page_changed.connect(self.page_changed.emit)
        
    def load_pdf(self, file_path):
        """加载PDF文件"""
        try:
            success = self.pdf_view.load_pdf(file_path)
            
            if success:
                # 平滑切换到PDF视图，没有布局重排
                self.stacked_widget.setCurrentIndex(1)
                
                # 强制刷新PDF视图
                QTimer.singleShot(100, self._refresh_pdf_view)
                
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
    
    def _refresh_pdf_view(self):
        """刷新PDF视图显示"""
        try:
            # 强制更新PDF视图
            self.pdf_view.update()
            self.pdf_view.repaint()
            
            # 确保PDF视图获得焦点
            self.pdf_view.setFocus()
            
            # 触发窗口重绘
            self.update()
            self.repaint()
            
            print("PDF视图已刷新")
        except Exception as e:
            print(f"刷新PDF视图失败: {e}")
    
    def _refresh_pdf_view(self):
        """刷新PDF视图显示"""
        try:
            # 强制更新PDF视图
            self.pdf_view.update()
            self.pdf_view.repaint()
            
            # 确保PDF视图获得焦点
            self.pdf_view.setFocus()
            
            # 触发整个窗口重绘
            self.update()
            self.repaint()
            
            print("PDF视图已刷新")
        except Exception as e:
            print(f"刷新PDF视图失败: {e}")
    
    def reset_to_placeholder(self):
        """重置到占位符状态"""
        self.stacked_widget.setCurrentIndex(0)
        if self.doc:
            self.doc.close()
            self.doc = None
    
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
    
    def showEvent(self, event):
        """显示事件处理"""
        super().showEvent(event)
        # 当PDFWidget显示时，确保PDF视图也能正确显示
        if self.stacked_widget.currentIndex() == 1:  # PDF视图激活
            QTimer.singleShot(100, self._refresh_pdf_view)
            
    def cleanup(self):
        """清理资源"""
        if hasattr(self, 'pdf_view'):
            self.pdf_view.cleanup()
            
        if self.doc:
            self.doc.close()
            self.doc = None
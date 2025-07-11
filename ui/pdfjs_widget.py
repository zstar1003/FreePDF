import os

from PyQt6.QtCore import QObject, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QHBoxLayout, QWidget

# This JS code will be injected into each viewer instance.
# It sets up the communication bridge and defines functions that Python can call.
PDFJS_WIDGET_JS = """
var isSyncingScroll = false;
var isZooming = false; // Flag to ignore scroll events triggered by zooming

// === Functions called by Python ===

// Called by Python to command a scroll change.
function setScroll(scrollTop, scrollLeft) {
    const container = document.getElementById('viewerContainer');
    if (container) {
        isSyncingScroll = true;
        container.scrollTop = scrollTop;
        container.scrollLeft = scrollLeft;
        setTimeout(() => { isSyncingScroll = false; }, 100);
    }
}

function zoomIn() {
    const { PDFViewerApplication } = window;
    if (PDFViewerApplication) {
        PDFViewerApplication.zoomIn();
    }
}

function zoomOut() {
    const { PDFViewerApplication } = window;
    if (PDFViewerApplication) {
        PDFViewerApplication.zoomOut();
    }
}

// === Setup function ===

// Sets up the QWebChannel bridge and attaches event listeners.
function setupPdfJsWidget(viewName) {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        // Make the Python 'bridge' object available globally in JS.
        window.bridge = channel.objects.bridge;

        const container = document.getElementById('viewerContainer');
        if (container) {
            // Listen for user-initiated scrolls and notify Python.
            container.addEventListener('scroll', () => {
                if (isSyncingScroll || isZooming) {
                    return; // Ignore scroll events during programmatic sync or zoom.
                }
                // Notify Python via the bridge.
                window.bridge.onScroll(viewName, container.scrollTop, container.scrollLeft);
            });
        } else {
             // Retry if the container isn't ready.
             setTimeout(() => setupPdfJsWidget(viewName), 100);
        }
    });
}
"""

class Bridge(QObject):
    """A bridge to pass signals from JavaScript to Python."""
    # Signal emitted when a scroll event happens in the JS viewer.
    # Args: view_name (str), scrollTop (int), scrollLeft (int)
    scrollChanged = pyqtSignal(str, int, int)

    @pyqtSlot(str, int, int)
    def onScroll(self, viewName, scrollTop, scrollLeft):
        self.scrollChanged.emit(viewName, scrollTop, scrollLeft)

class WebEnginePage(QWebEnginePage):
    """Custom page to log JS console messages."""
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if level in [QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel, QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel]:
             print(f"JS Console ({sourceID}:{lineNumber}): {message}")

class PdfJsWidget(QWidget):
    """PDF.js Viewer 封装控件，可指定界面语言。"""

    # Expose the scrollChanged signal from the bridge
    scrollChanged = pyqtSignal(str, int, int)

    def __init__(self, name: str, profile: QWebEngineProfile, locale: str = "zh-cn", parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        self._name = name
        # 保存语言代码，可在运行时修改
        self._locale = locale.lower() if locale else None

        # Use the shared profile passed from the main window
        self.profile = profile

        # The JS bridge for Python-JS communication
        self.bridge = Bridge(self)
        self.bridge.scrollChanged.connect(self.scrollChanged) # Pass signal up

        # Create and configure the web view
        self.view = QWebEngineView()
        
        # --- 优化渲染，尝试解决拖拽闪烁问题 ---
        # 1. 设置背景色为白色，避免闪烁时出现黑色背景
        self.view.page().setBackgroundColor(Qt.GlobalColor.white)
        
        # 2. 尝试禁用2D画布的GPU加速，这有时能解决特定驱动下的渲染问题
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)
        
        self.view.setAcceptDrops(False)  # Disable drop events on the view
        page = WebEnginePage(self.profile, self.view)
        self.view.setPage(page)
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.view)

        # Setup the web channel to expose the 'bridge' object to JavaScript
        channel = QWebChannel(page)
        page.setWebChannel(channel)
        channel.registerObject("bridge", self.bridge)

        # When the page finishes loading, inject our script
        page.loadFinished.connect(self.on_load_finished)

    def set_locale(self, locale: str | None):
        """设置界面语言（例如 'en-us', 'zh-cn', 'zh-tw' 等）。设置为 None 则使用浏览器默认。"""
        self._locale = locale.lower() if locale else None

    def load_pdf(self, pdf_path):
        """Loads a PDF file into the view."""
        if pdf_path == "about:blank":
             self.view.setUrl(QUrl(pdf_path))
             return

        viewer_path = os.path.abspath('pdfjs/web/viewer.html')
        viewer_url = QUrl.fromLocalFile(viewer_path)
        pdf_url = QUrl.fromLocalFile(os.path.abspath(pdf_path)).toString()

        base_url = f"{viewer_url.toString()}?file={pdf_url}"
        if self._locale:
            full_url = QUrl(f"{base_url}#locale={self._locale}")
        else:
            full_url = QUrl(base_url)
        self.view.load(full_url)

    def on_load_finished(self, ok):
        """Injects JS after the page has loaded."""
        if ok:
            # Inject CSS to hide unwanted toolbar buttons
            css_to_hide_buttons = """
                var style = document.createElement('style');
                style.innerHTML = `
                    /* Hide Open File, Print, and Add Image buttons */
                    #openFile,
                    #secondaryOpenFile,
                    #printButton,
                    #secondaryPrint,
                    #viewBookmark,
                    #viewBookmarkSeparator,
                    #secondaryDownload,
                    #editorStamp, /* Main stamp button on the toolbar */
                    #editorStampAddImage {
                        display: none !important;
                    }
                `;
                document.head.appendChild(style);
            """

            # 把保存(下载)按钮移动到绘图按钮之后，始终可见
            button_move_js = """
                (function() {
                    const dl = document.getElementById('downloadButton');
                    if (!dl) return;
                    // 先移除原位置（hiddenMediumView 容器）
                    dl.parentElement.removeChild(dl);

                    // 找到绘图按钮容器 (#editorInk) 并插入其后
                    const inkContainer = document.getElementById('editorInk');
                    if (inkContainer && inkContainer.parentElement) {
                        inkContainer.parentElement.insertAdjacentElement('afterend', dl);
                    } else {
                        // 退而求其次，放到右侧工具栏分隔符前
                        const rightGroup = document.getElementById('toolbarViewerRight');
                        rightGroup.insertBefore(dl, document.getElementById('secondaryToolbarToggle'));
                    }
                })();
            """

            loader_script = f"""
                {css_to_hide_buttons}
                {PDFJS_WIDGET_JS}
                var script = document.createElement('script');
                script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                script.onload = function() {{
                    setupPdfJsWidget('{self._name}');
                }};
                document.head.appendChild(script);

                // 调整下载按钮位置
                {button_move_js}
            """
            self.view.page().runJavaScript(loader_script)

    def set_scroll_position(self, top: int, left: int):
        """Public method to command a scroll change from outside."""
        # Wrap in a try-catch to gracefully handle cases where the JS function
        # might not be defined yet (e.g., during initial page load).
        js_code = f"""
            try {{
                setScroll({top}, {left});
            }} catch (e) {{
                // Function doesn't exist yet, do nothing.
                // console.error("setScroll failed, likely because view is not ready:", e);
            }}
        """
        self.view.page().runJavaScript(js_code)
    
    def zoom_in(self):
        self.view.page().runJavaScript("isZooming = true;")
        self.view.page().runJavaScript("zoomIn();")
        self.view.page().runJavaScript("setTimeout(() => { isZooming = false; }, 150);")

    def zoom_out(self):
        self.view.page().runJavaScript("isZooming = true;")
        self.view.page().runJavaScript("zoomOut();")
        self.view.page().runJavaScript("setTimeout(() => { isZooming = false; }, 150);") 

    def hide_loading(self):
        """Hide loading indicator - placeholder method for compatibility"""
        pass

    def cleanup(self):
        """Clean up resources to prevent memory leaks and shutdown warnings."""
        if self.view:
            page = self.view.page()
            if page:
                try:
                    # Disconnect all signals from the page to break reference cycles.
                    page.loadFinished.disconnect()
                except TypeError:
                    # This happens if it was already disconnected or never connected.
                    pass
                
                # The page is parented to the view, which is parented to the widget.
                # Qt's memory management should handle it, but we call deleteLater
                # to be explicit and help break cycles.
                page.deleteLater()

            self.view.setPage(None)
            self.view.deleteLater()
            self.view = None 
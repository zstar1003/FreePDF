import html
import json
import logging
import os
import time
import uuid
from urllib.parse import quote

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, QUrlQuery, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from utils.diagnostics import get_logger
from utils.pdfjs_diagnostics import PDFJS_DIAGNOSTICS_JS, PDFJS_SNAPSHOT_JS
from utils.pdfjs_paths import resolve_viewer


def build_viewer_url(viewer_path, pdf_url, locale=None):
    """Encode a file URL as a query value, preserving its own percent escapes."""
    url = QUrl.fromLocalFile(str(viewer_path))
    query = QUrlQuery()
    query.addQueryItem("file", quote(pdf_url.toString(QUrl.ComponentFormattingOption.FullyEncoded), safe=""))
    url.setQuery(query)
    if locale:
        url.setFragment("locale=" + locale)
    return url

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
    diagnosticEvent = pyqtSignal(object)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if message.startswith("FREEPDF_DIAGNOSTIC:"):
            try:
                self.diagnosticEvent.emit(json.loads(message.split(":", 1)[1]))
            except ValueError:
                get_logger("preview").warning("Malformed diagnostic message: %s", message)
            return
        severity = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: logging.DEBUG,
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: logging.WARNING,
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: logging.ERROR,
        }.get(level, logging.INFO)
        get_logger("javascript").log(severity, "view=%s load=%s %s:%s %s",
                                     self.property("view_name"), self.property("load_id"), sourceID, lineNumber, message)

class PdfJsWidget(QWidget):
    """PDF.js Viewer 封装控件，可指定界面语言。"""

    # Expose the scrollChanged signal from the bridge
    scrollChanged = pyqtSignal(str, int, int)
    previewFailed = pyqtSignal(str, str)
    previewReady = pyqtSignal(str)

    def __init__(self, name: str, profile: QWebEngineProfile, locale: str = "zh-cn", parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        self._name = name
        self._load_id = None
        self._started_at = 0
        self._state = {}
        self._awaiting_pdf = False
        self._failure_reported = False
        self._logger = get_logger("preview")
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.setInterval(30000)
        self._watchdog.timeout.connect(self._check_preview)
        # 保存语言代码，可在运行时修改
        self._locale = locale.lower() if locale else None

        # Use the shared profile passed from the main window
        self.profile = profile

        # The JS bridge for Python-JS communication
        self.bridge = Bridge(self)
        self.bridge.scrollChanged.connect(self.scrollChanged) # Pass signal up

        # Create and configure the web view
        self.view = QWebEngineView()
        
        page = WebEnginePage(self.profile, self.view)
        page.setProperty("view_name", name)
        self.view.setPage(page)
        # Configure the actual custom page; settings on the old default page are discarded.
        # 1. 设置背景色为白色，避免闪烁时出现黑色背景
        self.view.page().setBackgroundColor(Qt.GlobalColor.white)
        
        # 2. 尝试禁用2D画布的GPU加速，这有时能解决特定驱动下的渲染问题
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)
        
        # 3. 启用本地文件访问权限（解决打包后无法访问PDF文件的问题）
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        
        self.view.setAcceptDrops(False)  # Disable drop events on the view
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.view)

        # Setup the web channel to expose the 'bridge' object to JavaScript
        channel = QWebChannel(page)
        page.setWebChannel(channel)
        channel.registerObject("bridge", self.bridge)

        script = QWebEngineScript()
        script.setName("FreePDF diagnostics")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        script.setSourceCode(PDFJS_DIAGNOSTICS_JS)
        page.scripts().insert(script)
        self._diagnostic_script = script
        page.diagnosticEvent.connect(self._on_diagnostic_event)
        page.loadStarted.connect(lambda: self._log("navigation_started"))
        page.loadingChanged.connect(self._on_loading_changed)
        page.renderProcessTerminated.connect(self._on_renderer_terminated)

        # When the page finishes loading, inject our script
        page.loadFinished.connect(self.on_load_finished)

    def set_locale(self, locale: str | None):
        """设置界面语言（例如 'en-us', 'zh-cn', 'zh-tw' 等）。设置为 None 则使用浏览器默认。"""
        self._locale = locale.lower() if locale else None

    def load_pdf(self, pdf_path):
        """Loads a PDF file into the view."""
        self._watchdog.stop()
        self._load_id = uuid.uuid4().hex[:10]
        self._started_at = time.monotonic()
        self._awaiting_pdf = pdf_path != "about:blank"
        self._failure_reported = False
        self._state = {"view": self._name, "load_id": self._load_id, "pdf_path": str(pdf_path),
                       "stage": "requested", "first_page_rendered": False}
        self.view.page().setProperty("load_id", self._load_id)
        scripts = self.view.page().scripts()
        scripts.remove(self._diagnostic_script)
        source = PDFJS_DIAGNOSTICS_JS.replace("{event, ...details}",
                                             "{event, load_id: " + json.dumps(self._load_id) + ", ...details}")
        self._diagnostic_script.setSourceCode(source)
        scripts.insert(self._diagnostic_script)
        if pdf_path == "about:blank":
             self.view.setUrl(QUrl(pdf_path))
             return

        pdf_file_path = os.path.abspath(pdf_path)
        try:
            with open(pdf_file_path, "rb") as source:
                header = source.read(8)
            self._log("file_access", path=pdf_file_path, size=os.path.getsize(pdf_file_path),
                      pdf_header=header.startswith(b"%PDF-"))
            viewer_path, checks = resolve_viewer()
            self._log("resource_check", candidates=checks)
        except OSError:
            self._logger.exception("view=%s load=%s PDF/resource access failed", self._name, self._load_id)
            self._report_failure("无法读取 PDF 或缺少预览资源，请在引擎配置中导出日志。", show_in_view=True)
            return
        viewer_url = build_viewer_url(viewer_path, QUrl.fromLocalFile(pdf_file_path), self._locale)
        self._state["viewer_url"] = viewer_url.toString(QUrl.ComponentFormattingOption.FullyEncoded)
        self._log("load_requested", url=self._state["viewer_url"],
                  accelerated_canvas=self.view.settings().testAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled))
        self._watchdog.start()
        self.view.load(viewer_url)

    def _log(self, event, **details):
        self._logger.info("view=%s load=%s elapsed=%.3f event=%s details=%s", self._name, self._load_id,
                          time.monotonic() - self._started_at if self._started_at else 0,
                          event, json.dumps(details, ensure_ascii=False))

    def diagnostic_state(self):
        return dict(self._state, visible=self.isVisible(), width=self.width(), height=self.height())

    def _on_loading_changed(self, info):
        self._log("navigation_status", status=info.status().name, error_code=info.errorCode(),
                  error_domain=info.errorDomain().name, error=info.errorString(), url=info.url().toString())
        if (self._awaiting_pdf and info.status().name == "LoadFailedStatus"
                and info.url().toString(QUrl.ComponentFormattingOption.FullyEncoded) == self._state.get("viewer_url")):
            self._report_failure("预览页面加载失败，请在引擎配置中导出日志。")

    def _on_diagnostic_event(self, payload):
        if not self._awaiting_pdf or payload.get("load_id") != self._load_id:
            return
        event = payload.get("event", "unknown")
        self._state["stage"] = event
        self._log(event, **{key: value for key, value in payload.items() if key != "event"})
        if event == "document_loaded":
            self._state["pages"] = payload.get("pages")
        if event == "first_page_rendered":
            self._state["first_page_rendered"] = True
            self._state.pop("failure", None)
            self._failure_reported = False
            self._watchdog.stop()
            self.previewReady.emit(self._name)
            load_id = self._load_id

            def snapshot_received(snapshot):
                if load_id == self._load_id and self._awaiting_pdf:
                    self._state["snapshot"] = snapshot
                    self._log("render_snapshot", snapshot=snapshot)

            self.view.page().runJavaScript(PDFJS_SNAPSHOT_JS, snapshot_received)
        elif event in ("document_error", "page_render_error", "javascript_error", "unhandled_rejection"):
            self._state["last_error"] = payload.get("message")
            # Record JS errors immediately; the watchdog determines whether preview is actually stalled.
            if event in ("document_error", "page_render_error"):
                self._report_failure("PDF 预览失败，请在引擎配置中导出日志。")

    def _report_failure(self, message, show_in_view=False):
        self._watchdog.stop()
        self._state["failure"] = message
        if show_in_view:
            self._awaiting_pdf = False
            self.view.setHtml("<p style='padding:24px;color:#a33'>" + html.escape(message) + "</p>")
        if not self._failure_reported:
            self._failure_reported = True
            self._logger.error("view=%s load=%s %s", self._name, self._load_id, message)
            self.previewFailed.emit(self._name, message)

    def _on_renderer_terminated(self, status, exit_code):
        self._log("renderer_terminated", status=status.name, exit_code=exit_code)
        if self._awaiting_pdf:
            self._report_failure("预览进程已退出，请导出日志；可尝试启用软件渲染后重启。", show_in_view=True)

    def _check_preview(self):
        load_id = self._load_id
        self._log("preview_deadline", state=self.diagnostic_state())
        responded = [False]

        def received(snapshot):
            responded[0] = True
            if load_id != self._load_id or not self._awaiting_pdf:
                return
            self._state["snapshot"] = snapshot
            self._log("preview_watchdog", state=self.diagnostic_state())
            if not self._state.get("first_page_rendered"):
                if self.isVisible():
                    self._report_failure("PDF 预览长时间未完成，请在引擎配置中导出日志。")
                else:
                    self._watchdog.start()  # A hidden view may defer rendering until it is shown.

        self.view.page().runJavaScript(PDFJS_SNAPSHOT_JS, received)

        def no_response():
            if not responded[0] and load_id == self._load_id and self._awaiting_pdf:
                self._log("javascript_unresponsive")
                self._report_failure("预览页面无响应，请在引擎配置中导出日志。")

        QTimer.singleShot(5000, no_response)

    def show_message(self, message):
        """A translation placeholder is not a pending PDF preview."""
        self._awaiting_pdf = False
        self._watchdog.stop()
        self._state = {"view": self._name, "stage": "message", "message": message}
        self.view.setHtml("<div style='display:flex;justify-content:center;align-items:center;"
                          "height:100%;font-size:16px;color:grey;'>" + html.escape(message) + "</div>")

    def on_load_finished(self, ok):
        """Injects JS after the page has loaded."""
        self._log("html_load_finished", ok=ok)
        # A false result may belong to a previous navigation that a new import
        # cancelled. loadingChanged supplies the URL needed to identify failures.
        if ok and self._awaiting_pdf:
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
        self._awaiting_pdf = False
        self._watchdog.stop()
        if self.view:
            page = self.view.page()
            if page:
                try:
                    # Disconnect all signals from the page to break reference cycles.
                    page.loadFinished.disconnect()
                except TypeError:
                    # This happens if it was already disconnected or never connected.
                    pass
                
            # The custom page is parented to the view. Deleting the view destroys
            # it; setting a null page first can create an unwanted default page.
            self.view.close()
            self.view.deleteLater()
            self.view = None

import os

from PyQt6.QtCore import QEvent, QObject, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QWidget

# JavaScript for synchronization
SYNC_JS = """
var isSyncingScroll = false;
var isZooming = false; // Flag to ignore scroll events triggered by zooming

// This function will be called by Python to update the scroll position
function setScroll(scrollTop, scrollLeft) {
    const container = document.getElementById('viewerContainer');
    if (container) {
        isSyncingScroll = true;
        container.scrollTop = scrollTop;
        container.scrollLeft = scrollLeft;
        // A final reset in case the programmatic scroll doesn't trigger an event
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

// This function sets up all the event listeners
function setupSync(viewName) {
    // QWebChannel is available globally after being set in Python
    new QWebChannel(qt.webChannelTransport, function(channel) {
        window.bridge = channel.objects.bridge;

        const { PDFViewerApplication } = window;
        if (!PDFViewerApplication || !PDFViewerApplication.eventBus) {
             console.error("PDFViewerApplication or its eventBus is not available. Retrying...");
             setTimeout(() => setupSync(viewName), 100);
             return;
        }

        // --- Scroll Sync Setup ---
        const container = document.getElementById('viewerContainer');
        if (container) {
            container.addEventListener('scroll', () => {
                if (isSyncingScroll || isZooming) { // <-- Check the isZooming flag here
                    isSyncingScroll = false; // Reset flag and ignore this event
                    return;
                }
                // User-initiated scroll, send to Python
                window.bridge.onScroll(viewName, container.scrollTop, container.scrollLeft);
            });
            console.log("Scroll sync handler attached for " + viewName);
        } else {
             console.error("viewerContainer not found for scroll sync. Retrying...");
             setTimeout(() => setupSync(viewName), 100); // Retry if container isn't there yet
             return;
        }
    });
}
"""

class Bridge(QObject):
    """
    A bridge object to communicate between Python and JavaScript.
    An instance of this class is exposed to the JavaScript world.
    """
    # Signal to notify the main window of a scroll event
    # Arguments: source_view_name (str), scrollTop (int), scrollLeft (int)
    scrollChanged = pyqtSignal(str, int, int)

    @pyqtSlot(str, int, int)
    def onScroll(self, viewName, scrollTop, scrollLeft):
        """This slot is called from JavaScript when a scroll event occurs."""
        self.scrollChanged.emit(viewName, scrollTop, scrollLeft)

class WebEnginePage(QWebEnginePage):
    """Custom WebEnginePage to handle and print console messages for debugging."""
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # Optionally, you can filter which messages to show, e.g., only show errors.
        if level in [QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel, QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel]:
             print(f"JS Console ({level}, {sourceID}:{lineNumber}): {message}")

class PdfDualViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # A shared profile for both views can improve resource usage
        # We make it persistent to enable caching
        self.profile = QWebEngineProfile("pdf_viewer_profile", self)
        self.profile.setCachePath(os.path.join("cache", "web_engine_cache"))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)

        # The JS bridge for Python-JS communication
        self.bridge = Bridge(self)
        self.bridge.scrollChanged.connect(self.sync_scroll)

        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Create two web views
        self.view1 = self.create_web_view('view1')
        self.view2 = self.create_web_view('view2')

        layout.addWidget(self.view1)
        layout.addWidget(self.view2)

        # Install a global event filter.
        QApplication.instance().installEventFilter(self)

    def load_pdf(self, pdf_path):
        """Loads a PDF file into both views."""
        viewer_path = os.path.abspath('pdfjs/web/viewer.html')
        viewer_url = QUrl.fromLocalFile(viewer_path)
        
        # QWebEngineView requires a file URL in a specific format
        pdf_url = QUrl.fromLocalFile(os.path.abspath(pdf_path)).toString()
        
        full_url = QUrl(f"{viewer_url.toString()}?file={pdf_url}")
        
        self.view1.load(full_url)
        self.view2.load(full_url)

    def create_web_view(self, name):
        """Creates and configures a QWebEngineView instance."""
        view = QWebEngineView()
        view.setObjectName(name)
        page = WebEnginePage(self.profile, view)
        view.setPage(page)

        # Setup the web channel to expose the 'bridge' object to JavaScript
        channel = QWebChannel(page)
        page.setWebChannel(channel)
        channel.registerObject("bridge", self.bridge)

        # When the page finishes loading, inject our synchronization script
        page.loadFinished.connect(lambda ok, v=view, n=name: self.on_load_finished(ok, v, n))
        return view

    def on_load_finished(self, ok, view, name):
        """Called after a web view has finished loading its content."""
        if ok:
            # This script does three things:
            # 1. Defines our synchronization functions (from SYNC_JS).
            # 2. Dynamically loads the required 'qwebchannel.js' library.
            # 3. Once 'qwebchannel.js' is loaded, it calls our setup function.
            loader_script = f"""
                // Part 1: Define our functions
                {SYNC_JS}

                // Part 2: Dynamically load qwebchannel.js
                var script = document.createElement('script');
                script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                
                // Part 3: Set the onload callback to run our setup after the script loads
                script.onload = function() {{
                    setupSync('{name}');
                }};
                script.onerror = function() {{
                    console.error("Failed to load qwebchannel.js for {name}.");
                }};
                
                document.head.appendChild(script);
            """
            view.page().runJavaScript(loader_script)

    def eventFilter(self, obj, event):
        # We are only interested in Wheel events.
        if event.type() == QEvent.Type.Wheel:
            # First, ensure the object is a QWidget before using QWidget-specific methods.
            if not isinstance(obj, QWidget):
                return super().eventFilter(obj, event)

            source_view = None
            # Check if the widget that received the event is the source view
            # or a descendant of the source view.
            if self.view1.isAncestorOf(obj) or obj == self.view1:
                source_view = self.view1
            elif self.view2.isAncestorOf(obj) or obj == self.view2:
                source_view = self.view2

            if source_view:
                # We have identified the event's origin. Now, check for the Ctrl modifier.
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    # Set a flag in JS to temporarily disable scroll sync, preventing
                    # interference from scroll events triggered as a side-effect of zooming.
                    source_view.page().runJavaScript("isZooming = true;")

                    # Handle the zoom
                    if event.angleDelta().y() > 0:
                        source_view.page().runJavaScript("zoomIn();")
                    else:
                        source_view.page().runJavaScript("zoomOut();")
                    
                    # After a short delay, reset the flag.
                    source_view.page().runJavaScript("setTimeout(() => { isZooming = false; }, 150);")

                    # Return True to stop the event from being processed further by Qt.
                    return True
        
        # For all other objects and events (including normal scrolls), 
        # let them be handled by the default implementation.
        return super().eventFilter(obj, event)

    @pyqtSlot(str, int, int)
    def sync_scroll(self, source_name, scrollTop, scrollLeft):
        """
        Receives scroll data from one view (via the bridge) and
        commands the other view to scroll to the same position.
        """
        js_code = f"setScroll({scrollTop}, {scrollLeft});"

        if source_name == 'view1':
            self.view2.page().runJavaScript(js_code)
        else: # source_name == 'view2'
            self.view1.page().runJavaScript(js_code) 
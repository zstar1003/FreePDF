"""Exercise the bundled viewer in real Qt WebEngine, without translation APIs."""

import os
import time

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-web-security --allow-file-access-from-files")

import pymupdf
import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QEventLoop
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

from ui.pdfjs_widget import PdfJsWidget
from utils.pdfjs_diagnostics import PDFJS_SNAPSHOT_JS


@pytest.fixture
def viewer(app):
    profile = QWebEngineProfile(app)
    widget = PdfJsWidget("test_view", profile)
    widget.resize(900, 700)
    widget.show()
    yield widget
    widget.cleanup()
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    profile.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def wait_for(app, predicate, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Qt viewer did not reach expected state before timeout")


def run_js(app, viewer, code):
    result = []
    viewer.view.page().runJavaScript(code, result.append)
    wait_for(app, lambda: bool(result), 10)
    return result[0]


def test_special_filename_renders_actual_pdf_pages(app, viewer, tmp_path):
    pdf_path = tmp_path / "中文 & # + %23 % report.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "FreePDF preview diagnostic test", fontsize=24)
        document.save(pdf_path)
    failures = []
    viewer.previewFailed.connect(lambda *args: failures.append(args))
    viewer.load_pdf(str(pdf_path))
    wait_for(app, lambda: viewer.diagnostic_state().get("first_page_rendered") or bool(failures))
    assert not failures, viewer.diagnostic_state()
    snapshot = run_js(app, viewer, PDFJS_SNAPSHOT_JS)
    assert snapshot["documentLoaded"] and snapshot["pages"] == 1
    assert snapshot["canvas"]["width"] > 0
    assert snapshot["diagnostics"]["firstPageRendered"]
    assert not viewer.view.settings().testAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled)
    ink = run_js(app, viewer, """(() => {
        const canvas = document.querySelector('.page canvas');
        const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
        let ink = 0;
        for (let i = 0; i < pixels.length; i += 16) {
            if (pixels[i + 3] && pixels[i] < 200 && pixels[i + 1] < 200 && pixels[i + 2] < 200) ink++;
        }
        return ink;
    })();""")
    assert ink > 0, "PDF.js emitted a render event but its canvas contains no text pixels"
    # Optional local evidence for visual review; not included in exported support logs.
    screenshot = os.environ.get("FREEPDF_TEST_SCREENSHOT")
    if screenshot:
        viewer.grab().save(screenshot)


def test_invalid_pdf_reports_document_error(app, viewer, tmp_path):
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"This is not a PDF")
    failures = []
    viewer.previewFailed.connect(lambda *args: failures.append(args))
    viewer.load_pdf(str(pdf_path))
    wait_for(app, lambda: bool(failures))
    assert viewer.diagnostic_state()["last_error"]
    assert not viewer.diagnostic_state()["first_page_rendered"]


def test_inaccessible_pdf_reports_failure_without_navigation(app, viewer, tmp_path):
    failures = []
    viewer.previewFailed.connect(lambda *args: failures.append(args))
    viewer.load_pdf(str(tmp_path / "does-not-exist.pdf"))
    assert failures
    assert "failure" in viewer.diagnostic_state()
    assert not viewer._watchdog.isActive()

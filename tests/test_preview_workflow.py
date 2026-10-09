import json
import logging
import time
import zipfile

import pymupdf
from PyQt6.QtCore import QCoreApplication, QEvent, QEventLoop
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ui.diagnostics_dialog import DiagnosticsDialog
from ui.main_window import MainWindow
from utils import diagnostics


def test_dual_preview_workflow_exports_both_views_and_preserves_errors(app, tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(diagnostics, "_handler", None)
    import sys
    import threading
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diagnostics.initialize_logging(directory=tmp_path / "logs")
    monkeypatch.setattr(MainWindow, "_update_qa_panel_status", lambda self: None)
    monkeypatch.setattr(MainWindow, "_setup_fallback_timer", lambda self: None)
    monkeypatch.setattr(MainWindow, "_is_translation_enabled", lambda self: False)
    window = MainWindow()
    window.show()
    pdf_path = tmp_path / "双视图 & # + %.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Two preview panes")
        document.save(pdf_path)
    window.load_pdf_file(str(pdf_path))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if all(view.diagnostic_state().get("first_page_rendered") for view in (window.left_pdf_widget, window.right_pdf_widget)):
            break
        time.sleep(0.01)
    assert window.left_pdf_widget.diagnostic_state().get("first_page_rendered")
    assert window.right_pdf_widget.diagnostic_state().get("first_page_rendered")
    destination = tmp_path / "dual-preview.zip"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(destination), "ZIP"))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    DiagnosticsDialog(window)._export()
    with zipfile.ZipFile(destination) as archive:
        state = json.loads(archive.read("preview_state.json"))
        assert state["left"]["first_page_rendered"] and state["right"]["first_page_rendered"]
        log = archive.read("logs/freepdf.log").decode()
        assert "PDF import requested" in log
        assert "view=left_view" in log and "view=right_view" in log
        assert "first_page_rendered" in log
    # A successful translation callback must not erase an original preview failure.
    window.on_preview_failed("left_view", "simulated original preview error")
    window.on_translation_completed(str(pdf_path))
    assert "原文预览异常" in window.status_label.text()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    handler = diagnostics._handler
    logging.getLogger("freepdf").removeHandler(handler)
    handler.close()

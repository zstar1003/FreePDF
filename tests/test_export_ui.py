import time
import pymupdf
from PyQt6.QtCore import QEventLoop
from PyQt6.QtWidgets import QFileDialog
from ui.export_dialog import ExportDialog
from ui.main_window import AboutDialog


def test_export_button_creates_wide_pdf_and_reports_inline(app,tmp_path,monkeypatch):
    original,translated,destination=[tmp_path/name for name in ('source.pdf','mono.pdf','wide.pdf')]
    for path,text in ((original,'Original'),(translated,'Translation')):
        with pymupdf.open() as doc:
            doc.new_page().insert_text((72,72),text)
            doc.save(path)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(destination),'PDF'))
    dialog=ExportDialog(str(original),str(translated))
    dialog.export_button.click()
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents,50)
        if dialog.export_button.isEnabled():break
        time.sleep(.01)
    assert '已导出' in dialog.status.text()
    assert dialog.worker.wait(1000)
    with pymupdf.open(destination) as doc:
        assert doc.page_count==1
        assert 'Original' in doc[0].get_text() and 'Translation' in doc[0].get_text()
    dialog.deleteLater()


def test_about_log_export_is_bottom_left_next_to_updates(app):
    dialog=AboutDialog();dialog.show();app.processEvents()
    export=dialog.export_logs_btn.geometry();updates=dialog.update_btn.geometry()
    assert export.x()<updates.x()
    assert export.y()==updates.y() and export.y()>dialog.height()/2
    dialog.hide();dialog.deleteLater()

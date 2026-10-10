import time
from pathlib import Path
import pymupdf
from PyQt6.QtCore import Qt, QEvent, QCoreApplication
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLabel, QPushButton
from ui.main_window import MainWindow, AboutDialog
from ui.theme import install_theme
from utils.translation_logger import get_translation_logger


def close_window(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox,'question',lambda *args,**kwargs:QMessageBox.StandardButton.Yes)
    window.close();window.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


def test_about_copy_is_centered_and_actions_share_font(app):
    install_theme(app)
    dialog=AboutDialog();dialog.show();app.processEvents()
    for label in dialog.findChildren(QLabel):
        if label.text() and label is not dialog.feedback_label:
            assert label.alignment() & Qt.AlignmentFlag.AlignHCenter
    fonts={button.font().pixelSize() for button in dialog.findChildren(QPushButton)}
    assert fonts=={15}
    dialog.close();dialog.deleteLater()


def test_click_progress_opens_live_details_without_fake_advancement(app,monkeypatch,tmp_path):
    monkeypatch.setenv('FREEPDF_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('FREEPDF_PREVIEW_BACKEND','native')
    window=MainWindow();window.show();app.processEvents()
    logger=get_translation_logger();logger.start_translation('real.pdf')
    logger.update_state(total=10,completed=2,page=4,document_pages=15,stage='等待翻译服务返回段落',active=1,finished=7,last_activity=time.monotonic()-18)
    QTest.mouseClick(window.status_label,Qt.MouseButton.LeftButton)
    app.processEvents();dialog=window._progress_dialog
    assert dialog and dialog.isVisible()
    assert dialog.progress.value()==2 and dialog.progress.maximum()==10
    assert '第 4 页' in dialog.values['current'].text()
    assert '18 秒' in dialog.values['waiting'].text()
    dialog.refresh();assert dialog.progress.value()==2
    logger.update_state(completed=3,stage='保存已完成页面');app.processEvents()
    assert dialog.progress.value()==3
    close_window(window,monkeypatch)


def test_next_page_stage_and_failure_keep_partial_visible_and_exportable(app,monkeypatch,tmp_path):
    monkeypatch.setenv('FREEPDF_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('FREEPDF_PREVIEW_BACKEND','native')
    path=tmp_path/'partial.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page();page.insert_text((72,100),'Already translated');doc.save(path)
    window=MainWindow();window.show();app.processEvents()
    window.on_translation_partial(dict(path=str(path),preview_path=str(path),completed=1,total=2))
    window.on_translation_progress('识别页面布局 · 第 2 页')
    assert window.right_pdf_widget.diagnostic_state()['pdf_path']==str(path)
    window.on_translation_failed('service timeout; first page saved')
    assert window.translated_file==str(path) and window.export_btn.isEnabled()
    assert window.right_pdf_widget.diagnostic_state()['stage']!='message'
    close_window(window,monkeypatch)

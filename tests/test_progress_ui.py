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
    copy='\n'.join(label.text() for label in dialog.findChildren(QLabel))
    assert '致力于构建免费的优质产品' in copy
    assert '制作者：zstar<br>联系方式：微信 zstar1003' in copy
    assert '让阅读跨越语言' not in copy and '微信公众号' not in copy
    close=next(button for button in dialog.findChildren(QPushButton) if button.text()=='关闭')
    assert close.property('role')==dialog.update_btn.property('role')=='default'
    assert dialog.export_logs_btn.property('role')=='quiet'
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
    window.current_file=str(path)
    logger=get_translation_logger();logger.start_translation(str(path))
    logger.update_state(total=2,completed=1)
    window.on_translation_partial(dict(path=str(path),preview_path=str(path),completed=1,total=2))
    window.on_translation_progress('识别页面布局 · 第 2 页')
    assert window.right_pdf_widget.diagnostic_state()['pdf_path']==str(path)
    window.on_translation_failed('service timeout; first page saved')
    assert window.translated_file==str(path) and window.export_btn.isEnabled()
    assert window.right_pdf_widget.diagnostic_state()['stage']!='message'
    dialog=window._progress_dialog
    assert dialog.failure_hint.isVisible() and '测试连接' in dialog.failure_hint.text()
    opened=[]
    monkeypatch.setattr(window,'open_config',lambda:opened.append(not dialog.isVisible()))
    QTest.mouseClick(dialog.engine_button,Qt.MouseButton.LeftButton)
    assert opened==[True] and dialog.isVisible()
    logger.update_state(message='翻译已停止；已保存 1 页译文。')
    assert not dialog.failure_hint.isVisible() and not dialog.engine_button.isVisible()
    logger.start_translation(str(path))
    assert not dialog.failure_hint.isVisible()
    close_window(window,monkeypatch)


def test_progress_details_stay_narrow_with_long_filename_and_service_error(app,monkeypatch,tmp_path):
    install_theme(app)
    monkeypatch.setenv('FREEPDF_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('FREEPDF_PREVIEW_BACKEND','native')
    window=MainWindow();window.show();app.processEvents()
    logger=get_translation_logger();logger.start_translation('long-filename-'*20+'.pdf')
    message='Service timeout: '+('long-request-id-without-spaces'*30)
    logger.update_state(total=12345,completed=6789,page=6790,document_pages=12345,
                        active=1234,finished=123456,stage='翻译已暂停',status='partial',message=message)
    window.show_translation_details();app.processEvents()
    dialog=window._progress_dialog
    assert 380<=dialog.width()<=420
    assert dialog.notice.toolTip()==message and dialog.notice.text().endswith('…')
    assert dialog.engine_button.isVisible()
    assert dialog.close_button.geometry().right()<dialog.width()
    assert dialog.events.height()>=100
    assert dialog.progress.height()>=26
    for label in (dialog.stage,dialog.filename,dialog.notice,dialog.failure_hint):
        assert label.height()>=label.heightForWidth(label.width())
    close_window(window,monkeypatch)

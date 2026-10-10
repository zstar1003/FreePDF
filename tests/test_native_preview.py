import time

import pymupdf
from PyQt6.QtCore import QCoreApplication, QEvent, QEventLoop, QSize
from PyQt6.QtPdfWidgets import QPdfView

from ui.native_pdf_widget import NativePdfWidget
from utils.resources import application_icon


def wait_for(app, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Native preview did not become ready')


def make_pdf(path, pages=2):
    with pymupdf.open() as doc:
        for index in range(pages):
            page=doc.new_page()
            page.insert_text((72,90), f'Native PDF page {index + 1}', fontsize=30)
            page.draw_rect(pymupdf.Rect(72,140,260,240), color=(0,0,0), fill=(0,0,0))
        doc.save(path)


def test_native_pdf_renders_real_pixels_scrolls_zooms_and_reimports(app, tmp_path):
    path=tmp_path/'中文 & # + % report.pdf'
    make_pdf(path,3)
    widget=NativePdfWidget('native_test')
    widget.resize(800,600);widget.show()
    failures=[];widget.previewFailed.connect(lambda *args: failures.append(args))
    widget.load_pdf(str(path))
    wait_for(app,lambda: widget.diagnostic_state().get('first_page_rendered'))
    assert not failures
    assert widget.diagnostic_state()['pages']==3
    def ink():
        image=widget.view.viewport().grab().toImage()
        return sum(image.pixelColor(x,y).value()<60 for x in range(30,image.width()-30,8) for y in range(30,image.height()-30,8))
    wait_for(app,lambda: ink()>10)
    widget.zoom_in();assert widget.view.zoomMode()==QPdfView.ZoomMode.Custom
    first_zoom=widget.view.zoomFactor();widget.zoom_out();assert widget.view.zoomFactor()<first_zoom
    widget.set_scroll_position(200,0);assert widget.view.verticalScrollBar().value()==200
    widget._jump(2);app.processEvents();assert widget.view.pageNavigator().currentPage()==2
    widget.show_message('正在翻译');assert widget.document.pageCount()==0
    widget.load_pdf(str(path));wait_for(app,lambda: widget.diagnostic_state().get('first_page_rendered'))
    widget.cleanup();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


def test_native_invalid_pdf_emits_one_failure(app,tmp_path):
    path=tmp_path/'bad.pdf';path.write_bytes(b'bad file')
    widget=NativePdfWidget('invalid');failures=[]
    widget.previewFailed.connect(lambda *args: failures.append(args))
    widget.load_pdf(str(path));app.processEvents()
    assert len(failures)==1
    assert not widget.diagnostic_state()['first_page_rendered']
    widget.cleanup();widget.deleteLater()


def test_installed_icon_ignores_working_directory(app,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert not application_icon().isNull()
    assert not application_icon().pixmap(QSize(32,32)).isNull()


def test_preview_factory_avoids_webengine_import_in_native_mode(app,monkeypatch,tmp_path):
    import subprocess,sys,os
    env=dict(os.environ,FREEPDF_PREVIEW_BACKEND='native',QT_QPA_PLATFORM='offscreen')
    result=subprocess.run([sys.executable,'-c',
        "import sys;from PyQt6.QtWidgets import QApplication;app=QApplication([]);from ui.pdf_preview_widget import PdfPreviewWidget;w=PdfPreviewWidget('test');assert not any(k.startswith('PyQt6.QtWebEngine') for k in sys.modules);w.cleanup()"],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr

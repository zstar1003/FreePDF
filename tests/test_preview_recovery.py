import time
import pymupdf
from PyQt6.QtCore import QCoreApplication,QEvent,QEventLoop
from PyQt6.QtWebEngineCore import QWebEngineProfile
from ui.pdf_preview_widget import PdfPreviewWidget
from ui.native_pdf_widget import NativePdfWidget


def test_browser_failure_recovers_same_document_without_user_action(app,tmp_path,monkeypatch):
    import ui.pdf_preview_widget as preview
    monkeypatch.setattr(preview,'use_native_preview',lambda:False)
    path=tmp_path/'recover.pdf'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72,100),'Automatic native recovery')
        doc.save(path)
    profile=QWebEngineProfile(app)
    widget=PdfPreviewWidget('recovery',profile);widget.resize(800,600);widget.show()
    failures=[];widget.previewFailed.connect(lambda *args:failures.append(args))
    widget.load_pdf(str(path))
    widget._viewer.previewFailed.emit('recovery','simulated STATUS_DLL_NOT_FOUND')
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents,50)
        if widget.diagnostic_state().get('first_page_rendered'):break
        time.sleep(.01)
    assert isinstance(widget._viewer,NativePdfWidget)
    assert widget.diagnostic_state()['first_page_rendered']
    assert widget.diagnostic_state()['recovery']['previous_backend']=='webengine'
    assert not failures
    widget.cleanup();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    profile.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

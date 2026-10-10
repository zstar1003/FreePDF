import json
import logging
import zipfile
from PyQt6.QtWidgets import QFileDialog,QPushButton
from ui.main_window import AboutDialog
from ui.components import TranslationConfigDialog
from utils import diagnostics


def test_about_directly_exports_logs_without_diagnostics_popup(app,tmp_path,monkeypatch):
    monkeypatch.setattr(diagnostics,'data_dir',lambda:tmp_path)
    monkeypatch.setattr(diagnostics,'_handler',None)
    import sys,threading
    monkeypatch.setattr(sys,'excepthook',sys.excepthook);monkeypatch.setattr(threading,'excepthook',threading.excepthook)
    diagnostics.initialize_logging(directory=tmp_path/'logs')
    path=tmp_path/'logs.zip'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(path),'ZIP'))
    dialog=AboutDialog();dialog.export_logs_btn.click()
    assert '日志已导出' in dialog.feedback_label.text()
    with zipfile.ZipFile(path) as archive:
        assert 'logs/freepdf.log' in archive.namelist()
        assert json.loads(archive.read('preview_state.json'))=={}
    dialog.deleteLater()
    handler=diagnostics._handler;logging.getLogger('freepdf').removeHandler(handler);handler.close()


def test_engine_settings_has_no_diagnostics_navigation(app,monkeypatch):
    def defaults(dialog):
        dialog.current_config={'service':'bing','lang_in':'en','lang_out':'zh','envs':{}}
        dialog.current_qa_config={'service':'关闭','envs':{}}
    monkeypatch.setattr(TranslationConfigDialog,'load_current_config',defaults)
    dialog=TranslationConfigDialog()
    assert not any('诊断' in button.text() or '导出日志' in button.text() for button in dialog.findChildren(QPushButton))
    dialog.deleteLater()

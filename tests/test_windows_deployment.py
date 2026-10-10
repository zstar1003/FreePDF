import os
import sys
from utils import windows_deployment
from utils import preview_backend, build_config


def test_default_reader_follows_tracked_build_choice(monkeypatch):
    monkeypatch.delenv('FREEPDF_PREVIEW_BACKEND',raising=False)
    assert preview_backend.use_native_preview()==(build_config.PREVIEW_BACKEND=='native')
    monkeypatch.setenv('FREEPDF_PREVIEW_BACKEND','native')
    assert preview_backend.use_native_preview()
    monkeypatch.setenv('FREEPDF_PREVIEW_BACKEND','pdfjs')
    assert not preview_backend.use_native_preview()


def test_frozen_windows_helper_inherits_shipped_paths(tmp_path,monkeypatch):
    qt=tmp_path/'PyQt6/Qt6';(qt/'bin').mkdir(parents=True)
    (qt/'bin/QtWebEngineProcess.exe').touch()
    handles=[]
    monkeypatch.setattr(sys,'platform','win32')
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path),raising=False)
    monkeypatch.setattr(os,'add_dll_directory',lambda path:handles.append(path),raising=False)
    monkeypatch.setenv('PATH','system-only')
    windows_deployment.configure_windows_dll_search()
    assert os.environ['PATH'].split(os.pathsep)[:2]==[str(qt/'bin'),str(tmp_path)]
    assert handles==[str(qt/'bin'),str(tmp_path)]
    assert os.environ['QTWEBENGINEPROCESS_PATH']==str(qt/'bin/QtWebEngineProcess.exe')
    assert os.environ['QTWEBENGINE_RESOURCES_PATH']==str(qt/'resources')
    for key in ('QTWEBENGINEPROCESS_PATH','QTWEBENGINE_RESOURCES_PATH','QTWEBENGINE_LOCALES_PATH'):
        monkeypatch.delenv(key)

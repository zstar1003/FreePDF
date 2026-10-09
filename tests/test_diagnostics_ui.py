import json
import logging
import zipfile

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from ui.components import TranslationConfigDialog
from ui.diagnostics_dialog import DiagnosticsDialog
from utils import diagnostics


def test_diagnostics_is_available_in_engine_settings_and_exports(app, tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(diagnostics, "_handler", None)
    monkeypatch.setattr(diagnostics, "_secrets", set())
    import sys
    import threading
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diagnostics.initialize_logging(directory=tmp_path / "logs")

    def load_defaults(dialog):
        dialog.current_config = {"service": "bing", "lang_in": "en", "lang_out": "zh", "envs": {}}
        dialog.current_qa_config = {"service": "关闭", "envs": {}}

    monkeypatch.setattr(TranslationConfigDialog, "load_current_config", load_defaults)
    opened = []
    monkeypatch.setattr(DiagnosticsDialog, "exec", lambda self: opened.append(self.windowTitle()))
    engine_settings = TranslationConfigDialog()
    button = next(item for item in engine_settings.findChildren(QPushButton) if item.text() == "诊断与日志…")
    button.click()
    assert opened == ["诊断与日志"]
    dialog = DiagnosticsDialog(engine_settings)
    destination = tmp_path / "exported.zip"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(destination), "ZIP"))
    confirmations = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: confirmations.append(args[1]))
    dialog.export_button.click()
    assert confirmations == ["导出成功"]
    with zipfile.ZipFile(destination) as archive:
        assert "logs/freepdf.log" in archive.namelist()
        assert json.loads(archive.read("preview_state.json")) == {}
    dialog.software_checkbox.setChecked(True)
    assert diagnostics.read_preferences()["software_rendering"] is True
    dialog.close()
    engine_settings.close()
    handler = diagnostics._handler
    logging.getLogger("freepdf").removeHandler(handler)
    handler.close()

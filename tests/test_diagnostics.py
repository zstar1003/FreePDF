import json
import logging
from pathlib import Path
import sys
import zipfile

import pytest

from utils import diagnostics


@pytest.fixture
def log_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "_handler", None)
    monkeypatch.setattr(diagnostics, "_secrets", set())
    monkeypatch.setattr(diagnostics, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    import threading
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diagnostics.initialize_logging(directory=tmp_path / "logs")
    yield tmp_path
    handler = diagnostics._handler
    logging.getLogger("freepdf").removeHandler(handler)
    handler.close()


def test_export_redacts_logs_and_contains_only_support_files(log_directory):
    secret = "private-credential-12345"
    diagnostics.register_secrets({"envs": {"OPENAI_API_KEY": secret}})
    diagnostics.get_logger("test").error("request Authorization: Bearer %s url=?token=opaque-test-token", secret)
    diagnostics.get_logger("test").info("headers={'api_key': 'another-private-key'}")
    config = log_directory / "pdf2zh_config.json"
    config.write_text(json.dumps({"api_key": secret}))
    (log_directory / "sample.pdf").write_bytes(b"PDF content must not be exported")
    archive_path = log_directory / "support.zip"
    diagnostics.export_diagnostics(archive_path, {"view": "left", "api_key": secret})
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {"environment.json", "preview_state.json", "README.txt", "logs/freepdf.log"}
        output = "\n".join(archive.read(name).decode() for name in archive.namelist())
        assert secret not in output
        assert "another-private-key" not in output
        assert "opaque-test-token" not in output
        assert "[REDACTED]" in output
        metadata = json.loads(archive.read("environment.json"))
        assert json.loads(archive.read("preview_state.json"))["api_key"] == "[REDACTED]"
        assert metadata["session"] == diagnostics.SESSION_ID
        assert metadata["versions"]["PyQt6"]


def test_rotation_is_bounded_and_export_includes_rotated_files(log_directory):
    handler = diagnostics._handler
    handler.maxBytes = 1024
    for number in range(100):
        diagnostics.get_logger("test").info("event=%s %s", number, "x" * 100)
    files = list((log_directory / "logs").glob("freepdf.log*"))
    assert len(files) == 4
    assert all(path.stat().st_size < 1500 for path in files)
    archive_path = log_directory / "rotated.zip"
    diagnostics.export_diagnostics(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        assert "logs/freepdf.log.3" in archive.namelist()


def test_export_failure_does_not_break_subsequent_logging(log_directory):
    with pytest.raises(OSError):
        diagnostics.export_diagnostics(log_directory / "missing" / "report.zip")
    diagnostics.get_logger("test").info("logging still usable")
    diagnostics._handler.flush()
    assert "logging still usable" in Path(diagnostics._handler.baseFilename).read_text()


def test_disk_write_failure_is_reported_without_recursive_stderr_logging(log_directory, monkeypatch):
    import io

    class BrokenStream(io.StringIO):
        def write(self, text):
            raise OSError("disk full")

    handler = diagnostics._handler
    monkeypatch.setattr(handler, "stream", BrokenStream())
    diagnostics.get_logger("test").error("must not recurse or crash")
    assert diagnostics.environment_info()["log_write_error"] == "disk full"


def test_windowed_stdout_and_unterminated_lines_are_captured(log_directory):
    stream = diagnostics.LogStream(None, logging.INFO)
    stream.write("startup without console\n")
    stream.write("Authorization: Bearer hidden-value")
    stream.flush()
    diagnostics._handler.flush()
    output = Path(diagnostics._handler.baseFilename).read_text()
    assert "startup without console" in output
    assert "hidden-value" not in output


def test_software_rendering_preferences_take_effect_on_restart(log_directory, monkeypatch):
    tmp_path = log_directory
    monkeypatch.setattr(diagnostics, "data_dir", lambda: tmp_path)
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--lang=zh-CN")
    diagnostics.set_software_rendering(True)
    assert os_flags() == "--lang=zh-CN --disable-gpu"
    assert os_flags().count("--disable-gpu") == 1
    diagnostics.set_software_rendering(False)
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--lang=zh-CN")
    assert os_flags() == "--lang=zh-CN"


def os_flags():
    import os
    diagnostics.configure_chromium()
    return os.environ["QTWEBENGINE_CHROMIUM_FLAGS"]


def test_translation_clear_keeps_persistent_history(log_directory):
    from utils.translation_logger import get_translation_logger
    logger = get_translation_logger()
    logger.info("previous translation event")
    logger.clear()
    assert "previous translation event" not in logger.get_logs_text()
    diagnostics._handler.flush()
    assert "previous translation event" in Path(diagnostics._handler.baseFilename).read_text()

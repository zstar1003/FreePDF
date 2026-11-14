from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

from core.qa_engine import QAEngineThread
from ui import components
from utils.qa_endpoint import resolve_qa_endpoint


CASES = [
    ("https://example.com", "https://example.com/v1/chat/completions"),
    ("https://example.com/", "https://example.com/v1/chat/completions"),
    ("https://example.com/v1", "https://example.com/v1/chat/completions"),
    (" https://example.com/v1/ ", "https://example.com/v1/chat/completions"),
    ("http://localhost:8000/api/v3", "http://localhost:8000/api/v3/chat/completions"),
    ("https://example.com/proxy/v1", "https://example.com/proxy/v1/chat/completions"),
    ("https://example.com/chat/completions", "https://example.com/chat/completions"),
    ("https://example.com/v1/chat/completions/", "https://example.com/v1/chat/completions"),
    ("https://example.com/v1?api-version=1", "https://example.com/v1/chat/completions?api-version=1"),
    ("https://example.com/v1/chat/completions?api-version=1", "https://example.com/v1/chat/completions?api-version=1"),
]


@pytest.mark.parametrize("host,expected", CASES)
def test_endpoint_forms(host, expected):
    assert resolve_qa_endpoint(host) == expected
    assert resolve_qa_endpoint(expected) == expected


@pytest.mark.parametrize("host", [None, "", " ", "example.com/v1", "ftp://example.com", "https:///v1"])
def test_invalid_host(host):
    with pytest.raises(ValueError):
        resolve_qa_endpoint(host)


def make_engine(monkeypatch, host, model="test-model", endpoint=None):
    monkeypatch.setattr(QAEngineThread, "_load_qa_config", lambda self: {
        "service": "自定义",
        "envs": {"CUSTOM_HOST": host, "CUSTOM_MODEL": model, "CUSTOM_KEY": "test-key", "CUSTOM_API_URL": endpoint},
    })
    engine = QAEngineThread("ping", "", [])
    monkeypatch.setattr(engine, "_build_messages", lambda: [{"role": "user", "content": "ping"}])
    return engine


@pytest.mark.parametrize("host,expected,endpoint",
                         [(h, e, None) for h, e in CASES] + [
                             (None, "https://example.com/custom/invoke?version=2",
                              "https://example.com/custom/invoke?version=2"),
                             ("https://ignored.example/v1", "https://example.com/chat/",
                              "https://example.com/chat/"),
                         ])
def test_connection_test_and_streaming_qa_use_same_endpoint(app, monkeypatch, host, expected, endpoint):
    response = Mock(status_code=200)
    response.iter_lines.return_value = [
        b'data: {"choices":[{"delta":{"content":"answer"}}]}',
        b"data: [DONE]",
    ]
    post = Mock(return_value=response)
    monkeypatch.setattr(components.requests, "post", post)
    # Run the real connection-test worker synchronously, without network or timers.
    monkeypatch.setattr(components.threading, "Thread",
                        lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(components._QTimer, "singleShot", lambda *args: None)
    result = Mock()
    button = QPushButton()
    dialog = SimpleNamespace(qa_test_btn=button, connection_test_finished=SimpleNamespace(emit=result))
    try:
        components.TranslationConfigDialog._perform_connection_test(
            dialog, "自定义", host, {"Content-Type": "application/json", "Authorization": "Bearer test-key"},
            "test-model", is_qa=True, endpoint=endpoint,
        )
    finally:
        QApplication.restoreOverrideCursor()
    assert result.call_args.args[1:] == (True, "")
    test_call = post.call_args
    engine = make_engine(monkeypatch, host, endpoint=endpoint)
    chunks, failures, completed = [], [], []
    engine.response_chunk.connect(chunks.append)
    engine.response_failed.connect(failures.append)
    engine.response_completed.connect(lambda: completed.append(True))
    engine._handle_custom_qa()
    assert test_call.args[0] == post.call_args.args[0] == expected
    assert test_call.kwargs["json"]["model"] == post.call_args.kwargs["json"]["model"]
    assert post.call_args.kwargs["stream"] is True
    assert chunks == ["answer"]
    assert not failures
    assert completed == [True]


@pytest.mark.parametrize("host,model", [(None, "m"), ("", "m"), (" ", "m"), ("bad-url", "m"), ("https://example.com", None)])
def test_bad_config_reports_error_without_request(app, monkeypatch, host, model):
    post = Mock()
    monkeypatch.setattr(components.requests, "post", post)
    engine = make_engine(monkeypatch, host, model)
    failures = []
    engine.response_failed.connect(failures.append)
    engine._handle_custom_qa()
    assert len(failures) == 1
    assert "CUSTOM_HOST" in failures[0] or "CUSTOM_MODEL" in failures[0]
    post.assert_not_called()


def test_exact_endpoint_is_not_guessed():
    assert resolve_qa_endpoint(None, "https://example.com/invoke/") == "https://example.com/invoke/"
    with pytest.raises(ValueError, match="CUSTOM_API_URL"):
        resolve_qa_endpoint("https://example.com", "bad-url")


def test_exact_endpoint_setting_round_trip_and_clear(app, monkeypatch, tmp_path):
    import json
    from utils import config_path

    config = tmp_path / "config.json"
    monkeypatch.setattr(config_path, "get_config_file_path", lambda: str(config))
    dialog = components.TranslationConfigDialog()
    dialog.qa_service_combo.setCurrentText("自定义")
    dialog.custom_qa_host.setText("https://example.com/v1")
    dialog.custom_qa_endpoint.setText("https://example.com/custom/invoke?version=2")
    dialog.custom_qa_model.setText("model")
    dialog.save_config()
    assert json.loads(config.read_text())["qa_engine"]["envs"]["CUSTOM_API_URL"] == (
        "https://example.com/custom/invoke?version=2"
    )
    loaded = components.TranslationConfigDialog()
    loaded.apply_current_config()
    assert loaded.custom_qa_endpoint.text() == "https://example.com/custom/invoke?version=2"
    perform = Mock()
    monkeypatch.setattr(loaded, "_perform_connection_test", perform)
    loaded.custom_qa_host.clear()
    loaded._test_qa_connection()
    assert perform.call_args.kwargs["endpoint"] == "https://example.com/custom/invoke?version=2"
    loaded.custom_qa_endpoint.clear()
    loaded.custom_qa_host.setText("https://example.com/v1")
    loaded.save_config()
    assert "CUSTOM_API_URL" not in json.loads(config.read_text())["qa_engine"]["envs"]
    loaded.deleteLater()
    dialog.deleteLater()


@pytest.mark.parametrize("endpoint", [123, False, []])
def test_invalid_endpoint_type_reports_error(app, monkeypatch, endpoint):
    with pytest.raises(ValueError, match="CUSTOM_API_URL"):
        resolve_qa_endpoint("https://example.com", endpoint)
    engine = make_engine(monkeypatch, "https://example.com", endpoint=endpoint)
    failures = []
    engine.response_failed.connect(failures.append)
    engine._handle_custom_qa()
    assert len(failures) == 1
    assert "CUSTOM_API_URL" in failures[0]

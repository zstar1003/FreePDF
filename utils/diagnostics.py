"""Local, bounded diagnostic logging. No documents or configuration are exported."""

import importlib.metadata
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timezone

SESSION_ID = uuid.uuid4().hex[:12]
_handler = None
_qt_handler = None
_secrets = set()
_lock = threading.RLock()
_KEY = r"(?:[\w-]*(?:api[ _-]?key|[_-]key|token|secret|password|authorization|cookie)[\w-]*|key)"
_CREDENTIAL = re.compile(
    rf"(?i)([\"']?{_KEY}[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;&}}]+)"
)


def redact(value):
    text = str(value)
    with _lock:
        for secret in sorted(_secrets, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)\bBearer\s+[^\s'\",;]+", "Bearer [REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", text)
    return _CREDENTIAL.sub(r"\1[REDACTED]", text)


def register_secrets(config):
    """Register secret values without logging the configuration itself."""
    if not isinstance(config, dict):
        return
    with _lock:
        for key, value in config.items():
            if isinstance(value, dict):
                register_secrets(value)
            elif re.search(_KEY, str(key), re.I) and isinstance(value, str) and value:
                _secrets.add(value)


def redact_data(value):
    """Redact structured metadata before serialization, preserving valid JSON."""
    if isinstance(value, dict):
        return {key: "[REDACTED]" if re.fullmatch(_KEY, str(key), re.I) else redact_data(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_data(item) for item in value]
    return redact(value) if isinstance(value, str) else value


def data_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
        return base / "FreePDF"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/FreePDF"
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "FreePDF"


def read_preferences():
    try:
        value = json.loads((data_dir() / "diagnostics_settings.json").read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def set_software_rendering(enabled):
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "diagnostics_settings.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"software_rendering": bool(enabled)}), "utf-8")
    temporary.replace(path)
    get_logger("settings").info("software_rendering preference=%s (restart required)", enabled)


def configure_chromium():
    """Must run before importing QtWebEngine."""
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if read_preferences().get("software_rendering") and "--disable-gpu" not in flags.split():
        flags = (flags + " --disable-gpu").strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


class DiagnosticFileHandler(RotatingFileHandler):
    last_error = None

    def handleError(self, record):
        # logging's default error handler writes to stderr. Since stderr is also
        # captured, disk-full/permission errors would otherwise recurse forever.
        self.last_error = redact(str(sys.exc_info()[1]))


class LogStream(io.TextIOBase):
    """Capture legacy prints, including windowed builds where stdout is None."""
    def __init__(self, original, level):
        self.original = original
        self.level = level
        self._buffers = threading.local()

    @property
    def encoding(self):
        return "utf-8"

    def write(self, text):
        if self.original is not None:
            try:
                self.original.write(text)
            except (OSError, ValueError, UnicodeError):
                pass
        buffer = getattr(self._buffers, "text", "") + str(text)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if line.strip():
                get_logger("console").log(self.level, line.rstrip())
        # Bound progress output that uses carriage returns rather than newlines.
        if len(buffer) > 8192:
            get_logger("console").log(self.level, buffer)
            buffer = ""
        self._buffers.text = buffer
        return len(text)

    def flush(self):
        buffer = getattr(self._buffers, "text", "")
        if buffer.strip():
            get_logger("console").log(self.level, buffer)
        self._buffers.text = ""
        if self.original is not None:
            try:
                self.original.flush()
            except (OSError, ValueError):
                pass

    def isatty(self):
        return False


def get_logger(name):
    return logging.getLogger("freepdf." + name)


def environment_info():
    versions = {}
    for package in ("PyQt6", "PyQt6-Qt6", "PyQt6-WebEngine", "PyQt6-WebEngine-Qt6", "PyMuPDF", "pdf2zh", "pyinstaller"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "unavailable"
    return {
        "session": SESSION_ID,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "app_version": "5.1.3",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "working_directory": os.getcwd(),
        "bundle_directory": getattr(sys, "_MEIPASS", None),
        "versions": versions,
        "qt_environment": {key: os.environ.get(key, "") for key in (
            "QTWEBENGINE_CHROMIUM_FLAGS", "QT_OPENGL", "QT_QUICK_BACKEND", "QT_QPA_PLATFORM",
        )},
        "software_rendering_requested": bool(read_preferences().get("software_rendering")),
        "log_directory": str(Path(_handler.baseFilename).parent) if _handler else None,
        "log_write_error": getattr(_handler, "last_error", None),
    }


def initialize_logging(capture_console=False, directory=None):
    global _handler
    if _handler is not None:
        return Path(_handler.baseFilename).parent
    directory = Path(directory) if directory else data_dir() / "logs"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = DiagnosticFileHandler(directory / "freepdf.log", maxBytes=5 * 1024 * 1024,
                                      backupCount=3, encoding="utf-8")
    except OSError:
        directory = Path(tempfile.mkdtemp(prefix="freepdf-logs-"))
        handler = DiagnosticFileHandler(directory / "freepdf.log", maxBytes=5 * 1024 * 1024,
                                      backupCount=3, encoding="utf-8")
    handler.setFormatter(RedactingFormatter(
        f"%(asctime)s %(levelname)s session={SESSION_ID} pid=%(process)d thread=%(threadName)s %(name)s %(message)s"
    ))
    root = logging.getLogger("freepdf")
    root.setLevel(logging.DEBUG)
    root.propagate = False
    root.addHandler(handler)
    _handler = handler
    register_secrets(dict(os.environ))
    try:
        from utils.config_path import get_config_file_path
        register_secrets(json.loads(Path(get_config_file_path()).read_text("utf-8")))
    except (OSError, ValueError):
        pass
    if capture_console:
        sys.stdout = LogStream(sys.stdout, logging.INFO)
        sys.stderr = LogStream(sys.stderr, logging.ERROR)
    previous_hook = sys.excepthook

    def exception_hook(kind, value, traceback):
        get_logger("exception").critical("Unhandled exception", exc_info=(kind, value, traceback))
        previous_hook(kind, value, traceback)

    sys.excepthook = exception_hook
    previous_thread_hook = threading.excepthook

    def thread_hook(args):
        get_logger("exception").critical("Unhandled thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        previous_thread_hook(args)

    threading.excepthook = thread_hook
    get_logger("startup").info("environment=%s", json.dumps(environment_info(), ensure_ascii=False))
    return directory


def install_qt_logging():
    global _qt_handler
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    def handler(kind, context, message):
        levels = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
                  QtMsgType.QtWarningMsg: logging.WARNING, QtMsgType.QtCriticalMsg: logging.ERROR,
                  QtMsgType.QtFatalMsg: logging.CRITICAL}
        get_logger("qt").log(levels.get(kind, logging.INFO), "%s:%s %s",
                             context.category, context.line, message)

    _qt_handler = handler  # Keep the callback alive for the application lifetime.
    qInstallMessageHandler(handler)


def export_diagnostics(destination, viewer_states=None):
    initialize_logging()
    get_logger("export").info("diagnostic export requested")
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, LogStream):
            stream.flush()
    _handler.acquire()
    try:
        _handler.flush()
        directory = Path(_handler.baseFilename).parent
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("environment.json", json.dumps(redact_data(environment_info()), ensure_ascii=False, indent=2))
            archive.writestr("preview_state.json", json.dumps(redact_data(viewer_states or {}), ensure_ascii=False, indent=2))
            archive.writestr("README.txt", "FreePDF diagnostics: environment, preview state and rotating logs only.\n"
                              "No PDF files or API configuration included. Paths and filenames may appear in logs.\n")
            for path in sorted(directory.glob("freepdf.log*")):
                if path.is_file():
                    archive.writestr("logs/" + path.name, redact(path.read_text("utf-8", errors="replace")))
    finally:
        _handler.release()

"""Use shipped Qt/VC libraries for both Python and WebEngine child processes."""

import os
from pathlib import Path
import sys

_dll_directories = []


def configure_windows_dll_search():
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    root = Path(sys._MEIPASS)
    qt = root / "PyQt6/Qt6"
    paths = [qt / "bin", root]
    existing = [str(path) for path in paths if path.is_dir()]
    # AddDllDirectory is process-local; PATH is inherited by QtWebEngineProcess.
    os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])
    for path in existing:
        _dll_directories.append(os.add_dll_directory(path))
    helper = qt / "bin/QtWebEngineProcess.exe"
    if helper.exists():
        os.environ["QTWEBENGINEPROCESS_PATH"] = str(helper)
        os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(qt / "resources")
        os.environ["QTWEBENGINE_LOCALES_PATH"] = str(qt / "translations/qtwebengine_locales")

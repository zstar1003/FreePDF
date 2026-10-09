import os

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-web-security --allow-file-access-from-files")

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance() or QApplication(["freepdf-tests"])
    yield application

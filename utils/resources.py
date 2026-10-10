"""Application resources are independent of the launcher's working directory."""

from pathlib import Path
import sys


def resource_path(relative):
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / relative


def application_icon():
    from PyQt6.QtGui import QIcon

    return QIcon(str(resource_path("ui/logo/logo.png")))

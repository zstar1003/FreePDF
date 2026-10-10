"""Select the Windows reader before any WebEngine import can launch a helper."""

import os
import sys


def use_native_preview():
    return sys.platform == "win32" or os.environ.get("FREEPDF_PREVIEW_BACKEND") == "native"

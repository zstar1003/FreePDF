"""Select the packaged reader before any WebEngine import launches a helper."""

import os
from utils.build_config import PREVIEW_BACKEND


def use_native_preview():
    return os.environ.get("FREEPDF_PREVIEW_BACKEND", PREVIEW_BACKEND) == "native"

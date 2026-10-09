"""Check that a packaged application can preload translation and start WebEngine."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    executable = Path(sys.argv[1]).resolve()
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu")
    with tempfile.TemporaryDirectory(prefix="freepdf-smoke-") as temporary:
        if sys.platform == "win32":
            environment["LOCALAPPDATA"] = temporary
            log = Path(temporary) / "FreePDF/logs/freepdf.log"
        else:
            log = Path.home() / "Library/Application Support/FreePDF/logs/freepdf.log"
        offset = log.stat().st_size if log.exists() else 0
        with (Path(temporary) / "console.log").open("w") as output:
            process = subprocess.Popen([str(executable)], stdout=output, stderr=subprocess.STDOUT, env=environment)
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"Packaged application exited early: {process.returncode}")
                    content = log.read_bytes()[offset:].decode("utf-8", errors="replace") if log.exists() else ""
                    if "pdf2zh模块预加载成功" in content and "WebEngine核心组件预热完成" in content:
                        time.sleep(3)
                        if process.poll() is not None:
                            raise RuntimeError("Packaged application exited after startup")
                        if "初始化tiktoken失败" in content:
                            raise RuntimeError("Packaged tiktoken encoding plugin is missing")
                        print("Packaged translation preload and WebEngine startup passed")
                        return
                    if "pdf2zh模块预加载失败" in content:
                        raise RuntimeError("Packaged translation preload failed; inspect diagnostic log")
                    time.sleep(0.5)
                raise RuntimeError("Packaged application did not finish startup within 45 seconds")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    main()

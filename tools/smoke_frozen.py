"""Check that a packaged application can preload translation and start WebEngine."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def print_startup_failure(process_id, log, console):
    for label, path in (("Diagnostic log", log), ("Bootloader console", console)):
        content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else "not created"
        print(f"{label}:\n{content[-16000:]}")
    if sys.platform != "win32":
        return
    # A windowed PyInstaller boot failure may show a dialog before main.py can
    # initialize logging. Capture text only from this application's windows.
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]

    @callback_type
    def child_text(handle, _):
        buffer = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(handle) + 1)
        user32.GetWindowTextW(handle, buffer, len(buffer))
        if buffer.value:
            print("Application window:", buffer.value)
        return True

    @callback_type
    def own_windows(handle, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == process_id:
            child_text(handle, 0)
            user32.EnumChildWindows(handle, child_text, 0)
        return True

    user32.EnumWindows(own_windows, 0)


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
            except Exception:
                output.flush()
                print_startup_failure(process.pid, log, Path(temporary) / "console.log")
                raise
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

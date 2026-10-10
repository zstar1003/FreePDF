"""FreePDF主程序"""

import multiprocessing
import os
import sys

from utils.diagnostics import configure_chromium, initialize_logging, install_qt_logging, get_logger

if __name__ == "__main__":
    # Handle frozen worker startup before preloading modules or opening a log file.
    multiprocessing.freeze_support()
    sys.modules.setdefault("main", sys.modules[__name__])
    initialize_logging(capture_console=True)
configure_chromium()

# 追加禁用同源策略和允许 file:// 读取本地资源的标志，确保 PDF.js 能加载 locale/*.ftl
flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
extra = " --disable-web-security --allow-file-access-from-files --allow-file-access --lang=zh-CN"
if extra.strip() not in flags:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + extra).strip()
if __name__ == "__main__":
    get_logger("startup").info("effective Chromium flags=%s", os.environ["QTWEBENGINE_CHROMIUM_FLAGS"])

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 全局变量，防止重复加载
_PDF2ZH_MODULES = None
_PDF2ZH_CONFIG = None
_PDF2ZH_LOADED = False


def get_app_dir():
    """获取应用程序目录，兼容开发环境和打包环境"""
    if getattr(sys, "frozen", False):
        # PyInstaller打包后的环境
        if hasattr(sys, "_MEIPASS"):
            # 使用_MEIPASS作为基础目录
            app_dir = sys._MEIPASS
            print(f"运行环境: PyInstaller打包, 应用目录: {app_dir}")
        else:
            app_dir = os.path.dirname(sys.executable)
            print(f"运行环境: 打包环境, 应用目录: {app_dir}")
        return app_dir
    else:
        # 开发环境
        app_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"运行环境: 开发环境, 应用目录: {app_dir}")
        return app_dir


def get_resource_path(relative_path):
    """获取资源��件路径，兼容开发环境和打包环境"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller打包环境,资源在_MEIPASS目录下
        base_path = sys._MEIPASS
    else:
        # 开发环境或其他打包环境
        base_path = os.path.dirname(os.path.abspath(__file__))

    resource_path = os.path.join(base_path, relative_path)
    print(f"资源文件: {relative_path} -> {resource_path}")
    return resource_path


# 在PyQt6初始化之前预加载pdf2zh模块，避免环境冲突
def _load_pdf2zh_modules():
    """预加载pdf2zh模块"""
    global _PDF2ZH_MODULES, _PDF2ZH_CONFIG, _PDF2ZH_LOADED

    if _PDF2ZH_LOADED:
        print("pdf2zh模块已加载，跳过重复加载")
        return

    print("正在预加载pdf2zh模块...")
    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"sys.path: {sys.path[:3]}...")  # 只显示前3个路径避免输出过长

    try:
        print("步骤1: 导入标准库...")
        import json

        # 最早期修复cv2递归导入问题(必须在任何可能导入cv2的操作之前)
        if hasattr(sys, "_MEIPASS"):
            print("步骤1.1: 修复cv2递归导入问题...")
            paths_to_remove = []
            for path in list(sys.path):
                if (
                    path.endswith("/cv2")
                    or "/Resources/cv2" in path
                    or path.endswith("\\cv2")
                    or "/cv2" in path
                ):
                    paths_to_remove.append(path)

            for path in paths_to_remove:
                if path in sys.path:
                    try:
                        sys.path.remove(path)
                        print(f"  - 移除cv2路径: {path}")
                    except ValueError:
                        pass

        # 在打包环境下设置onnxruntime的库路径
        if hasattr(sys, "_MEIPASS"):
            print("步骤1.5: 设置打包环境下的库路径...")
            base_dir = sys._MEIPASS

            # 添加onnxruntime库路径
            onnx_paths = [
                os.path.join(base_dir, "onnxruntime", "capi"),
                os.path.join(base_dir, "onnxruntime"),
                base_dir,
            ]

            for path in onnx_paths:
                if os.path.exists(path):
                    # Windows: 使用add_dll_directory
                    if hasattr(os, "add_dll_directory"):
                        try:
                            os.add_dll_directory(path)
                            print(f"  - 添加DLL搜索路径: {path}")
                        except Exception as e:
                            print(f"  - 添加DLL路径失败: {e}")

                    # macOS/Linux: 更新环境变量
                    # macOS使用DYLD_LIBRARY_PATH (虽然受SIP限制,但在app内部仍有效)
                    if sys.platform == "darwin":
                        dyld_path = os.environ.get("DYLD_LIBRARY_PATH", "")
                        if path not in dyld_path:
                            os.environ["DYLD_LIBRARY_PATH"] = (
                                path + os.pathsep + dyld_path
                            )
                            print(f"  - 更新DYLD_LIBRARY_PATH: {path}")

                    # 通用: 更新PATH环境变量
                    current_path = os.environ.get("PATH", "")
                    if path not in current_path:
                        os.environ["PATH"] = path + os.pathsep + current_path
                        print(f"  - 更新PATH: {path}")

        print("步骤2: 导入pdf2zh模块...")

        # 尝试先导入onnxruntime（使用hook确保兼容性）
        try:
            print("  - 预导入onnxruntime hook...")
            print("  - onnxruntime hook 导入成功")
        except Exception as e:
            print(f"  - onnxruntime hook 导入失败: {e}")

        try:
            print("  - 预导入onnxruntime...")
            import onnxruntime

            print(f"  - onnxruntime版本: {onnxruntime.__version__}")
        except Exception as e:
            print(f"  - onnxruntime导入失败: {e}")
            # 继续尝试导入pdf2zh，也许不需要onnxruntime

        try:
            from pdf2zh import translate

            print("  - translate 导入成功")
        except Exception as e:
            print(f"  - translate 导入失败: {e}")
            raise

        try:
            from pdf2zh.config import ConfigManager

            print("  - ConfigManager 导入成功")
        except Exception as e:
            print(f"  - ConfigManager 导入失败: {e}")
            raise

        try:
            from pdf2zh.doclayout import OnnxModel

            print("  - OnnxModel 导入成功")
        except Exception as e:
            print(f"  - OnnxModel 导入失败: {e}")
            raise

        print("步骤3: 读取配置文件...")
        # 获取配置文件路径(使用统一的路径管理)
        from utils.config_path import get_config_file_path

        config_path = get_config_file_path()
        print(f"配置文件路径: {config_path}")

        if not os.path.exists(config_path):
            # 尝试其他可能的位置
            alternative_paths = [
                "pdf2zh_config.json",  # 当前目录
                os.path.join(os.getcwd(), "pdf2zh_config.json"),  # 工作目录
            ]
            for alt_path in alternative_paths:
                print(f"尝试替代路径: {alt_path}")
                if os.path.exists(alt_path):
                    config_path = alt_path
                    print(f"找到配置文件: {config_path}")
                    break
            else:
                raise FileNotFoundError(f"配置文件不存在: {config_path}")

        # 加载配置
        print(f"读取配置文件: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"原始配置: {config}")

        print("步骤4: 修正文件路径...")
        # 修正配置中的相对路径为绝对路径
        app_dir = get_app_dir()

        # 修正模型路径
        if "models" in config and "doclayout_path" in config["models"]:
            model_path = config["models"]["doclayout_path"]
            if not os.path.isabs(model_path):
                new_model_path = os.path.normpath(os.path.join(app_dir, model_path))
                config["models"]["doclayout_path"] = new_model_path
                print(f"模型路径: {model_path} -> {new_model_path}")

        # 修正字体路径
        if "fonts" in config:
            for font_key in config["fonts"]:
                font_path = config["fonts"][font_key]
                if not os.path.isabs(font_path):
                    new_font_path = os.path.normpath(os.path.join(app_dir, font_path))
                    config["fonts"][font_key] = new_font_path
                    print(f"字体路径 {font_key}: {font_path} -> {new_font_path}")

        print("步骤5: 检查文件存在性...")
        # 检查关键文件是否存在
        model_path = config["models"]["doclayout_path"]
        print(f"检查模型文件: {model_path}")
        if not os.path.exists(model_path):
            print("模型文件不存在！列出模型目录内容:")
            model_dir = os.path.dirname(model_path)
            if os.path.exists(model_dir):
                print(f"模型目录内容: {os.listdir(model_dir)}")
            else:
                print(f"模型目录不存在: {model_dir}")
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        font_path = config["fonts"]["zh"]
        print(f"检查字体文件: {font_path}")
        if not os.path.exists(font_path):
            print("字体文件不存在！列出字体目录内容:")
            font_dir = os.path.dirname(font_path)
            if os.path.exists(font_dir):
                print(f"字体目录内容: {os.listdir(font_dir)}")
            else:
                print(f"字体目录不存在: {font_dir}")
            raise FileNotFoundError(f"字体文件不存在: {font_path}")

        print("步骤6: 应用配置...")
        # 应用配置
        for key, value in config.items():
            if key not in ["models", "fonts"]:
                ConfigManager.set(key, value)
                print(f"设置配置: {key} = {value}")

        # 设置字体
        ConfigManager.set("NOTO_FONT_PATH", font_path)
        print(f"设置字体路径: {font_path}")

        print("步骤7: 保存到全局变量...")
        # 将预加载的模块和配置保存到全局变量
        _PDF2ZH_MODULES = {
            "translate": translate,
            "ConfigManager": ConfigManager,
            "OnnxModel": OnnxModel,
        }
        _PDF2ZH_CONFIG = config
        _PDF2ZH_LOADED = True

        print("✅ pdf2zh模块预加载成功")

    except Exception as e:
        print(f"❌ pdf2zh模块预加载失败: {e}")
        import traceback

        traceback.print_exc()
        _PDF2ZH_MODULES = None
        _PDF2ZH_CONFIG = None
        _PDF2ZH_LOADED = True  # 标记为已尝试加载，避免重复尝试


# 预加载模块
_load_pdf2zh_modules()

# 安全地导入PyQt6
from utils.preview_backend import use_native_preview  # noqa: E402
if not use_native_preview():
    from PyQt6.QtWebEngineCore import QWebEngineProfile  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

if __name__ == "__main__":
    install_qt_logging()

from ui.main_window import MainWindow  # noqa: E402


def get_pdf2zh_modules():
    """获取预加载的pdf2zh模块"""
    return _PDF2ZH_MODULES, _PDF2ZH_CONFIG


if __name__ == "__main__":
    # 配置多进程支持
    multiprocessing.freeze_support()

    from PyQt6.QtCore import QCoreApplication, Qt
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    from utils.resources import application_icon
    from ui.theme import install_theme
    install_theme(app)
    app.setWindowIcon(application_icon())
    from utils.resources import resource_path
    get_logger("startup").info("application icon=%s null=%s", resource_path("ui/logo/logo.png"), app.windowIcon().isNull())
    app.aboutToQuit.connect(lambda: get_logger("startup").info("application exiting"))

    # 全局字体设置
    try:
        from PyQt6.QtGui import QFont, QFontDatabase

        font_path = get_resource_path(os.path.join("fonts", "ht.ttf"))
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                family = QFontDatabase.applicationFontFamilies(font_id)[0]
                app.setFont(QFont(family, 10))
                print(f"已加载并设置全局字体: {family}")
            else:
                print(f"加载字体失败: {font_path}")
        else:
            print(f"字体文件不存在: {font_path}")
    except Exception as e:
        print(f"设置全局字体出错: {e}")

    # 设置应用程序属性
    app.setApplicationName("FreePDF")
    from utils.version import VERSION
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("zstar")
    for screen in app.screens():
        get_logger("display").info("screen=%s geometry=%s dpr=%s logical_dpi=%s",
                                   screen.name(), screen.geometry(), screen.devicePixelRatio(), screen.logicalDotsPerInch())

    if not use_native_preview():
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    get_logger("startup").info("preview backend=%s", "qt_pdf" if use_native_preview() else "webengine_with_native_recovery")

    # 创建主窗口
    window = MainWindow()
    window.showMaximized()

    if "--preview-smoke" in sys.argv:
        from PyQt6.QtCore import QTimer
        pdf_path = sys.argv[sys.argv.index("--preview-smoke") + 1]
        window._is_translation_enabled = lambda: False
        window._update_qa_panel_status = lambda: None
        window.load_pdf_file(pdf_path)
        timer = QTimer(window)
        timer.setInterval(100)
        def verify_packaged_preview():
            states = [widget.diagnostic_state() for widget in (window.left_pdf_widget, window.right_pdf_widget)]
            if all(state.get("first_page_rendered") for state in states):
                if window.windowIcon().isNull() or app.windowIcon().isNull():
                    get_logger("startup").error("packaged_icon_missing")
                    app.exit(2)
                    return
                get_logger("startup").info("packaged_preview_verified states=%s", states)
                screenshot = os.environ.get("FREEPDF_SMOKE_SCREENSHOT")
                if screenshot:
                    window.grab().save(screenshot)
                timer.stop()
                for widget in (window.left_pdf_widget, window.right_pdf_widget):
                    widget.cleanup()
                # Let deferred browser/page destruction finish while its profile
                # and Qt event loop still exist.
                QTimer.singleShot(100, lambda: app.exit(0))
        timer.timeout.connect(verify_packaged_preview)
        timer.start()
        QTimer.singleShot(45000, lambda: app.exit(3))

    # 运行应用程序
    exit_code = app.exec()
    # Destroy widgets/profiles while QApplication is still alive. Letting SIP
    # choose their order at Python shutdown can leave WebEngine GPU callbacks
    # referring to an already destroyed Qt object on macOS.
    from PyQt6 import sip
    from PyQt6.QtCore import QEvent
    for widget in (window.left_pdf_widget, window.right_pdf_widget):
        widget.cleanup()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    sip.delete(window)
    sip.delete(app)
    sys.exit(exit_code)

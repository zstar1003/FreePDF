"""PDF翻译处理模块"""

import os
import sys
import time
import traceback
from io import StringIO

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

from utils.constants import (
    DEFAULT_LANG_IN,
    DEFAULT_LANG_OUT,
    DEFAULT_SERVICE,
    DEFAULT_THREADS,
)
from utils.config_path import get_config_file_path
from utils.translation_logger import get_translation_logger


class TranslationThread(QThread):
    """PDF翻译线程"""

    translation_progress = pyqtSignal(str)
    translation_completed = pyqtSignal(str)
    translation_failed = pyqtSignal(str)
    heartbeat_signal = pyqtSignal()  # 心跳信号

    def __init__(
        self,
        input_file,
        lang_in=DEFAULT_LANG_IN,
        lang_out=DEFAULT_LANG_OUT,
        service=DEFAULT_SERVICE,
        threads=DEFAULT_THREADS,
        parent=None,
    ):
        super().__init__(parent)
        self.input_file = input_file
        self.logger = get_translation_logger()

        # 尝试从配置文件加载翻译设置
        config = self._load_translation_config()
        self.lang_in = config.get("lang_in", lang_in)
        self.lang_out = config.get("lang_out", lang_out)
        self.service = config.get("service", service)
        self.envs = config.get("envs", {})
        self.pages = config.get("pages", "")  # 添加页面参数
        self.save_dual_file = config.get("save_dual_file", False)  # 添加双语文件配置
        self.logger.debug(f"加载的pages参数: '{self.pages}'")
        self.logger.debug(f"保存双语文件: {self.save_dual_file}")
        self.threads = threads
        self._stop_requested = False
        self._last_heartbeat_time = time.time()

    def _parse_page_ranges(self, page_string):
        """将页面范围字符串转换为整数数组（0-based索引）
        支持格式: "1-5,8,10-15" -> [0,1,2,3,4,7,9,10,11,12,13,14]
        用户输入的页码从1开始，但翻译接口需要从0开始的索引
        """
        if not page_string or not page_string.strip():
            return None

        pages = []
        try:
            # 分割逗号分隔的部分
            parts = page_string.strip().split(",")
            for part in parts:
                part = part.strip()
                if "-" in part:
                    # 处理范围，如 "1-5"
                    start, end = part.split("-", 1)
                    start = int(start.strip())
                    end = int(end.strip())
                    if start <= end and start >= 1:  # 确保页码从1开始
                        # 转换为0-based索引
                        pages.extend(range(start - 1, end))
                else:
                    # 处理单个页面
                    page_num = int(part)
                    if page_num >= 1:  # 确保页码从1开始
                        pages.append(page_num - 1)  # 转换为0-based索引

            # 去重并排序
            pages = sorted(list(set(pages)))
            self.logger.debug(f"解析页面范围: {page_string} -> {pages}")
            return pages

        except Exception as e:
            self.logger.error(f"页面范围解析错误: {e}")
            return None

    def _preprocess_pdf(self, input_file):
        """预处理PDF文件（保留接口但不再需要复杂处理）"""
        return input_file

    def _translate_with_safe_subset_fonts(self, translate_func, input_file, params):
        """使用安全的subset_fonts包装执行翻译

        通过monkey patch临时替换pymupdf的subset_fonts方法，
        使其在遇到'bad value'错误时静默跳过而不是抛出异常。
        """
        import pymupdf

        original_subset_fonts = pymupdf.Document.subset_fonts

        def safe_subset_fonts(self, *args, **kwargs):
            """安全的subset_fonts包装，捕获字体处理相关错误"""
            try:
                return original_subset_fonts(self, *args, **kwargs)
            except ValueError as e:
                error_str = str(e)
                if "bad 'value'" in error_str or "invalid literal for int()" in error_str:
                    get_translation_logger().warning(f"字体子集化时遇到错误，已跳过: {e}")
                    return None
                raise e
            except Exception as e:
                get_translation_logger().warning(f"字体子集化时遇到未知错误，已跳过: {e}")
                return None

        try:
            pymupdf.Document.subset_fonts = safe_subset_fonts
            self.logger.info("已启用安全字体子集化模式")

            from utils.translation_engine import translate_preserving_source
            result = translate_preserving_source(translate_func, input_file, params)
            return result
        finally:
            pymupdf.Document.subset_fonts = original_subset_fonts
            self.logger.debug("已恢复原始字体子集化方法")

    def _load_translation_config(self):
        """加载翻译配置"""
        import json
        logger = get_translation_logger()

        config_file = get_config_file_path()
        default_config = {
            "service": DEFAULT_SERVICE,
            "lang_in": DEFAULT_LANG_IN,
            "lang_out": DEFAULT_LANG_OUT,
            "envs": {},
            "pages": "",
            "save_dual_file": False,
        }

        try:
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    full_config = json.load(f)
                    if "translation" in full_config:
                        config = full_config["translation"]
                    else:
                        # 如果没有translation节点，从根节点读取
                        config = full_config

                    # 合并配置，确保所有必要的键都存在
                    result_config = default_config.copy()
                    result_config.update(config)

                    # 特别处理pages、translation_enabled和save_dual_file参数，优先从根节点读取
                    if "pages" in full_config:
                        result_config["pages"] = full_config["pages"]
                    if "translation_enabled" in full_config:
                        result_config["translation_enabled"] = full_config[
                            "translation_enabled"
                        ]
                    if "save_dual_file" in full_config:
                        result_config["save_dual_file"] = full_config["save_dual_file"]

                    logger.debug(f"加载翻译配置: service={result_config.get('service')}, lang_in={result_config.get('lang_in')}, lang_out={result_config.get('lang_out')}")
                    return result_config
        except Exception as e:
            logger.error(f"读取翻译配置失败: {e}")

        return default_config

    def stop(self):
        """停止翻译"""
        self._stop_requested = True
        self.logger.warning("收到停止翻译请求")

    def send_heartbeat(self):
        """发送心跳信号"""
        self._last_heartbeat_time = time.time()
        self.heartbeat_signal.emit()

    def _is_valid_pdf(self, file_path):
        """检查PDF文件是否有效"""
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"PDF文件不存在: {file_path}")
                return False

            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size < 1024:  # 小于1KB可能是无效文件
                self.logger.warning(f"PDF文件太小，可能无效: {file_size} bytes")
                return False

            # 尝试读取PDF文件头
            with open(file_path, "rb") as f:
                header = f.read(8)
                if not header.startswith(b"%PDF-"):
                    self.logger.error(f"PDF文件头无效: {header}")
                    return False

            # 尝试使用pikepdf打开PDF
            try:
                import pikepdf

                with pikepdf.open(file_path) as pdf:
                    page_count = len(pdf.pages)

                if page_count == 0:
                    self.logger.error("PDF文件页数为0")
                    return False

                self.logger.info(f"PDF文件有效，共{page_count}页")
                return True

            except Exception as e:
                self.logger.error(f"无法使用pikepdf打开PDF: {e}")
                return False

        except Exception as e:
            self.logger.error(f"检查PDF文件时出错: {e}")
            return False

    def run(self):
        """执行翻译"""
        # 保存原始的stdout和stderr
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        # 开始翻译日志
        self.logger.start_translation(self.input_file)

        try:
            # 改进的进度捕获类 - 同时支持exe和普通环境
            class _ProgressStdout:
                """捕获 stdout 中的 "xx%" 字样并发射进度百分比"""

                def __init__(self, delegate, emit_fn):
                    self._delegate = delegate
                    self._emit_fn = emit_fn
                    import re
                    self._pattern = re.compile(r"(\d{1,3})%")
                    self._last_percent = -1

                def write(self, s):
                    # 原始写入（无论是否exe环境都尝试写入）
                    try:
                        if self._delegate:
                            self._delegate.write(s)
                    except Exception:
                        pass

                    # tqdm 会频繁使用回车覆盖行，可能一次 write 中含多个百分比；取最后一个
                    if s:
                        matches = self._pattern.findall(s)
                        if matches:
                            try:
                                percent = int(matches[-1])
                                # 只在百分比变化时发信号，避免过度刷新
                                if percent != self._last_percent:
                                    self._last_percent = percent
                                    self._emit_fn(percent)
                            except Exception:
                                pass

                def flush(self):
                    try:
                        if self._delegate:
                            self._delegate.flush()
                    except Exception:
                        pass

            # 在exe环境中，需要特殊处理
            is_frozen = getattr(sys, "frozen", False)
            if is_frozen:
                self.logger.info("检测到exe打包环境")
                # 创建一个可以写入的StringIO作为delegate
                fake_stdout = StringIO()
                fake_stderr = StringIO()
            else:
                fake_stdout = original_stdout
                fake_stderr = original_stderr

            # 进度发射函数
            def progress_emit(p):
                self.send_heartbeat()  # 在进度更新时发送心跳
                self.logger.progress(p)
                return self.translation_progress.emit(f"PROGRESS:{p}")

            # 包装stdout和stderr
            sys.stdout = _ProgressStdout(fake_stdout, progress_emit)
            sys.stderr = _ProgressStdout(fake_stderr, progress_emit)

            if self._stop_requested:
                self.logger.warning("翻译在启动前被取消")
                return

            # 阶段1: 准备翻译环境
            self.logger.start_stage("准备翻译环境")
            self.translation_progress.emit("正在准备翻译环境...")
            self.send_heartbeat()

            # 检查输入文件
            if not os.path.exists(self.input_file):
                error_msg = f"输入文件不存在: {self.input_file}"
                self.logger.error(error_msg)
                self.logger.end_translation(False, error_msg)
                self.translation_failed.emit(error_msg)
                return

            self.logger.info(f"输入文件: {self.input_file}")
            self.logger.info(f"文件大小: {os.path.getsize(self.input_file)} bytes")

            # 获取预加载的pdf2zh模块
            from main import get_pdf2zh_modules

            modules, config = get_pdf2zh_modules()

            if modules is None or config is None:
                error_msg = "pdf2zh模块未正确预加载，请重启应用程序"
                self.logger.error(error_msg)
                self.logger.end_translation(False, error_msg)
                self.translation_failed.emit(error_msg)
                return

            self.logger.info(f"翻译服务: {self.service}")
            self.logger.info(f"源语言: {self.lang_in}, 目标语言: {self.lang_out}")

            # 检查超时
            is_timeout, elapsed = self.logger.check_timeout()
            if is_timeout:
                error_msg = f"翻译超时（已运行{elapsed:.0f}秒）"
                self.logger.end_translation(False, error_msg)
                self.translation_failed.emit(error_msg)
                return

            if self._stop_requested:
                self.logger.warning("翻译被用户取消")
                return

            # 阶段2: 加载AI模型
            self.logger.start_stage("加载AI模型")
            self.translation_progress.emit("正在加载AI模型...")
            self.send_heartbeat()

            try:
                # 使用预加载的模块
                translate = modules["translate"]
                OnnxModel = modules["OnnxModel"]

                # 加载模型
                model_path = config["models"]["doclayout_path"]
                self.logger.info(f"模型路径: {model_path}")
                model = OnnxModel(model_path)

                if model is None:
                    error_msg = "无法加载AI模型，请检查模型文件"
                    self.logger.error(error_msg)
                    self.logger.end_translation(False, error_msg)
                    self.translation_failed.emit(error_msg)
                    return

                self.logger.info("AI模型加载成功")
                self.send_heartbeat()

            except Exception as e:
                error_msg = f"加载AI模型失败: {str(e)}"
                self.logger.error(error_msg)
                self.logger.error(traceback.format_exc())
                self.logger.end_translation(False, error_msg)
                self.translation_failed.emit(error_msg)
                return

            # 检查超时
            is_timeout, elapsed = self.logger.check_timeout()
            if is_timeout:
                error_msg = f"翻译超时（已运行{elapsed:.0f}秒）"
                self.logger.end_translation(False, error_msg)
                self.translation_failed.emit(error_msg)
                return

            if self._stop_requested:
                self.logger.warning("翻译被用户取消")
                return

            # 阶段3: 预处理PDF
            self.logger.start_stage("预处理PDF文档")
            self.translation_progress.emit("正在检查并预处理PDF文档...")
            self.send_heartbeat()

            # 预处理PDF文件，修复可能导致字体问题的文件
            processed_input_file = self._preprocess_pdf(self.input_file)

            if self._stop_requested:
                self.logger.warning("翻译被用户取消")
                return

            # 阶段4: 执行翻译
            self.logger.start_stage("执行PDF翻译")
            self.translation_progress.emit("正在翻译PDF文档\n请稍候...")
            self.send_heartbeat()

            try:
                # 获取输入文件所在目录作为输出目录
                input_dir = os.path.dirname(os.path.abspath(self.input_file))
                self.logger.info(f"输出目录: {input_dir}")

                # 设置翻译参数
                # 根据目标语言选择合适的字体
                font_path = config["fonts"].get(
                    self.lang_out, config["fonts"].get("default")
                )
                # 处理字体路径，确保在Windows系统上路径正确
                if font_path:
                    # 获取绝对路径并转换为正斜杠格式
                    font_path = os.path.abspath(font_path).replace("\\", "/")
                    self.logger.info(f"字体路径: {font_path}")

                # 映射服务名称：将"自定义"映射为pdf2zh支持的"openai"
                service_name = self.service
                if service_name == "自定义":
                    service_name = "openai"

                params = {
                    "model": model,
                    "lang_in": self.lang_in,
                    "lang_out": self.lang_out,
                    "service": service_name,
                    "thread": self.threads,
                    "vfont": font_path,
                    "output": input_dir,  # 设置输出目录为输入文件所在目录
                    "envs": self.envs,  # 添加环境变量
                }

                # 添加页面参数 - 转换页面范围字符串为整数数组
                if self.pages:
                    parsed_pages = self._parse_page_ranges(self.pages)
                    if parsed_pages:
                        params["pages"] = parsed_pages
                        self.logger.info(f"自定义翻译页面: {self.pages} -> {parsed_pages}")
                    else:
                        self.logger.warning(f"页面范围格式错误，将翻译所有页面: {self.pages}")
                else:
                    self.logger.info("翻译所有页面")

                self.logger.info(f"翻译参数: service={service_name}, thread={self.threads}")
                self.send_heartbeat()

                # 执行翻译，使用安全的subset_fonts包装
                self.logger.info("开始调用翻译引擎...")
                result = self._translate_with_safe_subset_fonts(
                    translate, processed_input_file, params
                )
                self.logger.info(f"翻译引擎返回结果: {result}")
                self.send_heartbeat()

                # 如果使用了临时文件，在翻译完成后清理
                if processed_input_file != self.input_file:
                    try:
                        os.remove(processed_input_file)
                        self.logger.debug(f"已清理临时文件: {processed_input_file}")
                    except Exception as cleanup_error:
                        self.logger.warning(f"清理临时文件失败: {cleanup_error}")

                if result and len(result) > 0:
                    file_mono, file_dual = result[0]
                    self.logger.info(f"翻译输出文件: mono={file_mono}, dual={file_dual}")
                    if self.save_dual_file and file_mono and file_dual:
                        from utils.pdf_export import export_pdf
                        export_pdf(self.input_file, file_mono, file_dual)
                        self.logger.info("已保存逐页左右对照 PDF")

                    if self._stop_requested:
                        self.logger.warning("翻译被用户取消")
                        return

                    # 根据配置决定是否保留双语文件
                    self.logger.debug(f"双语文件处理 - save_dual_file: {self.save_dual_file}")
                    if (
                        not self.save_dual_file
                        and file_dual
                        and os.path.exists(file_dual)
                    ):
                        try:
                            os.remove(file_dual)
                            self.logger.info(f"已删除双语文件: {file_dual}")
                            file_dual = None  # 设置为None，避免后续使用
                        except Exception as e:
                            self.logger.warning(f"删除双语文件失败: {e}")
                    elif self.save_dual_file:
                        self.logger.info(f"保留双语文件: {file_dual}")

                    # 检查文件是否存在和有效性
                    result_file = None
                    if (
                        file_mono
                        and os.path.exists(file_mono)
                        and self._is_valid_pdf(file_mono)
                    ):
                        result_file = file_mono
                        self.logger.info(f"使用单语版本: {file_mono}")
                    elif (
                        file_dual
                        and os.path.exists(file_dual)
                        and self._is_valid_pdf(file_dual)
                    ):
                        result_file = file_dual
                        self.logger.info(f"使用双语版本: {file_dual}")

                    if result_file:
                        self.logger.end_translation(True)
                        self.translation_completed.emit(os.path.abspath(result_file))
                    else:
                        error_msg = "翻译完成但生成的PDF文件无效或无法找到"
                        self.logger.error(error_msg)
                        self.logger.end_translation(False, error_msg)
                        self.translation_failed.emit(error_msg)
                else:
                    error_msg = "翻译结果为空"
                    self.logger.error(error_msg)
                    self.logger.end_translation(False, error_msg)
                    self.translation_failed.emit(error_msg)

            except Exception as e:
                error_msg = f"翻译过程中出错: {str(e)}"
                self.logger.error(error_msg)
                self.logger.error(traceback.format_exc())
                self.logger.end_translation(False, error_msg)
                self.translation_failed.emit(error_msg)

        except Exception as e:
            error_msg = f"翻译线程异常: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            self.logger.end_translation(False, error_msg)
            self.translation_failed.emit(error_msg)
        finally:
            # 恢复原始的stdout和stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr


class TranslationManager(QObject):
    """翻译管理器"""

    # 超时信号
    translation_timeout = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_thread = None
        self.translated_files = {}
        self.logger = get_translation_logger()

        # 超时检测定时器
        self._timeout_timer = QTimer(self)
        self._timeout_timer.timeout.connect(self._check_timeout)
        self._timeout_check_interval = 5000  # 5秒检查一次

        # 心跳检测
        self._last_heartbeat_time = 0
        self._heartbeat_timeout = 120  # 心跳超时时间（秒），如果超过这个时间没有心跳则认为卡住

        # 失败回调存储
        self._failed_callback = None

    def _on_heartbeat(self):
        """接收心跳信号"""
        self._last_heartbeat_time = time.time()
        self.logger.debug("收到心跳信号")

    def _check_timeout(self):
        """检查是否超时"""
        if not self.current_thread or not self.current_thread.isRunning():
            self._timeout_timer.stop()
            return

        # 检查翻译总超时
        is_timeout, elapsed = self.logger.check_timeout()
        if is_timeout:
            self.logger.error(f"翻译超时！已运行 {elapsed:.0f} 秒")
            self._handle_timeout(f"翻译超时（已运行{elapsed:.0f}秒），请检查网络连接或翻译服务配置")
            return

        # 检查心跳超时（如果长时间没有心跳，可能卡住了）
        if self._last_heartbeat_time > 0:
            heartbeat_elapsed = time.time() - self._last_heartbeat_time
            if heartbeat_elapsed > self._heartbeat_timeout:
                self.logger.error(f"心跳超时！距离上次心跳已 {heartbeat_elapsed:.0f} 秒")
                self._handle_timeout(f"翻译进程可能已卡住（{heartbeat_elapsed:.0f}秒无响应），建议停止并重试")
                return

        # 记录当前状态
        self.logger.debug(f"超时检查: 已运行 {elapsed:.0f}秒, 距上次心跳 {time.time() - self._last_heartbeat_time:.0f}秒")

    def _handle_timeout(self, message):
        """处理超时"""
        self._timeout_timer.stop()
        self.translation_timeout.emit(message)
        # 不自动停止，让用户决定

    def start_translation(
        self,
        input_file,
        progress_callback=None,
        completed_callback=None,
        failed_callback=None,
    ):
        """开始翻译"""
        # 停止当前翻译
        self.stop_current_translation()

        # 检查输入文件
        if not os.path.exists(input_file):
            if failed_callback:
                failed_callback(f"输入文件不存在: {input_file}")
            return

        # 存储失败回调
        self._failed_callback = failed_callback

        # 创建新的翻译线程
        self.current_thread = TranslationThread(input_file, parent=self)

        # 连接信号
        if progress_callback:
            self.current_thread.translation_progress.connect(progress_callback)
        if completed_callback:
            self.current_thread.translation_completed.connect(self._on_completed_wrapper(completed_callback))
        if failed_callback:
            self.current_thread.translation_failed.connect(self._on_failed_wrapper(failed_callback))

        # 连接心跳信号
        self.current_thread.heartbeat_signal.connect(self._on_heartbeat)

        # 重置心跳时间
        self._last_heartbeat_time = time.time()

        # 启动超时检测定时器
        self._timeout_timer.start(self._timeout_check_interval)

        # 启动翻译
        self.logger.info("启动翻译线程")
        self.current_thread.start()

    def _on_completed_wrapper(self, callback):
        """完成回调包装器"""
        def wrapper(result):
            self._timeout_timer.stop()
            self.logger.info("翻译线程完成")
            if callback:
                callback(result)
        return wrapper

    def _on_failed_wrapper(self, callback):
        """失败回调包装器"""
        def wrapper(error):
            self._timeout_timer.stop()
            self.logger.error(f"翻译线程失败: {error}")
            if callback:
                callback(error)
        return wrapper

    def stop_current_translation(self):
        """停止当前翻译"""
        # 停止超时检测
        self._timeout_timer.stop()

        if self.current_thread and self.current_thread.isRunning():
            self.logger.warning("正在停止翻译线程...")
            self.current_thread.stop()
            # 给线程一些时间正常退出
            if not self.current_thread.wait(3000):  # 等待3秒
                self.logger.warning("线程未响应，强制终止")
                self.current_thread.terminate()
                self.current_thread.wait(1000)  # 等待1秒确保终止

        # 清理线程对象
        if self.current_thread:
            self.current_thread.deleteLater()
            self.current_thread = None

    def is_translating(self):
        """是否正在翻译"""
        return self.current_thread and self.current_thread.isRunning()

    def get_translated_file(self, original_file):
        """获取翻译后的文件路径"""
        return self.translated_files.get(original_file)

    def set_translated_file(self, original_file, translated_file):
        """设置翻译后的文件路径"""
        self.translated_files[original_file] = translated_file

    def cleanup(self):
        """清理资源"""
        self.stop_current_translation()

        # 清理临时翻译文件
        # for translated_file in self.translated_files.values():
        #     try:
        #         if os.path.exists(translated_file):
        #             os.remove(translated_file)
        #     except:
        #         pass

        self.translated_files.clear()

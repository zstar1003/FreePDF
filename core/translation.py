"""PDF翻译处理模块"""

import os
import sys
import traceback
from io import StringIO

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from utils.constants import (
    DEFAULT_LANG_IN,
    DEFAULT_LANG_OUT,
    DEFAULT_SERVICE,
    DEFAULT_THREADS,
)


class TranslationThread(QThread):
    """PDF翻译线程"""
    translation_progress = pyqtSignal(str)
    translation_completed = pyqtSignal(str)
    translation_failed = pyqtSignal(str)
    
    def __init__(self, input_file, lang_in=DEFAULT_LANG_IN, lang_out=DEFAULT_LANG_OUT, 
                 service=DEFAULT_SERVICE, threads=DEFAULT_THREADS, parent=None):
        super().__init__(parent)
        self.input_file = input_file
        
        # 尝试从配置文件加载翻译设置
        config = self._load_translation_config()
        self.lang_in = config.get('lang_in', lang_in)
        self.lang_out = config.get('lang_out', lang_out)
        self.service = config.get('service', service)
        self.envs = config.get('envs', {})
        self.pages = config.get('pages', '')  # 添加页面参数
        print(f"DEBUG: 加载的pages参数: '{self.pages}'")
        self.threads = threads
        self._stop_requested = False
        
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
            parts = page_string.strip().split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # 处理范围，如 "1-5"
                    start, end = part.split('-', 1)
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
            return pages
            
        except (ValueError, IndexError) as e:
            print(f"页面范围解析错误: {e}")
            return None

    def _load_translation_config(self):
        """加载翻译配置"""
        import json
        config_file = "pdf2zh_config.json"
        default_config = {
            "service": DEFAULT_SERVICE,
            "lang_in": DEFAULT_LANG_IN,
            "lang_out": DEFAULT_LANG_OUT,
            "envs": {},
            "pages": ""
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
                    if "translation" in full_config:
                        config = full_config["translation"]
                    else:
                        # 如果没有translation节点，从根节点读取
                        config = full_config
                    
                    # 合并配置，确保所有必要的键都存在
                    result_config = default_config.copy()
                    result_config.update(config)
                    
                    # 特别处理pages和translation_enabled参数，优先从根节点读取
                    if "pages" in full_config:
                        result_config["pages"] = full_config["pages"]
                    if "translation_enabled" in full_config:
                        result_config["translation_enabled"] = full_config["translation_enabled"]
                    
                    return result_config
        except Exception as e:
            print(f"读取翻译配置失败: {e}")
            
        return default_config
        
    def stop(self):
        """停止翻译"""
        self._stop_requested = True
        
    def _is_valid_pdf(self, file_path):
        """检查PDF文件是否有效"""
        try:
            if not os.path.exists(file_path):
                return False
            
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size < 1024:  # 小于1KB可能是无效文件
                print(f"PDF文件太小，可能无效: {file_size} bytes")
                return False
            
            # 尝试读取PDF文件头
            with open(file_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF-'):
                    print(f"PDF文件头无效: {header}")
                    return False
            
            # 尝试使用pikepdf打开PDF
            try:
                import pikepdf
                with pikepdf.open(file_path) as pdf:
                    page_count = len(pdf.pages)
                
                if page_count == 0:
                    print("PDF文件页数为0")
                    return False
                
                print(f"PDF文件有效，共{page_count}页")
                return True
                
            except Exception as e:
                print(f"无法使用pikepdf打开PDF: {e}")
                return False
                
        except Exception as e:
            print(f"检查PDF文件时出错: {e}")
            return False
        
    def run(self):
        """执行翻译"""
        # 保存原始的stdout和stderr
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            # 在exe环境中，重定向stdout和stderr到StringIO对象
            if getattr(sys, 'frozen', False):  # 检查是否在PyInstaller打包的exe环境中
                fake_stdout = StringIO()
                fake_stderr = StringIO()
                sys.stdout = fake_stdout
                sys.stderr = fake_stderr
                print("在exe环境中运行，已重定向标准输出")

            # 包装 stdout 以捕获 tqdm 等进度输出并通过 Qt 信号上报
            class _ProgressStdout:
                """捕获 stdout 中的 "xx%" 字样并发射进度百分比"""
                def __init__(self, delegate, emit_fn):
                    self._delegate = delegate
                    self._emit_fn = emit_fn
                    import re
                    self._pattern = re.compile(r"(\d{1,3})%")
                    self._last_percent = -1
                def write(self, s):
                    # 原始写入
                    try:
                        self._delegate.write(s)
                    except Exception:
                        pass
                    # tqdm 会频繁使用回车覆盖行，可能一次 write 中含多个百分比；取最后一个
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
                        self._delegate.flush()
                    except Exception:
                        pass

            # 将 sys.stdout / sys.stderr 再包装一层，用于进度捕获
            progress_emit = lambda p: self.translation_progress.emit(f"PROGRESS:{p}")
            sys.stdout = _ProgressStdout(sys.stdout, progress_emit)
            sys.stderr = _ProgressStdout(sys.stderr, progress_emit)
            
            if self._stop_requested:
                return
                
            self.translation_progress.emit("正在准备翻译环境...")
            
            # 检查输入文件
            if not os.path.exists(self.input_file):
                self.translation_failed.emit(f"输入文件不存在: {self.input_file}")
                return
            
            # 获取预加载的pdf2zh模块
            from main import get_pdf2zh_modules
            modules, config = get_pdf2zh_modules()
            
            if modules is None or config is None:
                self.translation_failed.emit("pdf2zh模块未正确预加载，请重启应用程序")
                return
            
            print(f"开始翻译文件: {self.input_file}")
            
            if self._stop_requested:
                return
            
            self.translation_progress.emit("正在加载AI模型...")
            
            try:
                # 使用预加载的模块
                translate = modules['translate']
                OnnxModel = modules['OnnxModel']
                
                # 加载模型
                model_path = config['models']['doclayout_path']
                model = OnnxModel(model_path)
                
                if model is None:
                    self.translation_failed.emit("无法加载AI模型，请检查模型文件")
                    return
                    
                print("AI模型加载成功")
                
            except Exception as e:
                error_msg = f"加载AI模型失败: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                self.translation_failed.emit(error_msg)
                return
            
            if self._stop_requested:
                return
                
            self.translation_progress.emit("正在翻译PDF文档\n请稍候...")
            
            try:
                # 获取输入文件所在目录作为输出目录
                input_dir = os.path.dirname(os.path.abspath(self.input_file))
                print(f"输出目录设置为: {input_dir}")
                
                # 设置翻译参数  
                # 根据目标语言选择合适的字体
                font_path = config['fonts'].get(self.lang_out, config['fonts'].get('default'))
                # 处理字体路径，确保在Windows系统上不会产生正则表达式错误
                if font_path:
                    # 获取绝对路径并转换为正斜杠格式  
                    font_path = os.path.abspath(font_path).replace('\\', '/')
                    # 转义正则表达式特殊字符，防止被误解为正则表达式模式
                    import re
                    font_path = re.escape(font_path)
                    print(f"目标语言: {self.lang_out}, 处理后的字体路径: {font_path}")
                
                params = {
                    "model": model,
                    "lang_in": self.lang_in,
                    "lang_out": self.lang_out,
                    "service": self.service,
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
                        print(f"自定义翻译页面: {self.pages} -> {parsed_pages}")
                    else:
                        print(f"页面范围格式错误，将翻译所有页面: {self.pages}")
                else:
                    print("翻译所有页面")
                
                print(f"翻译参数: {params}")
                print(f"翻译文件: {self.input_file}")
                
                # 执行翻译
                result = translate(files=[self.input_file], **params)
                print(f"翻译结果: {result}")
                
                if result and len(result) > 0:
                    file_mono, file_dual = result[0]
                    print(f"翻译输出文件: mono={file_mono}, dual={file_dual}")
                    
                    if self._stop_requested:
                        return
 
                    # 检查文件是否存在和有效性
                    result_file = None
                    if file_mono and os.path.exists(file_mono) and self._is_valid_pdf(file_mono):
                        result_file = file_mono
                        print(f"使用单语版本: {file_mono}")
                    elif file_dual and os.path.exists(file_dual) and self._is_valid_pdf(file_dual):
                        result_file = file_dual
                        print(f"使用双语版本: {file_dual}")
                    
                    if result_file:
                        self.translation_completed.emit(os.path.abspath(result_file))
                    else:
                        error_msg = "翻译完成但生成的PDF文件无效或无法找到"
                        print(error_msg)
                        self.translation_failed.emit(error_msg)
                else:
                    self.translation_failed.emit("翻译结果为空")
                    
            except Exception as e:
                error_msg = f"翻译过程中出错: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                self.translation_failed.emit(error_msg)
                
        except Exception as e:
            error_msg = f"翻译线程异常: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.translation_failed.emit(error_msg)
        finally:
            # 恢复原始的stdout和stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr


class TranslationManager(QObject):
    """翻译管理器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_thread = None
        self.translated_files = {}
        
    def start_translation(self, input_file, progress_callback=None, 
                         completed_callback=None, failed_callback=None):
        """开始翻译"""
        # 停止当前翻译
        self.stop_current_translation()
        
        # 检查输入文件
        if not os.path.exists(input_file):
            if failed_callback:
                failed_callback(f"输入文件不存在: {input_file}")
            return
        
        # 创建新的翻译线程
        self.current_thread = TranslationThread(input_file, parent=self)
        
        # 连接信号
        if progress_callback:
            self.current_thread.translation_progress.connect(progress_callback)
        if completed_callback:
            self.current_thread.translation_completed.connect(completed_callback)
        if failed_callback:
            self.current_thread.translation_failed.connect(failed_callback)
            
        # 启动翻译
        self.current_thread.start()
        
    def stop_current_translation(self):
        """停止当前翻译"""
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.stop()
            # 给线程一些时间正常退出
            if not self.current_thread.wait(3000):  # 等待3秒
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
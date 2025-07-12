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

# 全局缓存，避免重复导入main模块
_MAIN_MODULE = None

def get_main_module():
    """获取main模块，只导入一次"""
    global _MAIN_MODULE
    if _MAIN_MODULE is None:
        import main
        _MAIN_MODULE = main
    return _MAIN_MODULE


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
        self.threads = threads
        self._stop_requested = False
        
    def _load_translation_config(self):
        """加载翻译配置"""
        import json
        config_file = "pdf2zh_config.json"
        default_config = {
            "service": DEFAULT_SERVICE,
            "lang_in": DEFAULT_LANG_IN,
            "lang_out": DEFAULT_LANG_OUT,
            "envs": {}
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
                    if "translation" in full_config:
                        return full_config["translation"]
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
            
            # 简单检查PDF文件头 - 不使用fitz
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(8)
                    if not header.startswith(b'%PDF-'):
                        print(f"PDF文件头无效: {header}")
                        return False
                
                print(f"PDF文件有效，大小: {file_size} bytes")
                return True
                
            except Exception as e:
                print(f"无法读取PDF文件: {e}")
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
                """捕获 stdout 中的进度信息并发射进度百分比"""
                def __init__(self, delegate, emit_fn):
                    self._delegate = delegate
                    self._emit_fn = emit_fn
                    import re
                    # 支持多种进度格式: "xx%", "xx/100", "xxx/xxx"
                    self._percent_pattern = re.compile(r"(\d{1,3})%")
                    self._fraction_pattern = re.compile(r"(\d+)/(\d+)")
                    self._last_percent = -1
                def write(self, s):
                    # 原始写入并立即刷新
                    try:
                        self._delegate.write(s)
                        self._delegate.flush()  # 立即刷新输出
                    except Exception:
                        pass
                    
                    # 先尝试匹配百分比格式
                    percent_matches = self._percent_pattern.findall(s)
                    if percent_matches:
                        try:
                            percent = int(percent_matches[-1])
                            if percent != self._last_percent:
                                self._last_percent = percent
                                self._emit_fn(percent)
                                # 处理Qt事件，确保信号立即发送
                                from PyQt6.QtCore import QCoreApplication
                                QCoreApplication.processEvents()
                        except Exception:
                            pass
                    else:
                        # 再尝试匹配分数格式
                        fraction_matches = self._fraction_pattern.findall(s)
                        if fraction_matches:
                            try:
                                current, total = map(int, fraction_matches[-1])
                                if total > 0:
                                    percent = int((current / total) * 100)
                                    if percent != self._last_percent:
                                        self._last_percent = percent
                                        self._emit_fn(percent)
                                        # 处理Qt事件，确保信号立即发送
                                        from PyQt6.QtCore import QCoreApplication
                                        QCoreApplication.processEvents()
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
            main_module = get_main_module()
            modules, config = main_module.get_pdf2zh_modules()
            
            if modules is None or config is None:
                self.translation_failed.emit("pdf2zh模块未正确预加载，请重启应用程序")
                return
            
            print(f"开始翻译文件: {self.input_file}")
            
            if self._stop_requested:
                return
            
            self.translation_progress.emit("正在准备翻译...")
            
            if self._stop_requested:
                return
                
            self.translation_progress.emit("正在翻译PDF文档\n请稍候...")
            
            try:
                try:
                    # 使用新的API
                    do_translate_file = modules['do_translate_file']
                    SettingsModel = modules['SettingsModel']
                    
                    # 获取输入文件所在目录作为输出目录
                    input_dir = os.path.dirname(os.path.abspath(self.input_file))
                    print(f"输出目录设置为: {input_dir}")
                    
                    # 根据目标语言选择合适的字体
                    font_path = config['fonts'].get(self.lang_out, config['fonts'].get('default'))
                    if font_path:
                        font_path = os.path.abspath(font_path)
                        print(f"目标语言: {self.lang_out}, 字体路径: {font_path}")
                    
                    # 创建配置对象
                    translate_engine_settings = config.get('translation', {})
                    # 将服务名转换为正确的格式（首字母大写）
                    service_name = translate_engine_settings.get('service', self.service)
                    service_mapping = {
                        'bing': 'Bing',
                        'google': 'Google',
                        'openai': 'OpenAI',
                        'deepl': 'DeepL',
                        'deepseek': 'DeepSeek',
                        'ollama': 'Ollama',
                        'xinference': 'Xinference',
                        'azureopenai': 'AzureOpenAI',
                        'modelscope': 'ModelScope',
                        'zhipu': 'Zhipu',
                        'siliconflow': 'SiliconFlow',
                        'tencentmechinetranslation': 'TencentMechineTranslation',
                        'gemini': 'Gemini',
                        'azure': 'Azure',
                        'anythingllm': 'AnythingLLM',
                        'dify': 'Dify',
                        'grok': 'Grok',
                        'groq': 'Groq',
                        'qwenmt': 'QwenMt',
                        'openaicompatible': 'OpenAICompatible'
                    }
                    translate_engine_settings['translate_engine_type'] = service_mapping.get(service_name.lower(), 'Bing')
                    
                    settings = SettingsModel(
                        layout_model_path=config['models']['doclayout_path'],
                        lang_in=self.lang_in,
                        lang_out=self.lang_out,
                        service=self.service,
                        thread_count=self.threads,
                        font_path=font_path,
                        output_dir=input_dir,
                        envs=self.envs,
                        translate_engine_settings=translate_engine_settings
                    )
                    
                    print(f"翻译配置: {settings}")
                    print(f"翻译文件: {self.input_file}")
                    
                    # 执行翻译 - 新API返回错误数量而非文件路径
                    # 设置输入文件到settings中
                    settings.basic.input_files = {self.input_file}
                    error_count = do_translate_file(settings)
                    print(f"翻译完成，错误数量: {error_count}")
                    
                    # 根据文件名推断输出文件路径 - 支持新的文件名格式
                    base_name = os.path.splitext(os.path.basename(self.input_file))[0]
                    
                    # 语言代码映射
                    lang_code_map = {
                        "zh": "zh",
                        "en": "en", 
                        "ja": "ja",
                        "ko": "ko",
                        "zh-TW": "zh-TW"
                    }
                    
                    # 获取目标语言代码
                    lang_code = lang_code_map.get(self.lang_out, self.lang_out)
                    
                    # 尝试新格式: 原文件名.语言代码.mono.pdf / 原文件名.语言代码.dual.pdf
                    file_mono_new = os.path.join(input_dir, f"{base_name}.{lang_code}.mono.pdf")
                    file_dual_new = os.path.join(input_dir, f"{base_name}.{lang_code}.dual.pdf")
                    
                    # 兼容旧格式: 原文件名-mono.pdf / 原文件名-dual.pdf
                    file_mono_old = os.path.join(input_dir, f"{base_name}-mono.pdf")
                    file_dual_old = os.path.join(input_dir, f"{base_name}-dual.pdf")
                    
                    print(f"预期输出文件: ")
                    print(f"  新格式mono: {file_mono_new}")
                    print(f"  新格式dual: {file_dual_new}")
                    print(f"  旧格式mono: {file_mono_old}")
                    print(f"  旧格式dual: {file_dual_old}")
                    
                    # 检查文件是否生成成功
                    result_found = False
                    
                    if self._stop_requested:
                        return
 
                    # 检查文件是否存在和有效性 - 优先检查新格式
                    result_file = None
                    
                    # 详细检查每个可能的文件
                    print("开始检查生成的PDF文件...")
                    
                    # 先检查新格式文件
                    print(f"检查新格式mono文件: {file_mono_new}")
                    if os.path.exists(file_mono_new):
                        print(f"  文件存在，大小: {os.path.getsize(file_mono_new)} bytes")
                        if self._is_valid_pdf(file_mono_new):
                            result_file = file_mono_new
                            result_found = True
                            print(f"使用新格式单语版本: {file_mono_new}")
                        else:
                            print(f"  文件无效")
                    else:
                        print(f"  文件不存在")
                    
                    if not result_found:
                        print(f"检查新格式dual文件: {file_dual_new}")
                        if os.path.exists(file_dual_new):
                            print(f"  文件存在，大小: {os.path.getsize(file_dual_new)} bytes")
                            if self._is_valid_pdf(file_dual_new):
                                result_file = file_dual_new
                                result_found = True
                                print(f"使用新格式双语版本: {file_dual_new}")
                            else:
                                print(f"  文件无效")
                        else:
                            print(f"  文件不存在")
                    
                    # 再检查旧格式文件作为兼容
                    if not result_found:
                        print(f"检查旧格式mono文件: {file_mono_old}")
                        if os.path.exists(file_mono_old):
                            print(f"  文件存在，大小: {os.path.getsize(file_mono_old)} bytes")
                            if self._is_valid_pdf(file_mono_old):
                                result_file = file_mono_old
                                result_found = True
                                print(f"使用旧格式单语版本: {file_mono_old}")
                            else:
                                print(f"  文件无效")
                        else:
                            print(f"  文件不存在")
                    
                    if not result_found:
                        print(f"检查旧格式dual文件: {file_dual_old}")
                        if os.path.exists(file_dual_old):
                            print(f"  文件存在，大小: {os.path.getsize(file_dual_old)} bytes")
                            if self._is_valid_pdf(file_dual_old):
                                result_file = file_dual_old
                                result_found = True
                                print(f"使用旧格式双语版本: {file_dual_old}")
                            else:
                                print(f"  文件无效")
                        else:
                            print(f"  文件不存在")
                    
                    if result_found and result_file:
                        self.translation_completed.emit(os.path.abspath(result_file))
                    elif error_count == 0:
                        # 翻译成功但找不到输出文件，可能是文件名格式变化
                        error_msg = "翻译完成但生成的PDF文件无法找到，请检查输出目录"
                        print(error_msg)
                        self.translation_failed.emit(error_msg)
                    else:
                        error_msg = f"翻译过程中发生 {error_count} 个错误"
                        print(error_msg)
                        self.translation_failed.emit(error_msg)
                        
                except Exception as api_error:
                    error_msg = f"调用新API失败: {str(api_error)}\n{traceback.format_exc()}"
                    print(error_msg)
                    self.translation_failed.emit(error_msg)
                    return
                    
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
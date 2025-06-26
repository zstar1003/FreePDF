"""PDF翻译处理模块"""

import json
import os
import traceback

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
        self.lang_in = lang_in
        self.lang_out = lang_out
        self.service = service
        self.threads = threads
        self._stop_requested = False
        
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
            
            # 尝试使用fitz打开PDF
            try:
                import fitz
                doc = fitz.open(file_path)
                page_count = doc.page_count
                doc.close()
                
                if page_count == 0:
                    print("PDF文件页数为0")
                    return False
                
                print(f"PDF文件有效，共{page_count}页")
                return True
                
            except Exception as e:
                print(f"无法使用fitz打开PDF: {e}")
                return False
                
        except Exception as e:
            print(f"检查PDF文件时出错: {e}")
            return False
        
    def run(self):
        """执行翻译"""
        try:
            if self._stop_requested:
                return
                
            self.translation_progress.emit("正在初始化翻译模块...")
            
            # 检查输入文件
            if not os.path.exists(self.input_file):
                self.translation_failed.emit(f"输入文件不存在: {self.input_file}")
                return
            
            print(f"开始翻译文件: {self.input_file}")
            
            # 导入pdf2zh模块
            try:
                print("正在导入pdf2zh模块...")
                from pdf2zh import translate
                from pdf2zh.config import ConfigManager
                from pdf2zh.doclayout import OnnxModel
                # 加载配置
                with open('pdf2zh_config.json', 'r') as f:
                    config = json.load(f)

                # 应用配置
                for key, value in config.items():
                    if key not in ['models', 'fonts']:
                        ConfigManager.set(key, value)

                # 设置模型
                model_path = config['models']['doclayout_path']

                # 设置字体
                font_path = config['fonts']['zh']
                ConfigManager.set("NOTO_FONT_PATH", font_path)
                
                print("pdf2zh模块导入成功")
                
            except ImportError as e:
                error_msg = f"导入pdf2zh模块失败: {str(e)}\n请检查依赖安装是否完整"
                print(error_msg)
                self.translation_failed.emit(error_msg)
                return
            except Exception as e:
                error_msg = f"导入pdf2zh模块时发生错误: {str(e)}"
                print(error_msg)
                self.translation_failed.emit(error_msg)
                return
            
            if self._stop_requested:
                return
            
            self.translation_progress.emit("正在加载AI模型...")
            
            try:
                print("开始加载OnnxModel...")
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
                
            self.translation_progress.emit("正在翻译PDF文档，请稍候...")
            
            try:
                # 获取输入文件所在目录作为输出目录
                input_dir = os.path.dirname(os.path.abspath(self.input_file))
                print(f"输出目录设置为: {input_dir}")
                
                # 设置翻译参数（参考test_api.py）
                params = {
                    "model": model,
                    "lang_in": self.lang_in,
                    "lang_out": self.lang_out,
                    "service": self.service,
                    "thread": self.threads,
                    "output": input_dir,  # 设置输出目录为输入文件所在目录
                }
                
                print(f"翻译参数: {params}")
                print(f"翻译文件: {self.input_file}")
                
                # 执行翻译（参考test_api.py）
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
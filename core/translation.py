"""PDF翻译处理模块"""

import os
import sys
import tempfile
import traceback
import subprocess
import json
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from utils.constants import *


class TranslationThread(QThread):
    """PDF翻译线程"""
    translation_progress = pyqtSignal(str)  # 进度信息
    translation_completed = pyqtSignal(str)  # 翻译完成，传递翻译后文件路径
    translation_failed = pyqtSignal(str)  # 翻译失败，传递错误信息
    
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
            
            if self._stop_requested:
                return
            
            self.translation_progress.emit("正在加载AI模型...")
            
            if self._stop_requested:
                return
                
            self.translation_progress.emit("正在翻译PDF文档，请稍候...")
            
            try:
                # 使用subprocess调用pdf2zh模块
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                pdf2zh_script = os.path.join(current_dir, 'pdf2zh', 'pdf2zh.py')
                
                # 构建命令行参数
                python_exe = sys.executable
                cmd = [
                    python_exe, pdf2zh_script,
                    self.input_file,
                    '--lang-in', self.lang_in,
                    '--lang-out', self.lang_out, 
                    '--service', self.service,
                    '--thread', str(self.threads)
                ]
                
                print(f"执行命令: {' '.join(cmd)}")
                
                # 执行翻译命令
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=current_dir
                )
                
                # 等待完成
                stdout, stderr = process.communicate()
                
                if self._stop_requested:
                    return
                
                if process.returncode == 0:
                    # 翻译成功，查找输出文件
                    base_name = os.path.splitext(self.input_file)[0]
                    base_filename = os.path.basename(base_name)
                    current_dir = os.path.dirname(os.path.abspath(self.input_file)) or '.'
                    
                    possible_outputs = [
                        os.path.join(current_dir, f"{base_filename}-dual.pdf"),
                        os.path.join(current_dir, f"{base_filename}-mono.pdf"),
                        f"{base_name}-dual.pdf",
                        f"{base_name}-mono.pdf",
                        f"{base_name}-zh.pdf", 
                        f"{base_name}_translated.pdf"
                    ]
                    
                    output_file = None
                    for possible_file in possible_outputs:
                        if os.path.exists(possible_file):
                            output_file = possible_file
                            print(f"找到输出文件: {possible_file}")
                            break
                    
                    if output_file:
                        print(f"翻译完成: {output_file}")
                        self.translation_completed.emit(os.path.abspath(output_file))
                    else:
                        # 检查当前目录是否有新生成的PDF文件
                        try:
                            current_files = [f for f in os.listdir('.') if f.endswith('.pdf') and f != os.path.basename(self.input_file)]
                            current_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                            
                            if current_files:
                                output_file = current_files[0]
                                print(f"找到最新的PDF文件: {output_file}")
                                self.translation_completed.emit(os.path.abspath(output_file))
                            else:
                                self.translation_failed.emit("翻译完成但无法找到结果文件")
                        except Exception as e:
                            self.translation_failed.emit(f"查找翻译结果文件时出错: {str(e)}")
                else:
                    error_msg = f"翻译失败 (返回码: {process.returncode})\n标准输出: {stdout}\n错误输出: {stderr}"
                    print(error_msg)
                    self.translation_failed.emit(error_msg)
                    
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
        self.translated_files = {}  # 原文件路径 -> 翻译文件路径
        
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
        
        # 可选：清理临时翻译文件（注意：用户可能需要保留这些文件）
        # for translated_file in self.translated_files.values():
        #     try:
        #         if os.path.exists(translated_file):
        #             os.remove(translated_file)
        #     except:
        #         pass
        
        self.translated_files.clear() 
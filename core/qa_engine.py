"""AI问答引擎模块"""

import json
import os
from typing import Any, Dict

import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from utils.text_processor import text_processor


class QAEngineThread(QThread):
    """AI问答线程"""
    response_chunk = pyqtSignal(str)  # 流式响应片段
    response_completed = pyqtSignal()  # 响应完成
    response_failed = pyqtSignal(str)  # 响应失败
    
    def __init__(self, question: str, pdf_content: str, chat_history: list, parent=None):
        super().__init__(parent)
        self.question = question
        self.pdf_content = pdf_content
        self.chat_history = chat_history
        self.config = self._load_qa_config()
        self._stop_requested = False
        
    def _load_qa_config(self) -> Dict[str, Any]:
        """加载问答引擎配置"""
        config_file = "pdf2zh_config.json"
        default_config = {
            "service": "关闭",
            "envs": {}
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
                    if "qa_engine" in full_config:
                        return full_config["qa_engine"]
        except Exception as e:
            print(f"读取问答引擎配置失败: {e}")
            
        return default_config
        
    def stop(self):
        """停止问答"""
        self._stop_requested = True
        
    def run(self):
        """执行问答"""
        try:
            service = self.config.get("service", "关闭")
            
            if service == "silicon":
                self._handle_silicon_qa()
            elif service == "ollama":
                self._handle_ollama_qa()
            elif service == "自定义":
                self._handle_custom_qa()
            else:
                self.response_failed.emit("问答引擎未配置或已关闭")
                return
                
        except Exception as e:
            self.response_failed.emit(f"问答过程中出错: {str(e)}")
            
    def _handle_silicon_qa(self):
        """处理硅基流动问答"""
        envs = self.config.get("envs", {})
        api_key = envs.get("SILICON_API_KEY")
        model = envs.get("SILICON_MODEL")
        
        if not api_key or not model:
            self.response_failed.emit("Silicon API配置不完整")
            return
            
        # 构建消息
        messages = self._build_messages()
        
        # 调用硅基流动API
        try:
            url = "https://api.siliconflow.cn/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": 0.7
            }
            
            response = requests.post(url, headers=headers, json=data, stream=True)
            response.raise_for_status()
            
            # 处理流式响应
            for line in response.iter_lines():
                if self._stop_requested:
                    break
                    
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            break
                            
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                choice = data['choices'][0]
                                if 'delta' in choice and 'content' in choice['delta']:
                                    content = choice['delta']['content']
                                    if content:
                                        self.response_chunk.emit(content)
                        except json.JSONDecodeError:
                            continue
                            
            if not self._stop_requested:
                self.response_completed.emit()
                
        except requests.exceptions.RequestException as e:
            self.response_failed.emit(f"Silicon API调用失败: {str(e)}")
        except Exception as e:
            self.response_failed.emit(f"Silicon问答处理失败: {str(e)}")
            
    def _handle_ollama_qa(self):
        """处理Ollama问答"""
        envs = self.config.get("envs", {})
        host = envs.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        model = envs.get("OLLAMA_MODEL")
        
        if not model:
            self.response_failed.emit("Ollama模型配置不完整")
            return
            
        # 构建消息
        messages = self._build_messages()
        
        # 调用Ollama API
        try:
            url = f"{host}/api/chat"
            data = {
                "model": model,
                "messages": messages,
                "stream": True
            }
            
            response = requests.post(url, json=data, stream=True)
            response.raise_for_status()
            
            # 处理流式响应
            for line in response.iter_lines():
                if self._stop_requested:
                    break
                    
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'message' in data and 'content' in data['message']:
                            content = data['message']['content']
                            if content:
                                self.response_chunk.emit(content)
                                
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                        
            if not self._stop_requested:
                self.response_completed.emit()
                
        except requests.exceptions.RequestException as e:
            self.response_failed.emit(f"Ollama API调用失败: {str(e)}")
        except Exception as e:
            self.response_failed.emit(f"Ollama问答处理失败: {str(e)}")
            
    def _handle_custom_qa(self):
        """处理自定义问答引擎"""
        envs = self.config.get("envs", {})
        api_url = envs.get("CUSTOM_HOST")
        api_key = envs.get("CUSTOM_KEY")  # 可选
        model = envs.get("CUSTOM_MODEL")
        url = api_url.rstrip('/') + "/v1/chat/completions"

        if not api_url or not model:
            self.response_failed.emit("自定义问答引擎配置不完整 (需要 CUSTOM_API_URL 和 CUSTOM_MODEL)")
            return

        # 构建消息
        messages = self._build_messages()

        # 调用自定义API
        try:
            headers = {
                "Content-Type": "application/json"
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            data = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": 0.7
            }

            print(f"自定义请求的url:{url}")
            response = requests.post(url, headers=headers, json=data, stream=True)
            response.raise_for_status()

            # 处理流式响应 (兼容OpenAI格式)
            for line in response.iter_lines():
                if self._stop_requested:
                    break
                
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        
                        try:
                            data_json = json.loads(data_str)
                            if 'choices' in data_json and len(data_json['choices']) > 0:
                                choice = data_json['choices'][0]
                                if 'delta' in choice and 'content' in choice['delta']:
                                    content = choice['delta']['content']
                                    if content:
                                        self.response_chunk.emit(content)
                        except json.JSONDecodeError:
                            continue
            
            if not self._stop_requested:
                self.response_completed.emit()

        except requests.exceptions.RequestException as e:
            self.response_failed.emit(f"自定义问答API调用失败: {str(e)}")
        except Exception as e:
            self.response_failed.emit(f"自定义问答处理失败: {str(e)}")
            
    def _build_messages(self) -> list:
        """构建对话消息"""
        messages = []
        
        # 获取当前模型名称
        model_name = self._get_current_model()
        
        # 系统提示词模板（不含PDF内容）
        system_prompt_template = """你是一个专业的PDF文档分析助手。用户上传了一个PDF文档，你需要基于文档内容回答用户的问题。

PDF文档内容如下：
{pdf_content}

请注意：
1. 请仅基于上述PDF文档内容回答问题
2. 如果问题与文档内容无关，请明确说明
3. 回答要准确、详细，并引用相关页面信息
4. 使用中文回答
5. 请使用纯文本回答，不要使用任何markdown格式（如 **、##、*、- 等符号），直接用文字表达重点
"""
        
        # 计算可用于PDF内容的token数量
        available_tokens = text_processor.calculate_available_tokens(
            model_name=model_name,
            system_prompt=system_prompt_template,
            chat_history=self.chat_history,
            current_question=self.question,
            max_response_tokens=2000
        )
        
        # 智能截断PDF内容
        processed_pdf_content, was_truncated = text_processor.smart_truncate_pdf_content(
            pdf_content=self.pdf_content,
            max_tokens=available_tokens,
            question=self.question
        )
        
        # 记录截断情况（仅在调试模式下输出）
        if was_truncated:
            text_processor.count_tokens(self.pdf_content)
            text_processor.count_tokens(processed_pdf_content)
            # 只在确实需要时进行调试输出
            pass
        
        # 构建最终的系统提示词
        system_prompt = system_prompt_template.format(pdf_content=processed_pdf_content)
        
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 添加历史对话
        for chat in self.chat_history:
            messages.append({
                "role": "user",
                "content": chat["question"]
            })
            messages.append({
                "role": "assistant", 
                "content": chat["answer"]
            })
            
        # 添加当前问题
        messages.append({
            "role": "user",
            "content": self.question
        })
        
        return messages
    
    def _get_current_model(self) -> str:
        """获取当前使用的模型名称"""
        service = self.config.get("service", "关闭")
        envs = self.config.get("envs", {})
        
        if service == "silicon":
            return envs.get("SILICON_MODEL", "deepseek-chat")
        elif service == "ollama":
            return envs.get("OLLAMA_MODEL", "llama2")
        elif service == "custom":
            return envs.get("CUSTOM_MODEL", "default")
        else:
            return "default"


class QAEngineManager(QObject):
    """问答引擎管理器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_thread = None
        
    def start_qa(self, question: str, pdf_content: str, chat_history: list,
                 chunk_callback=None, completed_callback=None, failed_callback=None):
        """开始问答"""
        # 停止当前问答
        self.stop_current_qa()
        
        # 创建新的问答线程
        self.current_thread = QAEngineThread(question, pdf_content, chat_history, parent=self)
        
        # 连接信号
        if chunk_callback:
            self.current_thread.response_chunk.connect(chunk_callback)
        if completed_callback:
            self.current_thread.response_completed.connect(completed_callback)
        if failed_callback:
            self.current_thread.response_failed.connect(failed_callback)
            
        # 启动问答
        self.current_thread.start()
        
    def stop_current_qa(self):
        """停止当前问答"""
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.stop()
            if not self.current_thread.wait(3000):  # 等待3秒
                self.current_thread.terminate()
                self.current_thread.wait(1000)  # 等待1秒确保终止
        
        # 清理线程对象
        if self.current_thread:
            self.current_thread.deleteLater()
            self.current_thread = None
            
    def is_qa_running(self):
        """是否正在问答"""
        return self.current_thread and self.current_thread.isRunning()
        
    def cleanup(self):
        """清理资源"""
        self.stop_current_qa() 
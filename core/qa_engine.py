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
                        config = full_config["qa_engine"]
                        # 如果有qa_settings，也加载进来
                        if "qa_settings" in full_config:
                            config["qa_settings"] = full_config["qa_settings"]
                        return config
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
        
        # 获取QA设置
        qa_settings = self.config.get("qa_settings", {})
        pages_config = qa_settings.get("pages", "").strip()
        
        # 从配置文件读取系统提示词（总是使用配置文件中的值）
        system_prompt_template = qa_settings.get("system_prompt", "").strip()
        
        # 如果配置文件中没有系统提示词，使用一个最基本的模板
        if not system_prompt_template:
            system_prompt_template = "你是一个AI助手，请基于以下PDF文档内容回答用户的问题。\n\nPDF文档内容如下：\n{pdf_content}\n\n请基于上述内容回答问题。"
            print("警告：配置文件中未找到系统提示词，使用基础模板")
        
        # 处理PDF内容：根据页面配置过滤
        processed_pdf_content = self._process_pdf_content_by_pages(self.pdf_content, pages_config)
        
        # 计算可用于PDF内容的token数量
        available_tokens = text_processor.calculate_available_tokens(
            model_name=model_name,
            system_prompt=system_prompt_template,
            chat_history=self.chat_history,
            current_question=self.question,
            max_response_tokens=2000
        )
        
        # 智能截断PDF内容
        final_pdf_content, was_truncated = text_processor.smart_truncate_pdf_content(
            pdf_content=processed_pdf_content,
            max_tokens=available_tokens,
            question=self.question
        )
        
        # 记录截断情况（仅在调试模式下输出）
        if was_truncated:
            text_processor.count_tokens(processed_pdf_content)
            text_processor.count_tokens(final_pdf_content)
            # 只在确实需要时进行调试输出
            pass
        
        # 构建最终的系统提示词
        system_prompt = system_prompt_template.format(pdf_content=final_pdf_content)
        
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
    
    def _process_pdf_content_by_pages(self, pdf_content: str, pages_config: str) -> str:
        """根据页面配置处理PDF内容"""
        if not pages_config or not pdf_content:
            print(f"页面过滤跳过: pages_config='{pages_config}', pdf_content_len={len(pdf_content)}")
            return pdf_content
            
        try:
            # 解析页面范围
            page_numbers = self._parse_page_ranges(pages_config)
            if not page_numbers:
                print(f"页面范围解析为空: {pages_config}")
                return pdf_content
                
            print(f"页面范围解析结果: {pages_config} -> {page_numbers} (0-based)")
                
            # 按页面分割PDF内容 - 使用更精确的分割方式
            import re
            # 匹配 "=== 第X页 ===" 模式，使用更严格的匹配
            page_pattern = r'=== 第(\d+)页 ==='
            page_matches = list(re.finditer(page_pattern, pdf_content))
            
            print(f"找到页面标记: {len(page_matches)} 个")
            
            # 验证页面标记的连续性和合理性
            page_nums_found = []
            for match in page_matches:
                page_num = int(match.group(1))
                page_nums_found.append(page_num)
                print(f"  第{page_num}页 at position {match.start()}")
            
            # 检查页面是否连续且合理
            if page_nums_found:
                page_nums_found.sort()
                max_page = max(page_nums_found)
                min_page = min(page_nums_found)
                expected_pages = list(range(min_page, max_page + 1))
                
                # 如果页面不连续或数量过多，可能是提取错误
                if len(page_nums_found) != len(expected_pages):
                    print(f"警告：页面标记不连续。找到页面: {page_nums_found}")
                
                # 如果最大页面号超过合理范围（比如超过100页），认为可能有错误
                if max_page > 100:
                    print(f"警告：检测到过多页面({max_page}页)，可能是文本提取错误")
                    # 可以选择只使用前面合理的页面
                    valid_matches = [m for m in page_matches if int(m.group(1)) <= 50]
                    if valid_matches:
                        page_matches = valid_matches
                        print("已限制为前50页进行处理")
            
            if not page_matches:
                # 如果没有页面标记，返回原内容
                print("PDF内容没有页面标记，返回原内容")
                return pdf_content
                
            # 提取指定页面的内容
            selected_pages = []
            
            for i, match in enumerate(page_matches):
                page_num = int(match.group(1))
                page_index = page_num - 1  # 转换为0-based索引
                
                print(f"检查第{page_num}页 (索引{page_index}): {'包含' if page_index in page_numbers else '跳过'}")
                
                if page_index in page_numbers:
                    # 确定页面内容的起始和结束位置
                    start_pos = match.start()
                    
                    # 找到下一页的开始位置或文档结尾
                    if i + 1 < len(page_matches):
                        end_pos = page_matches[i + 1].start()
                    else:
                        end_pos = len(pdf_content)
                    
                    # 提取页面内容
                    page_content = pdf_content[start_pos:end_pos].strip()
                    if page_content:
                        selected_pages.append(page_content)
                        print(f"  已添加第{page_num}页内容: {len(page_content)} 字符")
                        
            result = "\n\n".join(selected_pages)
            print(f"QA页面过滤完成: 原内容{len(pdf_content)}字符，配置页面{pages_config}，过滤后{len(result)}字符，选中{len(selected_pages)}个页面")
            return result if result.strip() else pdf_content
            
        except Exception as e:
            print(f"处理页面配置时出错: {e}")
            import traceback
            traceback.print_exc()
            return pdf_content
    
    def _parse_page_ranges(self, page_string: str) -> list:
        """将页面范围字符串转换为整数数组（0-based索引）
        支持格式: "1-5,8,10-15" -> [0,1,2,3,4,7,9,10,11,12,13,14]
        """
        if not page_string or not page_string.strip():
            return []
            
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
            return []
    
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
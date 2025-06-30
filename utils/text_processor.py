"""文本处理工具模块"""

import re
from typing import Dict, List, Tuple

try:
    import tiktoken
except ImportError:
    tiktoken = None


class TextProcessor:
    """文本处理器，支持token计数和智能截断"""
    
    # 不同模型的token限制配置
    MODEL_TOKEN_LIMITS = {
        # 硅基流动支持的主流模型
        "deepseek-chat": 32768,
        "deepseek-coder": 16384,
        "qwen-turbo": 8192,
        "qwen-plus": 32768,
        "qwen-max": 8192,
        "glm-4": 128000,
        "glm-4-flash": 128000,
        "yi-large": 32768,
        "claude-3-haiku": 200000,
        "claude-3-sonnet": 200000,
        "gpt-3.5-turbo": 16385,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        # Ollama模型（通常较小）
        "llama2": 4096,
        "llama3": 8192, 
        "llama3.1": 32768,
        "codellama": 16384,
        "qwen2": 32768,
        "gemma": 8192,
        "phi3": 4096,
        "mistral": 32768,
        # 默认限制
        "default": 32768
    }
    
    def __init__(self):
        """初始化文本处理器"""
        self.encoding = None
        self._init_tiktoken()
        
    def _init_tiktoken(self):
        """初始化tiktoken编码器"""
        if tiktoken is None:
            print("警告: tiktoken未安装，将使用字符数估算token数量")
            return
            
        try:
            # 使用cl100k_base编码器，适用于大多数OpenAI模型
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            print(f"警告: 初始化tiktoken失败: {e}，将使用字符数估算")
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        if not text:
            return 0
            
        if self.encoding:
            try:
                # 处理可能包含特殊token的文本，允许所有特殊token
                return len(self.encoding.encode(text, disallowed_special=()))
            except Exception as e:
                print(f"警告: token计数失败: {e}，使用字符数估算")
        
        # 降级方案：使用字符数估算（中文约1.5个字符=1个token，英文约4个字符=1个token）
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        estimated_tokens = int(chinese_chars * 0.67 + other_chars * 0.25)
        return max(estimated_tokens, len(text) // 4)  # 至少按4字符=1token计算
    
    def get_model_token_limit(self, model_name: str) -> int:
        """获取模型的token限制"""
        if not model_name:
            return self.MODEL_TOKEN_LIMITS["default"]
            
        # 模糊匹配模型名称
        model_lower = model_name.lower()
        for key, limit in self.MODEL_TOKEN_LIMITS.items():
            if key in model_lower or model_lower.startswith(key.split('-')[0]):
                return limit
        
        return self.MODEL_TOKEN_LIMITS["default"]
    
    def calculate_available_tokens(self, model_name: str, system_prompt: str, 
                                 chat_history: List[Dict], current_question: str,
                                 max_response_tokens: int = 2000) -> int:
        """计算可用于PDF内容的token数量"""
        total_limit = self.get_model_token_limit(model_name)
        
        # 计算已使用的token
        used_tokens = 0
        used_tokens += self.count_tokens(system_prompt.replace("{self.pdf_content}", ""))  # 系统提示词（不含PDF内容）
        used_tokens += self.count_tokens(current_question)
        
        # 计算历史对话token
        for chat in chat_history:
            used_tokens += self.count_tokens(chat.get("question", ""))
            used_tokens += self.count_tokens(chat.get("answer", ""))
        
        # 预留响应token和安全边距
        safety_margin = 500  # 安全边距
        reserved_tokens = max_response_tokens + safety_margin
        
        available_tokens = total_limit - used_tokens - reserved_tokens
        return max(available_tokens, 1000)  # 至少保留1000个token给PDF内容
    
    def smart_truncate_pdf_content(self, pdf_content: str, max_tokens: int, 
                                 question: str = "") -> Tuple[str, bool]:
        """
        智能截断PDF内容
        
        Args:
            pdf_content: PDF文本内容
            max_tokens: 最大允许的token数量
            question: 用户问题，用于关键词匹配
            
        Returns:
            Tuple[截断后的内容, 是否发生了截断]
        """
        if not pdf_content:
            return "", False
            
        current_tokens = self.count_tokens(pdf_content)
        if current_tokens <= max_tokens:
            return pdf_content, False
        
        # 开始智能截断（静默处理）
        
        # 分割PDF内容为页面
        pages = self._split_pdf_by_pages(pdf_content)
        if not pages:
            # 如果无法按页面分割，按段落分割
            pages = self._split_by_paragraphs(pdf_content)
        
        # 智能选择要保留的内容
        selected_content = self._select_important_content(pages, max_tokens, question)
        
        return selected_content, True
    
    def _split_pdf_by_pages(self, pdf_content: str) -> List[str]:
        """按页面分割PDF内容"""
        # 寻找页面分隔符（如"第X页:"或类似模式）
        page_pattern = r'第\s*\d+\s*页\s*[:：]'
        pages = re.split(page_pattern, pdf_content)
        
        # 过滤掉空内容
        pages = [page.strip() for page in pages if page.strip()]
        return pages
    
    def _split_by_paragraphs(self, content: str) -> List[str]:
        """按段落分割内容"""
        # 按双换行符分割段落
        paragraphs = re.split(r'\n\s*\n', content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        return paragraphs
    
    def _select_important_content(self, content_blocks: List[str], max_tokens: int, 
                                question: str) -> str:
        """
        智能选择重要内容
        
        策略：
        1. 保留前几个块（通常包含摘要、介绍）
        2. 保留最后几个块（通常包含结论）
        3. 基于问题关键词匹配相关块
        4. 确保总token数不超过限制
        """
        if not content_blocks:
            return ""
        
        selected_blocks = []
        current_tokens = 0
        
        # 提取问题关键词
        question_keywords = self._extract_keywords(question) if question else []
        
        # 计算每个块的重要性得分
        block_scores = []
        for i, block in enumerate(content_blocks):
            score = self._calculate_block_importance(block, i, len(content_blocks), question_keywords)
            block_tokens = self.count_tokens(block)
            block_scores.append((i, block, score, block_tokens))
        
        # 按重要性排序
        block_scores.sort(key=lambda x: x[2], reverse=True)
        
        # 选择最重要的块，直到达到token限制
        for block_idx, block, score, block_tokens in block_scores:
            if current_tokens + block_tokens <= max_tokens:
                selected_blocks.append((block_idx, block))
                current_tokens += block_tokens
            else:
                # 如果当前块过大，尝试截断
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens > 100:  # 至少需要100个token才值得截断
                    truncated_block = self._truncate_block(block, remaining_tokens)
                    if truncated_block:
                        selected_blocks.append((block_idx, truncated_block))
                break
        
        # 按原始顺序排序
        selected_blocks.sort(key=lambda x: x[0])
        
        # 组合选中的内容
        result_parts = []
        for block_idx, block in selected_blocks:
            if block_idx < len(content_blocks) - len(selected_blocks):
                result_parts.append(f"[页面 {block_idx + 1}]\n{block}")
            else:
                result_parts.append(block)
        
        result = "\n\n".join(result_parts)
        
        # 添加截断提示
        total_blocks = len(content_blocks)
        selected_count = len(selected_blocks)
        if selected_count < total_blocks:
            truncation_note = f"\n\n[注意：由于内容过长，已智能选择 {selected_count}/{total_blocks} 个重要部分]"
            result += truncation_note
        
        return result
    
    def _extract_keywords(self, question: str) -> List[str]:
        """从问题中提取关键词"""
        if not question:
            return []
        
        # 简单的关键词提取：去除停用词，保留有意义的词
        stop_words = {
            '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这样',
            '什么', '怎么', '为什么', '如何', '哪里', '哪个', '谁', '什么时候', '多少', '几个', '请问', '请', '问', '答', '回答'
        }
        
        # 简单分词（按空格和标点分割）
        words = re.findall(r'[\w\u4e00-\u9fff]+', question.lower())
        keywords = [word for word in words if len(word) > 1 and word not in stop_words]
        
        return keywords[:10]  # 最多10个关键词
    
    def _calculate_block_importance(self, block: str, index: int, total_blocks: int, 
                                  keywords: List[str]) -> float:
        """计算内容块的重要性得分"""
        score = 0.0
        
        # 位置权重：开头和结尾更重要
        if index < 2:  # 前两个块
            score += 3.0
        elif index >= total_blocks - 2:  # 后两个块
            score += 2.0
        else:
            score += 1.0
        
        # 长度权重：适中长度的块更重要
        block_len = len(block)
        if 200 <= block_len <= 2000:
            score += 1.5
        elif block_len > 100:
            score += 1.0
        
        # 关键词匹配权重
        if keywords:
            block_lower = block.lower()
            keyword_matches = sum(1 for keyword in keywords if keyword in block_lower)
            score += keyword_matches * 2.0
        
        # 内容特征权重
        if any(marker in block.lower() for marker in ['摘要', '总结', '结论', '概述', '引言', '介绍']):
            score += 2.0
        
        if any(marker in block.lower() for marker in ['重要', '关键', '核心', '主要']):
            score += 1.0
        
        return score
    
    def _truncate_block(self, block: str, max_tokens: int) -> str:
        """截断单个内容块"""
        if self.count_tokens(block) <= max_tokens:
            return block
        
        # 按句子分割
        sentences = re.split(r'[。！？.!?]\s*', block)
        
        result = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_tokens = self.count_tokens(sentence + "。")
            if current_tokens + sentence_tokens <= max_tokens - 20:  # 预留空间
                result += sentence + "。"
                current_tokens += sentence_tokens
            else:
                break
        
        if result:
            result += "...[内容截断]"
        
        return result


# 全局实例
text_processor = TextProcessor() 
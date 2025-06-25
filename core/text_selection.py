"""文本选择功能"""

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QCursor


class TextSelection:
    """文本选择管理类"""
    
    def __init__(self):
        self.selecting = False
        self.start_pos = QPoint()
        self.current_pos = QPoint()
        self.selected_text = ""
        self.visible_words = []
        self.selected_words = []
        
        # 光标
        self.text_cursor = QCursor(Qt.CursorShape.IBeamCursor)
        self.arrow_cursor = QCursor(Qt.CursorShape.ArrowCursor)
    
    def start_selection(self, pos):
        """开始选择"""
        self.start_pos = pos
        self.current_pos = pos
        self.clear_selection()
        
        if self.is_over_text(pos):
            self.selecting = True
            return True
        return False
    
    def update_selection(self, pos):
        """更新选择"""
        if not self.selecting:
            return
            
        self.current_pos = pos
        self._update_text_selection()
    
    def end_selection(self):
        """结束选择"""
        if self.selecting:
            self.selecting = False
            return self._extract_selected_text()
        return ""
    
    def clear_selection(self):
        """清除选择"""
        for word in self.visible_words:
            word['selected'] = False
        self.selected_words.clear()
    
    def set_visible_words(self, words):
        """设置可见单词"""
        self.visible_words = words
    
    def get_word_at_pos(self, pos):
        """获取指定位置的单词"""
        for i, word in enumerate(self.visible_words):
            if word['display_rect'].contains(pos):
                return i
        return -1
    
    def is_over_text(self, pos):
        """检查是否在文本上"""
        return self.get_word_at_pos(pos) >= 0
    
    def get_cursor(self, pos):
        """获取光标样式"""
        if self.is_over_text(pos):
            return self.text_cursor
        return self.arrow_cursor
    
    def _update_text_selection(self):
        """更新文本选择"""
        self.clear_selection()
        
        start_x = min(self.start_pos.x(), self.current_pos.x())
        end_x = max(self.start_pos.x(), self.current_pos.x())
        start_y = min(self.start_pos.y(), self.current_pos.y())
        end_y = max(self.start_pos.y(), self.current_pos.y())
        
        selected = []
        for i, word in enumerate(self.visible_words):
            rect = word['display_rect']
            center_x, center_y = rect.center().x(), rect.center().y()
            
            if start_x <= center_x <= end_x and start_y <= center_y <= end_y:
                selected.append((i, word['page_num'], center_y, center_x))
        
        # 如果没选中，使用相交检测
        if not selected:
            selection_rect = QRect(start_x, start_y, end_x - start_x, end_y - start_y)
            for i, word in enumerate(self.visible_words):
                if selection_rect.intersects(word['display_rect']):
                    rect = word['display_rect']
                    selected.append((i, word['page_num'], rect.center().y(), rect.center().x()))
        
        # 排序并标记选中
        selected.sort(key=lambda x: (x[1], x[2], x[3]))
        for word_idx, _, _, _ in selected:
            self.visible_words[word_idx]['selected'] = True
            self.selected_words.append(word_idx)
    
    def _extract_selected_text(self):
        """提取选中的文本"""
        if not self.selected_words:
            return ""
            
        texts = []
        last_y, last_page = None, None
        
        # 获取选中文本数据
        selected_data = []
        for idx in self.selected_words:
            word = self.visible_words[idx]
            rect = word['display_rect']
            selected_data.append((
                word['page_num'], 
                rect.center().y(), 
                rect.center().x(), 
                word['text']
            ))
        
        selected_data.sort()
        
        # 组合文本
        for page_num, y, x, text in selected_data:
            if last_page is not None and page_num != last_page:
                texts.append(f'\n--- 第 {page_num + 1} 页 ---\n')
            elif last_y is not None and abs(y - last_y) > 15:
                texts.append('\n')
            elif texts and not texts[-1].endswith(' ') and not texts[-1].endswith('\n'):
                texts.append(' ')
                
            texts.append(text)
            last_y, last_page = y, page_num
        
        self.selected_text = ''.join(texts).strip()
        return self.selected_text 
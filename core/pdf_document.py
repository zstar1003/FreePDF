"""PDF文档管理"""

from collections import OrderedDict

import pymupdf

from utils.constants import MAX_CACHE_SIZE


class PDFDocument:
    """PDF文档管理类"""
    
    def __init__(self):
        self.doc = None
        self.file_path = ""
        self.total_pages = 0
        
    def load(self, file_path):
        """加载PDF文档"""
        try:
            if self.doc:
                self.doc.close()
                
            self.doc = pymupdf .open(file_path)
            self.file_path = file_path
            self.total_pages = len(self.doc)
            return True, "加载成功"
            
        except Exception as e:
            return False, f"加载失败: {str(e)}"
    
    def close(self):
        """关闭文档"""
        if self.doc:
            self.doc.close()
            self.doc = None
            
    def get_page(self, page_num):
        """获取指定页面"""
        if self.doc and 0 <= page_num < self.total_pages:
            return self.doc[page_num]
        return None
    
    def get_page_rect(self, page_num):
        """获取页面尺寸"""
        page = self.get_page(page_num)
        return page.rect if page else None


class PageCache:
    """页面缓存管理"""
    
    def __init__(self, max_size=MAX_CACHE_SIZE):
        self.page_cache = OrderedDict()
        self.text_cache = {}
        self.max_size = max_size
    
    def get_page(self, page_num):
        """获取缓存的页面"""
        if page_num in self.page_cache:
            # 移动到末尾（LRU）
            self.page_cache.move_to_end(page_num)
            return self.page_cache[page_num]
        return None
    
    def get_text(self, page_num):
        """获取缓存的文本"""
        return self.text_cache.get(page_num, [])
    
    def set_page(self, page_num, pixmap, text_words):
        """设置页面缓存"""
        self.page_cache[page_num] = pixmap
        self.text_cache[page_num] = text_words
        
        # 移动到末尾（LRU）
        self.page_cache.move_to_end(page_num)
        
        # 清理过老的缓存
        self._cleanup_old_cache()
    
    def _cleanup_old_cache(self):
        """清理旧缓存"""
        while len(self.page_cache) > self.max_size:
            old_page = self.page_cache.popitem(last=False)[0]
            if old_page in self.text_cache:
                del self.text_cache[old_page]
    
    def clear(self):
        """清空缓存"""
        self.page_cache.clear()
        self.text_cache.clear()
    
    def has_page(self, page_num):
        """检查是否有页面缓存"""
        return page_num in self.page_cache 
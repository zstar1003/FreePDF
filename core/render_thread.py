"""PDF页面渲染线程"""

import fitz
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt


class PageRenderThread(QThread):
    """页面渲染线程"""
    page_rendered = pyqtSignal(int, object, object)  # 页码, QPixmap, 文本列表
    
    def __init__(self, doc, page_num, zoom_factor, dpi, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.page_num = page_num
        self.zoom_factor = zoom_factor
        self.dpi = dpi
        self._stop_mutex = QMutex()
        self._stop_requested = False
        
    def stop(self):
        """请求停止线程"""
        with QMutexLocker(self._stop_mutex):
            self._stop_requested = True
        
    def _should_stop(self):
        """检查是否应该停止"""
        with QMutexLocker(self._stop_mutex):
            return self._stop_requested
        
    def run(self):
        """执行渲染"""
        try:
            if self._should_stop():
                return
                
            page = self.doc[self.page_num]
            
            if self._should_stop():
                return
            
            # 高质量渲染
            scale = self.zoom_factor * (self.dpi / 72.0)
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            if self._should_stop():
                return
            
            # 转换为QPixmap
            img_data = pix.tobytes("ppm")
            qimg = QImage.fromData(img_data)
            pixmap = QPixmap.fromImage(qimg)
            
            if self._should_stop():
                return
            
            # 如果图像太大，进行高质量缩放
            from utils.constants import MAX_PAGE_WIDTH
            if pixmap.width() > MAX_PAGE_WIDTH:
                pixmap = pixmap.scaledToWidth(
                    MAX_PAGE_WIDTH, 
                    Qt.TransformationMode.SmoothTransformation
                )
            
            if self._should_stop():
                return
            
            # 提取文本单词
            text_words = self._extract_text_words(page)
            
            if not self._should_stop():
                self.page_rendered.emit(self.page_num, pixmap, text_words)
                
        except Exception as e:
            if not self._should_stop():
                print(f"渲染页面 {self.page_num} 时出错: {e}")
    
    def _extract_text_words(self, page):
        """提取文本单词"""
        words = page.get_text("words")
        text_words = []
        
        for word_info in words:
            if self._should_stop():
                break
                
            if len(word_info) >= 5:
                x0, y0, x1, y1, text = word_info[:5]
                if text.strip():
                    text_words.append({
                        'text': text,
                        'bbox': (x0, y0, x1, y1),
                        'page_num': self.page_num
                    })
        
        return text_words 
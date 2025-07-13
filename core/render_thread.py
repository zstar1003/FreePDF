"""PDF页面渲染线程"""

import pymupdf 
from PyQt6.QtCore import QMutex, QMutexLocker, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap


class PageRenderThread(QThread):
    """页面渲染线程"""
    page_rendered = pyqtSignal(int, object, object)  # 页码, QPixmap, 文本列表
    preview_rendered = pyqtSignal(int, object)  # 页码, 预览QPixmap
    
    def __init__(self, doc, page_num, zoom_factor, dpi, target_width=None, high_quality=True, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.page_num = page_num
        self.zoom_factor = zoom_factor
        self.dpi = max(dpi, 150)  # 最低DPI保证清晰度
        self.target_width = target_width
        self.high_quality = high_quality
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
            
            # 如果不是高质量模式，先发送快速预览
            if not self.high_quality:
                self._render_preview(page)
                if self._should_stop():
                    return
            
            # 计算最佳渲染参数
            render_dpi, render_scale = self._calculate_render_params(page)
            
            # 高质量渲染
            mat = pymupdf .Matrix(render_scale, render_scale)
            pix = page.get_pixmap(
                matrix=mat, 
                alpha=False,
                colorspace=pymupdf .csRGB,  # 明确指定RGB色彩空间
                annots=True,  # 包含注释
                clip=None
            )
            
            if self._should_stop():
                return
            
            # 转换为QPixmap
            pixmap = self._convert_to_pixmap(pix)
            
            if self._should_stop():
                return
            
            # 智能缩放到目标尺寸
            pixmap = self._smart_scale_pixmap(pixmap)
            
            if self._should_stop():
                return
            
            # 提取文本单词
            text_words = self._extract_text_words(page)
            
            if not self._should_stop():
                self.page_rendered.emit(self.page_num, pixmap, text_words)
                
        except Exception as e:
            if not self._should_stop():
                print(f"渲染页面 {self.page_num} 时出错: {e}")
    
    def _render_preview(self, page):
        """渲染快速预览版本"""
        try:
            # 使用较低的DPI快速渲染
            preview_scale = self.zoom_factor * (96 / 72.0)  # 96 DPI
            mat = pymupdf .Matrix(preview_scale, preview_scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            if self._should_stop():
                return
            
            pixmap = self._convert_to_pixmap(pix)
            pixmap = self._smart_scale_pixmap(pixmap)
            
            if not self._should_stop():
                self.preview_rendered.emit(self.page_num, pixmap)
                
        except Exception as e:
            print(f"渲染预览页面 {self.page_num} 时出错: {e}")
    
    def _calculate_render_params(self, page):
        """计算最佳渲染参数"""
        page_rect = page.rect
        
        # 基础缩放
        base_scale = self.zoom_factor
        
        # 如果指定了目标宽度，计算适配缩放
        if self.target_width:
            width_scale = self.target_width / page_rect.width
            base_scale = width_scale
        
        # 高质量渲染使用更高的DPI
        if self.high_quality:
            # 根据缩放级别动态调整DPI
            if base_scale <= 1.0:
                render_dpi = max(self.dpi, 200)
            elif base_scale <= 2.0:
                render_dpi = max(self.dpi, 250)
            else:
                render_dpi = max(self.dpi, 300)
        else:
            render_dpi = self.dpi
        
        render_scale = base_scale * (render_dpi / 72.0)
        
        return render_dpi, render_scale
    
    def _convert_to_pixmap(self, pix):
        """转换为QPixmap，使用优化的图像格式"""
        try:
            # 使用PNG格式获得更好的质量
            img_data = pix.tobytes("png")
            qimg = QImage.fromData(img_data)
            
            # 确保图像格式为RGB32以获得最佳性能
            if qimg.format() != QImage.Format.Format_RGB32:
                qimg = qimg.convertToFormat(QImage.Format.Format_RGB32)
            
            return QPixmap.fromImage(qimg)
        except:  # noqa: E722
            # 回退到PPM格式
            img_data = pix.tobytes("ppm")
            qimg = QImage.fromData(img_data)
            return QPixmap.fromImage(qimg)
    
    def _smart_scale_pixmap(self, pixmap):
        """智能缩放像素图"""
        if not pixmap or pixmap.isNull():
            return pixmap
        
        from utils.constants import MAX_PAGE_WIDTH
        
        # 如果指定了目标宽度，优先使用
        target_width = self.target_width or MAX_PAGE_WIDTH
        
        if pixmap.width() > target_width:
            # 使用高质量的平滑变换
            scaled_pixmap = pixmap.scaledToWidth(
                target_width, 
                Qt.TransformationMode.SmoothTransformation
            )
            return scaled_pixmap
        
        return pixmap
    
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
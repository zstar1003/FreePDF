"""PDF显示组件"""

from PyQt6.QtCore import QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.pdf_document import PageCache
from core.render_thread import PageRenderThread
from core.text_selection import TextSelection
from utils.constants import (
    BORDER_COLOR,
    DEFAULT_DPI,
    DEFAULT_ZOOM,
    HIGHLIGHT_COLOR,
    MAX_PAGE_WIDTH,
    MAX_ZOOM,
    MIN_ZOOM,
    PAGE_BORDER_COLOR,
    PAGE_SPACING,
    PLACEHOLDER_COLOR,
    PRELOAD_DELAY,
    PRELOAD_DISTANCE,
    VIEWPORT_BUFFER,
    ZOOM_STEP,
)


class VirtualPDFWidget(QWidget):
    """虚拟滚动PDF Widget"""
    text_selected = pyqtSignal(str)
    page_changed = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        
        # 初始化组件
        self.pdf_doc = None
        self.page_cache = PageCache()
        self.text_selection = TextSelection()
        
        # 渲染设置
        self.zoom_factor = DEFAULT_ZOOM
        self.dpi = DEFAULT_DPI
        
        # 虚拟滚动
        self.viewport_top = 0
        self.viewport_height = 800
        self.page_heights = []
        self.page_positions = []
        self.total_height = 0
        
        # 渲染管理
        self.render_threads = {}
        self.pending_renders = set()
        self._is_shutting_down = False
        
        # 预加载计时器
        self.preload_timer = QTimer()
        self.preload_timer.timeout.connect(self.preload_nearby_pages)
        self.preload_timer.setSingleShot(True)
        
    def set_document(self, pdf_doc, zoom_factor=None):
        """设置PDF文档"""
        # 只有在关闭时才清理线程
        if self._is_shutting_down:
            return
            
        self._cleanup_old_threads()
        
        self.pdf_doc = pdf_doc
        if zoom_factor is not None:
            self.zoom_factor = zoom_factor
            
        if pdf_doc and pdf_doc.doc:
            self._calculate_page_layout()
            self.page_cache.clear()
            
    def _calculate_page_layout(self):
        """计算页面布局"""
        if not self.pdf_doc or not self.pdf_doc.doc:
            return
            
        self.page_heights = []
        self.page_positions = []
        current_y = 0
        
        base_scale = self.zoom_factor * (self.dpi / 72.0)
        
        for page_num in range(self.pdf_doc.total_pages):
            page_rect = self.pdf_doc.get_page_rect(page_num)
            if not page_rect:
                continue
                
            # 计算显示尺寸
            display_width = int(page_rect.width * base_scale)
            display_height = int(page_rect.height * base_scale)
            
            # 限制最大宽度
            if display_width > MAX_PAGE_WIDTH:
                scale_ratio = MAX_PAGE_WIDTH / display_width
                display_width = MAX_PAGE_WIDTH
                display_height = int(display_height * scale_ratio)
            
            self.page_positions.append(current_y)
            self.page_heights.append(display_height)
            current_y += display_height + PAGE_SPACING
            
        self.total_height = current_y
        max_width = max([self._get_page_display_width(i) 
                        for i in range(self.pdf_doc.total_pages)]) if self.pdf_doc.total_pages > 0 else 800
        self.setFixedSize(max_width, self.total_height)
        
    def _get_page_display_width(self, page_num):
        """获取页面显示宽度"""
        if page_num >= self.pdf_doc.total_pages:
            return 800
            
        page_rect = self.pdf_doc.get_page_rect(page_num)
        if not page_rect:
            return 800
            
        base_scale = self.zoom_factor * (self.dpi / 72.0)
        display_width = int(page_rect.width * base_scale)
        
        return min(display_width, MAX_PAGE_WIDTH)
        
    def update_viewport(self, top, height):
        """更新视口"""
        if self._is_shutting_down:
            return
            
        self.viewport_top = top
        self.viewport_height = height
        
        visible_pages = self._get_visible_pages()
        
        # 渲染可见页面
        for page_num in visible_pages:
            if (not self.page_cache.has_page(page_num) and 
                page_num not in self.pending_renders and
                not self._is_shutting_down):
                self._render_page(page_num)
        
        # 启动预加载
        if not self._is_shutting_down:
            self.preload_timer.start(PRELOAD_DELAY)
        
        self._update_visible_words()
        
        current_page = self._get_current_page()
        self.page_changed.emit(current_page)
        
        self.update()
        
    def _get_visible_pages(self):
        """获取可见页面"""
        visible_pages = []
        viewport_bottom = self.viewport_top + self.viewport_height
        
        for i, (page_y, page_height) in enumerate(zip(self.page_positions, self.page_heights)):
            page_bottom = page_y + page_height
            
            if (page_y - VIEWPORT_BUFFER) < viewport_bottom and (page_bottom + VIEWPORT_BUFFER) > self.viewport_top:
                visible_pages.append(i)
                
        return visible_pages
        
    def _get_current_page(self):
        """获取当前页面"""
        viewport_center = self.viewport_top + self.viewport_height // 2
        
        for i, page_y in enumerate(self.page_positions):
            if i < len(self.page_heights):
                page_bottom = page_y + self.page_heights[i]
                if page_y <= viewport_center <= page_bottom:
                    return i
        return 0
        
    def _render_page(self, page_num):
        """渲染页面"""
        if (self._is_shutting_down or 
            page_num in self.pending_renders or 
            page_num in self.render_threads):
            return
            
        self.pending_renders.add(page_num)
        
        thread = PageRenderThread(
            self.pdf_doc.doc, page_num, 
            self.zoom_factor, self.dpi, self
        )
        
        # 连接信号
        thread.page_rendered.connect(self._on_page_rendered)
        thread.finished.connect(lambda: self._on_thread_finished(page_num))
        
        self.render_threads[page_num] = thread
        thread.start()
        
    def _on_thread_finished(self, page_num):
        """线程完成清理"""
        self.pending_renders.discard(page_num)
        if page_num in self.render_threads:
            thread = self.render_threads.pop(page_num)
            # 延迟删除线程对象
            QTimer.singleShot(100, thread.deleteLater)
        
    def _on_page_rendered(self, page_num, pixmap, text_words):
        """页面渲染完成"""
        if self._is_shutting_down:
            return
            
        self.page_cache.set_page(page_num, pixmap, text_words)
        self._update_visible_words()
        self.update()
        
    def preload_nearby_pages(self):
        """预加载附近页面"""
        if not self.pdf_doc or not self.pdf_doc.doc or self._is_shutting_down:
            return
            
        current_page = self._get_current_page()
        
        for offset in range(-PRELOAD_DISTANCE, PRELOAD_DISTANCE + 1):
            if offset == 0:
                continue
                
            page_num = current_page + offset
            if (0 <= page_num < self.pdf_doc.total_pages and 
                not self.page_cache.has_page(page_num) and 
                page_num not in self.pending_renders and
                not self._is_shutting_down):
                self._render_page(page_num)
                
    def _update_visible_words(self):
        """更新可见单词"""
        if self._is_shutting_down:
            return
            
        visible_words = []
        visible_pages = self._get_visible_pages()
        
        for page_num in visible_pages:
            if self.page_cache.has_page(page_num):
                pixmap = self.page_cache.get_page(page_num)
                words = self.page_cache.get_text(page_num)
                page_y = self.page_positions[page_num]
                
                page_rect = self.pdf_doc.get_page_rect(page_num)
                if page_rect:
                    scale_x = pixmap.width() / page_rect.width
                    scale_y = pixmap.height() / page_rect.height
                    
                    for word in words:
                        x0, y0, x1, y1 = word['bbox']
                        
                        screen_x = int(x0 * scale_x)
                        screen_y = int(y0 * scale_y) + page_y
                        screen_w = int((x1 - x0) * scale_x)
                        screen_h = int((y1 - y0) * scale_y)
                        
                        display_rect = QRect(screen_x, screen_y, screen_w, screen_h)
                        
                        visible_words.append({
                            'text': word['text'],
                            'display_rect': display_rect,
                            'page_num': page_num,
                            'selected': False
                        })
        
        self.text_selection.set_visible_words(visible_words)
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if self.text_selection.start_selection(pos):
                self.update()
    
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        pos = event.position().toPoint()
        
        if self.text_selection.selecting:
            self.text_selection.update_selection(pos)
            self.update()
        else:
            cursor = self.text_selection.get_cursor(pos)
            self.setCursor(cursor)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if event.button() == Qt.MouseButton.LeftButton:
            selected_text = self.text_selection.end_selection()
            if selected_text:
                self.text_selected.emit(selected_text)
    
    def paintEvent(self, event):
        """绘制事件"""
        if self._is_shutting_down:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        self._draw_pages(painter)
        self._draw_text_selection(painter)
    
    def _draw_pages(self, painter):
        """绘制页面"""
        visible_pages = self._get_visible_pages()
        
        for page_num in visible_pages:
            if page_num >= len(self.page_positions):
                continue
                
            page_y = self.page_positions[page_num]
            
            if self.page_cache.has_page(page_num):
                # 绘制已渲染页面
                pixmap = self.page_cache.get_page(page_num)
                painter.drawPixmap(0, page_y, pixmap)
                
                # 页面边框
                border_rect = QRect(0, page_y, pixmap.width(), pixmap.height())
                painter.setPen(QPen(QColor(*PAGE_BORDER_COLOR[:3]), 1))
                painter.drawRect(border_rect)
                
                # 页码
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.setFont(QFont("Arial", 10))
                text_y = page_y + pixmap.height() + 15
                painter.drawText(10, text_y, f"第 {page_num + 1} 页")
                
            else:
                # 绘制占位符
                self._draw_placeholder(painter, page_num, page_y)
    
    def _draw_placeholder(self, painter, page_num, page_y):
        """绘制占位符"""
        placeholder_height = self.page_heights[page_num] if page_num < len(self.page_heights) else 800
        placeholder_width = self._get_page_display_width(page_num)
        placeholder_rect = QRect(0, page_y, placeholder_width, placeholder_height)
        
        painter.fillRect(placeholder_rect, QColor(*PLACEHOLDER_COLOR[:3]))
        painter.setPen(QPen(QColor(*PAGE_BORDER_COLOR[:3]), 2, Qt.PenStyle.DashLine))
        painter.drawRect(placeholder_rect)
        
        # 加载文字
        painter.setPen(QPen(QColor(120, 120, 120)))
        painter.setFont(QFont("Microsoft YaHei", 14))
        
        loading_text = f"第 {page_num + 1} 页"
        if page_num in self.pending_renders:
            loading_text += "\n渲染中..."
        else:
            loading_text += "\n等待加载..."
            
        painter.drawText(placeholder_rect, Qt.AlignmentFlag.AlignCenter, loading_text)
    
    def _draw_text_selection(self, painter):
        """绘制文本选择"""
        highlight_color = QColor(*HIGHLIGHT_COLOR)
        border_color = QColor(*BORDER_COLOR[:3])
        
        for word in self.text_selection.visible_words:
            if word['selected']:
                painter.fillRect(word['display_rect'], highlight_color)
                painter.setPen(QPen(border_color, 1))
                painter.drawRect(word['display_rect'])
    
    def _cleanup_old_threads(self):
        """清理旧线程（非关闭时）"""
        if self._is_shutting_down:
            return
            
        # 只清理已完成的线程
        finished_threads = []
        for page_num, thread in list(self.render_threads.items()):
            if not thread.isRunning():
                finished_threads.append(page_num)
        
        for page_num in finished_threads:
            if page_num in self.render_threads:
                thread = self.render_threads.pop(page_num)
                QTimer.singleShot(100, thread.deleteLater)
    
    def cleanup_threads(self):
        """完全清理线程（关闭时）"""
        print("开始清理PDF Widget线程...")
        self._is_shutting_down = True
        
        # 停止计时器
        self.preload_timer.stop()
        
        # 停止所有线程
        active_threads = []
        for page_num, thread in list(self.render_threads.items()):
            if thread.isRunning():
                print(f"停止线程 {page_num}")
                thread.stop()
                active_threads.append(thread)
        
        # 等待线程完成
        for thread in active_threads:
            if not thread.wait(2000):  # 等待2秒
                print(f"强制终止线程 {thread.page_num}")
                thread.terminate()
                thread.wait(1000)  # 再等1秒
        
        # 清理所有引用
        self.render_threads.clear()
        self.pending_renders.clear()
        
        print("PDF Widget线程清理完成")
    
    def __del__(self):
        """析构函数"""
        if not self._is_shutting_down:
            self.cleanup_threads() 



class PDFWidget(QWidget):
    """PDF显示组件包装器"""
    text_selected = pyqtSignal(str)
    page_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = None
        self.zoom_factor = DEFAULT_ZOOM
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
        """)
        
        # 创建PDF显示组件
        self.pdf_display = VirtualPDFWidget()
        
        # 占位符
        self.placeholder = QLabel(
            "请打开PDF文件\n\n功能特点：\n• 连续滚动浏览\n• 虚拟渲染技术\n• 精确文本选择\n• Ctrl+滚轮缩放"
        )
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("""
            QLabel { 
                background: #f8f9fa; 
                padding: 50px; 
                font-size: 16px; 
                color: #666;
                border: 2px dashed #ddd;
                border-radius: 10px;
                margin: 20px;
            }
        """)
        
        self.scroll_area.setWidget(self.placeholder)
        layout.addWidget(self.scroll_area)
        
        # 连接信号
        self.pdf_display.text_selected.connect(self.text_selected.emit)
        self.pdf_display.page_changed.connect(self.page_changed.emit)
        
        # 绑定滚动事件
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.scroll_area.wheelEvent = self._wheel_event
        
    def load_pdf(self, file_path):
        """加载PDF文件"""
        try:
            import fitz
            
            # 加载文档
            doc = fitz.open(file_path)
            if not doc or doc.page_count == 0:
                return False
                
            self.doc = doc
            
            # 创建PDF文档对象
            from core.pdf_document import PDFDocument
            pdf_doc = PDFDocument()
            success, message = pdf_doc.load(file_path)
            
            if success:
                # 设置到显示组件
                self.pdf_display.set_document(pdf_doc, self.zoom_factor)
                self.scroll_area.setWidget(self.pdf_display)
                
                # 触发初始渲染
                QApplication.processEvents()
                self._on_scroll(0)
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"加载PDF失败: {e}")
            return False
            
    def set_zoom(self, zoom_factor):
        """设置缩放"""
        if not self.doc:
            return
            
        old_scroll_ratio = self._get_scroll_ratio()
        self.zoom_factor = zoom_factor
        
        # 重新设置文档
        if hasattr(self.pdf_display, 'pdf_doc') and self.pdf_display.pdf_doc:
            self.pdf_display.set_document(self.pdf_display.pdf_doc, zoom_factor)
            
            # 恢复滚动位置
            QTimer.singleShot(100, lambda: self._restore_scroll_position(old_scroll_ratio))
            
    def _get_scroll_ratio(self):
        """获取滚动比例"""
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() > 0:
            return scrollbar.value() / scrollbar.maximum()
        return 0
        
    def _restore_scroll_position(self, scroll_ratio):
        """恢复滚动位置"""
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() > 0:
            new_value = int(scroll_ratio * scrollbar.maximum())
            scrollbar.setValue(new_value)
            
    def _on_scroll(self, value):
        """滚动事件"""
        if hasattr(self.pdf_display, 'pdf_doc') and self.pdf_display.pdf_doc:
            viewport_height = self.scroll_area.viewport().height()
            self.pdf_display.update_viewport(value, viewport_height)
            
    def _wheel_event(self, event):
        """滚轮事件"""
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Ctrl+滚轮缩放
            delta = event.angleDelta().y()
            if delta > 0:
                new_zoom = min(self.zoom_factor * ZOOM_STEP, MAX_ZOOM)
            else:
                new_zoom = max(self.zoom_factor / ZOOM_STEP, MIN_ZOOM)
            self.set_zoom(new_zoom)
        else:
            # 正常滚动
            QScrollArea.wheelEvent(self.scroll_area, event)
            
    def cleanup(self):
        """清理资源"""
        if hasattr(self, 'pdf_display'):
            self.pdf_display.cleanup_threads()
            
        if self.doc:
            self.doc.close()
            self.doc = None
import sys
import fitz 
from PyQt6.QtWidgets import ( 
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QLabel, QScrollArea, QPushButton, QFileDialog, 
    QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt6.QtGui import QPixmap, QImage, QAction, QPainter, QPen, QColor, QFont, QCursor
from collections import OrderedDict


class PageRenderThread(QThread):
    """页面渲染线程"""
    page_rendered = pyqtSignal(int, QPixmap, list)
    
    def __init__(self, doc, page_num, zoom_factor, dpi, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.page_num = page_num
        self.zoom_factor = zoom_factor
        self.dpi = dpi
        self._stop_requested = False
        
    def stop(self):
        """请求停止线程"""
        self._stop_requested = True
        
    def run(self):
        try:
            if self._stop_requested:
                return
                
            page = self.doc[self.page_num]
            
            if self._stop_requested:
                return
            
            # 高质量渲染
            scale = self.zoom_factor * (self.dpi / 72.0)
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            if self._stop_requested:
                return
            
            # 转换为QPixmap
            img_data = pix.tobytes("ppm")
            qimg = QImage.fromData(img_data)
            pixmap = QPixmap.fromImage(qimg)
            
            if self._stop_requested:
                return
            
            # 如果图像太大，进行高质量缩放
            if pixmap.width() > 1200:
                pixmap = pixmap.scaledToWidth(1200, Qt.TransformationMode.SmoothTransformation)
            
            if self._stop_requested:
                return
            
            # 提取文本单词
            words = page.get_text("words")
            text_words = []
            
            for word_info in words:
                if self._stop_requested:
                    return
                    
                if len(word_info) >= 5:
                    x0, y0, x1, y1, text = word_info[:5]
                    if text.strip():
                        text_words.append({
                            'text': text,
                            'bbox': (x0, y0, x1, y1),
                            'page_num': self.page_num
                        })
            
            if not self._stop_requested:
                self.page_rendered.emit(self.page_num, pixmap, text_words)
                
        except Exception as e:
            if not self._stop_requested:
                print(f"渲染页面 {self.page_num} 时出错: {e}")


class VirtualPDFWidget(QWidget):
    """虚拟滚动PDF Widget"""
    text_selected = pyqtSignal(str)
    page_changed = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        
        # PDF相关
        self.doc = None
        self.zoom_factor = 1.5
        self.dpi = 180
        self.page_spacing = 20
        
        # 虚拟滚动相关
        self.viewport_top = 0
        self.viewport_height = 800
        self.page_heights = []
        self.page_positions = []
        self.total_height = 0
        
        # 页面缓存
        self.page_cache = OrderedDict()
        self.max_cache_size = 6
        self.text_cache = {}
        
        # 渲染相关
        self.render_threads = {}
        self.pending_renders = set()
        
        # 文本选择
        self.selecting = False
        self.start_pos = QPoint()
        self.current_pos = QPoint()
        self.selected_text = ""
        self.visible_words = []
        self.selected_words = []
        
        # 光标
        self.text_cursor = QCursor(Qt.CursorShape.IBeamCursor)
        self.arrow_cursor = QCursor(Qt.CursorShape.ArrowCursor)
        
        # 预加载计时器
        self.preload_timer = QTimer()
        self.preload_timer.timeout.connect(self.preload_nearby_pages)
        self.preload_timer.setSingleShot(True)
        
    def set_document(self, doc, zoom_factor=None):
        """设置PDF文档"""
        # 清理旧资源
        self.cleanup_threads()
        
        self.doc = doc
        if zoom_factor is not None:
            self.zoom_factor = zoom_factor
            
        if doc:
            self.calculate_page_layout()
            self.clear_cache()
            
    def calculate_page_layout(self):
        """计算页面布局"""
        if not self.doc:
            return
            
        self.page_heights = []
        self.page_positions = []
        current_y = 0
        
        # 计算基础缩放
        base_scale = self.zoom_factor * (self.dpi / 72.0)
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page_rect = page.rect
            
            # 计算显示尺寸
            display_width = int(page_rect.width * base_scale)
            display_height = int(page_rect.height * base_scale)
            
            # 如果太大，缩放到合适大小
            max_width = 1200
            if display_width > max_width:
                scale_ratio = max_width / display_width
                display_width = max_width
                display_height = int(display_height * scale_ratio)
            
            self.page_positions.append(current_y)
            self.page_heights.append(display_height)
            current_y += display_height + self.page_spacing
            
        self.total_height = current_y
        # 使用最大页面宽度作为widget宽度
        max_width = max([self.get_page_display_width(i) for i in range(len(self.doc))]) if self.doc else 800
        self.setFixedSize(max_width, self.total_height)
        
        print(f"布局计算完成: 总高度={self.total_height}, 宽度={max_width}, 缩放={self.zoom_factor}")
        
    def get_page_display_width(self, page_num):
        """获取页面显示宽度"""
        if page_num >= len(self.doc):
            return 800
            
        page = self.doc[page_num]
        base_scale = self.zoom_factor * (self.dpi / 72.0)
        display_width = int(page.rect.width * base_scale)
        
        max_width = 1200
        if display_width > max_width:
            display_width = max_width
            
        return display_width
        
    def cleanup_threads(self):
        """清理所有线程"""
        self.preload_timer.stop()
        
        # 停止所有渲染线程
        threads_to_wait = []
        for page_num, thread in list(self.render_threads.items()):
            if thread.isRunning():
                thread.stop()
                threads_to_wait.append(thread)
        
        # 等待线程完成
        for thread in threads_to_wait:
            if not thread.wait(1000):
                thread.terminate()
                thread.wait(500)
        
        self.render_threads.clear()
        self.pending_renders.clear()
        
    def clear_cache(self):
        """清除缓存"""
        self.page_cache.clear()
        self.text_cache.clear()
        self.visible_words.clear()
        
    def update_viewport(self, top, height):
        """更新视口信息"""
        self.viewport_top = top
        self.viewport_height = height
        
        visible_pages = self.get_visible_pages()
        
        # 渲染可见页面
        for page_num in visible_pages:
            if page_num not in self.page_cache and page_num not in self.pending_renders:
                self.render_page(page_num)
        
        # 启动预加载
        self.preload_timer.start(150)
        
        self.update_visible_words()
        
        current_page = self.get_current_page()
        self.page_changed.emit(current_page)
        
        self.update()
        
    def get_visible_pages(self):
        """获取当前可见的页面"""
        visible_pages = []
        viewport_bottom = self.viewport_top + self.viewport_height
        
        for i, (page_y, page_height) in enumerate(zip(self.page_positions, self.page_heights)):
            page_bottom = page_y + page_height
            
            # 添加一些缓冲区域
            buffer = 100
            if (page_y - buffer) < viewport_bottom and (page_bottom + buffer) > self.viewport_top:
                visible_pages.append(i)
                
        return visible_pages
        
    def get_current_page(self):
        """获取当前主要可见页面"""
        viewport_center = self.viewport_top + self.viewport_height // 2
        
        for i, page_y in enumerate(self.page_positions):
            if i < len(self.page_heights):
                page_bottom = page_y + self.page_heights[i]
                if page_y <= viewport_center <= page_bottom:
                    return i
        return 0
        
    def render_page(self, page_num):
        """渲染指定页面"""
        if page_num in self.pending_renders or page_num in self.render_threads:
            return
            
        self.pending_renders.add(page_num)
        
        # 创建渲染线程
        thread = PageRenderThread(self.doc, page_num, self.zoom_factor, self.dpi, self)
        thread.page_rendered.connect(self.on_page_rendered)
        thread.finished.connect(lambda: self.on_thread_finished(page_num))
        
        self.render_threads[page_num] = thread
        thread.start()
        
    def on_thread_finished(self, page_num):
        """线程完成时的清理"""
        self.pending_renders.discard(page_num)
        if page_num in self.render_threads:
            thread = self.render_threads.pop(page_num)
            thread.deleteLater()
        
    @pyqtSlot(int, QPixmap, list)
    def on_page_rendered(self, page_num, pixmap, text_words):
        """页面渲染完成"""
        # 添加到缓存
        self.page_cache[page_num] = pixmap
        self.text_cache[page_num] = text_words
        
        # 移动到缓存末尾（LRU）
        self.page_cache.move_to_end(page_num)
        
        # 清理过老的缓存
        while len(self.page_cache) > self.max_cache_size:
            old_page = self.page_cache.popitem(last=False)[0]
            if old_page in self.text_cache:
                del self.text_cache[old_page]
                
        self.update_visible_words()
        self.update()
        
    def preload_nearby_pages(self):
        """预加载附近的页面"""
        if not self.doc:
            return
            
        current_page = self.get_current_page()
        
        # 预加载前后2页
        for offset in [-2, -1, 1, 2]:
            page_num = current_page + offset
            if (0 <= page_num < len(self.doc) and 
                page_num not in self.page_cache and 
                page_num not in self.pending_renders):
                self.render_page(page_num)
                
    def update_visible_words(self):
        """更新可见文本单词"""
        self.visible_words.clear()
        
        visible_pages = self.get_visible_pages()
        
        for page_num in visible_pages:
            if page_num in self.text_cache and page_num in self.page_cache:
                pixmap = self.page_cache[page_num]
                words = self.text_cache[page_num]
                page_y = self.page_positions[page_num]
                
                page = self.doc[page_num]
                scale_x = pixmap.width() / page.rect.width
                scale_y = pixmap.height() / page.rect.height
                
                for word in words:
                    x0, y0, x1, y1 = word['bbox']
                    
                    screen_x = int(x0 * scale_x)
                    screen_y = int(y0 * scale_y) + page_y
                    screen_w = int((x1 - x0) * scale_x)
                    screen_h = int((y1 - y0) * scale_y)
                    
                    display_rect = QRect(screen_x, screen_y, screen_w, screen_h)
                    
                    self.visible_words.append({
                        'text': word['text'],
                        'display_rect': display_rect,
                        'page_num': page_num,
                        'selected': False
                    })
    
    def get_word_at_pos(self, pos):
        """获取指定位置的单词"""
        for i, word in enumerate(self.visible_words):
            if word['display_rect'].contains(pos):
                return i
        return -1
    
    def is_over_text(self, pos):
        """检查是否在文本上"""
        return self.get_word_at_pos(pos) >= 0
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.position().toPoint()
            self.current_pos = self.start_pos
            
            for word in self.visible_words:
                word['selected'] = False
            self.selected_words.clear()
            
            if self.is_over_text(self.start_pos):
                self.selecting = True
            else:
                self.selecting = False
                
            self.update()
    
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        pos = event.position().toPoint()
        
        if self.selecting:
            self.current_pos = pos
            self.update_text_selection()
            self.update()
        else:
            if self.is_over_text(pos):
                self.setCursor(self.text_cursor)
            else:
                self.setCursor(self.arrow_cursor)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if event.button() == Qt.MouseButton.LeftButton and self.selecting:
            self.selecting = False
            self.extract_selected_text()
    
    def update_text_selection(self):
        """更新文本选择"""
        if not self.selecting:
            return
            
        for word in self.visible_words:
            word['selected'] = False
        self.selected_words.clear()
        
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
        
        if not selected:
            selection_rect = QRect(start_x, start_y, end_x - start_x, end_y - start_y)
            for i, word in enumerate(self.visible_words):
                if selection_rect.intersects(word['display_rect']):
                    rect = word['display_rect']
                    selected.append((i, word['page_num'], rect.center().y(), rect.center().x()))
        
        selected.sort(key=lambda x: (x[1], x[2], x[3]))
        for word_idx, _, _, _ in selected:
            self.visible_words[word_idx]['selected'] = True
            self.selected_words.append(word_idx)
    
    def extract_selected_text(self):
        """提取选中文本"""
        if not self.selected_words:
            return
            
        texts = []
        last_y, last_page = None, None
        
        selected_data = []
        for idx in self.selected_words:
            word = self.visible_words[idx]
            rect = word['display_rect']
            selected_data.append((word['page_num'], rect.center().y(), rect.center().x(), word['text']))
        
        selected_data.sort()
        
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
        if self.selected_text:
            self.text_selected.emit(self.selected_text)
    
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        visible_pages = self.get_visible_pages()
        
        for page_num in visible_pages:
            if page_num >= len(self.page_positions):
                continue
                
            page_y = self.page_positions[page_num]
            
            if page_num in self.page_cache:
                # 绘制已渲染的页面
                pixmap = self.page_cache[page_num]
                painter.drawPixmap(0, page_y, pixmap)
                
                # 绘制边框
                border_rect = QRect(0, page_y, pixmap.width(), pixmap.height())
                painter.setPen(QPen(QColor(200, 200, 200), 1))
                painter.drawRect(border_rect)
                
                # 绘制页码
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.setFont(QFont("Arial", 10))
                text_y = page_y + pixmap.height() + 15
                painter.drawText(10, text_y, f"第 {page_num + 1} 页")
                
            else:
                # 绘制加载占位符
                placeholder_height = self.page_heights[page_num] if page_num < len(self.page_heights) else 800
                placeholder_width = self.get_page_display_width(page_num)
                placeholder_rect = QRect(0, page_y, placeholder_width, placeholder_height)
                
                painter.fillRect(placeholder_rect, QColor(248, 249, 250))
                painter.setPen(QPen(QColor(200, 200, 200), 2, Qt.PenStyle.DashLine))
                painter.drawRect(placeholder_rect)
                
                # 绘制加载文字
                painter.setPen(QPen(QColor(120, 120, 120)))
                painter.setFont(QFont("Microsoft YaHei", 14))
                
                loading_text = f"第 {page_num + 1} 页"
                if page_num in self.pending_renders:
                    loading_text += "\n渲染中..."
                else:
                    loading_text += "\n等待加载..."
                    
                painter.drawText(placeholder_rect, Qt.AlignmentFlag.AlignCenter, loading_text)
        
        # 绘制选中文本高亮
        highlight_color = QColor(0, 123, 255, 80)
        border_color = QColor(0, 123, 255, 150)
        
        for word in self.visible_words:
            if word['selected']:
                painter.fillRect(word['display_rect'], highlight_color)
                painter.setPen(QPen(border_color, 1))
                painter.drawRect(word['display_rect'])


class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高性能连续PDF预览器")
        self.setGeometry(100, 100, 1200, 800)
        
        self.doc = None
        self.zoom_factor = 1.5
        self.current_page = 0
        self.total_pages = 0
        
        self.create_menu()
        self.create_ui()
        self.create_status_bar()
        
    def create_menu(self):
        """创建菜单"""
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu('文件')
        
        open_action = QAction('打开PDF', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        edit_menu = menubar.addMenu('编辑')
        
        copy_action = QAction('复制', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(self.copy_text)
        edit_menu.addAction(copy_action)
        
    def create_ui(self):
        """创建界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        toolbar = QHBoxLayout()
        
        self.page_label = QLabel('页面: 0 / 0')
        toolbar.addWidget(self.page_label)
        
        toolbar.addStretch()
        
        zoom_out_btn = QPushButton('缩小 (-)')
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        self.zoom_label = QLabel('150%')
        toolbar.addWidget(self.zoom_label)
        
        zoom_in_btn = QPushButton('放大 (+)')
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        reset_btn = QPushButton('重置')
        reset_btn.clicked.connect(self.reset_zoom)
        toolbar.addWidget(reset_btn)
        
        main_layout.addLayout(toolbar)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.pdf_widget = VirtualPDFWidget()
        self.pdf_widget.text_selected.connect(self.on_text_selected)
        self.pdf_widget.page_changed.connect(self.on_page_changed)
        
        placeholder = QLabel("请打开PDF文件\n\n功能特点：\n• 连续滚动浏览\n• 虚拟渲染技术\n• 精确文本选择\n• Ctrl+滚轮缩放")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("QLabel { background: #f8f9fa; padding: 50px; font-size: 16px; color: #666; }")
        
        self.scroll_area.setWidget(placeholder)
        main_layout.addWidget(self.scroll_area)
        
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.scroll_area.wheelEvent = self.wheel_event
        
        self.selected_text = ""
        
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
    def open_file(self):
        """打开文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF文件 (*.pdf)"
        )
        
        if file_path:
            self.load_pdf(file_path)
            
    def load_pdf(self, file_path):
        """加载PDF"""
        try:
            if self.doc:
                self.doc.close()
                
            self.doc = fitz.open(file_path)
            self.total_pages = len(self.doc)
            
            self.status_bar.showMessage("正在初始化PDF显示...")
            
            # 设置PDF widget
            self.pdf_widget.set_document(self.doc, self.zoom_factor)
            self.scroll_area.setWidget(self.pdf_widget)
            
            # 更新界面
            self.page_label.setText(f'页面: 1 / {self.total_pages}')
            self.zoom_label.setText(f'{int(self.zoom_factor * 100)}%')
            
            # 触发初始加载
            QApplication.processEvents()
            self.on_scroll(0)
            
            self.status_bar.showMessage(f"已载入: {file_path.split('/')[-1]} ({self.total_pages} 页)")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开PDF:\n{str(e)}")
            
    def wheel_event(self, event):
        """滚轮事件"""
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            QScrollArea.wheelEvent(self.scroll_area, event)
            
    def zoom_in(self):
        """放大"""
        if self.zoom_factor < 3.0:
            old_ratio = self.get_scroll_ratio()
            self.zoom_factor *= 1.25
            self.refresh_view(old_ratio)
            
    def zoom_out(self):
        """缩小"""
        if self.zoom_factor > 0.5:
            old_ratio = self.get_scroll_ratio()
            self.zoom_factor /= 1.25
            self.refresh_view(old_ratio)
    
    def reset_zoom(self):
        """重置缩放"""
        old_ratio = self.get_scroll_ratio()
        self.zoom_factor = 1.5
        self.refresh_view(old_ratio)
            
    def get_scroll_ratio(self):
        """获取当前滚动比例"""
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() > 0:
            return scrollbar.value() / scrollbar.maximum()
        return 0
        
    def refresh_view(self, scroll_ratio=0):
        """刷新视图"""
        if self.doc:
            self.status_bar.showMessage(f"正在重新渲染 (缩放: {int(self.zoom_factor * 100)}%)...")
            
            # 重新设置文档和缩放
            self.pdf_widget.set_document(self.doc, self.zoom_factor)
            self.zoom_label.setText(f'{int(self.zoom_factor * 100)}%')
            
            # 等待布局更新
            QApplication.processEvents()
            
            # 恢复滚动位置
            QTimer.singleShot(50, lambda: self.restore_scroll_position(scroll_ratio))
            
            self.status_bar.showMessage(f"缩放完成: {int(self.zoom_factor * 100)}%")
    
    def restore_scroll_position(self, scroll_ratio):
        """恢复滚动位置"""
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() > 0:
            new_value = int(scroll_ratio * scrollbar.maximum())
            scrollbar.setValue(new_value)
            
    def on_scroll(self, value):
        """滚动事件"""
        if hasattr(self.pdf_widget, 'doc') and self.pdf_widget.doc:
            viewport_height = self.scroll_area.viewport().height()
            self.pdf_widget.update_viewport(value, viewport_height)
            
    def on_page_changed(self, page_num):
        """页面改变"""
        self.current_page = page_num
        self.page_label.setText(f'页面: {page_num + 1} / {self.total_pages}')
        
    def on_text_selected(self, text):
        """文本选择"""
        self.selected_text = text
        word_count = len(text.split())
        self.status_bar.showMessage(f"已选择: {word_count} 词 - Ctrl+C复制")
        
    def copy_text(self):
        """复制文本"""
        if self.selected_text:
            QApplication.clipboard().setText(self.selected_text)
            self.status_bar.showMessage("已复制到剪贴板")
        else:
            self.status_bar.showMessage("没有选中文本")
            
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'pdf_widget'):
            self.pdf_widget.cleanup_threads()
        
        if self.doc:
            self.doc.close()
            
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec())
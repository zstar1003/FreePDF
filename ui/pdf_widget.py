"""PDF显示组件"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.pdf_document import PageCache
from core.render_thread import PageRenderThread
from core.text_selection import TextSelection
from utils.constants import (
    DEFAULT_DPI,
    DEFAULT_ZOOM,
    HIGH_QUALITY_DPI,
    MAX_PAGE_WIDTH,
    MAX_ZOOM,
    MIN_ZOOM,
    PAGE_SPACING,
    PLACEHOLDER_COLOR,
    PRELOAD_DELAY,
    PRELOAD_DISTANCE,
    VIEWPORT_BUFFER,
    ZOOM_STEP,
)


class PageGraphicsItem(QGraphicsPixmapItem):
    """PDF页面图形项"""
    
    def __init__(self, page_num, pixmap=None):
        super().__init__(pixmap)
        self.page_num = page_num
        self.is_placeholder = pixmap is None
        self.base_zoom = DEFAULT_ZOOM
        
    def set_pixmap(self, pixmap):
        """设置页面像素图"""
        self.setPixmap(pixmap)
        self.is_placeholder = False
        
    def set_placeholder(self, width, height):
        """设置占位符"""
        from PyQt6.QtGui import QPainter, QPixmap
        
        placeholder = QPixmap(width, height)
        placeholder.fill(QColor(*PLACEHOLDER_COLOR))
        
        painter = QPainter(placeholder)
        painter.setPen(QColor(120, 120, 120))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, 
                        f"加载中... ({self.page_num + 1})")
        painter.end()
        
        self.setPixmap(placeholder)
        self.is_placeholder = True


class SmoothPDFView(QGraphicsView):
    """丝滑缩放的PDF视图"""
    text_selected = pyqtSignal(str)
    page_changed = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        
        # 基础设置
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        
        # 样式设置，类似原来的scroll_area样式
        self.setStyleSheet("""
            QGraphicsView {
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
        
        # 创建场景
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # PDF相关
        self.pdf_doc = None
        self.page_cache = PageCache()
        self.page_items = []  # 页面图形项列表
        self.page_heights = []
        self.page_positions = []
        
        # 缩放设置
        self.base_zoom = DEFAULT_ZOOM
        self.current_zoom = DEFAULT_ZOOM
        self.min_zoom = MIN_ZOOM
        self.max_zoom = MAX_ZOOM
        
        # 渲染管理
        self.render_threads = {}
        self.pending_renders = set()
        self._is_shutting_down = False
        
        # 预加载计时器
        self.preload_timer = QTimer()
        self.preload_timer.timeout.connect(self.preload_nearby_pages)
        self.preload_timer.setSingleShot(True)
        
        # 高质量渲染计时器
        self.high_quality_timer = QTimer()
        self.high_quality_timer.timeout.connect(self._render_high_quality)
        self.high_quality_timer.setSingleShot(True)
        
        # 文本选择
        self.text_selection = TextSelection()
        
        # 自适应缩放相关
        self.auto_fit_zoom = DEFAULT_ZOOM
        self.container_width = 800  # 默认容器宽度
        
        # 全局缩放回调（由主窗口设置）
        self.zoom_requested = None
        
        # 绑定滚动事件
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        
    def set_document(self, pdf_doc):
        """设置PDF文档"""
        if self._is_shutting_down:
            return
            
        # 停止所有当前的渲染操作
        self._cleanup_old_threads()
        
        self.pdf_doc = pdf_doc
        if pdf_doc and pdf_doc.doc:
            # 1. 先计算自适应缩放
            self._calculate_auto_fit_zoom()
            
            # 2. 清除所有缓存，确保从头开始
            self.page_cache.clear()
            self.pending_renders.clear()
            
            # 3. 使用自适应缩放值重新设置页面布局
            self._setup_pages()
            
            # 4. 延迟渲染，确保布局完成后再开始渲染
            QTimer.singleShot(50, self._render_visible_pages)
            
    def _setup_pages(self):
        """设置页面布局"""
        if not self.pdf_doc or not self.pdf_doc.doc:
            return
            
        # 清除旧的页面项
        self.scene.clear()
        self.page_items = []
        self.page_heights = []
        self.page_positions = []
        
        current_y = 0  # 从顶部开始，不留空间
        # 使用当前缩放值（包括自适应缩放）
        base_scale = self.current_zoom * (DEFAULT_DPI / 72.0)
        
        # 计算容器宽度用于居中
        container_width = self.viewport().width()
        if container_width <= 0:
            container_width = 800  # 默认宽度
        
        max_page_width = 0
        
        for page_num in range(self.pdf_doc.total_pages):
            page_rect = self.pdf_doc.get_page_rect(page_num)
            if not page_rect:
                continue
                
            # 计算基础显示尺寸
            display_width = int(page_rect.width * base_scale)
            display_height = int(page_rect.height * base_scale)
            
            # 限制最大宽度
            if display_width > MAX_PAGE_WIDTH:
                scale_ratio = MAX_PAGE_WIDTH / display_width
                display_width = MAX_PAGE_WIDTH
                display_height = int(display_height * scale_ratio)
            
            # 记录最大页面宽度
            max_page_width = max(max_page_width, display_width)
            
            # 计算居中的x坐标，确保页面在容器内居中
            center_x = max(0, (container_width - display_width) / 2)
            
            # 创建页面图形项（先用占位符）
            page_item = PageGraphicsItem(page_num)
            page_item.set_placeholder(display_width, display_height)
            page_item.setPos(center_x, current_y)
            
            self.scene.addItem(page_item)
            self.page_items.append(page_item)
            self.page_positions.append(current_y)
            self.page_heights.append(display_height)
            
            # 页面间距处理
            current_y += display_height
            if page_num < self.pdf_doc.total_pages - 1 and PAGE_SPACING > 0:
                current_y += PAGE_SPACING
        
        # 设置场景大小，确保不超出容器宽度
        # 在自适应缩放下，页面应该正好适合容器，因此场景宽度应该等于容器宽度
        scene_width = container_width
        self.scene.setSceneRect(0, 0, scene_width, current_y)
        
        # 重新居中所有页面
        self._center_all_pages()
    
    def _center_all_pages(self):
        """重新居中所有页面"""
        if not self.page_items:
            return
            
        container_width = self.viewport().width()
        if container_width <= 0:
            return
            
        for page_item in self.page_items:
            current_pos = page_item.pos()
            page_width = page_item.pixmap().width() if page_item.pixmap() else 0
            
            if page_width > 0:
                # 计算新的居中x坐标，保持最小边距一致
                center_x = max(0, (container_width - page_width) / 2)
                page_item.setPos(center_x, current_pos.y())
    
    def _calculate_auto_fit_zoom(self):
        """计算自适应缩放比例"""
        if not self.pdf_doc or not self.pdf_doc.doc:
            return
        
        # 更新容器宽度，确保页面完全适合容器
        self.container_width = self.viewport().width()
        
        # 获取第一页尺寸作为参考
        first_page_rect = self.pdf_doc.get_page_rect(0)
        if not first_page_rect:
            return
        
        # 计算适合容器宽度的缩放比例
        page_width = first_page_rect.width
        if page_width > 0:
            fit_zoom = self.container_width / page_width
            # 限制在合理范围内
            fit_zoom = max(self.min_zoom, min(fit_zoom, self.max_zoom))
            
            self.auto_fit_zoom = fit_zoom
            self.base_zoom = fit_zoom
            self.current_zoom = fit_zoom
            
            print(f"自适应缩放: {fit_zoom:.2f}, 页面宽度: {page_width:.1f}, 容器宽度: {self.container_width}")
        
    def set_zoom(self, zoom_factor):
        """设置缩放（即时变换）- 外部调用"""
        if hasattr(self, 'zoom_requested') and self.zoom_requested:
            # 如果有全局缩放管理器，转发给它处理
            self.zoom_requested(zoom_factor)
        else:
            # 否则使用内部处理
            self.set_zoom_internal(zoom_factor)
            
    def set_zoom_internal(self, zoom_factor):
        """内部缩放设置（不经过全局管理器）"""
        if not self.pdf_doc:
            return
            
        # 限制缩放范围
        zoom_factor = max(self.min_zoom, min(zoom_factor, self.max_zoom))
        
        if abs(zoom_factor - self.current_zoom) < 0.01:
            return
            
        # 获取当前滚动位置作为百分比
        old_scroll_ratio_x = 0
        old_scroll_ratio_y = 0
        
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        
        if h_bar.maximum() > 0:
            old_scroll_ratio_x = h_bar.value() / h_bar.maximum()
        if v_bar.maximum() > 0:
            old_scroll_ratio_y = v_bar.value() / v_bar.maximum()
            
        # 更新缩放比例
        self.current_zoom = zoom_factor
        self.base_zoom = zoom_factor
        
        # 重新布局所有页面（这是关键！）
        self._setup_pages()
        
        # 清除缓存并重新渲染可见页面
        self.page_cache.clear()
        self._render_visible_pages()
        
        # 恢复滚动位置
        QTimer.singleShot(50, lambda: self._restore_scroll_position(old_scroll_ratio_x, old_scroll_ratio_y))
        
    def _restore_scroll_position(self, ratio_x, ratio_y):
        """恢复滚动位置"""
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        
        if h_bar.maximum() > 0:
            h_bar.setValue(int(ratio_x * h_bar.maximum()))
        if v_bar.maximum() > 0:
            v_bar.setValue(int(ratio_y * v_bar.maximum()))
        
    def _render_high_quality(self):
        """渲染高质量页面"""
        if not self.pdf_doc:
            return
            
        # 获取可见页面
        visible_pages = self._get_visible_pages()
        
        # 停止所有正在进行的渲染
        self._cleanup_old_threads()
        
        # 清除可见页面的缓存，强制重新渲染
        for page_num in visible_pages:
            if page_num in self.page_cache.page_cache:
                del self.page_cache.page_cache[page_num]
                
        # 重新渲染可见页面，使用高质量
        for page_num in visible_pages:
            if (page_num not in self.pending_renders and
                not self._is_shutting_down):
                self._render_page(page_num, high_quality=True)
        
    def _get_visible_pages(self):
        """获取可见页面"""
        visible_pages = []
        viewport_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        
        for i, (page_y, page_height) in enumerate(zip(self.page_positions, self.page_heights)):
            page_bottom = page_y + page_height
            
            if (page_y - VIEWPORT_BUFFER) < viewport_rect.bottom() and \
               (page_bottom + VIEWPORT_BUFFER) > viewport_rect.top():
                visible_pages.append(i)
                
        return visible_pages
        
    def _render_visible_pages(self):
        """渲染可见页面"""
        if self._is_shutting_down:
            return
            
        visible_pages = self._get_visible_pages()
        
        for page_num in visible_pages:
            if (not self.page_cache.has_page(page_num) and 
                page_num not in self.pending_renders and
                not self._is_shutting_down):
                self._render_page(page_num)
        
        # 启动预加载
        if not self._is_shutting_down:
            self.preload_timer.start(PRELOAD_DELAY)
            
    def _render_page(self, page_num, high_quality=True):
        """渲染指定页面"""
        if (self._is_shutting_down or 
            page_num in self.pending_renders or 
            page_num in self.render_threads):
            return
            
        self.pending_renders.add(page_num)
        
        # 计算当前缩放下的渲染尺寸
        effective_zoom = self.current_zoom
        
        # 使用更高的DPI获得更好的质量
        render_dpi = HIGH_QUALITY_DPI if high_quality else DEFAULT_DPI
        
        thread = PageRenderThread(
            self.pdf_doc.doc, page_num, 
            effective_zoom, render_dpi, 
            target_width=self.container_width,
            high_quality=high_quality,
            parent=self
        )
        
        # 连接信号
        thread.page_rendered.connect(self._on_page_rendered)
        thread.preview_rendered.connect(self._on_preview_rendered)
        thread.finished.connect(lambda: self._on_thread_finished(page_num))
        
        self.render_threads[page_num] = thread
        thread.start()
        
    def _on_page_rendered(self, page_num, pixmap, text_words):
        """页面渲染完成"""
        if self._is_shutting_down or page_num >= len(self.page_items):
            return
            
        # 缓存渲染结果
        self.page_cache.set_page(page_num, pixmap, text_words)
        
        # 更新页面图形项
        page_item = self.page_items[page_num]
        old_height = self.page_heights[page_num] if page_num < len(self.page_heights) else 0
        
        page_item.set_pixmap(pixmap)
        
        # 检查实际渲染的页面高度是否与预期不同
        actual_height = pixmap.height()
        if abs(actual_height - old_height) > 1:  # 高度差超过1像素则需要重新布局
            print(f"页面 {page_num} 高度调整: {old_height} -> {actual_height}")
            self._update_page_layout_from(page_num)
        else:
            # 只需要重新居中该页面
            self._center_page(page_item)
        
        # 更新文本选择
        self._update_visible_words()
    
    def _on_preview_rendered(self, page_num, pixmap):
        """预览渲染完成（快速低质量版本）"""
        if self._is_shutting_down or page_num >= len(self.page_items):
            return
            
        # 只有当没有高质量版本时才显示预览
        if not self.page_cache.has_page(page_num):
            page_item = self.page_items[page_num]
            old_height = self.page_heights[page_num] if page_num < len(self.page_heights) else 0
            
            page_item.set_pixmap(pixmap)
            
            # 检查实际渲染的页面高度是否与预期不同
            actual_height = pixmap.height()
            if abs(actual_height - old_height) > 1:  # 高度差超过1像素则需要重新布局
                self._update_page_layout_from(page_num)
            else:
                # 只需要重新居中该页面
                self._center_page(page_item)
        
    def _update_page_layout_from(self, start_page_num):
        """从指定页面开始重新计算和更新页面布局"""
        if not self.page_items or start_page_num >= len(self.page_items):
            return
            
        # 更新指定页面的高度
        page_item = self.page_items[start_page_num]
        if page_item.pixmap():
            self.page_heights[start_page_num] = page_item.pixmap().height()
        
        # 重新计算从该页面开始的所有页面位置
        if start_page_num == 0:
            current_y = 0
        else:
            # 从前一页的底部开始
            prev_page_bottom = self.page_positions[start_page_num - 1] + self.page_heights[start_page_num - 1]
            current_y = prev_page_bottom + (PAGE_SPACING if PAGE_SPACING > 0 else 0)
        
        container_width = self.viewport().width()
        
        # 更新从start_page_num开始的所有页面位置
        for i in range(start_page_num, len(self.page_items)):
            page_item = self.page_items[i]
            
            # 更新页面位置
            self.page_positions[i] = current_y
            
            # 重新居中页面
            if page_item.pixmap():
                page_width = page_item.pixmap().width()
                center_x = max(0, (container_width - page_width) / 2)
                page_item.setPos(center_x, current_y)
                
                # 更新页面高度（如果已渲染）
                self.page_heights[i] = page_item.pixmap().height()
            
            # 计算下一页的y位置
            current_y += self.page_heights[i]
            if i < len(self.page_items) - 1 and PAGE_SPACING > 0:
                current_y += PAGE_SPACING
        
        # 更新场景大小
        scene_width = container_width
        self.scene.setSceneRect(0, 0, scene_width, current_y)
    
    def _center_page(self, page_item):
        """居中单个页面"""
        current_pos = page_item.pos()
        page_width = page_item.pixmap().width() if page_item.pixmap() else 0
        
        if page_width > 0:
            container_width = self.viewport().width()
            center_x = max(0, (container_width - page_width) / 2)
            page_item.setPos(center_x, current_pos.y())
         
    def _on_thread_finished(self, page_num):
        """线程完成清理"""
        self.pending_renders.discard(page_num)
        if page_num in self.render_threads:
            thread = self.render_threads.pop(page_num)
            QTimer.singleShot(100, thread.deleteLater)
        
    def preload_nearby_pages(self):
        """预加载附近页面"""
        if not self.pdf_doc or self._is_shutting_down:
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
                # 预加载页面使用快速渲染
                self._render_page(page_num, high_quality=False)
                
    def _get_current_page(self):
        """获取当前页面"""
        viewport_center = self.mapToScene(self.viewport().rect().center())
        
        for i, page_y in enumerate(self.page_positions):
            if i < len(self.page_heights):
                page_bottom = page_y + self.page_heights[i]
                if page_y <= viewport_center.y() <= page_bottom:
                    return i
        return 0
        
    def _on_scroll(self):
        """滚动事件"""
        if not self._is_shutting_down:
            self._render_visible_pages()
            
            current_page = self._get_current_page()
            self.page_changed.emit(current_page)
            
    def _update_visible_words(self):
        """更新可见文本单词"""
        # TODO: 实现文本选择功能
        pass
        
    def wheelEvent(self, event):
        """滚轮事件"""
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Ctrl+滚轮缩放 - 通过全局缩放管理器
            delta = event.angleDelta().y()
            zoom_factor = ZOOM_STEP if delta > 0 else 1/ZOOM_STEP
            new_zoom = self.current_zoom * zoom_factor
            
            # 使用全局缩放管理
            if hasattr(self, 'zoom_requested') and self.zoom_requested:
                self.zoom_requested(new_zoom)
            else:
                self.set_zoom_internal(new_zoom)
                
            event.accept()
        else:
            # 正常滚动
            super().wheelEvent(event)
            
    def _cleanup_old_threads(self):
        """清理旧线程"""
        if self._is_shutting_down:
            return
            
        # 停止所有正在运行的线程
        for page_num, thread in list(self.render_threads.items()):
            if thread.isRunning():
                thread.stop()  # 停止渲染
        
        # 清理已完成的线程
        finished_threads = []
        for page_num, thread in list(self.render_threads.items()):
            if not thread.isRunning():
                finished_threads.append(page_num)
        
        for page_num in finished_threads:
            if page_num in self.render_threads:
                thread = self.render_threads.pop(page_num)
                QTimer.singleShot(100, thread.deleteLater)
                
        # 清空pending renders
        self.pending_renders.clear()
    
    def cleanup_threads(self):
        """完全清理线程"""
        print("开始清理PDF视图线程...")
        self._is_shutting_down = True
        
        # 停止计时器
        self.preload_timer.stop()
        self.high_quality_timer.stop()
        
        # 停止所有线程
        active_threads = []
        for page_num, thread in list(self.render_threads.items()):
            if thread.isRunning():
                print(f"停止线程 {page_num}")
                thread.stop()
                active_threads.append(thread)
        
        # 等待线程完成
        for thread in active_threads:
            if not thread.wait(2000):
                print(f"强制终止线程 {thread.page_num}")
                thread.terminate()
                thread.wait(1000)
        
        # 清理所有引用
        self.render_threads.clear()
        self.pending_renders.clear()
        
        print("PDF视图线程清理完成")
    
    def resizeEvent(self, event):
        """窗口大小变化事件"""
        super().resizeEvent(event)
        
        # 如果有文档加载，重新计算自适应缩放和重新布局
        if self.pdf_doc and hasattr(self, 'auto_fit_zoom'):
            old_width = self.container_width
            self._calculate_auto_fit_zoom()
            
            # 重新设置整个页面布局（包括场景大小）
            self._setup_pages()
            
            # 如果容器宽度显著变化，重新渲染以获得最佳显示效果
            if abs(self.container_width - old_width) > 20:
                self._render_visible_pages()


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
        
        # 创建PDF视图
        self.pdf_view = SmoothPDFView()
        
        # 占位符
        self.placeholder = QLabel(
            "请打开PDF文件\n\n可通过 Ctrl+滚轮 控制缩放"
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
        
        # 默认显示占位符
        layout.addWidget(self.placeholder)
        
        # 连接信号
        self.pdf_view.text_selected.connect(self.text_selected.emit)
        self.pdf_view.page_changed.connect(self.page_changed.emit)
        
        # 为了兼容旧代码，添加scroll_area属性指向pdf_view
        self.scroll_area = self.pdf_view
        
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
                # 切换到PDF视图
                layout = self.layout()
                layout.removeWidget(self.placeholder)
                self.placeholder.hide()
                layout.addWidget(self.pdf_view)
                
                # 设置文档到视图
                self.pdf_view.set_document(pdf_doc)
                
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
            
        self.zoom_factor = zoom_factor
        self.pdf_view.set_zoom(zoom_factor)
        
    def cleanup(self):
        """清理资源"""
        if hasattr(self, 'pdf_view'):
            self.pdf_view.cleanup_threads()
            
        if self.doc:
            self.doc.close()
            self.doc = None
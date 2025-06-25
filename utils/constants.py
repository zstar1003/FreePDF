"""常量定义"""

# 渲染设置
DEFAULT_ZOOM = 1.0  # 改为1.0，让自适应缩放来决定初始缩放
DEFAULT_DPI = 200   # 提高默认DPI获得更好清晰度
HIGH_QUALITY_DPI = 300  # 高质量渲染DPI
MAX_ZOOM = 5.0      # 增加最大缩放
MIN_ZOOM = 0.3      # 允许更小的缩放
ZOOM_STEP = 1.25

# 缓存设置
MAX_CACHE_SIZE = 6
PRELOAD_DISTANCE = 2

# 显示设置
PAGE_SPACING = 1  # 进一步减少到1像素，实现真正无缝连续
MAX_PAGE_WIDTH = 1200  # 增加以支持更高清晰度，会被自适应缩放控制
VIEWPORT_BUFFER = 50  # 减少缓冲区以节省空间

# 定时器设置
PRELOAD_DELAY = 150  # ms
SCROLL_RESTORE_DELAY = 50  # ms
TRANSLATION_CHECK_DELAY = 1000  # ms 翻译状态检查间隔

# 颜色定义
HIGHLIGHT_COLOR = (0, 123, 255, 80)
BORDER_COLOR = (0, 123, 255, 150)
PAGE_BORDER_COLOR = (200, 200, 200, 255)
PLACEHOLDER_COLOR = (248, 249, 250, 255)

# 双预览器设置
PREVIEW_SPLITTER_RATIO = 0.5  # 左右预览器宽度比例
PROCESSING_ANIMATION_SPEED = 100  # ms 处理动画速度

# 翻译设置
DEFAULT_LANG_IN = "en"
DEFAULT_LANG_OUT = "zh"
DEFAULT_SERVICE = "google"
DEFAULT_THREADS = 4 
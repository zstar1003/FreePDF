"""翻译日志管理器"""

import time
from datetime import datetime
from collections import deque
import threading
from typing import Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from utils.diagnostics import get_logger, redact


class TranslationLogger(QObject):
    """翻译日志管理器 - 单例模式"""

    # 日志更新信号
    state_updated = pyqtSignal(dict)
    log_updated = pyqtSignal(str)  # 新日志消息

    def __init__(self):
        # QObject must be initialized before setting Python instance attributes.
        # The get_translation_logger() accessor owns the singleton.
        super().__init__()

        # 日志存储（最多保留1000条）
        self._logs = deque(maxlen=1000)
        self._state_lock = threading.RLock()
        self._state = {"status": "idle", "stage": "尚未开始翻译", "completed": 0, "total": 0, "active": 0, "finished": 0, "failed": 0}
        self._ended_at = 0

        # 心跳时间戳
        self._last_heartbeat = 0
        self._heartbeat_interval = 30  # 心跳间隔（秒）

        # 超时设置
        self._translation_timeout = 0  # 逐页提交，无整份文档固定截止时间
        self._api_timeout = 120  # API调用超时时间（秒，默认2分钟）

        # 翻译开始时间
        self._translation_start_time = 0

        # 当前阶段
        self._current_stage = ""
        self._stage_start_time = 0

    def set_timeout(self, translation_timeout: int = 0, api_timeout: int = 120):
        """设置超时时间"""
        self._translation_timeout = translation_timeout
        self._api_timeout = api_timeout
        self.info(f"超时设置更新: 翻译超时={translation_timeout}秒, API超时={api_timeout}秒")

    def get_translation_timeout(self) -> int:
        """获取翻译超时时间"""
        return self._translation_timeout

    def get_api_timeout(self) -> int:
        """获取API超时时间"""
        return self._api_timeout

    def start_translation(self, file_path: str):
        """开始翻译时调用"""
        self._translation_start_time = time.time()
        self._last_heartbeat = time.time()
        self.clear()
        self._ended_at = 0
        with self._state_lock:
            self._state = {"status": "running", "stage": "准备翻译", "file": file_path, "completed": 0, "total": 0, "page": 0, "active": 0, "finished": 0, "failed": 0, "last_activity": time.monotonic()}
        self.state_updated.emit(self.get_state())
        self.info("=" * 50)
        self.info(f"开始翻译: {file_path}")
        self.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info(f"API 无响应上限: {self._api_timeout}秒；逐页保存，无整份文档固定时限")
        self.info("=" * 50)

    def end_translation(self, success: bool, message: str = ""):
        """结束翻译时调用"""
        self._ended_at = time.time()
        elapsed = self._ended_at - self._translation_start_time
        self.info("=" * 50)
        if success:
            self.info(f"翻译成功完成")
        else:
            self.error(f"翻译失败: {message}")
        self.info(f"总耗时: {elapsed:.2f}秒")
        self.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info("=" * 50)

    def start_stage(self, stage_name: str):
        """开始新阶段"""
        if self._current_stage:
            self._end_current_stage()
        self._current_stage = stage_name
        self._stage_start_time = time.time()
        self.info(f"[阶段开始] {stage_name}")

    def _end_current_stage(self):
        """结束当前阶段"""
        if self._current_stage:
            elapsed = time.time() - self._stage_start_time
            self.info(f"[阶段结束] {self._current_stage} (耗时: {elapsed:.2f}秒)")
            self._current_stage = ""

    def heartbeat(self) -> bool:
        """心跳检测，返回是否超时"""
        current_time = time.time()
        self._last_heartbeat = current_time

        # 检查是否超时
        if self._translation_start_time > 0:
            elapsed = current_time - self._translation_start_time
            if self._translation_timeout > 0 and elapsed > self._translation_timeout:
                self.error(f"翻译超时! 已运行 {elapsed:.2f}秒，超时阈值 {self._translation_timeout}秒")
                return True  # 超时
        return False  # 未超时

    def check_timeout(self) -> tuple[bool, float]:
        """检查是否超时，返回(是否超时, 已运行时间)"""
        if self._translation_start_time <= 0:
            return False, 0
        elapsed = time.time() - self._translation_start_time
        is_timeout = self._translation_timeout > 0 and elapsed > self._translation_timeout
        return is_timeout, elapsed

    def get_elapsed_time(self) -> float:
        """获取已运行时间"""
        if self._translation_start_time <= 0:
            return 0
        return (self._ended_at or time.time()) - self._translation_start_time

    def update_state(self, **values):
        with self._state_lock:
            self._state.update(values)
        self.state_updated.emit(self.get_state())

    def get_state(self):
        with self._state_lock:
            return dict(self._state, elapsed=self.get_elapsed_time())

    def _format_log(self, level: str, message: str) -> str:
        """格式化日志消息"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        return f"[{timestamp}] [{level}] {message}"

    def _add_log(self, level: str, message: str):
        """添加日志"""
        message = redact(message)
        formatted = self._format_log(level, message)
        self._logs.append(formatted)
        self.log_updated.emit(formatted)
        # Persistent diagnostics survive clear() and work in windowed Windows builds.
        import logging
        severity = {"DEBUG": logging.DEBUG, "WARN": logging.WARNING, "ERROR": logging.ERROR}.get(level, logging.INFO)
        get_logger("translation").log(severity, message)

    def debug(self, message: str):
        """调试日志"""
        self._add_log("DEBUG", message)

    def info(self, message: str):
        """信息日志"""
        self._add_log("INFO", message)

    def warning(self, message: str):
        """警告日志"""
        self._add_log("WARN", message)

    def error(self, message: str):
        """错误日志"""
        self._add_log("ERROR", message)

    def progress(self, percent: int, message: str = ""):
        """进度日志"""
        if message:
            self._add_log("PROGRESS", f"{percent}% - {message}")
        else:
            self._add_log("PROGRESS", f"{percent}%")

    def get_all_logs(self) -> list:
        """获取所有日志"""
        return list(self._logs)

    def get_logs_text(self) -> str:
        """获取所有日志的文本"""
        return "\n".join(self._logs)

    def clear(self):
        """清空日志"""
        self._logs.clear()
        self._current_stage = ""
        self._stage_start_time = 0


# 全局日志实例
_logger = None

def get_translation_logger() -> TranslationLogger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        _logger = TranslationLogger()
    return _logger

"""Supervise incremental translation without blocking or terminating Qt threads."""

import json
import multiprocessing
import os
from pathlib import Path
import queue
import sys
import tempfile
import time
import uuid

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from utils.config_path import get_config_file_path, application_data_dir
from utils.constants import DEFAULT_LANG_IN, DEFAULT_LANG_OUT, DEFAULT_SERVICE, DEFAULT_THREADS
from utils.resources import resource_path
from utils.translation_logger import get_translation_logger
from utils.incremental_translation import translation_process


class TranslationThread(QThread):
    translation_progress = pyqtSignal(str)
    translation_completed = pyqtSignal(str)
    translation_failed = pyqtSignal(str)
    translation_partial = pyqtSignal(dict)
    heartbeat_signal = pyqtSignal()

    def __init__(self, input_file, lang_in=DEFAULT_LANG_IN, lang_out=DEFAULT_LANG_OUT,
                 service=DEFAULT_SERVICE, threads=DEFAULT_THREADS, parent=None):
        super().__init__(parent)
        self.input_file = input_file
        self.logger = get_translation_logger()
        config = self._load_translation_config()
        self.lang_in = config.get('lang_in', lang_in)
        self.lang_out = config.get('lang_out', lang_out)
        self.service = config.get('service', service)
        self.envs = config.get('envs', {})
        self.pages = config.get('pages', '')
        self.save_dual_file = config.get('save_dual_file', False)
        self.threads = threads
        self._stop_requested = False
        self._process = None
        self._last_activity = time.monotonic()
        self._active_requests = 0
        self._partial = None
        self._stage = ''
        self.smoke_test = False
        self._job = None

    def _load_translation_config(self):
        try:
            settings = json.loads(Path(get_config_file_path()).read_text('utf-8'))
            config = dict(settings.get('translation', settings))
            for key in ('pages', 'save_dual_file'):
                if key in settings:
                    config[key] = settings[key]
            return config
        except (OSError, ValueError):
            return {}

    def _build_job(self):
        # Use the application's preloaded resource configuration when available.
        main_module = sys.modules.get('main')
        config = None
        if main_module and hasattr(main_module, 'get_pdf2zh_modules'):
            _, config = main_module.get_pdf2zh_modules()
        font_name = {'zh': 'SourceHanSerifCN-Regular.ttf', 'zh-cn': 'SourceHanSerifCN-Regular.ttf',
                     'zh-tw': 'SourceHanSerifTW-Regular.ttf', 'ja': 'SourceHanSerifJP-Regular.ttf',
                     'ko': 'SourceHanSerifKR-Regular.ttf'}.get(self.lang_out, 'GoNotoKurrent-Regular.ttf')
        font = config['fonts'].get(self.lang_out, config['fonts'].get('default')) if config else str(resource_path('fonts/' + font_name))
        model = config['models']['doclayout_path'] if config else str(resource_path('models/doclayout_yolo_docstructbench_imgsz1024.onnx'))
        preview_dir = application_data_dir() / 'translation-previews' / uuid.uuid4().hex
        job = dict(input_file=str(Path(self.input_file).resolve()), lang_in=self.lang_in,
                    lang_out=self.lang_out, service=self.service, threads=self.threads, envs=self.envs,
                    pages=self.pages, save_dual_file=self.save_dual_file, font=font,
                    model_path=model, preview_dir=str(preview_dir), smoke_test=self.smoke_test)
        if self.smoke_test:
            job.update(service="google", lang_in="en", lang_out="zh", pages="", save_dual_file=False, envs={})
        return job

    def stop(self):
        self._stop_requested = True

    def _handle_event(self, event):
        kind = event['type']
        self.heartbeat_signal.emit()
        if kind in ('stage', 'page_started', 'document', 'checkpoint', 'request_finished'):
            self._last_activity = time.monotonic()
        if kind == 'request_started':
            if self._active_requests == 0:
                self._last_activity = time.monotonic()
            self._active_requests = event['active']
            self._stage = '等待翻译服务返回段落'
        elif kind in ('request_finished', 'request_failed'):
            self._active_requests = event['active']
        if kind in ('stage', 'page_started'):
            self._stage = event['stage']
            self.logger.start_stage(self._stage)
            self.translation_progress.emit(self._stage + (f" · 第 {event['page']} 页" if 'page' in event else ''))
        self.logger.update_state(stage=self._stage, last_activity=self._last_activity,
                                 **{key: value for key, value in event.items() if key not in ('type', 'stage')})
        if kind == 'checkpoint':
            self._partial = event
            percent = int(event['completed'] * 100 / event['total'])
            self.logger.progress(percent, f"已保存 {event['completed']}/{event['total']} 页")
            self.translation_partial.emit(event)
            self.translation_progress.emit(f'PROGRESS:{percent}')
        elif kind == 'completed':
            self.logger.update_state(status='completed', stage='翻译完成', active=0)
            self.logger.end_translation(True)
            self.translation_completed.emit(event['path'])
            return True
        elif kind in ('failed', 'stopped'):
            self._fail(event.get('message', '翻译已停止'))
            return True
        return False

    def _fail(self, message):
        # A worker can be stopped between its atomic save and queue delivery.
        # Recover only this job's committed manifest, never a stale checkpoint.
        if self._job:
            from utils.incremental_translation import checkpoint_paths
            import shutil
            partial, manifest = checkpoint_paths(self.input_file)
            try:
                saved_manifest = json.loads(manifest.read_text('utf-8'))
                if saved_manifest.get('job_id') == Path(self._job['preview_dir']).name:
                    count = len(saved_manifest['completed_pages'])
                    if count > (self._partial['completed'] if self._partial else 0):
                        snapshot = Path(self._job['preview_dir']) / ('recovered-' + uuid.uuid4().hex + '.pdf')
                        shutil.copyfile(partial, snapshot)
                        self._handle_event(dict(type='checkpoint', path=str(partial), preview_path=str(snapshot),
                                                completed=count, total=saved_manifest['total'],
                                                completed_pages=saved_manifest['completed_pages'],
                                                document_pages=saved_manifest['document_pages']))
            except (OSError, ValueError, KeyError):
                pass
        saved = self._partial['completed'] if self._partial else 0
        if saved:
            message += f'；已保存 {saved} 页译文，其余页面保留原文。重新导入可继续翻译。'
        self.logger.update_state(status='partial' if saved else 'failed', stage='翻译已暂停',
                                 message=message, active=0)
        self.logger.end_translation(False, message)
        self.translation_failed.emit(message)

    def run(self):
        self.logger.start_translation(self.input_file)
        self.logger.update_state(status='running', service=self.service)
        events = cancellation = None
        terminal = False
        try:
            context = multiprocessing.get_context('spawn')
            events = context.Queue()
            cancellation = context.Event()
            self._last_activity = time.monotonic()
            self._job = self._build_job()
            self._process = context.Process(target=translation_process,
                                            args=(self._job, events, cancellation))
            self._process.start()
            while True:
                try:
                    event = events.get(timeout=0.2)
                    terminal = self._handle_event(event)
                    if terminal:
                        break
                except queue.Empty:
                    pass
                if self._stop_requested:
                    cancellation.set()
                    self._fail('翻译已停止')
                    terminal = True
                    break
                waiting = time.monotonic() - self._last_activity
                # Network wait is measured since actual service responses, not
                # tqdm percentages; large documents have no overall deadline.
                timeout = self.logger.get_api_timeout() if self._active_requests else 300
                if waiting > timeout:
                    self._fail(f'翻译服务 {int(timeout)} 秒未返回结果' if self._active_requests else f'当前步骤 {int(timeout)} 秒未完成')
                    terminal = True
                    break
                if not self._process.is_alive():
                    # Queue feeder messages may arrive just after process exit.
                    try:
                        while not terminal:
                            terminal = self._handle_event(events.get(timeout=0.5))
                    except queue.Empty:
                        if not terminal:
                            self._fail(f'翻译工作进程退出（代码 {self._process.exitcode}）')
                    break
        except Exception as error:
            self._fail(str(error))
        finally:
            if cancellation:
                cancellation.set()
            if self._process and self._process.pid:
                self._process.join(timeout=0.5)
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=1)
                if self._process.is_alive():
                    self._process.kill()
                    self._process.join(timeout=1)
                self._process.close()
            self._process = None
            if events:
                events.close()
                events.cancel_join_thread()


class TranslationManager(QObject):
    translation_timeout = pyqtSignal(str)  # Compatibility for earlier callers.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_thread = None
        self.translated_files = {}
        self.logger = get_translation_logger()

    def start_translation(self, input_file, progress_callback=None, completed_callback=None,
                          failed_callback=None, partial_callback=None, smoke_test=False):
        self.stop_current_translation()
        self.current_thread = TranslationThread(input_file, parent=self)
        self.current_thread.smoke_test = smoke_test
        for signal, callback in ((self.current_thread.translation_progress, progress_callback),
                                 (self.current_thread.translation_completed, completed_callback),
                                 (self.current_thread.translation_failed, failed_callback),
                                 (self.current_thread.translation_partial, partial_callback)):
            if callback:
                thread = self.current_thread
                signal.connect(lambda value, callback=callback, thread=thread: callback(value) if self.current_thread is thread else None)
        self.current_thread.start()

    def stop_current_translation(self):
        if self.current_thread:
            self.current_thread.stop()
            self.current_thread.wait(5000)
            # The supervising loop only performs bounded process waits.
            if self.current_thread.isRunning():
                raise RuntimeError('翻译工作进程尚未停止，请稍候')
            self.current_thread.deleteLater()
            self.current_thread = None

    def is_translating(self):
        return bool(self.current_thread and self.current_thread.isRunning())

    def get_translated_file(self, original_file):
        return self.translated_files.get(original_file)

    def set_translated_file(self, original_file, translated_file):
        self.translated_files[original_file] = translated_file

    def cleanup(self):
        self.stop_current_translation()
        self.translated_files.clear()

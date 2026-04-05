"""
日志服务 - 日志文件监控和读取
"""
import threading
import time
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime

from ..lib.log_utils import get_service_logger, get_cli_logger, get_ui_logger

logger = get_service_logger()
cli_logger = get_cli_logger()
ui_logger = get_ui_logger()


class LogService:
    """日志服务"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.ralph_dir = project_dir / ".ralph"
        self.logs_dir = self.ralph_dir / "logs"
        self._last_position: int = 0
        self._last_file: Optional[Path] = None
        self._stop_event = threading.Event()
        logger.debug(f"LogService initialized. project_dir={project_dir}, logs_dir={self.logs_dir}")

    def get_latest_log_file(self) -> Optional[Path]:
        """获取最新的日志文件"""
        if not self.logs_dir.exists():
            logger.debug(f"Logs directory does not exist: {self.logs_dir}")
            return None

        log_files = list(self.logs_dir.glob("*.log"))
        if not log_files:
            logger.debug("No log files found in logs directory")
            return None

        latest = max(log_files, key=lambda p: p.stat().st_mtime)
        logger.debug(f"Latest log file: {latest}")
        return latest

    def read_new_lines(self, callback: Callable[[str], None], poll_interval: float = 0.5) -> None:
        """
        持续读取新日志行

        这是一个阻塞方法，应该在后台线程中调用
        """
        logger.info(f"Starting log reader thread. poll_interval={poll_interval}")
        while not self._stop_event.is_set():
            log_file = self.get_latest_log_file()
            if log_file is None:
                logger.debug("No log file available, waiting...")
                time.sleep(poll_interval)
                continue

            # 如果是新的日志文件，重置位置
            if log_file != self._last_file:
                logger.info(f"New log file detected: {log_file}. Resetting position from {self._last_position}")
                self._last_file = log_file
                self._last_position = 0

            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    f.seek(self._last_position)
                    lines_read = 0
                    for line in f:
                        line = line.strip()
                        if line:
                            callback(line)
                            lines_read += 1
                    self._last_position = f.tell()
                    if lines_read > 0:
                        logger.debug(f"Read {lines_read} lines from {log_file}. New position: {self._last_position}")
            except IOError as e:
                logger.error(f"Error reading log file: {e}")
                pass

            time.sleep(poll_interval)
        logger.info("Log reader thread stopped")

    def stop(self):
        """停止日志读取线程"""
        logger.debug("Stopping log reader...")
        self._stop_event.set()

    def read_recent_logs(self, lines: int = 100) -> List[str]:
        """读取最近的日志行"""
        log_file = self.get_latest_log_file()
        if log_file is None:
            logger.debug("No log file available for reading recent logs")
            return []

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                result = [line.strip() for line in recent if line.strip()]
                logger.debug(f"Read {len(result)} recent lines from {log_file}")
                return result
        except IOError as e:
            logger.error(f"Error reading recent logs: {e}")
            return []

    def get_log_content(self, log_file: Optional[Path] = None, max_chars: int = 10000) -> str:
        """获取日志文件内容"""
        if log_file is None:
            log_file = self.get_latest_log_file()
        if log_file is None:
            logger.debug("No log file specified and none available")
            return ""

        logger.debug(f"Reading log content from {log_file}, max_chars={max_chars}")
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) > max_chars:
                    content = content[-max_chars:]
                    logger.debug(f"Log content truncated from {len(content)} to {max_chars} chars")
                return content
        except IOError as e:
            logger.error(f"Error reading log content: {e}")
            return ""

    def format_log_line(self, line: str) -> str:
        """格式化日志行"""
        # 尝试解析时间戳
        # 格式: [2026-04-03 12:34:56] [INFO] message
        import re
        match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(\w+)\] (.+)', line)
        if match:
            timestamp, level, message = match.groups()
            return f"[{timestamp}] [{level}] {message}"
        return line

    def tail(self, lines: int = 50) -> List[str]:
        """返回日志文件最后n行"""
        return self.read_recent_logs(lines)

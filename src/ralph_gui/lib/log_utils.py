"""
log_utils.py - Log management utilities for Ralph
rotate_logs - Rotate ralph.log when it exceeds 10MB

Keeps 4 archived files: ralph.log.1 through ralph.log.4
(ralph.log.4 is deleted to make room)
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB in bytes


class RalphLogger:
    """Ralph统一日志管理器"""

    _instance: Optional['RalphLogger'] = None
    _loggers: Dict[str, logging.Logger] = {}

    # 日志级别配置
    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    def __init__(self):
        self._root_logger: Optional[logging.Logger] = None
        self._log_dir: Optional[Path] = None
        self._app_logger: Optional[logging.Logger] = None
        self._cli_logger: Optional[logging.Logger] = None
        self._ui_logger: Optional[logging.Logger] = None
        self._service_logger: Optional[logging.Logger] = None

    @classmethod
    def get_instance(cls) -> 'RalphLogger':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = RalphLogger()
        return cls._instance

    def initialize(self, log_dir: Path, level: str = "INFO") -> None:
        """
        初始化日志系统

        Args:
            log_dir: 日志文件目录
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self._log_dir = log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        # 配置根日志器
        self._root_logger = logging.getLogger("ralph")
        self._root_logger.setLevel(self.LOG_LEVELS.get(level, logging.INFO))

        # 避免重复添加handler
        if self._root_logger.handlers:
            self._root_logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)

        # 文件处理器 - 分类日志
        log_file = log_dir / "ralph.log"

        # 使用RotatingFileHandler实现自动轮转
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=4,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        self._root_logger.addHandler(console_handler)
        self._root_logger.addHandler(file_handler)

        # 创建分类日志器
        self._app_logger = self.get_logger("ralph.app")
        self._cli_logger = self.get_logger("ralph.cli")
        self._ui_logger = self.get_logger("ralph.ui")
        self._service_logger = self.get_logger("ralph.service")

        self._root_logger.info(f"RalphLogger initialized. Log dir: {log_dir}")

    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定名称的日志器

        Args:
            name: 日志器名称，如 "ralph.app", "ralph.cli.startup"

        Returns:
            日志器实例
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            if self._root_logger and not logger.handlers:
                logger.setLevel(logging.DEBUG)
            self._loggers[name] = logger
        return self._loggers[name]

    @property
    def app(self) -> logging.Logger:
        """应用主日志器"""
        return self._app_logger or logging.getLogger("ralph.app")

    @property
    def cli(self) -> logging.Logger:
        """CLI日志器"""
        return self._cli_logger or logging.getLogger("ralph.cli")

    @property
    def ui(self) -> logging.Logger:
        """UI日志器"""
        return self._ui_logger or logging.getLogger("ralph.ui")

    @property
    def service(self) -> logging.Logger:
        """服务日志器"""
        return self._service_logger or logging.getLogger("ralph.service")

    def set_level(self, level: str) -> None:
        """设置日志级别"""
        if self._root_logger:
            self._root_logger.setLevel(self.LOG_LEVELS.get(level, logging.INFO))
            for handler in self._root_logger.handlers:
                handler.setLevel(self.LOG_LEVELS.get(level, logging.INFO))


# 便捷函数
def get_logger(name: str = "ralph") -> logging.Logger:
    """获取日志器"""
    return RalphLogger.get_instance().get_logger(name)


def get_app_logger() -> logging.Logger:
    """获取应用日志器"""
    return RalphLogger.get_instance().app


def get_cli_logger() -> logging.Logger:
    """获取CLI日志器"""
    return RalphLogger.get_instance().cli


def get_ui_logger() -> logging.Logger:
    """获取UI日志器"""
    return RalphLogger.get_instance().ui


def get_service_logger() -> logging.Logger:
    """获取服务日志器"""
    return RalphLogger.get_instance().service


def init_logger(log_dir: Path, level: str = "INFO") -> None:
    """初始化日志系统"""
    RalphLogger.get_instance().initialize(log_dir, level)


def rotate_logs(log_dir: Path, log_file: str = "ralph.log") -> bool:
    """Rotate logs when file exceeds 10MB.

    Args:
        log_dir: Directory containing the log file
        log_file: Name of the log file (default: ralph.log)

    Returns:
        True if rotation occurred, False otherwise
    """
    log_path = log_dir / log_file

    if not log_path.exists():
        return False

    file_size = log_path.stat().st_size

    if file_size < MAX_LOG_SIZE:
        return False

    # Rotate: delete oldest, shift others up
    # ralph.log.4 -> delete
    # ralph.log.3 -> ralph.log.4
    # ralph.log.2 -> ralph.log.3
    # ralph.log.1 -> ralph.log.2
    # ralph.log -> ralph.log.1

    log_path_4 = log_dir / f"{log_file}.4"
    log_path_3 = log_dir / f"{log_file}.3"
    log_path_2 = log_dir / f"{log_file}.2"
    log_path_1 = log_dir / f"{log_file}.1"

    if log_path_4.exists():
        log_path_4.unlink()
    if log_path_3.exists():
        log_path_3.rename(log_path_4)
    if log_path_2.exists():
        log_path_2.rename(log_path_3)
    if log_path_1.exists():
        log_path_1.rename(log_path_2)

    log_path.rename(log_path_1)

    return True

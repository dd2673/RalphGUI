"""
配置服务 - .ralphrc解析和管理
"""
from pathlib import Path
from typing import Dict, Any, Optional
import re
import logging

# 获取日志器
logger = logging.getLogger("ralph.service")


class ConfigService:
    """配置服务"""

    # 默认配置
    DEFAULTS: Dict[str, Any] = {
        "PROJECT_NAME": "",
        "PROJECT_TYPE": "",
        "MAX_CALLS_PER_HOUR": 100,
        "MAX_TOKENS_PER_HOUR": 0,
        "CLAUDE_TIMEOUT_MINUTES": 15,
        "CLAUDE_OUTPUT_FORMAT": "json",
        "ALLOWED_TOOLS": "",
        "SESSION_CONTINUITY": "true",
        "SESSION_EXPIRY_HOURS": 24,
        "CB_NO_PROGRESS_THRESHOLD": 3,
        "CB_SAME_ERROR_THRESHOLD": 5,
        "CB_OUTPUT_DECLINE_THRESHOLD": 70,
        "CB_PERMISSION_DENIAL_THRESHOLD": 2,
        "CB_COOLDOWN_MINUTES": 30,
        "CB_AUTO_RESET": "false",
        "DANGEROUSLY_SKIP_PERMISSIONS": "true",
        "LOOP_DELAY_SECONDS": 5,
        "RALPH_VERBOSE": "false",
        "CLAUDE_CODE_CMD": "claude",
        "CLAUDE_AUTO_UPDATE": "true",
        "RALPH_SHELL_INIT_FILE": "",
        "CLAUDE_MODEL": "",
        "CLAUDE_EFFORT": "",
    }

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file
        self._config: Dict[str, str] = {}

    def load(self) -> Dict[str, str]:
        """加载配置文件"""
        self._config = self.DEFAULTS.copy()

        logger.debug(f"Loading config from: {self.config_file}")

        if self.config_file and self.config_file.exists():
            try:
                line_count = 0
                config_count = 0
                custom_configs = []  # 收集自定义配置，稍后统一记录
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line_count += 1
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            key, _, value = line.partition('=')
                            key = key.strip()
                            value = value.strip()
                            # 移除引号
                            if (value.startswith('"') and value.endswith('"')) or \
                               (value.startswith("'") and value.endswith("'")):
                                value = value[1:-1]
                            self._config[key] = value
                            config_count += 1
                            # 记录非默认配置
                            if key in self.DEFAULTS and self.DEFAULTS[key] != value:
                                custom_configs.append(f"{key}={value}")

                # 合并为少量日志
                if custom_configs:
                    logger.debug(f"Custom configs: {custom_configs}")
                logger.info(f"Config loaded: {config_count} items from {line_count} lines")
            except IOError as e:
                logger.error(f"Failed to read config file: {e}")
        else:
            if self.config_file:
                logger.debug(f"Config file not found: {self.config_file}")
            logger.debug(f"Using {len(self.DEFAULTS)} default config items")

        return self._config

    def save(self, config: Dict[str, str]) -> bool:
        """保存配置文件"""
        if not self.config_file:
            logger.error(f"Cannot save config: config_file is None")
            return False

        logger.info(f"Saving config to {self.config_file}")
        logger.debug(f"Config content: {config}")

        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                for key, value in config.items():
                    # 布尔值配置始终写入，不被默认值逻辑跳过
                    bool_keys = ("SESSION_CONTINUITY", "CB_AUTO_RESET", "RALPH_VERBOSE",
                                 "CLAUDE_AUTO_UPDATE", "DANGEROUSLY_SKIP_PERMISSIONS")
                    if key in bool_keys:
                        f.write(f"{key}={value}\n")
                    # 跳过默认值
                    elif key in self.DEFAULTS and self.DEFAULTS[key] == value:
                        continue
                    else:
                        # 值中包含空格或特殊字符时加引号
                        if isinstance(value, str) and (' ' in value or '#' in value):
                            value = f'"{value}"'
                        f.write(f"{key}={value}\n")
            self._config = config
            logger.info(f"Config saved to {self.config_file}")
            return True
        except IOError as e:
            logger.error(f"Failed to save config to {self.config_file}: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        if not self._config:
            self.load()

        value = self._config.get(key)
        if value is None:
            return default

        # 类型转换
        if key in ("MAX_CALLS_PER_HOUR", "MAX_TOKENS_PER_HOUR", "CLAUDE_TIMEOUT_MINUTES",
                   "SESSION_EXPIRY_HOURS", "CB_NO_PROGRESS_THRESHOLD", "CB_SAME_ERROR_THRESHOLD",
                   "CB_OUTPUT_DECLINE_THRESHOLD", "CB_PERMISSION_DENIAL_THRESHOLD", "CB_COOLDOWN_MINUTES"):
            try:
                return int(value)
            except ValueError:
                return default
        elif key in ("SESSION_CONTINUITY", "CB_AUTO_RESET", "RALPH_VERBOSE",
                     "CLAUDE_AUTO_UPDATE", "DANGEROUSLY_SKIP_PERMISSIONS",
                     "APPEND_PREVIOUS_SUMMARY"):
            return value.lower() in ("true", "1", "yes")
        else:
            return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        if not self._config:
            self.load()
        self._config[key] = str(value)

    def as_dict(self) -> Dict[str, Any]:
        """返回完整配置字典"""
        if not self._config:
            self.load()
        return self._config.copy()

    @staticmethod
    def diagnose_project(project_dir: Path) -> Dict[str, Any]:
        """诊断项目目录结构和配置状态

        返回诊断结果字典，包含项目目录的各项检查状态。
        """
        result = {
            "project_dir": str(project_dir),
            "checks": {},
            "ralph_dir": {},
            "config": {},
            "recommendations": []
        }

        # 1. 检查项目目录
        if project_dir.exists():
            result["checks"]["project_dir_exists"] = True

            # 检查读写权限
            try:
                test_file = project_dir / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
                result["checks"]["project_dir_writable"] = True
            except Exception as e:
                result["checks"]["project_dir_writable"] = False
                result["recommendations"].append("检查项目目录权限")
        else:
            result["checks"]["project_dir_exists"] = False
            result["recommendations"].append("选择有效的项目目录")
            return result  # 提前返回，避免后续检查

        # 2. 检查 .ralph 目录
        ralph_dir = project_dir / ".ralph"
        if ralph_dir.exists():
            result["checks"]["ralph_dir_exists"] = True

            # 列出目录内容
            try:
                files = list(ralph_dir.iterdir())
                result["ralph_dir"]["file_count"] = len(files)
            except Exception as e:
                logger.warning(f"Cannot list .ralph directory: {e}")
        else:
            result["checks"]["ralph_dir_exists"] = False
            result["recommendations"].append("运行启用向导初始化项目")

        # 3. 检查关键文件
        key_files = {
            "PROMPT.md": "主提示文件",
            "AGENT.md": "代理指令文件",
            "fix_plan.md": "任务计划文件",
            "status.json": "状态文件"
        }

        for filename, description in key_files.items():
            file_path = ralph_dir / filename
            if file_path.exists():
                try:
                    size = file_path.stat().st_size
                    result["ralph_dir"][filename] = {"exists": True, "size": size}
                except Exception as e:
                    result["ralph_dir"][filename] = {"exists": True, "error": str(e)}
            else:
                result["ralph_dir"][filename] = {"exists": False}
                if filename in ["PROMPT.md", "AGENT.md"]:
                    result["recommendations"].append(f"创建 {filename}")

        # 4. 检查 .ralphrc 配置
        config_file = project_dir / ".ralphrc"
        if config_file.exists():
            result["checks"]["config_file_exists"] = True
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                result["config"]["file_size"] = len(content)
            except Exception as e:
                logger.warning(f"Cannot read .ralphrc: {e}")
        else:
            result["checks"]["config_file_exists"] = False

        # 5. 检查日志目录
        logs_dir = ralph_dir / "logs"
        if logs_dir.exists():
            result["checks"]["logs_dir_exists"] = True
        else:
            result["checks"]["logs_dir_exists"] = False

        # 记录诊断结果
        passed = sum(1 for v in result["checks"].values() if v)
        total = len(result["checks"])
        logger.info(f"Project diagnostic: {passed}/{total} checks passed for {project_dir.name}")

        return result

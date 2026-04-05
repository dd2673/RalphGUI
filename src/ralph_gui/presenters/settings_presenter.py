"""
设置Presenter
"""
from pathlib import Path
from typing import Dict, Any, Optional
from ..services import ConfigService, StateService


class SettingsPresenter:
    """设置Presenter"""

    def __init__(
        self,
        config_service: ConfigService,
        state_service: StateService
    ):
        self.config_service = config_service
        self.state_service = state_service

    def load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        return self.config_service.as_dict()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取单个设置"""
        return self.config_service.get(key, default)

    def update_setting(self, key: str, value: Any) -> bool:
        """更新单个设置"""
        self.config_service.set(key, value)
        return True

    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """保存设置"""
        # 保存到 ConfigService (.ralphrc)
        config_saved = self.config_service.save(settings)

        # 同步更新 LoopStateModel 中的配置值
        loop_state = self.state_service.load_loop_state()
        if "MAX_CALLS_PER_HOUR" in settings:
            loop_state.max_calls_per_hour = int(settings["MAX_CALLS_PER_HOUR"])
        if "MAX_TOKENS_PER_HOUR" in settings:
            loop_state.max_tokens_per_hour = int(settings["MAX_TOKENS_PER_HOUR"])
        self.state_service.save_loop_state(loop_state)

        return config_saved

    def reset_to_defaults(self) -> bool:
        """重置为默认设置"""
        return self.config_service.save(self.config_service.DEFAULTS)

    def get_editable_settings(self) -> list:
        """获取可编辑设置列表"""
        return [
            {
                "key": "MAX_CALLS_PER_HOUR",
                "label": "每小时最大调用次数",
                "type": "int",
                "default": 100,
                "min": 1,
                "max": 1000,
            },
            {
                "key": "MAX_TOKENS_PER_HOUR",
                "label": "每小时最大令牌数 (0=无限制)",
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 1000000,
            },
            {
                "key": "CLAUDE_TIMEOUT_MINUTES",
                "label": "超时时间（分钟）",
                "type": "int",
                "default": 15,
                "min": 1,
                "max": 120,
            },
            {
                "key": "SESSION_CONTINUITY",
                "label": "启用会话连续性",
                "type": "bool",
                "default": True,
            },
            {
                "key": "SESSION_EXPIRY_HOURS",
                "label": "会话过期时间（小时）",
                "type": "int",
                "default": 24,
                "min": 1,
                "max": 168,
            },
            {
                "key": "CB_NO_PROGRESS_THRESHOLD",
                "label": "无进度阈值",
                "type": "int",
                "default": 3,
                "min": 1,
                "max": 10,
            },
            {
                "key": "MAX_ITERATIONS_WITHOUT_PROGRESS",
                "label": "最大无进度迭代次数 (0=无限制)",
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 10000,
            },
            {
                "key": "CB_SAME_ERROR_THRESHOLD",
                "label": "相同错误阈值",
                "type": "int",
                "default": 5,
                "min": 1,
                "max": 20,
            },
            {
                "key": "CB_AUTO_RESET",
                "label": "自动重置回路",
                "type": "bool",
                "default": False,
            },
            {
                "key": "DANGEROUSLY_SKIP_PERMISSIONS",
                "label": "跳过权限检查（危险）",
                "type": "bool",
                "default": False,
            },
        ]

    def validate_setting(self, key: str, value: Any) -> tuple[bool, str]:
        """
        验证设置值

        Returns:
            (is_valid, error_message)
        """
        int_keys = {
            "MAX_CALLS_PER_HOUR": (1, 1000),
            "MAX_TOKENS_PER_HOUR": (0, 1000000),
            "CLAUDE_TIMEOUT_MINUTES": (1, 120),
            "SESSION_EXPIRY_HOURS": (1, 168),
            "CB_NO_PROGRESS_THRESHOLD": (1, 10),
            "MAX_ITERATIONS_WITHOUT_PROGRESS": (0, 10000),
            "CB_SAME_ERROR_THRESHOLD": (1, 20),
            "CB_COOLDOWN_MINUTES": (1, 60),
            "LOOP_DELAY_SECONDS": (1, 60),
        }

        if key in int_keys:
            try:
                val = int(value)
                min_val, max_val = int_keys[key]
                if val < min_val or val > max_val:
                    return False, f"值必须在 {min_val} 到 {max_val} 之间"
            except ValueError:
                return False, "必须是整数"

        return True, ""

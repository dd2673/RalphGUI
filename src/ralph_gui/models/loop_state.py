"""
循环状态模型
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .circuit_breaker import CircuitBreakerModel, CircuitBreakerState

logger = logging.getLogger(__name__)


@dataclass
class LoopStateModel:
    """循环状态模型"""
    status: str = "stopped"  # stopped, running, paused, waiting
    loop_count: int = 0
    calls_made_this_hour: int = 0
    max_calls_per_hour: int = 100
    tokens_used_this_hour: int = 0
    max_tokens_per_hour: int = 0  # 0 = disabled
    last_action: str = ""
    exit_reason: Optional[str] = None
    last_reset: str = ""  # YYYYMMDDHH format
    next_reset: str = ""
    last_loop_time: Optional[datetime] = None

    STATUS_FILE: str = ".ralph/status.json"

    @classmethod
    def from_project(cls, project_dir: Path) -> "LoopStateModel":
        """从项目目录加载模型"""
        model = cls()
        model.load(project_dir)
        return model

    def load(self, project_dir: Path) -> None:
        """从JSON文件加载状态"""
        status_file = project_dir / self.STATUS_FILE
        if status_file.exists():
            try:
                import json
                with open(status_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.status = data.get("status", "stopped")
                self.loop_count = data.get("loop_count", 0)
                self.calls_made_this_hour = data.get("calls_made_this_hour", 0)
                self.max_calls_per_hour = data.get("max_calls_per_hour", 100)
                self.tokens_used_this_hour = data.get("tokens_used_this_hour", 0)
                self.max_tokens_per_hour = data.get("max_tokens_per_hour", 0)
                self.last_action = data.get("last_action", "")
                self.exit_reason = data.get("exit_reason")
                self.last_reset = data.get("last_reset", "")
                self.next_reset = data.get("next_reset", "")
                logger.debug(f"Loop state loaded: status={self.status}, loop_count={self.loop_count}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load loop state from {status_file}: {e}")

    def save(self, project_dir: Path) -> bool:
        """保存状态到JSON文件"""
        import json
        data = {
            "timestamp": datetime.now().isoformat(),
            "status": self.status,
            "loop_count": self.loop_count,
            "calls_made_this_hour": self.calls_made_this_hour,
            "max_calls_per_hour": self.max_calls_per_hour,
            "tokens_used_this_hour": self.tokens_used_this_hour,
            "max_tokens_per_hour": self.max_tokens_per_hour,
            "last_action": self.last_action,
            "exit_reason": self.exit_reason,
            "last_reset": self.last_reset,
            "next_reset": self.next_reset,
        }
        try:
            project_dir.joinpath(self.STATUS_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(project_dir / self.STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Loop state saved: status={self.status}, loop_count={self.loop_count}")
            return True
        except IOError as e:
            logger.error(f"Failed to save loop state: {e}")
            return False

    def increment_loop(self) -> None:
        """增加循环计数"""
        self.loop_count += 1
        self.last_loop_time = datetime.now()

    def increment_calls(self, tokens: int = 0) -> None:
        """增加API调用计数"""
        self.calls_made_this_hour += 1
        self.tokens_used_this_hour += tokens

    def can_make_call(self) -> bool:
        """检查是否可以发起调用"""
        if self.max_calls_per_hour > 0:
            if self.calls_made_this_hour >= self.max_calls_per_hour:
                return False
        if self.max_tokens_per_hour > 0:
            if self.tokens_used_this_hour >= self.max_tokens_per_hour:
                return False
        return True

    def check_rate_limit_reset(self) -> bool:
        """检查速率限制是否需要重置"""
        from datetime import datetime
        current = datetime.now().strftime("%Y%m%d%H")
        if self.last_reset != current:
            self.calls_made_this_hour = 0
            self.tokens_used_this_hour = 0
            self.last_reset = current
            return True
        return False

    @property
    def calls_remaining(self) -> int:
        """剩余调用次数"""
        if self.max_calls_per_hour <= 0:
            return -1  # 无限制
        return max(0, self.max_calls_per_hour - self.calls_made_this_hour)

    @property
    def tokens_remaining(self) -> int:
        """剩余令牌数"""
        if self.max_tokens_per_hour <= 0:
            return -1  # 无限制
        return max(0, self.max_tokens_per_hour - self.tokens_used_this_hour)

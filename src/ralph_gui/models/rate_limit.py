"""
速率限制模型
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from ..utils import read_json, write_json


@dataclass
class RateLimitModel:
    """速率限制模型"""
    calls_made: int = 0
    tokens_used: int = 0
    last_reset: Optional[datetime] = None
    max_calls_per_hour: int = 100
    max_tokens_per_hour: int = 0  # 0 = disabled

    COUNTER_FILE: str = ".ralph/.call_count"
    TOKEN_FILE: str = ".ralph/.token_count"
    RESET_FILE: str = ".ralph/.last_reset"

    def __post_init__(self):
        if self.last_reset is None:
            self.last_reset = datetime.now()

    @classmethod
    def from_project(cls, project_dir: Path, max_calls: int = 100, max_tokens: int = 0) -> "RateLimitModel":
        """从项目目录加载模型"""
        model = cls(max_calls_per_hour=max_calls, max_tokens_per_hour=max_tokens)
        model.load(project_dir)
        return model

    def load(self, project_dir: Path) -> None:
        """从文件加载状态"""
        # 读取调用计数
        call_file = project_dir / self.COUNTER_FILE
        if call_file.exists():
            try:
                with open(call_file, 'r') as f:
                    self.calls_made = int(f.read().strip())
            except (ValueError, IOError):
                pass

        # 读取令牌计数
        token_file = project_dir / self.TOKEN_FILE
        if token_file.exists():
            try:
                with open(token_file, 'r') as f:
                    self.tokens_used = int(f.read().strip())
            except (ValueError, IOError):
                pass

        # 读取上次重置时间
        reset_file = project_dir / self.RESET_FILE
        if reset_file.exists():
            try:
                with open(reset_file, 'r') as f:
                    reset_str = f.read().strip()
                    self.last_reset = datetime.fromisoformat(reset_str)
            except (ValueError, IOError):
                pass

    def save(self, project_dir: Path) -> bool:
        """保存状态到文件"""
        try:
            # 保存调用计数
            call_file = project_dir / self.COUNTER_FILE
            call_file.parent.mkdir(parents=True, exist_ok=True)
            with open(call_file, 'w') as f:
                f.write(str(self.calls_made))

            # 保存令牌计数
            token_file = project_dir / self.TOKEN_FILE
            with open(token_file, 'w') as f:
                f.write(str(self.tokens_used))

            # 保存重置时间
            reset_file = project_dir / self.RESET_FILE
            with open(reset_file, 'w') as f:
                f.write(self.last_reset.isoformat())

            return True
        except IOError:
            return False

    def check_and_reset_if_needed(self) -> bool:
        """检查是否需要重置"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        if self.last_reset is None or self.last_reset < current_hour:
            self.calls_made = 0
            self.tokens_used = 0
            self.last_reset = current_hour
            return True
        return False

    def increment(self, tokens: int = 0) -> None:
        """增加计数"""
        self.calls_made += 1
        self.tokens_used += tokens

    def can_make_call(self) -> bool:
        """检查是否可以发起调用"""
        if self.max_calls_per_hour > 0:
            if self.calls_made >= self.max_calls_per_hour:
                return False
        if self.max_tokens_per_hour > 0:
            if self.tokens_used >= self.max_tokens_per_hour:
                return False
        return True

    def time_until_reset(self) -> timedelta:
        """距离重置的时间"""
        if self.last_reset is None:
            return timedelta(hours=1)
        next_reset = self.last_reset + timedelta(hours=1)
        return max(timedelta(0), next_reset - datetime.now())

    @property
    def calls_remaining(self) -> int:
        """剩余调用次数"""
        if self.max_calls_per_hour <= 0:
            return -1  # 无限制
        return max(0, self.max_calls_per_hour - self.calls_made)

    @property
    def tokens_remaining(self) -> int:
        """剩余令牌数"""
        if self.max_tokens_per_hour <= 0:
            return -1  # 无限制
        return max(0, self.max_tokens_per_hour - self.tokens_used)

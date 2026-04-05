"""
回路断路器状态模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..utils import read_json, write_json
from ..lib.circuit_breaker import CircuitBreakerState


@dataclass
class CircuitBreakerModel:
    """回路断路器模型"""
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    last_change: datetime = field(default_factory=datetime.now)
    opened_at: Optional[datetime] = None
    consecutive_no_progress: int = 0
    consecutive_same_error: int = 0
    consecutive_permission_denials: int = 0
    consecutive_same_output: int = 0
    last_progress_loop: int = 0
    last_output_hash: str = ""
    total_opens: int = 0
    reason: str = ""
    current_loop: int = 0
    # 持有 project_dir 引用以便立即持久化
    _project_dir: Optional[Path] = field(default=None, repr=False)

    # 配置阈值
    NO_PROGRESS_THRESHOLD: int = 3
    SAME_ERROR_THRESHOLD: int = 5
    SAME_OUTPUT_THRESHOLD: int = 3
    PERMISSION_DENIAL_THRESHOLD: int = 2
    OUTPUT_DECLINE_THRESHOLD: int = 70
    COOLDOWN_MINUTES: int = 30

    STATE_FILE: str = ".ralph/.circuit_breaker_state"

    @classmethod
    def from_project(cls, project_dir: Path) -> "CircuitBreakerModel":
        """从项目目录加载模型"""
        model = cls()
        model._project_dir = project_dir
        model.load(project_dir)
        return model

    def set_project_dir(self, project_dir: Path) -> None:
        """设置项目目录（用于立即持久化）"""
        self._project_dir = project_dir

    def load(self, project_dir: Path) -> None:
        """从JSON文件加载状态"""
        state_file = project_dir / self.STATE_FILE
        data = read_json(state_file)
        if data:
            self.state = CircuitBreakerState(data.get("state", "CLOSED"))
            self.consecutive_no_progress = data.get("consecutive_no_progress", 0)
            self.consecutive_same_error = data.get("consecutive_same_error", 0)
            self.consecutive_permission_denials = data.get("consecutive_permission_denials", 0)
            self.consecutive_same_output = data.get("consecutive_same_output", 0)
            self.last_progress_loop = data.get("last_progress_loop", 0)
            self.last_output_hash = data.get("last_output_hash", "")
            self.total_opens = data.get("total_opens", 0)
            self.reason = data.get("reason", "")
            self.current_loop = data.get("current_loop", 0)

            # 解析时间字段
            if "last_change" in data:
                self.last_change = datetime.fromisoformat(data["last_change"])
            if "opened_at" in data and data["opened_at"]:
                self.opened_at = datetime.fromisoformat(data["opened_at"])

    def save(self, project_dir: Path) -> bool:
        """保存状态到JSON文件"""
        data = {
            "state": self.state.value,
            "last_change": self.last_change.isoformat(),
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "consecutive_no_progress": self.consecutive_no_progress,
            "consecutive_same_error": self.consecutive_same_error,
            "consecutive_permission_denials": self.consecutive_permission_denials,
            "consecutive_same_output": self.consecutive_same_output,
            "last_progress_loop": self.last_progress_loop,
            "last_output_hash": self.last_output_hash,
            "total_opens": self.total_opens,
            "reason": self.reason,
            "current_loop": self.current_loop,
        }
        return write_json(project_dir / self.STATE_FILE, data)

    def _save_if_possible(self) -> None:
        """如果项目目录已设置，立即保存"""
        if self._project_dir:
            self.save(self._project_dir)

    def record_progress(self, loop_number: int, project_dir: Path = None) -> None:
        """记录有进度的循环"""
        self.consecutive_no_progress = 0
        self.consecutive_same_error = 0
        self.last_progress_loop = loop_number
        if self.state == CircuitBreakerState.HALF_OPEN:
            self._transition_to(CircuitBreakerState.CLOSED, "Progress detected, circuit recovered", project_dir)

    def record_no_progress(self, loop_number: int, project_dir: Path = None) -> None:
        """记录无进度的循环"""
        self.consecutive_no_progress += 1
        if self.consecutive_no_progress >= self.NO_PROGRESS_THRESHOLD:
            self._transition_to(
                CircuitBreakerState.OPEN,
                f"No progress detected in {self.consecutive_no_progress} consecutive loops",
                project_dir
            )

    def record_error(self, error: str, project_dir: Path = None) -> None:
        """记录错误"""
        self.consecutive_same_error += 1
        if self.consecutive_same_error >= self.SAME_ERROR_THRESHOLD:
            self._transition_to(
                CircuitBreakerState.OPEN,
                f"Same error repeated {self.consecutive_same_error} times: {error[:50]}",
                project_dir
            )

    def record_permission_denial(self, command: str, project_dir: Path = None) -> None:
        """记录权限拒绝"""
        self.consecutive_permission_denials += 1
        if self.consecutive_permission_denials >= self.PERMISSION_DENIAL_THRESHOLD:
            self._transition_to(
                CircuitBreakerState.OPEN,
                f"Permission denied for command: {command}",
                project_dir
            )

    def record_same_output(self, output: str, project_dir: Path = None) -> None:
        """
        记录连续相同输出的检测

        Args:
            output: 当前循环的输出内容
            project_dir: 项目目录（用于立即持久化）
        """
        import hashlib

        # 计算输出的哈希值
        output_hash = hashlib.md5(output.encode('utf-8')).hexdigest() if output else ""

        # 检查是否与上次输出相同
        if output_hash and output_hash == self.last_output_hash:
            # 输出相同，增加计数
            self.consecutive_same_output += 1
            if self.consecutive_same_output >= self.SAME_OUTPUT_THRESHOLD:
                self._transition_to(
                    CircuitBreakerState.OPEN,
                    f"Same output repeated {self.consecutive_same_output} times",
                    project_dir
                )
        else:
            # 输出不同，重置计数
            self.consecutive_same_output = 0
            self.last_output_hash = output_hash

    def check_cooldown(self) -> bool:
        """检查冷却时间是否已过"""
        if self.state != CircuitBreakerState.OPEN:
            return False
        if not self.opened_at:
            return True
        elapsed = datetime.now() - self.opened_at
        return elapsed.total_seconds() >= (self.COOLDOWN_MINUTES * 60)

    def attempt_recovery(self, project_dir: Path = None) -> None:
        """尝试恢复"""
        if self.state == CircuitBreakerState.OPEN and self.check_cooldown():
            self._transition_to(CircuitBreakerState.HALF_OPEN, "Cooldown complete, attempting recovery", project_dir)

    def _transition_to(self, new_state: CircuitBreakerState, reason: str, project_dir: Path = None) -> None:
        """状态转换（立即持久化）"""
        if self.state == new_state:
            return
        old_state = self.state
        self.state = new_state
        self.last_change = datetime.now()
        self.reason = reason
        if new_state == CircuitBreakerState.OPEN:
            self.opened_at = datetime.now()
            self.total_opens += 1
        elif new_state == CircuitBreakerState.CLOSED:
            self.opened_at = None
            self.consecutive_no_progress = 0
            self.consecutive_same_error = 0
            self.consecutive_same_output = 0

        # 立即持久化状态变更
        target_dir = project_dir or self._project_dir
        if target_dir:
            self.save(target_dir)

    def reset(self, project_dir: Path = None) -> None:
        """重置断路器"""
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_no_progress = 0
        self.consecutive_same_error = 0
        self.consecutive_permission_denials = 0
        self.consecutive_same_output = 0
        self.last_output_hash = ""
        self.last_change = datetime.now()
        self.opened_at = None
        self.reason = "Manual reset"

        # 立即持久化
        target_dir = project_dir or self._project_dir
        if target_dir:
            self.save(target_dir)

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitBreakerState.CLOSED

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitBreakerState.HALF_OPEN

    @property
    def is_open(self) -> bool:
        return self.state == CircuitBreakerState.OPEN

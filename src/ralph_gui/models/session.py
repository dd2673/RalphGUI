"""
会话模型
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from ..utils import read_json, write_json


@dataclass
class SessionModel:
    """会话模型"""
    session_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    reset_at: Optional[datetime] = None
    reset_reason: str = ""

    SESSION_FILE: str = ".ralph/.ralph_session"
    SESSION_ID_FILE: str = ".ralph/.claude_session_id"
    EXPIRY_HOURS: int = 24

    @classmethod
    def from_project(cls, project_dir: Path) -> "SessionModel":
        """从项目目录加载模型"""
        model = cls()
        model.load(project_dir)
        return model

    def load(self, project_dir: Path) -> None:
        """从JSON文件加载状态"""
        # 尝试加载主会话文件
        session_file = project_dir / self.SESSION_FILE
        data = read_json(session_file)
        if data:
            self.session_id = data.get("session_id", "")
            if "created_at" in data:
                self.created_at = datetime.fromisoformat(data["created_at"])
            if "last_used" in data:
                self.last_used = datetime.fromisoformat(data["last_used"])
            if "reset_at" in data and data["reset_at"]:
                self.reset_at = datetime.fromisoformat(data["reset_at"])
            self.reset_reason = data.get("reset_reason", "")

        # 尝试加载 Claude session ID
        session_id_file = project_dir / self.SESSION_ID_FILE
        id_data = read_json(session_id_file)
        if id_data and not self.session_id:
            self.session_id = id_data.get("session_id", "")

    def save(self, project_dir: Path) -> bool:
        """保存状态到JSON文件"""
        data = {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
            "reset_reason": self.reset_reason,
        }
        result = write_json(project_dir / self.SESSION_FILE, data)

        # 同时保存 session ID 文件
        id_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
        }
        write_json(project_dir / self.SESSION_ID_FILE, id_data)

        return result

    def update_usage(self) -> None:
        """更新最后使用时间"""
        self.last_used = datetime.now()

    def is_expired(self) -> bool:
        """检查会话是否过期"""
        if not self.session_id:
            return True
        expiry_time = self.last_used + timedelta(hours=self.EXPIRY_HOURS)
        return datetime.now() > expiry_time

    def reset(self, reason: str = "") -> None:
        """重置会话"""
        self.session_id = ""
        self.reset_at = datetime.now()
        self.reset_reason = reason
        self.created_at = datetime.now()

    def set_session_id(self, session_id: str) -> None:
        """设置会话ID"""
        self.session_id = session_id
        self.update_usage()

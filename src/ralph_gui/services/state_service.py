"""
状态服务 - 读写Ralph状态文件
"""
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..models import (
    CircuitBreakerModel,
    LoopStateModel,
    SessionModel,
    RateLimitModel,
    Project
)
from ..utils import read_json
from ..lib.log_utils import get_service_logger

logger = get_service_logger()


class StateService:
    """状态服务"""

    def __init__(self, project_dir: Path):
        logger.debug(f"StateService initializing for: {project_dir}")
        self.project_dir = project_dir
        self.ralph_dir = project_dir / ".ralph"
        logger.debug(f"StateService ready. ralph_dir: {self.ralph_dir}")

    def is_ralph_enabled(self) -> bool:
        """检查Ralph是否已启用"""
        required_files = ["PROMPT.md", "fix_plan.md", "AGENT.md"]
        enabled = all((self.ralph_dir / f).exists() for f in required_files)
        logger.debug(f"RALPH enabled check: {enabled}")
        return enabled

    def load_project(self) -> Project:
        """加载项目信息"""
        logger.debug(f"Loading project from: {self.project_dir}")
        return Project.from_directory(self.project_dir)

    def load_circuit_breaker(self) -> CircuitBreakerModel:
        """加载回路断路器状态"""
        logger.debug("Loading circuit breaker")
        return CircuitBreakerModel.from_project(self.project_dir)

    def load_loop_state(self) -> LoopStateModel:
        """加载循环状态"""
        logger.debug("Loading loop state")
        return LoopStateModel.from_project(self.project_dir)

    def load_session(self) -> SessionModel:
        """加载会话状态"""
        logger.debug("Loading session")
        return SessionModel.from_project(self.project_dir)

    def load_rate_limit(self, max_calls: int = 100, max_tokens: int = 0) -> RateLimitModel:
        """加载速率限制状态"""
        logger.debug(f"Loading rate limit: max_calls={max_calls}, max_tokens={max_tokens}")
        return RateLimitModel.from_project(self.project_dir, max_calls, max_tokens)

    def load_response_analysis(self) -> Optional[Dict[str, Any]]:
        """加载响应分析结果"""
        analysis_file = self.ralph_dir / ".response_analysis"
        logger.debug(f"Loading response analysis from: {analysis_file}")
        return read_json(analysis_file)

    def load_exit_signals(self) -> Optional[Dict[str, Any]]:
        """加载退出信号"""
        signals_file = self.ralph_dir / ".exit_signals"
        logger.debug(f"Loading exit signals from: {signals_file}")
        return read_json(signals_file)

    def load_status(self) -> Dict[str, Any]:
        """加载完整状态"""
        status_file = self.ralph_dir / "status.json"
        logger.debug(f"Loading status from: {status_file}")
        return read_json(status_file) or {}

    def save_circuit_breaker(self, model: CircuitBreakerModel) -> bool:
        """保存回路断路器状态"""
        logger.debug("Saving circuit breaker")
        return model.save(self.project_dir)

    def save_loop_state(self, model: LoopStateModel) -> bool:
        """保存循环状态"""
        logger.debug("Saving loop state")
        return model.save(self.project_dir)

    def save_session(self, model: SessionModel) -> bool:
        """保存会话状态"""
        logger.debug("Saving session")
        return model.save(self.project_dir)

    def save_rate_limit(self, model: RateLimitModel) -> bool:
        """保存速率限制状态"""
        logger.debug("Saving rate limit")
        return model.save(self.project_dir)

    def get_recent_logs(self, count: int = 10) -> List[str]:
        """获取最近的日志文件"""
        logs_dir = self.ralph_dir / "logs"
        logger.debug(f"Getting recent logs from: {logs_dir}, count={count}")
        if not logs_dir.exists():
            logger.debug("Logs directory does not exist")
            return []

        log_files = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        logs = []
        for log_file in log_files[:count]:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs.append(f.read()[-5000:])  # 最后5KB
            except IOError as e:
                logger.error(f"Error reading log file {log_file}: {e}", exc_info=True)
        logger.debug(f"Retrieved {len(logs)} recent logs")
        return logs

    def get_fix_plan_content(self) -> Optional[str]:
        """获取fix_plan内容"""
        fix_plan = self.ralph_dir / "fix_plan.md"
        logger.debug(f"Loading fix_plan from: {fix_plan}")
        if fix_plan.exists():
            try:
                with open(fix_plan, 'r', encoding='utf-8') as f:
                    return f.read()
            except IOError as e:
                logger.error(f"Error reading fix_plan: {e}", exc_info=True)
        return None

    def get_prompt_content(self) -> Optional[str]:
        """获取PROMPT内容"""
        prompt = self.ralph_dir / "PROMPT.md"
        logger.debug(f"Loading PROMPT from: {prompt}")
        if prompt.exists():
            try:
                with open(prompt, 'r', encoding='utf-8') as f:
                    return f.read()
            except IOError as e:
                logger.error(f"Error reading PROMPT: {e}")
        return None

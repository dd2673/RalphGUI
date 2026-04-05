"""
启动流程Presenter
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QObject, Signal
from ..services import StateService, CLIService, ConfigService


class StartupPresenter(QObject):
    """启动流程Presenter"""

    init_completed = Signal(bool)  # 初始化完成信号

    def __init__(
        self,
        state_service: StateService,
        cli_service: CLIService,
        config_service: ConfigService
    ):
        super().__init__()
        self.state_service = state_service
        self.cli_service = cli_service
        self.config_service = config_service
        self._project = None

    @property
    def project(self):
        return self._project

    def validate_directory(self, dir_path: Path) -> tuple[bool, str]:
        """
        验证目录

        Returns:
            (is_valid, message)
        """
        if not dir_path.exists():
            return False, "目录不存在"

        if not dir_path.is_dir():
            return False, "路径不是目录"

        # 检查git仓库
        git_dir = dir_path / ".git"
        if not git_dir.exists():
            return False, "不是Git仓库"

        return True, "OK"

    def check_ralph_enabled(self, dir_path: Path) -> bool:
        """检查Ralph是否已启用"""
        self.state_service.project_dir = dir_path
        return self.state_service.is_ralph_enabled()

    def load_project(self, dir_path: Path):
        """加载项目"""
        self.state_service.project_dir = dir_path
        self._project = self.state_service.load_project()

        # 加载配置
        if self._project.ralphrc_file and self._project.ralphrc_file.exists():
            self.config_service.config_file = self._project.ralphrc_file
            self.config_service.load()

        return self._project

    def initialize_project(
        self,
        dir_path: Path,
        from_source: str = None,
        non_interactive: bool = True,
        callback=None
    ) -> bool:
        """
        初始化项目

        Returns:
            是否成功（注意：当使用callback时返回True，实际结果通过callback传递）
        """
        try:
            # 连接信号以在主线程执行 callback
            if callback:
                self.init_completed.connect(lambda success: self._on_init_completed(success, callback, dir_path))

            # 在后台线程中执行初始化，避免阻塞UI
            import threading
            thread = threading.Thread(
                target=self._initialize_in_thread,
                args=(dir_path, from_source, non_interactive)
            )
            thread.daemon = True
            thread.start()
            return True

        except Exception as e:
            return False

    def _on_init_completed(self, success, callback, dir_path):
        """在主线程中处理初始化完成"""
        if success:
            self.load_project(dir_path)
        callback(success)

    def _initialize_in_thread(self, dir_path: Path, from_source: str, non_interactive: bool):
        """在后台线程中执行初始化"""
        try:
            returncode = self.cli_service.run_enable_wizard(
                dir_path,
                from_source=from_source,
                non_interactive=non_interactive,
            )
            success = returncode == 0
            # 通过信号通知结果，信号会自动在主线程发射
            self.init_completed.emit(success)
        except Exception as e:
            self.init_completed.emit(False)

    def get_project_state_summary(self) -> dict:
        """获取项目状态摘要"""
        if not self._project:
            return {}

        circuit = self.state_service.load_circuit_breaker()
        loop_state = self.state_service.load_loop_state()

        return {
            "project_name": self._project.name,
            "is_ralph_enabled": self._project.is_ralph_enabled,
            "circuit_state": circuit.state.value,
            "loop_count": loop_state.loop_count,
            "calls_made": loop_state.calls_made_this_hour,
            "max_calls": loop_state.max_calls_per_hour,
        }

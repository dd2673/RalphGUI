"""
Ralph GUI 应用类 - Midnight Studio
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PySide6.QtCore import Qt, QTimer
from .main_window import MainWindow
from .views.startup_dialog import StartupDialog
from .services import StateService, CLIService, ConfigService, LogService
from .presenters import StartupPresenter, LoopPresenter, SettingsPresenter
from .views.theme import create_dark_palette, Colors, TOOLTIP_STYLE
from .i18n import tr
from .lib.log_utils import get_app_logger, init_logger

# 获取应用日志器
app_logger = get_app_logger()


class RalphApp:
    """Ralph GUI应用 - Midnight Studio 深色主题"""

    def __init__(self):
        # 获取或创建 QApplication 实例
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication([])

        # 设置 app 属性以便其他组件访问
        self.app.setProperty("ralph_app", self)

        self.app.setApplicationName("Ralph")
        self.app.setApplicationVersion("0.1.0")

        # 应用全局样式
        self.app.setStyle("Fusion")

        # 设置全局调色板
        palette = create_dark_palette()
        self.app.setPalette(palette)

        # 设置全局样式表
        self.app.setStyleSheet(f"""
            QToolTip {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QMessageBox {{
                background-color: {Colors.BG_SURFACE};
            }}
        """)

        # 初始化服务
        self.cli_service = CLIService()
        self.config_service = ConfigService()

        # 初始化presenters
        self.startup_presenter = None
        self.loop_presenter = None
        self.settings_presenter = None

        # 主窗口
        self.main_window = None

    def _create_presenters(self, project_dir: Path):
        """创建Presenters"""
        app_logger.info(f"Creating presenters for: {project_dir}")
        try:
            state_service = StateService(project_dir)
            log_service = LogService(project_dir)

            self.startup_presenter = StartupPresenter(
                state_service, self.cli_service, self.config_service
            )
            self.loop_presenter = LoopPresenter(
                state_service, self.cli_service, self.config_service, log_service
            )
            self.settings_presenter = SettingsPresenter(
                self.config_service, state_service
            )

            # 加载配置（如果项目已初始化）
            if project_dir:
                project = self.startup_presenter.load_project(project_dir)
                app_logger.info(f"Project loaded: ralphrc_file={project.ralphrc_file if project else None}")
                if project and project.ralphrc_file:
                    self.config_service.config_file = project.ralphrc_file
                    self.config_service.load()
                    app_logger.info(f"Config file set to: {self.config_service.config_file}")
                else:
                    app_logger.warning(f"No .ralphrc file found for project")

            app_logger.info("Presenters created successfully")
        except Exception as e:
            app_logger.error(f"Error creating presenters: {e}", exc_info=True)
            raise

    def run(self):
        """运行应用 - 直接显示主窗口"""
        # 初始化日志系统
        log_dir = Path("D:/AI/ralph-gui/logs")
        init_logger(log_dir, level="DEBUG")

        # 读取上次使用的目录
        from PySide6.QtCore import QSettings
        settings = QSettings("RalphGUI", "RalphGUI")
        last_dir = settings.value("last_project_directory", "")

        # 如果目录存在且有效，使用它
        project_dir = Path(last_dir) if last_dir and Path(last_dir).exists() else None

        # 如果有目录，先创建 presenters
        if project_dir:
            self._create_presenters(project_dir)

        # 直接创建主窗口（即使没有目录也会显示界面）
        self.main_window = MainWindow(project_dir)
        self._connect_presenter_signals()
        self.main_window.show()

        self.app.exec()

    def _on_directory_selected(self, dir_path: Path):
        """目录已选择"""
        app_logger.info(f"Directory selected: {dir_path}")
        try:
            self._create_presenters(dir_path)
            app_logger.info("Creating main window...")
            self.main_window = MainWindow(dir_path)
            self._connect_presenter_signals()
            app_logger.info("Showing main window...")
            self.main_window.show()
            app_logger.info("Main window shown successfully")
        except Exception as e:
            app_logger.error(f"Error in _on_directory_selected: {e}", exc_info=True)
            QMessageBox.critical(
                None,
                tr("error"),
                f"加载项目时发生错误: {e}"
            )

    def _on_init_requested(self, dir_path: Path):
        """请求初始化"""
        app_logger.info(f"Init requested for: {dir_path}")
        try:
            self._create_presenters(dir_path)
        except Exception as e:
            app_logger.error(f"Failed to create presenters for initialization: {e}", exc_info=True)
            QMessageBox.critical(
                None,
                tr("error"),
                f"初始化失败: {e}"
            )
            return

        # 显示进度对话框
        progress = QProgressDialog(
            tr("initializing"),
            None,
            0,
            100,
            None
        )
        progress.setWindowTitle(tr("init_ralph"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        init_done = False
        timer = QTimer()

        def init_callback(success):
            nonlocal init_done
            init_done = True
            # 通过事件循环在主线程中处理，避免线程安全问题
            QTimer.singleShot(0, lambda: self._on_init_done(dir_path, success, progress, timer))

        # 使用presenter的初始化方法，它会处理后台线程
        self.startup_presenter.initialize_project(
            dir_path,
            non_interactive=True,
            callback=init_callback
        )

        # 模拟进度条动画
        def update_progress():
            if init_done:
                return
            current = progress.value()
            if current < 90:
                progress.setValue(current + 10)

        timer.timeout.connect(update_progress)
        timer.start(50)

    def _on_init_done(self, dir_path: Path, success: bool, progress: QProgressDialog, timer: QTimer):
        """初始化完成处理"""
        timer.stop()
        progress.setValue(100)
        progress.close()

        if success:
            self._on_directory_selected(dir_path)
        else:
            QMessageBox.warning(
                None,
                tr("error"),
                tr("init_failed_reason").format(reason="初始化过程失败")
            )

    def _on_cancelled(self):
        """取消启动"""
        pass

    def _connect_presenter_signals(self):
        """连接Presenter信号"""
        if not self.main_window:
            return

        if self.loop_presenter:
            self.main_window.set_loop_presenter(self.loop_presenter)

        if self.settings_presenter:
            self.main_window.set_settings_presenter(self.settings_presenter)

    def get_startup_presenter(self):
        """获取StartupPresenter供MainWindow使用"""
        return self.startup_presenter

    def initialize_project(self, dir_path: Path, callback):
        """初始化项目（供MainWindow调用）"""
        app_logger.info(f"Initializing project: {dir_path}")
        try:
            if not self.startup_presenter:
                self._create_presenters(dir_path)
        except Exception as e:
            app_logger.error(f"Failed to create presenters for initialization: {e}", exc_info=True)
            callback(False)
            return

        # 使用presenter的初始化方法
        self.startup_presenter.initialize_project(
            dir_path,
            non_interactive=True,
            callback=callback
        )

    def on_project_selected(self, dir_path: Path):
        """项目选择或切换时的处理"""
        self._create_presenters(dir_path)
        if self.main_window:
            self.main_window.on_project_changed(dir_path)

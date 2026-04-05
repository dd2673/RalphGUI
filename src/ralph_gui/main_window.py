"""
主窗口 - Midnight Studio
"""
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QStatusBar, QApplication,
    QMessageBox, QMenuBar, QMenu, QFrame, QDialog,
    QStyle, QFileDialog, QProgressDialog, QComboBox,
    QSpinBox, QCheckBox, QFormLayout, QToolButton, QProgressBar,
    QSizePolicy, QSplitter, QScrollArea, QSystemTrayIcon
)
from PySide6.QtCore import Qt, QTimer, QSettings, QSize, Signal
from PySide6.QtGui import QAction, QShortcut
from .views.startup_dialog import StartupDialog
from .views.settings_panel import SettingsPanel
from .i18n import tr
from .views.theme import (
    BUTTON_PRIMARY_STYLE, BUTTON_SECONDARY_STYLE, BUTTON_DANGER_STYLE,
    STATUS_BAR_STYLE, LOG_VIEWER_STYLE, LINE_EDIT_STYLE,
    Colors, FONT_MONO,
    HEADER_BAR_STYLE, HERO_CARD_STYLE, CONTROL_PANEL_STYLE,
    PROGRESS_BAR_STYLE, get_circuit_state_style
)
from .lib.log_utils import get_ui_logger, get_app_logger

# 获取日志器
ui_logger = get_ui_logger()
app_logger = get_app_logger()


def get_process_memory_mb() -> float:
    """
    获取当前进程内存使用量（MB）

    使用跨平台方法：
    - Windows: 使用 ctypes 调用 Windows API
    - Unix: 读取 /proc/self/status
    """
    if sys.platform == 'win32':
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            ctypes.windll.psapi.GetProcessMemoryInfo

            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmi = PROCESS_MEMORY_COUNTERS_EX()
            pmi.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            kernel32.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(),
                ctypes.byref(pmi),
                pmi.cb
            )
            return pmi.WorkingSetSize / (1024 * 1024)
        except Exception:
            return 0.0
    else:
        # Unix-like: 读取 /proc/self/status
        try:
            with open('/proc/self/status', 'r') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        # VmRSS 是 resident set size，即实际物理内存
                        kb = int(line.split()[1])
                        return kb / 1024
        except Exception:
            pass
        return 0.0


class MainWindow(QMainWindow):
    """主窗口 - Midnight Studio 深色主题"""

    # 信号定义 - 用于线程安全的日志更新
    log_line_signal = Signal(str)

    def __init__(self, project_dir: Path = None):
        super().__init__()
        ui_logger.debug("MainWindow initializing...")
        self.project_dir = project_dir
        self.is_running = False
        self.loop_presenter = None
        self.settings_presenter = None
        # 运行时间计时器
        self._run_timer = QTimer(self)
        self._run_timer.timeout.connect(self._update_run_time)
        self._loop_start_time = None
        self._paused_elapsed = 0  # 暂停时已累积的时间（毫秒）
        self._run_time_label = None  # 状态栏运行时间标签
        # 内存监控
        self._memory_baseline_mb = get_process_memory_mb()
        self._memory_timer = QTimer(self)
        self._memory_timer.timeout.connect(self._check_memory_leak)
        ui_logger.info(f"Memory baseline: {self._memory_baseline_mb:.1f} MB")
        # 内存显示更新定时器（每5秒更新一次）
        self._memory_display_timer = QTimer(self)
        self._memory_display_timer.timeout.connect(self._update_memory_display)
        self._memory_display_timer.start(5000)
        # 初始内存显示
        self._update_memory_display()
        self._setup_ui()
        self._restore_window_geometry()
        self._setup_menu()
        self._setup_shortcuts()
        self._setup_system_tray()
        self._connect_control_signals()

        # 连接日志信号 - 线程安全的跨线程日志更新
        self.log_line_signal.connect(self._do_append_log)

        # 如果有项目目录，延迟显示诊断信息，避免阻塞启动
        if self.project_dir:
            QTimer.singleShot(500, self._do_initial_diagnostic)

        ui_logger.info("MainWindow UI setup complete")

    def _do_initial_diagnostic(self):
        """执行初始诊断（延迟调用，避免阻塞启动）"""
        if not self.project_dir:
            return

        # 使用统一的诊断方法获取结果
        from .services.config_service import ConfigService
        result = ConfigService.diagnose_project(self.project_dir)

        # 直接将诊断信息输出到日志面板
        self._append_diagnostic_to_log(result)

    def set_loop_presenter(self, presenter):
        """设置循环控制器Presenter"""
        ui_logger.info(f"Setting loop presenter: {presenter}")
        self.loop_presenter = presenter
        if presenter:
            presenter.set_callbacks(
                on_status_change=self._on_loop_status_change,
                on_log_line=self._on_loop_log_line,
                on_error=self._on_loop_error
            )
            ui_logger.debug("Loop presenter callbacks configured")

    def set_settings_presenter(self, presenter):
        """设置设置面板Presenter"""
        self.settings_presenter = presenter
        # _settings_action 可能在 _setup_menu() 之前被调用时尚未创建
        if hasattr(self, '_settings_action'):
            self._settings_action.setEnabled(presenter is not None)
        if presenter:
            self._load_current_settings()

    def _show_settings(self):
        """显示设置面板"""
        if not self.settings_presenter:
            QMessageBox.warning(self, tr("error"), tr("select_project_first"))
            return

        from PySide6.QtWidgets import QDialog
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("settings_panel"))
        dialog.setMinimumSize(580, 520)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_BASE};
            }}
        """)

        layout = QVBoxLayout(dialog)
        settings_panel = SettingsPanel(self.settings_presenter, dialog)
        layout.addWidget(settings_panel)

        # 关闭按钮
        close_btn = QPushButton(tr("confirm"))
        close_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _setup_ui(self):
        """设置UI - Midnight Studio Dashboard Layout"""
        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Colors.BG_BASE};
            }}
        """)

        # 中央部件
        # 创建滚动区域作为中央部件
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Colors.BG_BASE};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {Colors.BG_SURFACE};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {Colors.BORDER};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {Colors.BORDER_HOVER};
            }}
        """)
        
        # 滚动内容容器
        scroll_content = QWidget()
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Header Bar
        self._setup_header_bar(main_layout)

        # 2. Dashboard 区 (Grid: 60% + 40%)
        dashboard_container = self._setup_dashboard()
        main_layout.addWidget(dashboard_container, 0, Qt.AlignTop)

        # 3. Settings Panel (紧凑折叠)
        self._setup_settings_panel_compact()
        main_layout.addWidget(self.settings_container)

        # 4. Log Terminal (stretch=1)
        log_container = self._setup_log_terminal()
        main_layout.addWidget(log_container, 1)

        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        self.setCentralWidget(scroll_area)

        # 5. Status Bar
        self._setup_status_bar()

        # 设置窗口最小尺寸（合理的最小值）
        self.setMinimumSize(800, 600)

        # 启动时最大化窗口
        self.showMaximized()

        # 检查项目状态
        if self.project_dir:
            self._check_project_status(self.project_dir)
        else:
            self._show_no_directory_state()

    def _setup_header_bar(self, parent_layout):
        """设置 Header Bar - 紧凑的项目路径 + 操作按钮"""
        header = QFrame()
        header.setStyleSheet(HEADER_BAR_STYLE)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(12)

        # 标题
        title_label = QLabel("RALPH")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.PRIMARY};
                font-size: 20px;
                font-weight: bold;
                font-family: {FONT_MONO};
                letter-spacing: 4px;
            }}
        """)
        header_layout.addWidget(title_label)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet(f"border: 1px solid {Colors.BORDER};")
        separator.setFixedWidth(1)
        header_layout.addWidget(separator)

        # 项目图标
        self.dir_icon = QLabel("📁")
        self.dir_icon.setStyleSheet("font-size: 16px;")
        header_layout.addWidget(self.dir_icon)

        # 项目路径标签
        self.project_path_label = QLabel(tr("no_project_selected"))
        self.project_path_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                font-family: {FONT_MONO};
            }}
        """)
        header_layout.addWidget(self.project_path_label, 1)

        # 历史目录选择下拉
        self.dir_combo = QComboBox()
        self.dir_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.dir_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QComboBox::dropDown {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
            }}
        """)
        self.dir_combo.currentIndexChanged.connect(self._on_recent_directory_selected)
        self._populate_recent_combo()
        header_layout.addWidget(self.dir_combo)

        # 更改目录按钮
        self.change_dir_btn = QPushButton(tr("change_directory"))
        self.change_dir_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.change_dir_btn.setCursor(Qt.PointingHandCursor)
        self.change_dir_btn.clicked.connect(self._on_change_directory)
        header_layout.addWidget(self.change_dir_btn)

        # 初始化按钮（仅未初始化时显示）
        self.init_btn = QPushButton(tr("initialize"))
        self.init_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        self.init_btn.setCursor(Qt.PointingHandCursor)
        self.init_btn.clicked.connect(self._on_initialize)
        self.init_btn.hide()
        header_layout.addWidget(self.init_btn)

        parent_layout.addWidget(header)

    def _setup_dashboard(self):
        """设置 Dashboard 区 - Grid 布局，自适应窗口大小"""
        container = QFrame()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QGridLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        # 左: Status Hero Card (跨两行)
        self.status_hero = self._create_status_hero_card()
        layout.addWidget(self.status_hero, 0, 0, 2, 1)

        # 右: Control Panel
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel, 0, 1, 2, 1)

        # 设置列宽比例: 左60% 右40%
        layout.setColumnStretch(0, 6)
        layout.setColumnStretch(1, 4)

        return container

    def _create_status_hero_card(self):
        """创建 Status Hero Card - 整合所有状态信息"""
        card = QFrame()
        card.setStyleSheet(HERO_CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 回路状态 (大号 + 发光)
        circuit_header = QLabel(tr("circuit_breaker"))
        circuit_header.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 0.5px;
            }}
        """)
        layout.addWidget(circuit_header)

        self.circuit_state_label = QLabel(tr("state_closed"))
        self.circuit_state_label.setObjectName("circuit_state")
        self.circuit_state_label.setStyleSheet(get_circuit_state_style("CLOSED"))
        layout.addWidget(self.circuit_state_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"border: 1px solid {Colors.BORDER};")
        layout.addWidget(line)

        # 运行状态
        run_status_layout = QHBoxLayout()
        run_status_layout.setSpacing(8)

        self.run_indicator = QLabel("●")
        self.run_indicator.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 14px;
            }}
        """)
        run_status_layout.addWidget(self.run_indicator)

        self.run_status_label = QLabel(tr("stopped"))
        self.run_status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 13px;
            }}
        """)
        run_status_layout.addWidget(self.run_status_label)
        run_status_layout.addStretch()

        layout.addLayout(run_status_layout)

        # 循环计数和 API 配额
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(16)

        # 循环计数
        loop_frame = QFrame()
        loop_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_ELEVATED};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        loop_layout = QVBoxLayout(loop_frame)
        loop_layout.setContentsMargins(8, 8, 8, 8)
        loop_layout.setSpacing(4)

        loop_title = QLabel(tr("loop_count"))
        loop_title.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 10px;
                font-weight: 500;
            }}
        """)
        loop_layout.addWidget(loop_title)

        self.loop_count_label = QLabel("0")
        self.loop_count_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 28px;
                font-weight: bold;
                font-family: {FONT_MONO};
            }}
        """)
        loop_layout.addWidget(self.loop_count_label)

        metrics_layout.addWidget(loop_frame, 1)

        # API 配额
        api_frame = QFrame()
        api_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_ELEVATED};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        api_layout = QVBoxLayout(api_frame)
        api_layout.setContentsMargins(8, 8, 8, 8)
        api_layout.setSpacing(4)

        api_title = QLabel(tr("api_calls"))
        api_title.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 10px;
                font-weight: 500;
            }}
        """)
        api_layout.addWidget(api_title)

        self.api_progress = QProgressBar()
        self.api_progress.setStyleSheet(PROGRESS_BAR_STYLE)
        self.api_progress.setMinimum(0)
        self.api_progress.setMaximum(100)
        self.api_progress.setValue(0)
        self.api_progress.setTextVisible(False)
        self.api_progress.setFixedHeight(8)
        api_layout.addWidget(self.api_progress)

        self.api_calls_label = QLabel("0/100")
        self.api_calls_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 16px;
                font-weight: bold;
                font-family: {FONT_MONO};
            }}
        """)
        api_layout.addWidget(self.api_calls_label)

        metrics_layout.addWidget(api_frame, 1)

        # 内存使用
        memory_frame = QFrame()
        memory_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_ELEVATED};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        memory_layout = QVBoxLayout(memory_frame)
        memory_layout.setContentsMargins(8, 8, 8, 8)
        memory_layout.setSpacing(4)

        memory_title = QLabel(tr("memory_usage"))
        memory_title.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 10px;
                font-weight: 500;
            }}
        """)
        memory_layout.addWidget(memory_title)

        self.memory_label = QLabel("-- MB")
        self.memory_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 16px;
                font-weight: bold;
                font-family: {FONT_MONO};
            }}
        """)
        memory_layout.addWidget(self.memory_label)

        metrics_layout.addWidget(memory_frame, 1)

        layout.addLayout(metrics_layout)

        return card

    def _create_control_panel(self):
        """创建 Control Panel - 垂直排列按钮"""
        panel = QFrame()
        panel.setStyleSheet(CONTROL_PANEL_STYLE)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 按钮容器
        buttons_frame = QFrame()
        buttons_frame.setStyleSheet("background: transparent;")
        buttons_layout = QVBoxLayout(buttons_frame)
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        # 图标大小
        icon_size = QSize(18, 18)

        # Start 按钮
        self.start_btn = QPushButton(tr("start"))
        self.start_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.start_btn.setIconSize(icon_size)
        self.start_btn.setMinimumHeight(44)
        buttons_layout.addWidget(self.start_btn)

        # Stop 按钮
        self.stop_btn = QPushButton(tr("stop"))
        self.stop_btn.setStyleSheet(BUTTON_DANGER_STYLE)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.setIconSize(icon_size)
        self.stop_btn.setMinimumHeight(44)
        buttons_layout.addWidget(self.stop_btn)

        # Pause 按钮
        self.pause_btn = QPushButton(tr("pause"))
        self.pause_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.pause_btn.setIconSize(icon_size)
        self.pause_btn.setMinimumHeight(44)
        buttons_layout.addWidget(self.pause_btn)

        # Reset Circuit 按钮
        self.reset_circuit_btn = QPushButton(tr("reset_circuit"))
        self.reset_circuit_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.reset_circuit_btn.setCursor(Qt.PointingHandCursor)
        self.reset_circuit_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.reset_circuit_btn.setIconSize(icon_size)
        self.reset_circuit_btn.setMinimumHeight(44)
        buttons_layout.addWidget(self.reset_circuit_btn)

        layout.addWidget(buttons_frame)

        # 运行时间
        time_frame = QFrame()
        time_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_ELEVATED};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        time_layout = QVBoxLayout(time_frame)
        time_layout.setContentsMargins(8, 8, 8, 8)
        time_layout.setSpacing(4)

        time_title = QLabel(tr("elapsed_time"))
        time_title.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 10px;
                font-weight: 500;
            }}
        """)
        time_layout.addWidget(time_title)

        self._run_time_label = QLabel("00:00:00")
        self._run_time_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.PRIMARY};
                font-size: 24px;
                font-weight: bold;
                font-family: {FONT_MONO};
            }}
        """)
        self._run_time_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self._run_time_label)

        layout.addWidget(time_frame)

        layout.addStretch()

        return panel

    def _setup_settings_panel_compact(self):
        """设置紧凑的设置面板 - 四行布局以显示所有配置"""
        self.settings_container = QFrame()
        self.settings_container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
            }}
        """)

        # 标题行（可点击展开/折叠）
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(16, 10, 16, 8)

        self.settings_toggle = QToolButton()
        self.settings_toggle.setText(tr("settings") + " ▼")
        self.settings_toggle.setStyleSheet(f"""
            QToolButton {{
                color: {Colors.TEXT_PRIMARY};
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }}
            QToolButton:hover {{
                color: {Colors.PRIMARY};
            }}
        """)
        self.settings_toggle.setCursor(Qt.PointingHandCursor)
        self.settings_toggle.clicked.connect(self._toggle_settings)
        header_layout.addWidget(self.settings_toggle)
        header_layout.addStretch()

        # 内容区（可折叠）- 使用垂直布局包含四行
        self.settings_content = QFrame()
        self.settings_content.setStyleSheet("background: transparent;")
        content_main_layout = QVBoxLayout(self.settings_content)
        content_main_layout.setSpacing(10)
        content_main_layout.setContentsMargins(16, 0, 16, 16)

        # 第 1 行: MAX_CALLS + TIMEOUT
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(12)

        calls_label = QLabel(tr("max_calls_per_hour"))
        calls_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        row1_layout.addWidget(calls_label)

        self.max_calls_spin = QSpinBox()
        self.max_calls_spin.setRange(1, 1000)
        self.max_calls_spin.setSuffix(tr("suffix_calls_per_hour"))
        self.max_calls_spin.setStyleSheet(LINE_EDIT_STYLE)
        self.max_calls_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.max_calls_spin.setMinimumWidth(100)
        self.max_calls_spin.valueChanged.connect(self._on_setting_changed)
        row1_layout.addWidget(self.max_calls_spin)

        timeout_label = QLabel(tr("timeout_minutes"))
        timeout_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        row1_layout.addWidget(timeout_label)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setSuffix(tr("suffix_minutes"))
        self.timeout_spin.setStyleSheet(LINE_EDIT_STYLE)
        self.timeout_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.timeout_spin.setMinimumWidth(80)
        self.timeout_spin.valueChanged.connect(self._on_setting_changed)
        row1_layout.addWidget(self.timeout_spin)

        row1_layout.addStretch()
        content_main_layout.addLayout(row1_layout)

        # 第 2 行: NO_PROGRESS + SAME_ERROR
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(12)

        no_progress_label = QLabel(tr("no_progress_threshold"))
        no_progress_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        row2_layout.addWidget(no_progress_label)

        self.no_progress_spin = QSpinBox()
        self.no_progress_spin.setRange(1, 10)
        self.no_progress_spin.setStyleSheet(LINE_EDIT_STYLE)
        self.no_progress_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.no_progress_spin.setMinimumWidth(60)
        self.no_progress_spin.valueChanged.connect(self._on_setting_changed)
        row2_layout.addWidget(self.no_progress_spin)

        same_error_label = QLabel(tr("same_error_threshold"))
        same_error_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        row2_layout.addWidget(same_error_label)

        self.same_error_spin = QSpinBox()
        self.same_error_spin.setRange(1, 20)
        self.same_error_spin.setStyleSheet(LINE_EDIT_STYLE)
        self.same_error_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.same_error_spin.setMinimumWidth(60)
        self.same_error_spin.valueChanged.connect(self._on_setting_changed)
        row2_layout.addWidget(self.same_error_spin)

        row2_layout.addStretch()
        content_main_layout.addLayout(row2_layout)

        # 第 3 行: COOLDOWN + LOOP_DELAY
        row3_layout = QHBoxLayout()
        row3_layout.setSpacing(12)

        cooldown_label = QLabel(tr("cooldown_minutes"))
        cooldown_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        row3_layout.addWidget(cooldown_label)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(1, 60)
        self.cooldown_spin.setSuffix(tr("suffix_minutes"))
        self.cooldown_spin.setStyleSheet(LINE_EDIT_STYLE)
        self.cooldown_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.cooldown_spin.setMinimumWidth(80)
        self.cooldown_spin.valueChanged.connect(self._on_setting_changed)
        row3_layout.addWidget(self.cooldown_spin)

        delay_label = QLabel(tr("loop_delay_seconds"))
        delay_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        row3_layout.addWidget(delay_label)

        self.loop_delay_spin = QSpinBox()
        self.loop_delay_spin.setRange(1, 60)
        self.loop_delay_spin.setSuffix("s")
        self.loop_delay_spin.setStyleSheet(LINE_EDIT_STYLE)
        self.loop_delay_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.loop_delay_spin.setMinimumWidth(60)
        self.loop_delay_spin.valueChanged.connect(self._on_setting_changed)
        row3_layout.addWidget(self.loop_delay_spin)

        row3_layout.addStretch()
        content_main_layout.addLayout(row3_layout)

        # 第 4 行: SKIP_PERMISSIONS + APPEND_PREVIOUS_SUMMARY + SESSION_EXPIRY
        row4_layout = QHBoxLayout()
        row4_layout.setSpacing(12)

        self.skip_permissions_check = QCheckBox()
        self.skip_permissions_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
            }}
        """)
        self.skip_permissions_check.setText(tr("dangerously_skip_permissions"))
        self.skip_permissions_check.stateChanged.connect(self._on_setting_changed)
        row4_layout.addWidget(self.skip_permissions_check)

        self.append_summary_check = QCheckBox()
        self.append_summary_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
            }}
        """)
        self.append_summary_check.setText(tr("append_previous_summary"))
        self.append_summary_check.stateChanged.connect(self._on_setting_changed)
        row4_layout.addWidget(self.append_summary_check)

        self.session_continuity_check = QCheckBox()
        self.session_continuity_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
            }}
        """)
        self.session_continuity_check.setText(tr("session_continuity"))
        self.session_continuity_check.stateChanged.connect(self._on_setting_changed)
        row4_layout.addWidget(self.session_continuity_check)

        session_label = QLabel(tr("session_expiry_hours"))
        session_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        row4_layout.addWidget(session_label)

        self.session_expiry_spin = QSpinBox()
        self.session_expiry_spin.setRange(1, 168)
        self.session_expiry_spin.setSuffix(tr("suffix_hours"))
        self.session_expiry_spin.setStyleSheet(LINE_EDIT_STYLE)
        self.session_expiry_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.session_expiry_spin.setMinimumWidth(80)
        self.session_expiry_spin.valueChanged.connect(self._on_setting_changed)
        row4_layout.addWidget(self.session_expiry_spin)

        row4_layout.addStretch()

        # 应用按钮
        self.apply_settings_btn = QPushButton(tr("save_settings"))
        self.apply_settings_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        self.apply_settings_btn.setCursor(Qt.PointingHandCursor)
        self.apply_settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.apply_settings_btn.clicked.connect(self._apply_settings)
        row4_layout.addWidget(self.apply_settings_btn)

        content_main_layout.addLayout(row4_layout)

        # 主布局
        main_layout = QVBoxLayout(self.settings_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.settings_content)

        # 默认折叠
        self.settings_content.setVisible(False)
        self._settings_expanded = False

    def _setup_log_terminal(self):
        """设置日志终端 - 左右分屏布局"""
        # 日志区域容器
        log_container = QFrame()
        log_container.setStyleSheet("background: transparent; border: none;")
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(6)

        # 使用 QSplitter 实现左右分屏
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Colors.BORDER};
                width: 1px;
            }}
        """)

        # === 左侧: 内部日志面板 ===
        left_panel = QFrame()
        left_panel.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # 左侧标签行
        left_header = QHBoxLayout()
        left_header.setSpacing(8)
        self.log_label = QLabel(tr("logs"))
        self.log_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        left_header.addWidget(self.log_label)
        left_header.addStretch()
        left_layout.addLayout(left_header)

        # 内部日志查看器
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setPlaceholderText(tr("no_logs_yet"))
        self.log_viewer.setStyleSheet(LOG_VIEWER_STYLE)
        left_layout.addWidget(self.log_viewer, 1)

        # === 右侧: Claude 输出面板 ===
        right_panel = QFrame()
        right_panel.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # 右侧标签行
        right_header = QHBoxLayout()
        right_header.setSpacing(8)
        self.claude_output_label = QLabel(tr("claude_output"))
        self.claude_output_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        right_header.addWidget(self.claude_output_label)
        right_header.addStretch()
        right_layout.addLayout(right_header)

        # Claude 输出查看器
        self.claude_output_viewer = QTextEdit()
        self.claude_output_viewer.setReadOnly(True)
        self.claude_output_viewer.setPlaceholderText(tr("no_claude_output_yet"))
        self.claude_output_viewer.setStyleSheet(LOG_VIEWER_STYLE)
        right_layout.addWidget(self.claude_output_viewer, 1)

        # 添加到 splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # 工具按钮行 (全局)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        header_layout.addStretch()

        self.clear_btn = QPushButton(tr("clear_logs"))
        self.clear_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_both_logs)
        header_layout.addWidget(self.clear_btn)

        self.diagnose_btn = QPushButton(tr("check_project"))
        self.diagnose_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.diagnose_btn.setCursor(Qt.PointingHandCursor)
        self.diagnose_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.diagnose_btn.clicked.connect(self._run_project_diagnosis)
        self.diagnose_btn.setEnabled(False)  # 初始禁用
        header_layout.addWidget(self.diagnose_btn)

        self.export_logs_btn = QPushButton(tr("export_logs"))
        self.export_logs_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.export_logs_btn.setCursor(Qt.PointingHandCursor)
        self.export_logs_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.export_logs_btn.clicked.connect(self._export_logs)
        header_layout.addWidget(self.export_logs_btn)

        log_layout.addLayout(header_layout)
        log_layout.addWidget(splitter, 1)

        return log_container

    def _setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(STATUS_BAR_STYLE)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("ready"))

    def _populate_recent_combo(self):
        """填充历史目录下拉列表"""
        from PySide6.QtCore import QSettings
        self.dir_combo.blockSignals(True)
        self.dir_combo.clear()

        settings = QSettings("RalphGUI", "RalphGUI")
        dirs = settings.value("recent_directories", [])
        if isinstance(dirs, str):
            dirs = [dirs] if dirs else []

        # 过滤不存在的目录
        valid_dirs = [d for d in dirs if Path(d).exists()]
        if valid_dirs:
            for d in valid_dirs:
                name = Path(d).name
                parent = Path(d).parent.name
                display = f"{parent}/{name}" if len(parent) > 0 else name
                self.dir_combo.addItem(display, d)
        else:
            self.dir_combo.addItem(tr("no_recent_directories"), "")

        self.dir_combo.blockSignals(False)

    def _on_recent_directory_selected(self, index):
        """从历史列表选择目录"""
        if index < 0:
            return
        dir_path = self.dir_combo.currentData()
        if dir_path:
            self._check_project_status(Path(dir_path))

    def _check_project_status(self, dir_path: Path):
        """检查项目状态并更新UI"""
        from .services import StateService
        ui_logger.debug(f"_check_project_status called with: {dir_path}")

        self.project_dir = dir_path
        self._save_last_directory(dir_path)
        
        # 启用诊断按钮
        if hasattr(self, 'diagnose_btn'):
            self.diagnose_btn.setEnabled(True)

        if not dir_path or not dir_path.exists():
            ui_logger.debug("No valid dir_path, showing no directory state")
            self._show_no_directory_state()
            return

        state_service = StateService(dir_path)
        is_enabled = state_service.is_ralph_enabled()
        ui_logger.debug(f"RALPH enabled: {is_enabled}")

        if is_enabled:
            # 已初始化的项目，确保 app 有对应的 presenters
            ui_logger.debug("Project is RALPH enabled, ensuring presenters")
            self._ensure_presenters_for_project(dir_path)
            ui_logger.debug("About to call _show_initialized_state")
            self._show_initialized_state(dir_path)
            ui_logger.debug("_show_initialized_state completed")
        else:
            ui_logger.debug("Project is not RALPH enabled, showing uninitialized state")
            self._show_uninitialized_state(dir_path)

    def _ensure_presenters_for_project(self, dir_path: Path):
        """为指定项目确保 presenters 可用"""
        from .app import RalphApp
        app = QApplication.instance().property("ralph_app")

        # 检查 app 是否有这个项目的 presenters
        if app and hasattr(app, 'startup_presenter') and app.startup_presenter:
            # app 已经有 presenters，检查是否匹配当前项目
            if hasattr(app.startup_presenter, 'state_service'):
                existing_dir = app.startup_presenter.state_service.project_dir
                if existing_dir != dir_path:
                    # 项目不匹配，需要重新创建
                    app._create_presenters(dir_path)
        else:
            # app 还没有 presenters，创建它们
            if app:
                app._create_presenters(dir_path)

        # 连接 presenters 到 main_window
        if app and app.loop_presenter:
            self.loop_presenter = app.loop_presenter
            app.main_window = self
            self.loop_presenter.set_callbacks(
                on_status_change=self._on_loop_status_change,
                on_log_line=self._on_loop_log_line,
                on_error=self._on_loop_error
            )

        # 设置 settings_presenter（这会触发 _load_current_settings）
        if app and app.settings_presenter:
            self.set_settings_presenter(app.settings_presenter)

    def _toggle_settings(self):
        """切换设置面板展开/折叠"""
        self._settings_expanded = not self._settings_expanded
        self.settings_content.setVisible(self._settings_expanded)
        self.settings_toggle.setText(tr("settings") + (" ▼" if self._settings_expanded else " ►"))

    def _on_setting_changed(self):
        """设置值变化"""
        # 可以在这里标记有未保存的更改
        pass

    def _apply_settings(self):
        """应用设置"""
        if not self.settings_presenter:
            # 尝试获取 settings_presenter
            from .app import RalphApp
            app = QApplication.instance().property("ralph_app")
            if app and app.settings_presenter:
                self.settings_presenter = app.settings_presenter
            else:
                QMessageBox.warning(self, tr("error"), tr("select_project_first"))
                return

        settings = {
            "MAX_CALLS_PER_HOUR": self.max_calls_spin.value(),
            "CLAUDE_TIMEOUT_MINUTES": self.timeout_spin.value(),
            "CB_NO_PROGRESS_THRESHOLD": self.no_progress_spin.value(),
            "CB_SAME_ERROR_THRESHOLD": self.same_error_spin.value(),
            "CB_COOLDOWN_MINUTES": self.cooldown_spin.value(),
            "LOOP_DELAY_SECONDS": self.loop_delay_spin.value(),
            "DANGEROUSLY_SKIP_PERMISSIONS": str(self.skip_permissions_check.isChecked()).lower(),
            "APPEND_PREVIOUS_SUMMARY": str(self.append_summary_check.isChecked()).lower(),
            "SESSION_CONTINUITY": str(self.session_continuity_check.isChecked()).lower(),
            "SESSION_EXPIRY_HOURS": self.session_expiry_spin.value(),
        }

        if self.settings_presenter.save_settings(settings):
            self.status_bar.showMessage(tr("settings_saved"))
            self._append_log(tr("settings_saved"))
            # 保存成功后更新 API 调用配额显示
            max_calls = self.max_calls_spin.value()
            self.api_calls_label.setText(f"0/{max_calls}")
            self.api_progress.setValue(0)
        else:
            QMessageBox.warning(self, tr("error"), tr("settings_save_failed"))

    def _load_current_settings(self):
        """加载当前设置到面板"""
        if not self.settings_presenter:
            return

        self.max_calls_spin.setValue(self.settings_presenter.get_setting("MAX_CALLS_PER_HOUR", 100))
        self.timeout_spin.setValue(self.settings_presenter.get_setting("CLAUDE_TIMEOUT_MINUTES", 15))
        self.no_progress_spin.setValue(self.settings_presenter.get_setting("CB_NO_PROGRESS_THRESHOLD", 3))
        self.same_error_spin.setValue(self.settings_presenter.get_setting("CB_SAME_ERROR_THRESHOLD", 5))
        self.cooldown_spin.setValue(self.settings_presenter.get_setting("CB_COOLDOWN_MINUTES", 10))
        self.loop_delay_spin.setValue(self.settings_presenter.get_setting("LOOP_DELAY_SECONDS", 5))
        # 将字符串 "True"/"False" 转换为布尔值
        skip_perms = self.settings_presenter.get_setting("DANGEROUSLY_SKIP_PERMISSIONS", False)
        if isinstance(skip_perms, str):
            skip_perms = skip_perms.lower() == "true"
        self.skip_permissions_check.setChecked(skip_perms)
        append_prev = self.settings_presenter.get_setting("APPEND_PREVIOUS_SUMMARY", True)
        if isinstance(append_prev, str):
            append_prev = append_prev.lower() == "true"
        self.append_summary_check.setChecked(append_prev)
        session_cont = self.settings_presenter.get_setting("SESSION_CONTINUITY", True)
        if isinstance(session_cont, str):
            session_cont = session_cont.lower() == "true"
        self.session_continuity_check.setChecked(session_cont)
        self.session_expiry_spin.setValue(self.settings_presenter.get_setting("SESSION_EXPIRY_HOURS", 24))

    def _show_no_directory_state(self):
        """显示未选择目录状态"""
        self.project_path_label.setText(tr("no_project_selected"))
        self.dir_icon.setText("📁")
        self.init_btn.hide()
        self._disable_controls()
        self._append_log(tr("no_project_selected"))

    def _show_uninitialized_state(self, dir_path: Path):
        """显示未初始化状态"""
        self.project_path_label.setText(f"{dir_path} ({tr('not_initialized')})")
        self.dir_icon.setText("⚠️")
        self.init_btn.show()
        self._disable_controls()
        self._append_log(tr("project_not_initialized").format(dir_path=dir_path))

    def _show_initialized_state(self, dir_path: Path):
        """显示已初始化状态"""
        self.project_path_label.setText(f"{dir_path} ({tr('initialized')})")
        self.dir_icon.setText("✅")
        self.init_btn.hide()
        self._enable_controls()
        self._load_project(dir_path)
        # 注意：_load_current_settings() 会在 set_settings_presenter() 中被调用
        self._append_log(tr("log_project_loaded").format(dir_path=dir_path))

    def _on_change_directory(self):
        """更改目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            tr("select_project_directory"),
            str(Path.home()) if not self.project_dir else str(self.project_dir.parent),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self._check_project_status(Path(dir_path))

    def _on_initialize(self):
        """初始化项目"""
        if not self.project_dir:
            QMessageBox.warning(self, tr("error"), tr("select_project_first"))
            return

        reply = QMessageBox.question(
            self,
            tr("init_ralph"),
            tr("init_ralph_prompt"),
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 检查是否是 git 仓库
        if not (self.project_dir / ".git").exists():
            reply = QMessageBox.question(
                self,
                tr("init_ralph"),
                tr("not_git_repo_prompt"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                import subprocess
                try:
                    subprocess.run(["git", "init"], cwd=self.project_dir, check=True)
                except Exception as e:
                    QMessageBox.warning(self, tr("error"), tr("git_init_failed").format(reason=e))
                    return

        # 显示进度对话框
        progress = QProgressDialog(
            tr("initializing"),
            None,
            0,
            100,
            self
        )
        progress.setWindowTitle(tr("init_ralph"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        init_done = False

        def init_callback(success):
            nonlocal init_done
            init_done = True
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_init_done(success, progress))

        # 获取 app 实例并调用初始化
        from .app import RalphApp
        app = QApplication.instance().property("ralph_app")
        if app:
            app.initialize_project(self.project_dir, init_callback)

        # 模拟进度条动画
        from PySide6.QtCore import QTimer
        self._init_timer = QTimer()
        self._init_timer.timeout.connect(lambda: self._update_init_progress(progress, init_done))
        self._init_timer.start(50)

    def _update_init_progress(self, progress, init_done):
        """更新初始化进度"""
        if init_done:
            self._init_timer.stop()
            return
        current = progress.value()
        if current < 90:
            progress.setValue(current + 10)

    def _on_init_done(self, success: bool, progress: QProgressDialog):
        """初始化完成"""
        progress.setValue(100)
        progress.close()

        if success:
            self._check_project_status(self.project_dir)
        else:
            QMessageBox.warning(
                self,
                tr("error"),
                tr("init_failed_reason").format(reason="初始化过程失败")
            )

    def _save_last_directory(self, dir_path: Path):
        """保存目录到历史记录"""
        from PySide6.QtCore import QSettings
        settings = QSettings("RalphGUI", "RalphGUI")

        # 保存最后使用的目录
        settings.setValue("last_project_directory", str(dir_path))

        # 更新历史目录
        dirs = settings.value("recent_directories", [])
        if isinstance(dirs, str):
            dirs = [dirs] if dirs else []

        dir_str = str(dir_path)
        if dir_str in dirs:
            dirs.remove(dir_str)
        dirs.insert(0, dir_str)
        dirs = dirs[:10]
        settings.setValue("recent_directories", dirs)

        self._populate_recent_combo()

    def _disable_controls(self):
        """禁用控制按钮"""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.reset_circuit_btn.setEnabled(False)

    def _enable_controls(self):
        """启用控制按钮"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.reset_circuit_btn.setEnabled(True)

    def on_project_changed(self, dir_path: Path):
        """项目切换时的回调"""
        self._check_project_status(dir_path)

    def _setup_menu(self):
        """设置菜单"""
        self.menuBar().setStyleSheet(f"""
            QMenuBar {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border-bottom: 1px solid {Colors.BORDER};
                padding: 4px;
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {Colors.BG_HOVER};
            }}
            QMenu {{
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.BG_HOVER};
            }}
        """)

        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu(tr("menu_file"))

        open_action = QAction(tr("open_project"), self)
        open_action.triggered.connect(self._show_startup_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction(tr("exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 设置菜单
        settings_menu = menubar.addMenu(tr("menu_settings"))
        self._settings_action = QAction(tr("settings_panel"), self)
        self._settings_action.triggered.connect(self._show_settings)
        settings_menu.addAction(self._settings_action)

        # 帮助菜单
        help_menu = menubar.addMenu(tr("menu_help"))
        about_action = QAction(tr("about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _connect_control_signals(self):
        """连接控制按钮信号"""
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self.pause_btn.clicked.connect(self._on_pause)
        self.reset_circuit_btn.clicked.connect(self._on_reset_circuit)

    def _restore_window_geometry(self):
        """恢复窗口几何尺寸"""
        settings = QSettings("RalphGUI", "RalphGUI")
        width = settings.value("window_width", 1200, type=int)
        height = settings.value("window_height", 800, type=int)
        x = settings.value("window_x", -1, type=int)
        y = settings.value("window_y", -1, type=int)

        # 应用大小
        self.resize(width, height)

        # 如果位置有效，则恢复位置；否则让窗口系统决定位置
        if x >= 0 and y >= 0:
            self.move(x, y)
            ui_logger.debug(f"Window geometry restored: {width}x{height} at ({x}, {y})")
        else:
            ui_logger.debug(f"Window size restored: {width}x{height} (position not saved)")

    def _save_window_geometry(self):
        """保存窗口几何尺寸"""
        settings = QSettings("RalphGUI", "RalphGUI")
        settings.setValue("window_width", self.width())
        settings.setValue("window_height", self.height())
        settings.setValue("window_x", self.x())
        settings.setValue("window_y", self.y())
        ui_logger.debug(f"Window geometry saved: {self.width()}x{self.height()} at ({self.x()}, {self.y()})")

    def _setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+O: 打开项目
        open_shortcut = QShortcut(Qt.CTRL | Qt.Key_O, self)
        open_shortcut.activated.connect(self._show_startup_dialog)

        # Ctrl+S: 保存设置
        save_shortcut = QShortcut(Qt.CTRL | Qt.Key_S, self)
        save_shortcut.activated.connect(self._save_settings)

        # F5: 开始/继续循环
        start_shortcut = QShortcut(Qt.Key_F5, self)
        start_shortcut.activated.connect(self._on_start)

        # Esc: 停止循环
        stop_shortcut = QShortcut(Qt.Key_Escape, self)
        stop_shortcut.activated.connect(self._on_stop)

    def _setup_system_tray(self):
        """设置系统托盘"""
        self._tray_icon = QSystemTrayIcon(self)

        # 创建托盘菜单
        tray_menu = QMenu(self)

        # 显示/隐藏窗口
        show_action = QAction(tr("show_window"), self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        # 开始循环
        start_action = QAction(tr("start_loop"), self)
        start_action.triggered.connect(self._on_start)
        tray_menu.addAction(start_action)

        # 停止循环
        stop_action = QAction(tr("stop_loop"), self)
        stop_action.triggered.connect(self._on_stop)
        tray_menu.addAction(stop_action)

        tray_menu.addSeparator()

        # 退出
        quit_action = QAction(tr("quit"), self)
        quit_action.triggered.connect(self._quit_application)
        tray_menu.addAction(quit_action)

        self._tray_icon.setContextMenu(tray_menu)

        # 双击显示窗口
        self._tray_icon.activated.connect(self._on_tray_activated)

        # 设置图标（使用默认 application图标）
        self._tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        self._tray_icon.show()
        ui_logger.debug("System tray initialized")

    def _on_tray_activated(self, reason):
        """托盘图标被激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()

    def _quit_application(self):
        """退出应用程序"""
        self._on_stop()
        QApplication.quit()

    def _send_notification(self, title: str, message: str, icon=QSystemTrayIcon.Information):
        """
        发送系统通知

        Args:
            title: 通知标题
            message: 通知内容
            icon: 通知图标 (Information, Warning, Critical, NoIcon)
        """
        if hasattr(self, '_tray_icon') and self._tray_icon.isVisible():
            self._tray_icon.showMessage(title, message, icon, 5000)

    def _save_settings(self):
        """保存设置"""
        if not self.settings_presenter:
            return
        current_settings = self.settings_presenter.load_settings()
        if self.settings_presenter.save_settings(current_settings):
            self.status_bar.showMessage(tr("settings_saved"))
        else:
            QMessageBox.warning(self, tr("error"), tr("settings_save_failed"))

    def _show_startup_dialog(self):
        """显示启动对话框"""
        dialog = StartupDialog(self)
        dialog.directory_selected.connect(self._on_directory_selected)
        dialog.init_requested.connect(self._on_init_requested)
        dialog.cancelled.connect(self._on_startup_cancelled)
        dialog.exec()

    def _on_directory_selected(self, dir_path: Path):
        """目录已选择"""
        self._load_project(dir_path)

    def _on_init_requested(self, dir_path: Path):
        """请求初始化

        注意: 通过"文件→打开项目"选择新项目时，如果需要初始化，
        当前实现会跳过初始化直接加载。这是已知限制。
        完整初始化应该通过应用首次启动时的启动对话框完成。
        """
        ui_logger.warning(f"Init requested but not fully supported via menu: {dir_path}")
        self._load_project(dir_path)

    def _on_startup_cancelled(self):
        """启动取消"""
        pass  # 对话框自己会关闭，不需要关闭主窗口

    def _load_project(self, dir_path: Path):
        """加载项目"""
        ui_logger.info(f"Loading project from: {dir_path}")
        self.project_dir = dir_path
        project_name = dir_path.name
        self.setWindowTitle(tr("app_title_with_project").format(project_name=project_name))
        self.status_bar.showMessage(tr("project_loaded"))
        self._append_log(tr("log_project_loaded").format(dir_path=dir_path))
        ui_logger.info(f"Project loaded: {project_name}")

    def _on_start(self):
        """开始按钮点击"""
        ui_logger.info("Start button clicked")
        if not self.project_dir:
            ui_logger.warning("No project selected, showing warning")
            QMessageBox.warning(self, tr("error"), tr("select_project_first"))
            return

        if not self.loop_presenter:
            ui_logger.warning("No loop_presenter set, project may not be initialized")
            QMessageBox.warning(
                self,
                tr("error"),
                tr("error_ralph_not_enabled")
            )
            return

        ui_logger.debug("Using loop_presenter to start loop")
        success = self.loop_presenter.start()
        if not success:
            ui_logger.error("Failed to start loop via presenter")
            QMessageBox.warning(self, tr("error"), tr("error_loop_start_failed"))
            return
        # 开始运行计时
        self._loop_start_time = datetime.now()
        self._paused_elapsed = 0
        self._run_timer.start(1000)  # 每秒更新
        self._run_time_label.setText("00:00:00")
        # 开始内存监控（每60秒检查一次）
        self._memory_timer.start(60000)
        # 记录新的内存基线
        self._memory_baseline_mb = get_process_memory_mb()
        ui_logger.info(f"Memory baseline reset to: {self._memory_baseline_mb:.1f} MB")
        # 发送通知
        self._send_notification(tr("notification_loop_started"), tr("notification_loop_started_msg"))

    def _on_stop(self):
        """停止按钮点击"""
        ui_logger.info("Stop button clicked")
        reply = QMessageBox.question(
            self,
            tr("confirm_stop"),
            tr("confirm_stop_message"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            ui_logger.debug("Stop cancelled by user")
            return

        ui_logger.debug("Stopping loop...")
        if self.loop_presenter:
            self.loop_presenter.stop()
        else:
            self.is_running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.status_bar.showMessage(tr("stopped"))
            self._append_log(tr("log_loop_stopped"))
        # 停止运行计时器
        self._run_timer.stop()
        self._loop_start_time = None
        self._paused_elapsed = 0
        self._run_time_label.setText("00:00:00")
        # 发送通知
        self._send_notification(tr("notification_loop_stopped"), tr("notification_loop_stopped_msg"))

    def _on_pause(self):
        """暂停按钮点击"""
        ui_logger.info("Pause button clicked")
        if self.loop_presenter:
            ui_logger.debug("Using loop_presenter to pause/resume loop")
            self.loop_presenter.pause()
        else:
            if self.is_running:
                self.is_running = False
                self.pause_btn.setText(tr("resume"))
                self.status_bar.showMessage(tr("paused"))
                self._append_log(tr("log_loop_paused"))
                ui_logger.info("Loop paused (fallback)")
                # 暂停时记录已累积时间并停止计时器
                if self._loop_start_time:
                    self._paused_elapsed += int((datetime.now() - self._loop_start_time).total_seconds() * 1000)
                self._run_timer.stop()
            else:
                self.is_running = True
                self.pause_btn.setText(tr("pause"))
                self.status_bar.showMessage(tr("running"))
                self._append_log(tr("log_loop_resumed"))
                ui_logger.info("Loop resumed (fallback)")
                # 继续时重新开始计时
                self._loop_start_time = datetime.now()
                self._run_timer.start(1000)

    def _on_reset_circuit(self):
        """重置回路"""
        ui_logger.info("Reset circuit button clicked")
        if self.loop_presenter:
            success = self.loop_presenter.reset_circuit()
            if not success:
                ui_logger.error("Failed to reset circuit via presenter")
                QMessageBox.warning(self, tr("error"), tr("error_circuit_reset_failed"))
        else:
            ui_logger.debug("No loop_presenter, logging circuit reset")
            self._append_log(tr("log_circuit_reset"))

    def _on_loop_status_change(self, status: dict):
        """循环状态变化回调 - 线程安全"""
        # 直接调用进行同步更新，确保实时性
        # 使用 copy() 避免引用问题
        self._do_update_status(status.copy())

    def _do_update_status(self, status: dict):
        """实际执行状态更新（必须在主线程调用）"""
        loop_count = status.get("loop_count", 0)
        is_running = status.get("is_running", False)
        ui_logger.info(f"Loop status changed: loop_count={loop_count}, is_running={is_running}")
        status_str = status.get("status", "unknown")
        is_running = status.get("is_running", False)
        is_paused = status.get("is_paused", False)

        self.is_running = is_running
        self.start_btn.setEnabled(not is_running and not is_paused)
        self.stop_btn.setEnabled(is_running or is_paused)
        self.pause_btn.setEnabled(is_running or is_paused)

        if is_paused:
            self.pause_btn.setText(tr("resume"))
        else:
            self.pause_btn.setText(tr("pause"))

        self.status_bar.showMessage(status_str)
        self._update_status_cards(status)

    def _update_status_cards(self, status: dict):
        """更新状态卡片"""
        # 回路状态 - 使用发光效果
        circuit_state = status.get("circuit_state", "CLOSED")
        self.circuit_state_label.setText(circuit_state)
        self.circuit_state_label.setStyleSheet(get_circuit_state_style(circuit_state))

        # 运行状态指示
        is_running = status.get("is_running", False)
        is_paused = status.get("is_paused", False)
        if is_running:
            self.run_indicator.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.SUCCESS};
                    font-size: 14px;
                }}
            """)
            self.run_status_label.setText(tr("running"))
        elif is_paused:
            self.run_indicator.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.WARNING};
                    font-size: 14px;
                }}
            """)
            self.run_status_label.setText(tr("paused"))
        else:
            self.run_indicator.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.TEXT_MUTED};
                    font-size: 14px;
                }}
            """)
            self.run_status_label.setText(tr("stopped"))

        # 循环计数
        loop_count = status.get("loop_count", 0)
        self.loop_count_label.setText(str(loop_count))

        # API调用配额
        calls_made = status.get("calls_made", 0)
        max_calls = status.get("max_calls", 100)
        self.api_calls_label.setText(f"{calls_made}/{max_calls}" if max_calls > 0 else str(calls_made))
        # 更新进度条
        if max_calls > 0:
            percentage = min(int(calls_made / max_calls * 100), 100)
            self.api_progress.setValue(percentage)
        else:
            self.api_progress.setValue(0)

    def _on_loop_log_line(self, line: str):
        """循环日志行回调 - 线程安全"""
        ui_logger.debug(f"_on_loop_log_line called with: {line[:50]}...")
        # 使用 Qt 信号跨线程发射日志 - 信号会自动在主线程调用槽函数
        self.log_line_signal.emit(line)

    def _do_append_log(self, message: str):
        """实际追加日志（必须在主线程调用）"""
        ui_logger.debug(f"_do_append_log called with: {message[:50]}...")
        self.status_bar.showMessage(f"收到日志: {message[:30]}...")
        try:
            display_message = message

            # 如果是 JSON 格式，提取 result 字段并格式化
            if message.strip().startswith('{'):
                try:
                    parsed = json.loads(message)
                    # 提取关键字段
                    result = parsed.get('result', '')
                    status = parsed.get('status', '')
                    subtype = parsed.get('subtype', '')
                    duration = parsed.get('duration_ms', 0)
                    num_turns = parsed.get('num_turns', 0)

                    # 构建易读的输出
                    lines = []
                    lines.append("=" * 50)
                    if subtype:
                        lines.append(f"类型: {subtype}")
                    if status:
                        lines.append(f"状态: {status}")
                    if duration:
                        lines.append(f"耗时: {duration/1000:.1f}秒")
                    if num_turns:
                        lines.append(f"轮次: {num_turns}")
                    if result:
                        lines.append("")
                        lines.append("【结果】")
                        lines.append(result)
                    lines.append("=" * 50)

                    display_message = "\n".join(lines)
                except json.JSONDecodeError:
                    pass  # 不是有效 JSON，保持原样

            # 追加到 Claude 输出面板
            self.claude_output_viewer.append(display_message)
            # 自动滚动到底部
            scrollbar = self.claude_output_viewer.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            ui_logger.error(f"Failed to append log to viewer: {e}", exc_info=True)

    def _save_log_to_file(self, message: str, is_claude_output: bool):
        """保存日志到文件"""
        if not self.project_dir:
            return
        try:
            log_dir = self.project_dir / ".ralph" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            if is_claude_output:
                # Claude 输出保存到 claude_output.jsonl
                log_file = log_dir / "claude_output.jsonl"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
            else:
                # 其他日志保存到 gui_log.txt
                log_file = log_dir / "gui_log.txt"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            ui_logger.error(f"Failed to save log to file: {e}", exc_info=True)

    def _on_loop_error(self, error: str):
        """循环错误回调 - 线程安全"""
        QTimer.singleShot(0, lambda: self._do_show_error(error))

    def _do_show_error(self, error: str):
        """实际显示错误（必须在主线程调用）"""
        ui_logger.error(f"Loop error: {error}")
        self._append_log(f"Error: {error}")
        QMessageBox.warning(self, tr("error"), error)
        self._send_notification(tr("notification_error"), error, QSystemTrayIcon.Critical)

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            tr("about"),
            tr("about_text").format(version="0.1.0")
        )

    def _append_log(self, message: str):
        """追加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"

        # 根据消息类型设置颜色
        if message.startswith("Error:"):
            color = "#F7768E"  # 错误 - 红色
        elif "WARNING" in message or "警告" in message:
            color = "#FF9E64"  # 警告 - 橙色
        elif "INFO" in message:
            color = "#9ECE6A"  # 信息 - 绿色
        else:
            color = "#A9B1D6"  # 默认 - 浅灰紫色

        self.log_viewer.append(f'<span style="color: {color};">{formatted}</span>')

        # 自动滚动到底部
        scrollbar = self.log_viewer.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        ui_logger.debug(f"Log appended to UI: {message[:50]}...")

    def _clear_both_logs(self):
        """清空两个日志面板"""
        self.log_viewer.clear()
        self.claude_output_viewer.clear()

    def _run_project_diagnosis(self):
        """运行项目诊断，结果输出到日志面板"""
        if not self.project_dir:
            self._append_log("❌ 请先选择项目目录")
            return
        
        ui_logger.info(f"Running project diagnosis for: {self.project_dir}")
        self._append_log("=" * 50)
        self._append_log("🔍 开始项目诊断...")
        
        # 导入 ConfigService 进行诊断（统一入口）
        from .services.config_service import ConfigService
        
        # 运行诊断
        result = ConfigService.diagnose_project(self.project_dir)
        
        # 直接输出到日志面板
        self._append_diagnostic_to_log(result)

    def _append_diagnostic_to_log(self, result: dict):
        """将诊断结果输出到日志面板"""
        self._append_log(f"📁 项目: {result['project_dir']}")
        
        # 关键状态
        self._append_log("【关键检查】")
        check_names = {
            'project_dir_exists': '项目目录',
            'project_dir_writable': '目录权限',
            'ralph_dir_exists': '.ralph目录',
            'config_file_exists': '.ralphrc配置',
        }
        for key, name in check_names.items():
            if key in result['checks']:
                status = "✅" if result['checks'][key] else "❌"
                self._append_log(f"  {status} {name}")
        
        # 文件状态
        if result['ralph_dir']:
            self._append_log("【关键文件】")
            key_files = ['PROMPT.md', 'AGENT.md', 'status.json']
            for filename in key_files:
                if filename in result['ralph_dir']:
                    info = result['ralph_dir'][filename]
                    if info.get('exists'):
                        self._append_log(f"  ✅ {filename} ({info.get('size', 0)} bytes)")
                    else:
                        self._append_log(f"  ❌ {filename} (缺失)")
        
        # 建议
        if result['recommendations']:
            self._append_log("【建议】")
            for rec in result['recommendations'][:3]:
                self._append_log(f"  • {rec}")
        
        # 总结
        passed = sum(1 for v in result['checks'].values() if v)
        total = len(result['checks'])
        self._append_log(f"【结果】{passed}/{total} 项检查通过")
        
        if passed == total:
            self._append_log("✅ 项目配置正常，可以启动循环")
        elif passed >= total * 0.7:
            self._append_log("⚠️ 项目基本可用，建议完善配置")
        else:
            self._append_log("❌ 项目配置有问题，请先运行启用向导")
        
        self._append_log("=" * 50)
        ui_logger.info(f"Project diagnosis complete: {passed}/{total} checks passed")

    def _export_logs(self):
        """导出日志到文件"""
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime
        
        # 选择保存位置
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"ralph_logs_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("export_logs"),
            default_name,
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Ralph GUI 日志导出\n")
                f.write(f"时间: {datetime.now().isoformat()}\n")
                f.write(f"项目: {self.project_dir}\n")
                f.write("=" * 60 + "\n\n")
                
                f.write("【应用日志】\n")
                f.write(self.log_viewer.toPlainText())
                f.write("\n\n" + "=" * 60 + "\n\n")
                
                f.write("【Claude 输出】\n")
                f.write(self.claude_output_viewer.toPlainText())
            
            ui_logger.info(f"Logs exported to: {file_path}")
            QMessageBox.information(self, tr("export_success"), tr("log_export_success").format(path=file_path))
        except Exception as e:
            ui_logger.error(f"Failed to export logs: {e}", exc_info=True)
            QMessageBox.warning(self, tr("export_failed"), tr("log_export_failed").format(error=str(e)))

    def _update_run_time(self):
        """更新运行时间显示"""
        if self._loop_start_time is None:
            return
        from datetime import timedelta
        elapsed = datetime.now() - self._loop_start_time + timedelta(milliseconds=self._paused_elapsed)
        total_seconds = int(elapsed.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self._run_time_label.setText(time_str)

    def _update_memory_display(self):
        """更新内存使用显示"""
        if hasattr(self, 'memory_label'):
            current_memory = get_process_memory_mb()
            if current_memory > 0:
                self.memory_label.setText(f"{current_memory:.0f} MB")

    def _check_memory_leak(self):
        """
        检查内存泄漏

        验证标准: 内存增长超过 100MB → 警告
        """
        current_memory = get_process_memory_mb()
        if current_memory <= 0:
            return  # 获取内存失败，跳过检查

        memory_increase = current_memory - self._memory_baseline_mb

        # 检查是否超过 100MB 增长阈值
        if memory_increase > 100:
            warning_msg = f"⚠️ 内存增长警告: 当前 {current_memory:.1f} MB（基线 {self._memory_baseline_mb:.1f} MB），增长 {memory_increase:.1f} MB"
            ui_logger.warning(warning_msg)
            self._append_log(warning_msg)

    def closeEvent(self, event):
        """关闭事件"""
        ui_logger.info("Close event triggered")
        if self.is_running:
            ui_logger.debug("Loop is running, asking for confirmation")
            reply = QMessageBox.question(
                self,
                tr("confirm_exit"),
                tr("confirm_exit_message"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                ui_logger.debug("Exit cancelled by user")
                event.ignore()
                return

        # 停止后台进程和线程
        if self.loop_presenter:
            ui_logger.debug("Stopping loop presenter...")
            self.loop_presenter.stop()

        # 保存窗口几何尺寸
        self._save_window_geometry()
        # 隐藏托盘图标
        if hasattr(self, '_tray_icon'):
            self._tray_icon.hide()
        ui_logger.info("Application closing")
        event.accept()

    def changeEvent(self, event):
        """窗口状态改变事件（最小化、恢复等）"""
        if event.type() == event.Type.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                # 最小化到系统托盘
                self.hide()
                if hasattr(self, '_tray_icon') and self._tray_icon.isVisible():
                    self._tray_icon.showMessage(
                        tr("app_title"),
                        tr("minimized_to_tray"),
                        QSystemTrayIcon.Information,
                        3000
                    )
        super().changeEvent(event)

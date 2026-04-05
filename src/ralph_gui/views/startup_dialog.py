"""
启动对话框 - Midnight Studio
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QMessageBox,
    QProgressDialog, QFrame, QComboBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QSettings

# 历史目录相关常量
MAX_RECENT_DIRECTORIES = 10
RECENT_DIRECTORIES_KEY = "recent_directories"
from ..i18n import tr
from .theme import (
    BUTTON_PRIMARY_STYLE, BUTTON_SECONDARY_STYLE,
    LINE_EDIT_STYLE, GLASS_CARD_STYLE,
    Colors, FONT_MONO
)


class StartupDialog(QDialog):
    """启动对话框 - 深色主题"""

    directory_selected = Signal(Path)
    init_requested = Signal(Path)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("select_project_directory"))
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_BASE};
            }}
        """)
        self._setup_ui()
        self._check_prerequisites()
        self.startup_presenter = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # 标题
        title_label = QLabel("RALPH")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.PRIMARY};
                font-size: 28px;
                font-weight: bold;
                font-family: {FONT_MONO};
                letter-spacing: 6px;
            }}
        """)
        layout.addWidget(title_label)

        subtitle_label = QLabel(tr("app_title"))
        subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 14px;
            }}
        """)
        layout.addWidget(subtitle_label)

        layout.addSpacing(16)

        # 说明标签
        self.instruction_label = QLabel(tr("select_directory_instruction"))
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 14px;
                line-height: 1.6;
            }}
        """)
        layout.addWidget(self.instruction_label)

        layout.addSpacing(8)

        # 历史目录选择区域
        recent_container = QFrame()
        recent_container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                padding: 4px;
            }}
        """)
        recent_layout = QVBoxLayout(recent_container)
        recent_layout.setContentsMargins(12, 10, 12, 10)
        recent_layout.setSpacing(8)

        # 历史目录标签
        recent_label = QLabel(tr("recent_directories"))
        recent_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
            }}
        """)
        recent_layout.addWidget(recent_label)

        # 历史目录下拉列表
        self.recent_combo = QComboBox()
        self.recent_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {Colors.BORDER_HOVER};
            }}
            QComboBox::dropDown {{
                border: none;
                width: 30px;
            }}
            QComboBox::downArrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {Colors.TEXT_SECONDARY};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                selection-background-color: {Colors.BG_HOVER};
                padding: 4px;
            }}
        """)
        self.recent_combo.setMinimumHeight(36)
        self._populate_recent_combo()
        self.recent_combo.currentIndexChanged.connect(self._on_recent_directory_selected)
        recent_layout.addWidget(self.recent_combo)

        # 清除历史按钮
        clear_btn = QPushButton(tr("clear_history"))
        clear_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._on_clear_history)
        recent_layout.addWidget(clear_btn)

        layout.addWidget(recent_container)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"QFrame {{ border: none; border-top: 1px solid {Colors.BORDER}; margin: 8px 0; }}")
        layout.addWidget(separator)

        # 目录输入框 + 浏览按钮
        dir_container = QFrame()
        dir_container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                padding: 4px;
            }}
        """)
        dir_layout = QHBoxLayout(dir_container)
        dir_layout.setContentsMargins(8, 8, 8, 8)
        dir_layout.setSpacing(12)

        self.dir_input = QLineEdit()
        self.dir_input.setStyleSheet(LINE_EDIT_STYLE)
        self.dir_input.setPlaceholderText(tr("select_project_directory"))
        dir_layout.addWidget(self.dir_input, 1)

        self.browse_btn = QPushButton(tr("browse"))
        self.browse_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(self.browse_btn)

        layout.addWidget(dir_container)

        layout.addStretch()

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.confirm_btn = QPushButton(tr("confirm"))
        self.confirm_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.clicked.connect(self._on_confirm)
        self.confirm_btn.setDefault(True)
        btn_layout.addWidget(self.confirm_btn)

        self.cancel_btn = QPushButton(tr("cancel"))
        self.cancel_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _check_prerequisites(self):
        """检查系统前提条件"""
        pass

    def _browse_directory(self):
        """浏览目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            tr("select_project_directory"),
            self.dir_input.text() or str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self.dir_input.setText(dir_path)
            self._save_recent_directory(Path(dir_path))
            self._populate_recent_combo()

    def _on_confirm(self):
        """确认选择目录"""
        dir_text = self.dir_input.text().strip()
        if not dir_text:
            QMessageBox.warning(self, tr("error"), tr("directory_not_found"))
            return

        dir_path = Path(dir_text)
        if not dir_path.exists():
            QMessageBox.warning(self, tr("error"), tr("directory_does_not_exist"))
            return

        # 检查是否是 git 仓库
        if not (dir_path / ".git").exists():
            reply = QMessageBox.question(
                self,
                tr("init_ralph"),
                tr("not_git_repo_prompt"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # 初始化 git
            import subprocess
            try:
                subprocess.run(["git", "init"], cwd=dir_path, check=True)
            except Exception as e:
                QMessageBox.warning(self, tr("error"), tr("git_init_failed").format(reason=e))
                return

        # 保存到历史目录
        self._save_recent_directory(dir_path)

        # 检查 .ralph 目录是否存在
        ralph_dir = dir_path / ".ralph"
        if ralph_dir.exists():
            # 项目已启用，直接发送信号
            self.directory_selected.emit(dir_path)
            self.accept()
        else:
            # 需要初始化
            self._show_init_dialog(dir_path)

    def _show_init_dialog(self, dir_path: Path):
        """显示初始化确认对话框"""
        reply = QMessageBox.question(
            self,
            tr("init_ralph"),
            tr("init_ralph_prompt"),
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.init_requested.emit(dir_path)
        else:
            self.cancelled.emit()
            self.reject()

    def _show_init_progress(self, dir_path: Path, presenter):
        """显示初始化进度"""
        self.startup_presenter = presenter

        self.progress = QProgressDialog(
            tr("initializing"),
            None,
            0,
            100,
            self
        )
        self.progress.setWindowTitle(tr("init_ralph"))
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.show()

        # 使用回调方式执行初始化
        self._init_callback_done = False

        def init_callback(success):
            self._init_callback_done = True
            # 在主线程中处理结果
            QTimer.singleShot(0, lambda: self._on_init_done(dir_path, success))

        self.startup_presenter.initialize_project(
            dir_path,
            non_interactive=True,
            callback=init_callback
        )

        # 模拟进度条动画
        self._init_timer = QTimer()
        self._init_timer.timeout.connect(self._update_progress)
        self._init_timer.start(50)

    def _update_progress(self):
        """更新进度条"""
        if self._init_callback_done:
            return  # 等待回调

        current = self.progress.value()
        if current < 90:
            self.progress.setValue(current + 10)

    def _on_init_done(self, dir_path: Path, success: bool):
        """初始化完成回调"""
        self._init_timer.stop()
        self.progress.setValue(100)
        self.progress.close()

        if success:
            self.directory_selected.emit(dir_path)
            self.accept()
        else:
            QMessageBox.warning(
                self,
                tr("error"),
                tr("init_failed_reason").format(reason="初始化过程失败")
            )
            self.reject()

    def _on_cancel(self):
        """取消"""
        self.cancelled.emit()
        self.reject()

    def _get_recent_directories(self) -> list:
        """从 QSettings 读取历史目录（过滤不存在的目录）"""
        settings = QSettings("RalphGUI", "RalphGUI")
        dirs = settings.value(RECENT_DIRECTORIES_KEY, [])
        if isinstance(dirs, str):
            dirs = [dirs] if dirs else []
        # 过滤掉不存在的目录
        return [d for d in dirs if Path(d).exists()]

    def _save_recent_directory(self, dir_path: Path) -> None:
        """保存目录到历史记录"""
        settings = QSettings("RalphGUI", "RalphGUI")
        dirs = self._get_recent_directories()

        # 移除已存在的相同目录（如果存在）
        dir_str = str(dir_path)
        if dir_str in dirs:
            dirs.remove(dir_str)

        # 添加到最前面
        dirs.insert(0, dir_str)

        # 限制数量
        dirs = dirs[:MAX_RECENT_DIRECTORIES]

        settings.setValue(RECENT_DIRECTORIES_KEY, dirs)

    def _clear_recent_directories(self) -> None:
        """清除历史记录"""
        settings = QSettings("RalphGUI", "RalphGUI")
        settings.remove(RECENT_DIRECTORIES_KEY)

    def _populate_recent_combo(self) -> None:
        """填充历史目录下拉列表"""
        self.recent_combo.blockSignals(True)
        self.recent_combo.clear()

        dirs = self._get_recent_directories()
        if dirs:
            # 显示目录简称（取最后一级路径）
            for d in dirs:
                name = Path(d).name
                parent = Path(d).parent.name
                display = f"{parent}/{name}" if len(parent) > 0 else name
                self.recent_combo.addItem(display, d)  # userData 存储完整路径
            self.recent_combo.setCurrentIndex(-1)  # 不选中任何项
        else:
            self.recent_combo.addItem(tr("no_recent_directories"), "")

        self.recent_combo.blockSignals(False)

    def _on_recent_directory_selected(self, index: int) -> None:
        """从历史列表选择目录"""
        if index < 0:
            return
        dir_path = self.recent_combo.currentData()
        if dir_path:
            self.dir_input.setText(dir_path)

    def _on_clear_history(self) -> None:
        """清除历史记录"""
        reply = QMessageBox.question(
            self,
            tr("clear_history"),
            tr("clear_history_confirm"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._clear_recent_directories()
            self._populate_recent_combo()

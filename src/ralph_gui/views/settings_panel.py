"""
设置面板组件 - Midnight Studio
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QCheckBox,
    QPushButton, QScrollArea, QFormLayout,
    QGroupBox, QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QTimer
from ..i18n import tr
from .theme import (
    BUTTON_PRIMARY_STYLE, BUTTON_SECONDARY_STYLE,
    LINE_EDIT_STYLE, SPIN_BOX_STYLE, GROUP_BOX_STYLE,
    Colors, FONT_MONO
)


class SettingsPanel(QWidget):
    """设置面板组件 - 深色主题"""

    settings_saved = Signal(dict)
    settings_reset = Signal()

    def __init__(self, presenter, parent=None):
        super().__init__(parent)
        self.presenter = presenter
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_BASE};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # 标题
        title_label = QLabel(tr("settings_panel"))
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 20px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(title_label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumSize(0, 300)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {Colors.BG_SURFACE};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle {{
                background-color: {Colors.BORDER};
                border-radius: 4px;
            }}
        """)

        content = QWidget()
        content.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
        """)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 循环设置组
        loop_group = QFrame()
        loop_group.setStyleSheet(GROUP_BOX_STYLE)
        loop_group.setMinimumHeight(160)
        loop_layout = QFormLayout(loop_group)
        loop_layout.setLabelAlignment(Qt.AlignLeft)
        loop_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        loop_layout.setSpacing(16)
        loop_layout.setHorizontalSpacing(20)
        loop_layout.setFieldGrowthPolicy(QFormLayout.FieldStaysLabeledAtEnd)

        self.max_calls_spin = QSpinBox()
        self.max_calls_spin.setRange(1, 1000)
        self.max_calls_spin.setSuffix(tr("suffix_calls_per_hour"))
        self.max_calls_spin.setStyleSheet(SPIN_BOX_STYLE)
        self.max_calls_spin.setMinimumWidth(120)
        loop_layout.addRow(tr("max_calls_per_hour"), self.max_calls_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(0, 1000000)
        self.max_tokens_spin.setSuffix(tr("suffix_tokens_per_hour"))
        self.max_tokens_spin.setSpecialValueText(tr("unlimited"))
        self.max_tokens_spin.setStyleSheet(SPIN_BOX_STYLE)
        self.max_tokens_spin.setMinimumWidth(120)
        loop_layout.addRow(tr("max_tokens_per_hour"), self.max_tokens_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setSuffix(tr("suffix_minutes"))
        self.timeout_spin.setStyleSheet(SPIN_BOX_STYLE)
        self.timeout_spin.setMinimumWidth(120)
        loop_layout.addRow(tr("timeout_minutes"), self.timeout_spin)

        content_layout.addWidget(loop_group)

        # 会话设置组
        session_group = QFrame()
        session_group.setStyleSheet(GROUP_BOX_STYLE)
        session_group.setMinimumHeight(100)
        session_layout = QFormLayout(session_group)
        session_layout.setLabelAlignment(Qt.AlignLeft)
        session_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        session_layout.setSpacing(16)
        session_layout.setHorizontalSpacing(20)
        session_layout.setFieldGrowthPolicy(QFormLayout.FieldStaysLabeledAtEnd)

        self.session_continuity_check = QCheckBox()
        self.session_continuity_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        session_layout.addRow(tr("session_continuity"), self.session_continuity_check)

        self.session_expiry_spin = QSpinBox()
        self.session_expiry_spin.setRange(1, 168)
        self.session_expiry_spin.setSuffix(tr("suffix_hours"))
        self.session_expiry_spin.setStyleSheet(SPIN_BOX_STYLE)
        self.session_expiry_spin.setMinimumWidth(120)
        session_layout.addRow(tr("session_expiry_hours"), self.session_expiry_spin)

        content_layout.addWidget(session_group)

        # 危险选项组
        danger_group = QFrame()
        danger_group.setStyleSheet(GROUP_BOX_STYLE)
        danger_group.setMinimumHeight(60)
        danger_layout = QFormLayout(danger_group)
        danger_layout.setLabelAlignment(Qt.AlignLeft)
        danger_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        danger_layout.setSpacing(16)
        danger_layout.setHorizontalSpacing(20)
        danger_layout.setFieldGrowthPolicy(QFormLayout.FieldStaysLabeledAtEnd)

        self.skip_permissions_check = QCheckBox()
        self.skip_permissions_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        danger_layout.addRow(tr("dangerously_skip_permissions"), self.skip_permissions_check)

        content_layout.addWidget(danger_group)

        # 回路设置组
        circuit_group = QFrame()
        circuit_group.setStyleSheet(GROUP_BOX_STYLE)
        circuit_group.setMinimumHeight(140)
        circuit_layout = QFormLayout(circuit_group)
        circuit_layout.setLabelAlignment(Qt.AlignLeft)
        circuit_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        circuit_layout.setSpacing(16)
        circuit_layout.setHorizontalSpacing(20)
        circuit_layout.setFieldGrowthPolicy(QFormLayout.FieldStaysLabeledAtEnd)

        self.no_progress_spin = QSpinBox()
        self.no_progress_spin.setRange(1, 10)
        self.no_progress_spin.setStyleSheet(SPIN_BOX_STYLE)
        self.no_progress_spin.setMinimumWidth(120)
        circuit_layout.addRow(tr("no_progress_threshold"), self.no_progress_spin)

        self.same_error_spin = QSpinBox()
        self.same_error_spin.setRange(1, 20)
        self.same_error_spin.setStyleSheet(SPIN_BOX_STYLE)
        self.same_error_spin.setMinimumWidth(120)
        circuit_layout.addRow(tr("same_error_threshold"), self.same_error_spin)

        self.auto_reset_check = QCheckBox()
        self.auto_reset_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        circuit_layout.addRow(tr("cb_auto_reset"), self.auto_reset_check)

        content_layout.addWidget(circuit_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton(tr("save_settings"))
        self.save_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton(tr("reset_to_defaults"))
        self.reset_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(self.reset_btn)

        layout.addLayout(btn_layout)

    def _load_settings(self):
        """加载设置"""
        self.max_calls_spin.setValue(self.presenter.get_setting("MAX_CALLS_PER_HOUR", 100))
        self.max_tokens_spin.setValue(self.presenter.get_setting("MAX_TOKENS_PER_HOUR", 0))
        self.timeout_spin.setValue(self.presenter.get_setting("CLAUDE_TIMEOUT_MINUTES", 15))
        self.session_continuity_check.setChecked(self.presenter.get_setting("SESSION_CONTINUITY", True))
        self.session_expiry_spin.setValue(self.presenter.get_setting("SESSION_EXPIRY_HOURS", 24))
        self.no_progress_spin.setValue(self.presenter.get_setting("CB_NO_PROGRESS_THRESHOLD", 3))
        self.same_error_spin.setValue(self.presenter.get_setting("CB_SAME_ERROR_THRESHOLD", 5))
        self.auto_reset_check.setChecked(self.presenter.get_setting("CB_AUTO_RESET", False))
        skip_perms = self.presenter.get_setting("DANGEROUSLY_SKIP_PERMISSIONS", False)
        if isinstance(skip_perms, str):
            skip_perms = skip_perms.lower() == "true"
        self.skip_permissions_check.setChecked(skip_perms)

    def _on_save(self):
        """保存按钮点击"""
        settings = {
            "MAX_CALLS_PER_HOUR": self.max_calls_spin.value(),
            "MAX_TOKENS_PER_HOUR": self.max_tokens_spin.value(),
            "CLAUDE_TIMEOUT_MINUTES": self.timeout_spin.value(),
            "SESSION_CONTINUITY": str(self.session_continuity_check.isChecked()).lower(),
            "SESSION_EXPIRY_HOURS": self.session_expiry_spin.value(),
            "CB_NO_PROGRESS_THRESHOLD": self.no_progress_spin.value(),
            "CB_SAME_ERROR_THRESHOLD": self.same_error_spin.value(),
            "CB_AUTO_RESET": str(self.auto_reset_check.isChecked()).lower(),
            "DANGEROUSLY_SKIP_PERMISSIONS": str(self.skip_permissions_check.isChecked()).lower(),
        }

        if self.presenter.save_settings(settings):
            # 保存成功：按钮变红显示反馈
            original_style = self.save_btn.styleSheet()
            self.save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            self.save_btn.setText("已保存")
            # 1秒后恢复原样式
            QTimer.singleShot(1000, lambda: self._restore_save_button(original_style))
            self.settings_saved.emit(settings)
        else:
            # 保存失败：按钮变橙色
            original_style = self.save_btn.styleSheet()
            self.save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e67e22;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d35400;
                }
            """)
            self.save_btn.setText("保存失败")
            QTimer.singleShot(1000, lambda: self._restore_save_button(original_style))
            QMessageBox.warning(self, tr("error"), tr("settings_save_failed"))

    def _restore_save_button(self, original_style: str):
        """恢复保存按钮原样式"""
        self.save_btn.setStyleSheet(original_style)
        self.save_btn.setText(tr("save_settings"))

    def _on_reset(self):
        """重置按钮点击"""
        reply = QMessageBox.question(
            self,
            tr("confirm_reset"),
            tr("confirm_reset_message"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.presenter.reset_to_defaults():
                self._load_settings()
                self.settings_reset.emit()
                QMessageBox.information(self, tr("reset_success"), tr("reset_success"))

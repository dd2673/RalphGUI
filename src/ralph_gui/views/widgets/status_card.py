"""
通用状态卡片组件
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from ..theme import Colors


class StatusCard(QWidget):
    """通用状态卡片组件"""

    def __init__(
        self,
        title: str,
        value: str = "",
        description: str = "",
        value_color: str = None,
        parent=None
    ):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._description = description
        self._value_color = value_color
        self._setup_ui()
        self._update()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 16px;
                min-width: 120px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 12px;
        """)
        layout.addWidget(self.title_label)

        self.value_label = QLabel(self._value)
        self.value_label.setObjectName("value")
        value_style = f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: bold;
        """
        if self._value_color:
            value_style = value_style.replace(Colors.TEXT_PRIMARY, self._value_color)
        self.value_label.setStyleSheet(value_style)
        layout.addWidget(self.value_label)

        if self._description:
            self.desc_label = QLabel(self._description)
            self.desc_label.setStyleSheet(f"""
                color: {Colors.TEXT_MUTED};
                font-size: 11px;
            """)
            layout.addWidget(self.desc_label)

        layout.addStretch()

    def _update(self):
        """更新显示"""
        self.title_label.setText(self._title)
        self.value_label.setText(self._value)
        if hasattr(self, 'desc_label'):
            self.desc_label.setText(self._description)

    def set_value(self, value: str):
        """设置值"""
        self._value = value
        self.value_label.setText(value)

    def set_value_color(self, color: str):
        """设置值颜色"""
        self._value_color = color
        self.value_label.setStyleSheet(f"""
            color: {color};
            font-size: 28px;
            font-weight: bold;
        """)

    def set_description(self, description: str):
        """设置描述"""
        self._description = description
        if hasattr(self, 'desc_label'):
            self.desc_label.setText(description)

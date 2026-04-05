"""
指标显示组件
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

from ..theme import Colors


class MetricDisplay(QWidget):
    """指标显示组件"""

    def __init__(
        self,
        label: str = "",
        value: str = "",
        unit: str = "",
        parent=None
    ):
        super().__init__(parent)
        self._label = label
        self._value = value
        self._unit = unit
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label_widget = QLabel(self._label)
        self.label_widget.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 11px;
        """)
        layout.addWidget(self.label_widget)

        value_layout = QHBoxLayout()
        value_layout.setContentsMargins(0, 0, 0, 0)

        self.value_widget = QLabel(self._value)
        self.value_widget.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: bold;
        """)
        value_layout.addWidget(self.value_widget)

        if self._unit:
            self.unit_widget = QLabel(self._unit)
            self.unit_widget.setStyleSheet(f"""
                color: {Colors.TEXT_MUTED};
                font-size: 12px;
            """)
            value_layout.addWidget(self.unit_widget)

        value_layout.addStretch()
        layout.addLayout(value_layout)

    def set_label(self, label: str):
        """设置标签"""
        self._label = label
        self.label_widget.setText(label)

    def set_value(self, value: str):
        """设置值"""
        self._value = value
        self.value_widget.setText(value)

    def set_unit(self, unit: str):
        """设置单位"""
        self._unit = unit
        if hasattr(self, 'unit_widget'):
            self.unit_widget.setText(unit)

    def set_value_color(self, color: str):
        """设置值颜色"""
        self.value_widget.setStyleSheet(f"""
            color: {color};
            font-size: 18px;
            font-weight: bold;
        """)

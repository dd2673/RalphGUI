"""
主题和样式定义 - Midnight Studio
深色科技风格主题 - 霓虹青 + 紫色强调
"""
from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtCore import Qt


# 字体定义
FONT_FAMILY = "Segoe UI, SF Pro Display, -apple-system, sans-serif"
FONT_MONO = "JetBrains Mono, Consolas, Monaco, monospace"


# 颜色定义
class Colors:
    """Midnight Studio 颜色调色板"""

    # === 背景色 (Layered dark theme) ===
    BG_BASE = "#0D1117"           # 最深层背景 - 窗口
    BG_SURFACE = "#161B22"        # 卡片/面板背景
    BG_ELEVATED = "#1C2128"       # 悬浮元素背景
    BG_HOVER = "#21262D"          # 悬停状态

    # === 主强调色 (Cyan/Teal) ===
    PRIMARY = "#00D9FF"            # 主色 - 霓虹青
    PRIMARY_HOVER = "#33E1FF"     # 主色悬停
    PRIMARY_PRESSED = "#00B8D9"   # 主色按下
    PRIMARY_GLOW = "rgba(0, 217, 255, 0.3)"  # 发光效果

    # === 次强调色 (Purple) ===
    SECONDARY = "#A855F7"         # 紫色
    SECONDARY_HOVER = "#C084FC"   # 紫色悬停
    SECONDARY_GLOW = "rgba(168, 85, 247, 0.3)"

    # === 状态色 ===
    SUCCESS = "#10B981"           # 翡翠绿
    SUCCESS_GLOW = "rgba(16, 185, 129, 0.4)"
    WARNING = "#F59E0B"           # 琥珀色
    WARNING_GLOW = "rgba(245, 158, 11, 0.4)"
    ERROR = "#EF4444"             # 红色
    ERROR_GLOW = "rgba(239, 68, 68, 0.4)"
    INFO = "#3B82F6"              # 蓝色

    # === 回路状态色 ===
    CIRCUIT_CLOSED = "#10B981"     # 正常 - 绿色
    CIRCUIT_HALF_OPEN = "#F59E0B"  # 监控中 - 琥珀
    CIRCUIT_OPEN = "#EF4444"       # 已触发 - 红色

    # === 文字色 ===
    TEXT_PRIMARY = "#E6EDF3"       # 主要文字
    TEXT_SECONDARY = "#8B949E"     # 次要文字
    TEXT_DISABLED = "#484F58"      # 禁用文字
    TEXT_MUTED = "#6E7681"        # 弱化文字

    # === 边框色 ===
    BORDER = "#30363D"            # 默认边框
    BORDER_HOVER = "#484F58"      # 悬停边框
    BORDER_FOCUS = "#00D9FF"      # 聚焦边框 (cyan)

    # === 渐变定义 ===
    GRADIENT_PRIMARY = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00D9FF, stop:1 #A855F7)"

    # === 阴影色 ===
    SHADOW_COLOR = "rgba(0, 0, 0, 0.5)"
    GLOW_PRIMARY = "0 0 20px rgba(0, 217, 255, 0.3)"
    GLOW_SECONDARY = "0 0 20px rgba(168, 85, 247, 0.3)"


# === 基础样式 ===
BASE_STYLE = f"""
QWidget {{
    background-color: {Colors.BG_BASE};
    color: {Colors.TEXT_PRIMARY};
    font-family: "{FONT_FAMILY}";
    font-size: 14px;
}}
"""


WINDOW_STYLE = f"""
QMainWindow {{
    background-color: {Colors.BG_BASE};
}}
"""


# === 玻璃态卡片样式 ===
GLASS_CARD_STYLE = f"""
QWidget {{
    background-color: rgba(22, 27, 34, 0.85);
    border: 1px solid {Colors.BORDER};
    border-radius: 12px;
    padding: 16px;
}}
"""


# === 状态卡片样式 ===
STATUS_CARD_STYLE = f"""
QFrame {{
    background-color: {Colors.BG_SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 12px;
    padding: 16px;
    min-width: 160px;
}}
"""

STATUS_CARD_TITLE_STYLE = f"""
QLabel {{
    color: {Colors.TEXT_SECONDARY};
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.5px;
}}
"""

STATUS_CARD_VALUE_STYLE = f"""
QLabel {{
    color: {Colors.TEXT_PRIMARY};
    font-size: 32px;
    font-weight: bold;
    font-family: "{FONT_MONO}";
}}
"""

STATUS_CARD_DESC_STYLE = f"""
QLabel {{
    color: {Colors.TEXT_MUTED};
    font-size: 11px;
}}
"""


# === 按钮样式 ===
# 注意: min-width 应该在代码中使用 setMinimumWidth() 设置，而不是 CSS
BUTTON_PRIMARY_STYLE = f"""
QPushButton {{
    background-color: {Colors.PRIMARY};
    color: {Colors.BG_BASE};
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {Colors.PRIMARY_HOVER};
    border: 1px solid {Colors.PRIMARY};
}}
QPushButton:pressed {{
    background-color: {Colors.PRIMARY_PRESSED};
}}
QPushButton:disabled {{
    background-color: {Colors.BORDER};
    color: {Colors.TEXT_DISABLED};
    border: none;
}}
"""

BUTTON_SECONDARY_STYLE = f"""
QPushButton {{
    background-color: transparent;
    color: {Colors.PRIMARY};
    border: 1px solid {Colors.PRIMARY};
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: rgba(0, 217, 255, 0.1);
    border: 1px solid {Colors.PRIMARY};
}}
QPushButton:pressed {{
    background-color: rgba(0, 217, 255, 0.2);
}}
"""

BUTTON_DANGER_STYLE = f"""
QPushButton {{
    background-color: {Colors.ERROR};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #DC2626;
    border: 1px solid {Colors.ERROR};
}}
"""

BUTTON_ICON_STYLE = f"""
QPushButton {{
    background-color: transparent;
    color: {Colors.TEXT_SECONDARY};
    border: none;
    border-radius: 6px;
    padding: 8px;
}}
QPushButton:hover {{
    background-color: {Colors.BG_HOVER};
    color: {Colors.TEXT_PRIMARY};
}}
"""


# === 输入框样式 ===
LINE_EDIT_STYLE = f"""
QLineEdit {{
    background-color: {Colors.BG_ELEVATED};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLineEdit:hover {{
    border-color: {Colors.BORDER_HOVER};
}}
QLineEdit:focus {{
    border-color: {Colors.PRIMARY};
}}
"""

# === SpinBox 样式 ===
# 注意: min-width 应该在代码中使用 setMinimumWidth() 设置
SPIN_BOX_STYLE = f"""
QSpinBox {{
    background-color: {Colors.BG_ELEVATED};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
}}
QSpinBox:hover {{
    border-color: {Colors.BORDER_HOVER};
}}
QSpinBox:focus {{
    border-color: {Colors.PRIMARY};
}}
QSpinBox::up-button {{
    background-color: {Colors.BG_HOVER};
    border-radius: 4px;
    width: 20px;
    padding: 2px;
}}
QSpinBox::up-button:hover {{
    background-color: {Colors.BORDER};
}}
QSpinBox::down-button {{
    background-color: {Colors.BG_HOVER};
    border-radius: 4px;
    width: 20px;
    padding: 2px;
}}
QSpinBox::down-button:hover {{
    background-color: {Colors.BORDER};
}}
"""


# === 日志查看器样式 (Terminal) ===
LOG_VIEWER_STYLE = f"""
QTextEdit {{
    background-color: #0A0E14;
    color: #A9B1D6;
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    padding: 12px;
    font-family: "{FONT_MONO}";
    font-size: 13px;
    line-height: 1.6;
}}
"""


# === 状态栏样式 ===
STATUS_BAR_STYLE = f"""
QStatusBar {{
    background-color: {Colors.BG_SURFACE};
    color: {Colors.TEXT_SECONDARY};
    border-top: 1px solid {Colors.BORDER};
    padding: 8px;
    font-size: 12px;
}}
"""


# === 菜单样式 ===
MENU_BAR_STYLE = f"""
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
"""


# === 组框样式 ===
GROUP_BOX_STYLE = f"""
QGroupBox {{
    background-color: {Colors.BG_SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 12px;
    padding: 16px;
    margin-top: 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    color: {Colors.TEXT_PRIMARY};
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
}}
"""


# === 复选框样式 ===
CHECKBOX_STYLE = f"""
QCheckBox {{
    color: {Colors.TEXT_PRIMARY};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {Colors.BORDER};
    border-radius: 4px;
    background-color: transparent;
}}
QCheckBox::indicator:hover {{
    border-color: {Colors.PRIMARY};
}}
QCheckBox::indicator:checked {{
    background-color: {Colors.PRIMARY};
    border-color: {Colors.PRIMARY};
}}
"""


# === 工具提示样式 ===
TOOLTIP_STYLE = f"""
QToolTip {{
    background-color: {Colors.BG_ELEVATED};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""


# === Dashboard 布局样式 ===

# Header Bar 样式
HEADER_BAR_STYLE = f"""
QFrame {{
    background-color: {Colors.BG_SURFACE};
    border-bottom: 1px solid {Colors.BORDER};
    padding: 8px 16px;
}}
"""

# Hero Card 样式 (状态主卡片)
HERO_CARD_STYLE = f"""
QFrame {{
    background-color: {Colors.BG_SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 16px;
    padding: 20px;
}}
"""

# 控制面板样式
CONTROL_PANEL_STYLE = f"""
QFrame {{
    background-color: {Colors.BG_SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 16px;
    padding: 16px;
}}
"""

# Dashboard 容器样式
DASHBOARD_STYLE = f"""
QFrame {{
    background-color: transparent;
    border: none;
}}
"""

# 紧凑设置面板样式
SETTINGS_COMPACT_STYLE = f"""
QFrame {{
    background-color: {Colors.BG_SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 10px;
}}
"""

# 进度条样式
PROGRESS_BAR_STYLE = f"""
QProgressBar {{
    background-color: {Colors.BG_ELEVATED};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {Colors.PRIMARY};
    border-radius: 5px;
}}
"""

# 状态指示点样式
STATUS_INDICATOR_STYLE = f"""
QLabel {{
    font-size: 12px;
    font-weight: bold;
}}
"""


def get_circuit_state_style(state: str) -> str:
    """获取回路状态样式"""
    color_map = {
        "CLOSED": Colors.CIRCUIT_CLOSED,
        "HALF_OPEN": Colors.CIRCUIT_HALF_OPEN,
        "OPEN": Colors.CIRCUIT_OPEN,
    }
    color = color_map.get(state, Colors.TEXT_DISABLED)
    return f"""
QLabel {{
    color: {color};
    font-size: 28px;
    font-weight: bold;
    font-family: "{FONT_MONO}";
}}
"""


def get_status_indicator_style(color: str, glow: str = "") -> str:
    """获取状态指示器样式"""
    return f"""
QLabel {{
    color: {color};
    font-size: 12px;
    font-weight: bold;
}}
"""


def get_theme_font(size: int = 10, weight: str = "normal") -> QFont:
    """获取主题字体"""
    font = QFont()
    font.setPointSize(size)
    if weight == "bold":
        font.setBold(True)
    font.setFamily(FONT_FAMILY)
    return font


def create_dark_palette() -> QPalette:
    """创建深色palette (Midnight Studio)"""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(Colors.BG_BASE))
    palette.setColor(QPalette.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.AlternateBase, QColor(Colors.BG_SURFACE))
    palette.setColor(QPalette.ToolTipBase, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.ToolTipText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.ButtonText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.BrightText, QColor(Colors.PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(Colors.PRIMARY))
    palette.setColor(QPalette.HighlightedText, QColor(Colors.BG_BASE))
    return palette

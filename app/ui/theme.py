"""暗色主题."""

COLOR_BG = "#0D1117"
COLOR_PANEL = "#161B22"
COLOR_PANEL_ALT = "#1C232C"
COLOR_TEXT = "#E6EDF3"
COLOR_SUB = "#8B949E"
COLOR_BORDER = "#30363D"

# 单双
COLOR_ODD = "#E53E3E"   # 单 - 红
COLOR_EVEN = "#22A06B"  # 双 - 绿


QSS = f"""
* {{
    color: {COLOR_TEXT};
    font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QWidget {{
    background-color: {COLOR_BG};
}}
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background: {COLOR_PANEL};
}}
QTabBar::tab {{
    background: {COLOR_BG};
    color: {COLOR_SUB};
    padding: 6px 16px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {COLOR_PANEL};
    color: {COLOR_TEXT};
}}
QGroupBox {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    margin-top: 8px;
    padding: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {COLOR_SUB};
}}
QPushButton {{
    background: {COLOR_PANEL_ALT};
    border: 1px solid {COLOR_BORDER};
    padding: 6px 14px;
    border-radius: 4px;
}}
QPushButton:hover {{
    background: #2A323C;
}}
QPushButton:disabled {{
    color: {COLOR_SUB};
}}
QLineEdit, QSpinBox, QComboBox {{
    background: {COLOR_PANEL_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #1f6feb;
}}
QCheckBox {{ spacing: 6px; }}
QLabel#sub {{ color: {COLOR_SUB}; }}

QListWidget, QTableWidget {{
    background: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDER};
}}
QStatusBar {{
    background: {COLOR_PANEL};
    color: {COLOR_SUB};
}}
"""

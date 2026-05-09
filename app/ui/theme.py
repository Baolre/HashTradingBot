"""暗色主题 + 大小颜色 + 动态配色."""
from __future__ import annotations
from typing import Dict

COLOR_BG = "#0D1117"
COLOR_PANEL = "#161B22"
COLOR_PANEL_ALT = "#1C232C"
COLOR_TEXT = "#E6EDF3"
COLOR_SUB = "#8B949E"
COLOR_BORDER = "#30363D"
COLOR_ODD = "#E53E3E"
COLOR_EVEN = "#22A06B"
COLOR_BIG = "#D97706"
COLOR_SMALL = "#2563EB"

_custom: Dict[str, str] = {}


def set_custom_colors(odd: str = "", even: str = "", big: str = "", small: str = "") -> None:
    if odd: _custom["odd"] = odd
    if even: _custom["even"] = even
    if big: _custom["big"] = big
    if small: _custom["small"] = small


def C(key: str) -> str:
    defaults = {"odd": COLOR_ODD, "even": COLOR_EVEN, "big": COLOR_BIG, "small": COLOR_SMALL,
                "bg": COLOR_BG, "panel": COLOR_PANEL, "panel_alt": COLOR_PANEL_ALT,
                "text": COLOR_TEXT, "sub": COLOR_SUB, "border": COLOR_BORDER}
    return _custom.get(key, defaults.get(key, "#FFFFFF"))


QSS = f"""
* {{ color: {COLOR_TEXT}; font-family: "Microsoft YaHei","PingFang SC",Arial,sans-serif; font-size: 13px; }}
QMainWindow, QWidget {{ background-color: {COLOR_BG}; }}
QTabWidget::pane {{ border: 1px solid {COLOR_BORDER}; background: {COLOR_PANEL}; }}
QTabBar::tab {{ background: {COLOR_BG}; color: {COLOR_SUB}; padding: 6px 16px; border: 1px solid {COLOR_BORDER}; border-bottom: none; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {COLOR_PANEL}; color: {COLOR_TEXT}; }}
QGroupBox {{ border: 1px solid {COLOR_BORDER}; border-radius: 6px; margin-top: 8px; padding: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {COLOR_SUB}; }}
QPushButton {{ background: {COLOR_PANEL_ALT}; border: 1px solid {COLOR_BORDER}; padding: 6px 14px; border-radius: 4px; }}
QPushButton:hover {{ background: #2A323C; }}
QPushButton:disabled {{ color: {COLOR_SUB}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {COLOR_PANEL_ALT}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 4px 8px; }}
QCheckBox {{ spacing: 6px; }}
QListWidget, QTableWidget {{ background: {COLOR_PANEL}; border: 1px solid {COLOR_BORDER}; alternate-background-color: {COLOR_PANEL_ALT}; }}
QScrollArea {{ background: {COLOR_BG}; border: none; }}
QStatusBar {{ background: {COLOR_PANEL}; color: {COLOR_SUB}; }}
"""

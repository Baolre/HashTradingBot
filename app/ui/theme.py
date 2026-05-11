"""全局主题 - 深色 + 现代卡片风."""

# ===== 基础色 =====
COLOR_BG = "#0B0F14"             # 窗口主背景（比 0D1117 稍深）
COLOR_PANEL = "#141A22"           # 卡片背景
COLOR_PANEL_ALT = "#1C232C"       # 输入/hover
COLOR_ELEVATED = "#1A2230"        # 更高层卡片
COLOR_TEXT = "#E6EDF3"
COLOR_SUB = "#8B949E"
COLOR_BORDER = "#232C38"
COLOR_BORDER_STRONG = "#2F3B4C"

# ===== 单双色 =====
COLOR_ODD = "#E53E3E"    # 单 - 红
COLOR_EVEN = "#22A06B"   # 双 - 绿

# ===== 强调色 =====
COLOR_ACCENT = "#3B82F6"  # 蓝 - 主按钮
COLOR_ACCENT_HOVER = "#2563EB"
COLOR_BIG = "#D97706"     # 橙 - 倒计时
COLOR_SMALL = "#2563EB"


QSS = f"""
* {{
    color: {COLOR_TEXT};
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QWidget {{
    background-color: {COLOR_BG};
}}

/* ========= Tabs ========= */
QTabWidget::pane {{
    border: none;
    background: {COLOR_BG};
    top: -1px;
}}
QTabBar {{
    qproperty-drawBase: 0;
    background: {COLOR_BG};
}}
QTabBar::tab {{
    background: transparent;
    color: {COLOR_SUB};
    padding: 10px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    min-width: 80px;
}}
QTabBar::tab:hover {{
    color: {COLOR_TEXT};
}}
QTabBar::tab:selected {{
    color: {COLOR_TEXT};
    border-bottom: 2px solid {COLOR_ACCENT};
    font-weight: bold;
}}

/* ========= Cards ========= */
QFrame#card {{
    background: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}
QFrame#cardElevated {{
    background: {COLOR_ELEVATED};
    border: 1px solid {COLOR_BORDER_STRONG};
    border-radius: 10px;
}}
QFrame#topbar {{
    background: {COLOR_PANEL};
    border-bottom: 1px solid {COLOR_BORDER};
}}

/* ========= Typography ========= */
QLabel#h1 {{ font-size: 18px; font-weight: bold; color: {COLOR_TEXT}; }}
QLabel#h2 {{ font-size: 14px; font-weight: bold; color: {COLOR_TEXT}; }}
QLabel#cardTitle {{ font-size: 12px; font-weight: bold; color: {COLOR_SUB};
                    letter-spacing: 1px; }}
QLabel#muted {{ color: {COLOR_SUB}; }}
QLabel#mutedSmall {{ color: {COLOR_SUB}; font-size: 11px; }}
QLabel#metricValue {{ font-size: 22px; font-weight: bold; color: {COLOR_TEXT}; }}
QLabel#metricLabel {{ color: {COLOR_SUB}; font-size: 11px; }}
QLabel#bigNumber {{ font-size: 28px; font-weight: bold; color: {COLOR_TEXT}; }}

/* 状态 chip */
QLabel#chipOk {{
    background: rgba(34, 160, 107, 0.12);
    color: {COLOR_EVEN};
    border: 1px solid rgba(34, 160, 107, 0.3);
    border-radius: 10px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 11px;
}}
QLabel#chipErr {{
    background: rgba(229, 62, 62, 0.12);
    color: {COLOR_ODD};
    border: 1px solid rgba(229, 62, 62, 0.3);
    border-radius: 10px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 11px;
}}
QLabel#chipIdle {{
    background: rgba(139, 148, 158, 0.12);
    color: {COLOR_SUB};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 2px 10px;
    font-weight: bold;
    font-size: 11px;
}}

/* ========= Buttons ========= */
QPushButton {{
    background: {COLOR_PANEL_ALT};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER_STRONG};
    padding: 7px 16px;
    border-radius: 6px;
}}
QPushButton:hover {{
    background: #2A323C;
    border-color: #3A4452;
}}
QPushButton:disabled {{
    color: {COLOR_SUB};
    background: {COLOR_PANEL};
    border-color: {COLOR_BORDER};
}}
QPushButton#primary {{
    background: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
    color: white;
    font-weight: bold;
    padding: 8px 20px;
}}
QPushButton#primary:hover {{
    background: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#primary:disabled {{
    background: #2B3343;
    border-color: #2B3343;
    color: {COLOR_SUB};
}}
QPushButton#danger {{
    background: transparent;
    border: 1px solid {COLOR_ODD};
    color: {COLOR_ODD};
}}
QPushButton#danger:hover {{
    background: rgba(229, 62, 62, 0.1);
}}
QPushButton#danger:disabled {{
    border-color: {COLOR_BORDER};
    color: {COLOR_SUB};
}}

/* ========= Inputs ========= */
QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox {{
    background: {COLOR_PANEL_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {COLOR_ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {COLOR_ACCENT};
}}

QCheckBox {{ spacing: 8px; padding: 2px; }}

/* ========= Group Box（备用，已基本不用） ========= */
QGroupBox {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {COLOR_SUB};
}}

/* ========= Tables / Lists ========= */
QListWidget, QTableWidget {{
    background: transparent;
    border: none;
    gridline-color: {COLOR_BORDER};
    outline: none;
}}
QTableWidget::item, QListWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {COLOR_BORDER};
}}
QTableWidget::item:selected, QListWidget::item:selected {{
    background: rgba(59, 130, 246, 0.1);
    color: {COLOR_TEXT};
}}
QHeaderView::section {{
    background: transparent;
    color: {COLOR_SUB};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_STRONG};
    font-weight: bold;
    font-size: 11px;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ========= Scrollbars ========= */
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER_STRONG}; border-radius: 5px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: #3A4452; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER_STRONG}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #3A4452; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent; border: none;
}}

/* ========= Splitter ========= */
QSplitter::handle {{ background: {COLOR_BG}; }}
QSplitter::handle:horizontal {{ width: 6px; }}
QSplitter::handle:vertical {{ height: 6px; }}
QSplitter::handle:hover {{ background: {COLOR_BORDER}; }}

/* ========= ProgressBar ========= */
QProgressBar {{
    background: {COLOR_PANEL_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    text-align: center;
    color: {COLOR_TEXT};
    font-size: 11px;
    height: 14px;
}}
QProgressBar::chunk {{
    background: {COLOR_ACCENT};
    border-radius: 5px;
}}

/* ========= StatusBar ========= */
QStatusBar {{
    background: {COLOR_PANEL};
    color: {COLOR_SUB};
    border-top: 1px solid {COLOR_BORDER};
}}
QStatusBar::item {{ border: none; }}
"""

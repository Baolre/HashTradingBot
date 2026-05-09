"""连珠走势图 - 参考截图中"区块走势"样式.

规则:
- 每列最多堆 column_max 个圆珠
- 来了新一期：若与当前列最顶同色则向上叠；否则开新列从底部开始
- 红 = 单 odd，绿 = 双 even；unknown 跳过
"""
from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from ..core.analyzer import PARITY_EVEN, PARITY_ODD, Analyzer, Period
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_PANEL, COLOR_SUB, COLOR_TEXT


def _metric(title: str, value_label: QLabel) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("sub")
    t.setStyleSheet(f"color: {COLOR_SUB};")
    lay.addWidget(t)
    lay.addWidget(value_label)
    return w


# -------------------- 计数胶囊 --------------------
class CountPill(QFrame):
    """类似截图中的 [双 96] / [单 104] 胶囊."""

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._count = 0
        self.setFixedHeight(32)
        self.setMinimumWidth(90)

    def set_count(self, n: int) -> None:
        self._count = n
        self.update()

    def paintEvent(self, event) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2

        # 背景
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(COLOR_PANEL)))
        p.drawRoundedRect(rect, radius, radius)

        # 左侧色点
        dot_r = rect.height() - 10
        dot_rect = QRect(rect.left() + 6, rect.top() + 5, dot_r, dot_r)
        p.setBrush(QBrush(QColor(self._color)))
        p.drawEllipse(dot_rect)

        # 文字: 标签
        font = QFont(self.font())
        font.setPointSize(10)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        label_rect = QRect(dot_rect.right() + 8, rect.top(), 28, rect.height())
        p.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, self._label)

        # 文字: 数字
        num_font = QFont(self.font())
        num_font.setPointSize(12)
        num_font.setBold(True)
        p.setFont(num_font)
        num_rect = QRect(label_rect.right() + 2, rect.top(),
                         rect.right() - label_rect.right() - 10, rect.height())
        p.setPen(QColor(COLOR_TEXT))
        p.drawText(num_rect, Qt.AlignVCenter | Qt.AlignLeft, str(self._count))


# -------------------- 珠盘 --------------------
class BeadBoard(QWidget):
    """红绿圆珠走势盘."""

    def __init__(self, column_max: int = 6, dot_size: int = 30, column_gap: int = 6, parent=None):
        super().__init__(parent)
        self.column_max = max(3, column_max)
        self.dot_size = max(18, dot_size)
        self.column_gap = max(2, column_gap)
        self._columns: List[List[str]] = []   # 每列是 parity 列表，["odd", "odd"]
        self.setMinimumHeight(self.column_max * (self.dot_size + 4) + 20)
        self.setStyleSheet(f"background: {COLOR_BG};")

        # 横向扩展策略，允许在 QScrollArea 中正确显示
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ---------------- 数据刷新 ----------------
    def set_periods(self, periods: List[Period]) -> None:
        """用整段历史重新布局列."""
        self._columns = []
        for p in periods:
            self._push(p.parity)
        self.updateGeometry()
        self.update()

    def append(self, period: Period) -> None:
        self._push(period.parity)
        self.updateGeometry()
        self.update()

    def clear(self) -> None:
        self._columns = []
        self.update()

    def _push(self, parity: str) -> None:
        if parity not in (PARITY_ODD, PARITY_EVEN):
            return
        if not self._columns:
            self._columns.append([parity])
            return
        last_col = self._columns[-1]
        if last_col[-1] == parity and len(last_col) < self.column_max:
            last_col.append(parity)
        else:
            self._columns.append([parity])

    # ---------------- 尺寸 ----------------
    def minimumSizeHint(self):
        cols = max(1, len(self._columns))
        step = self.dot_size + self.column_gap
        w = 20 + cols * step
        h = self.column_max * (self.dot_size + 4) + 20
        return QSize(w, h)

    def sizeHint(self):
        return self.minimumSizeHint()

    # ---------------- 绘制 ----------------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLOR_BG))

        if not self._columns:
            p.setPen(QColor(COLOR_SUB))
            p.drawText(self.rect(), Qt.AlignCenter, "暂无数据，等待区块...")
            return

        step_x = self.dot_size + self.column_gap
        step_y = self.dot_size + 4
        x0 = 10
        # 底部对齐：最新的珠永远贴底
        y_base = self.height() - 10 - self.dot_size

        for ci, col in enumerate(self._columns):
            x = x0 + ci * step_x
            for ri, parity in enumerate(col):
                y = y_base - ri * step_y
                color = QColor(COLOR_ODD if parity == PARITY_ODD else COLOR_EVEN)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                p.drawEllipse(x, y, self.dot_size, self.dot_size)

                # 文字
                font = QFont(self.font())
                font.setPointSize(10)
                font.setBold(True)
                p.setFont(font)
                p.setPen(QColor("#FFFFFF"))
                rect = QRect(x, y, self.dot_size, self.dot_size)
                p.drawText(rect, Qt.AlignCenter, "单" if parity == PARITY_ODD else "双")


# -------------------- 顶部容器：标题 + 胶囊 + 珠盘 --------------------
class TrendView(QWidget):
    """外层容器."""

    refresh_requested = Signal()

    def __init__(self, column_max: int = 6, dot_size: int = 30, column_gap: int = 6, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # 顶栏
        top = QHBoxLayout()
        title = QLabel("开奖走势")
        f = title.font()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        top.addWidget(title)
        top.addStretch()

        self.even_pill = CountPill("双", COLOR_EVEN)
        self.odd_pill = CountPill("单", COLOR_ODD)
        top.addWidget(self.even_pill)
        top.addSpacing(8)
        top.addWidget(self.odd_pill)

        root.addLayout(top)

        # 子标签按钮（纯样式，参考截图）
        tab_bar = QHBoxLayout()
        tab_bar.setContentsMargins(0, 0, 0, 0)
        btn_a = QPushButton("区块走势")
        btn_a.setCheckable(True)
        btn_a.setChecked(True)
        btn_a.setFixedHeight(26)
        btn_b = QPushButton("我的走势")
        btn_b.setCheckable(True)
        btn_b.setFixedHeight(26)
        btn_b.setEnabled(False)  # 先占位
        for b in (btn_a, btn_b):
            b.setStyleSheet(
                f"QPushButton {{ border-radius: 13px; padding: 2px 14px; "
                f"background: {COLOR_PANEL}; color: {COLOR_SUB}; }}"
                f"QPushButton:checked {{ background: #FFFFFF; color: #000000; }}"
            )
        tab_bar.addWidget(btn_a)
        tab_bar.addWidget(btn_b)
        tab_bar.addStretch()
        root.addLayout(tab_bar)

        # 珠盘
        self.board = BeadBoard(column_max=column_max, dot_size=dot_size, column_gap=column_gap)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 允许垂直滚动
        scroll.setWidget(self.board)
        scroll.setStyleSheet(f"QScrollArea {{ background: {COLOR_BG}; border: none; }}")

        # 确保滚动区域可以横向扩展
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setMinimumHeight(400)
        root.addWidget(scroll, 10)

        # 底部容器：统计和表格水平排列
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        # 统计指标（左侧，紧凑）
        grp = QGroupBox("实时统计")
        grid = QGridLayout(grp)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)

        self.lbl_total = QLabel("0")
        self.lbl_odd = QLabel("0")
        self.lbl_even = QLabel("0")
        self.lbl_ratio = QLabel("0% / 0%")
        self.lbl_streak = QLabel("-")
        self.lbl_longest_odd = QLabel("0")
        self.lbl_longest_even = QLabel("0")
        self.lbl_alt = QLabel("0")

        for lbl in (self.lbl_total, self.lbl_odd, self.lbl_even, self.lbl_ratio,
                    self.lbl_streak, self.lbl_longest_odd, self.lbl_longest_even, self.lbl_alt):
            f = lbl.font()
            f.setPointSize(12)
            f.setBold(True)
            lbl.setFont(f)

        self.lbl_odd.setStyleSheet(f"color: {COLOR_ODD};")
        self.lbl_even.setStyleSheet(f"color: {COLOR_EVEN};")

        grid.addWidget(_metric("总期数", self.lbl_total), 0, 0)
        grid.addWidget(_metric("单 (总)", self.lbl_odd), 0, 1)
        grid.addWidget(_metric("双 (总)", self.lbl_even), 0, 2)
        grid.addWidget(_metric("单/双 占比", self.lbl_ratio), 0, 3)
        grid.addWidget(_metric("当前连号", self.lbl_streak), 1, 0)
        grid.addWidget(_metric("最长单连号", self.lbl_longest_odd), 1, 1)
        grid.addWidget(_metric("最长双连号", self.lbl_longest_even), 1, 2)
        grid.addWidget(_metric("当前交叉长度", self.lbl_alt), 1, 3)

        grp.setMaximumWidth(500)  # 限制宽度
        bottom.addWidget(grp)

        # 最近 20 期表（右侧，紧凑）
        grp2 = QGroupBox("最近 20 期")
        inner = QVBoxLayout(grp2)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["区块号", "单/双", "末位数字", "区块哈希"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setMaximumHeight(180)  # 紧凑高度
        inner.addWidget(self.table)

        bottom.addWidget(grp2, 1)

        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom)
        root.addWidget(bottom_widget)

        # 状态行
        self.status = QLabel("等待启动监控…")
        self.status.setObjectName("sub")
        root.addWidget(self.status)

    # ---------------- 对外 ----------------
    def apply_periods(self, periods: List[Period], odd_total: int, even_total: int) -> None:
        self.board.set_periods(periods)
        self.odd_pill.set_count(odd_total)
        self.even_pill.set_count(even_total)
        self._refresh_stats()

    def on_new_period(self, period: Period, odd_total: int, even_total: int) -> None:
        self.board.append(period)
        self.odd_pill.set_count(odd_total)
        self.even_pill.set_count(even_total)
        self._refresh_stats()

    def set_status(self, text: str) -> None:
        self.status.setText(text)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def refresh(self, analyzer: Analyzer) -> None:
        """刷新统计数据（供外部调用）."""
        self._refresh_stats_from_analyzer(analyzer)

    def _refresh_stats(self) -> None:
        """从珠盘数据刷新统计（简化版）."""
        # 这个方法仅更新显示，需要外部传入完整analyzer
        pass

    def _refresh_stats_from_analyzer(self, analyzer: Analyzer) -> None:
        """从analyzer刷新所有统计."""
        s = analyzer.stats
        self.lbl_total.setText(str(s.total))
        self.lbl_odd.setText(str(s.odd_total))
        self.lbl_even.setText(str(s.even_total))
        if s.total:
            odd_pct = s.odd_total * 100 / s.total
            even_pct = s.even_total * 100 / s.total
            self.lbl_ratio.setText(f"{odd_pct:.1f}% / {even_pct:.1f}%")
        else:
            self.lbl_ratio.setText("- / -")

        if s.current_streak_parity == PARITY_ODD:
            self.lbl_streak.setText(f"单 × {s.current_streak_len}")
            self.lbl_streak.setStyleSheet(f"color: {COLOR_ODD};")
        elif s.current_streak_parity == PARITY_EVEN:
            self.lbl_streak.setText(f"双 × {s.current_streak_len}")
            self.lbl_streak.setStyleSheet(f"color: {COLOR_EVEN};")
        else:
            self.lbl_streak.setText("-")
            self.lbl_streak.setStyleSheet("")

        self.lbl_longest_odd.setText(str(s.longest_odd_streak))
        self.lbl_longest_even.setText(str(s.longest_even_streak))
        self.lbl_alt.setText(str(s.current_alternation_len))

        # 表格
        last = analyzer.last(20)
        last = list(reversed(last))
        self.table.setRowCount(len(last))
        for i, p in enumerate(last):
            self.table.setItem(i, 0, QTableWidgetItem(str(p.block_number)))
            label = "单" if p.parity == PARITY_ODD else ("双" if p.parity == PARITY_EVEN else "?")
            cell = QTableWidgetItem(label)
            cell.setTextAlignment(Qt.AlignCenter)
            if p.parity == PARITY_ODD:
                cell.setForeground(Qt.red)
            elif p.parity == PARITY_EVEN:
                cell.setForeground(Qt.green)
            self.table.setItem(i, 1, cell)
            self.table.setItem(i, 2, QTableWidgetItem("-" if p.digit is None else str(p.digit)))
            self.table.setItem(i, 3, QTableWidgetItem(p.block_hash))

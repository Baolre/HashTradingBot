"""走势图基础组件 - 红绿圆珠板（被 DashboardPanel 复用）."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.analyzer import PARITY_EVEN, PARITY_ODD, Period
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_SUB


class BeadBoard(QWidget):
    """红绿圆珠走势盘 - 最新在最右侧，旧数据向左推出.

    规则：
    - 相同颜色竖向堆叠，最多 column_max；超过后换新列
    - 宽度 = max(视口宽度, 列数 * step)，保证列少时也贴右侧
    - 绘制方向：从最右开始画最新列（i=0 画最右），越旧越靠左
    """

    def __init__(self, column_max: int = 6, dot_size: int = 30, column_gap: int = 6, parent=None):
        super().__init__(parent)
        self.column_max = max(3, column_max)
        self.dot_size = max(18, dot_size)
        self.column_gap = max(2, column_gap)
        self._columns: List[List[str]] = []
        self._min_height = self.column_max * (self.dot_size + 4) + 20
        self._visible_columns = 500
        self._viewport_width = 400
        self.setMinimumHeight(self._min_height)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def set_viewport_width(self, w: int) -> None:
        self._viewport_width = max(100, int(w))
        self._update_size()
        self.update()

    def set_periods(self, periods: List[Period]) -> None:
        self._columns = []
        for p in periods:
            self._push(p.parity)
        self._update_size()
        self.update()

    def append(self, period: Period) -> None:
        self._push(period.parity)
        self._update_size()
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

    def _update_size(self) -> None:
        step = self.dot_size + self.column_gap
        cols = max(1, len(self._columns))
        content_w = 20 + cols * step
        w = max(content_w, self._viewport_width)
        self.setFixedSize(w, self._min_height)

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
        x_right = self.width() - 10 - self.dot_size
        y_base = self.height() - 10 - self.dot_size
        visible = self._columns[-self._visible_columns:]
        for i, col in enumerate(reversed(visible)):
            x = x_right - i * step_x
            if x < -step_x:
                break
            for ri, parity in enumerate(col):
                y = y_base - ri * step_y
                color = QColor(COLOR_ODD if parity == PARITY_ODD else COLOR_EVEN)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                p.drawEllipse(x, y, self.dot_size, self.dot_size)
                font = QFont(self.font()); font.setPointSize(10); font.setBold(True)
                p.setFont(font)
                p.setPen(QColor("#FFFFFF"))
                p.drawText(
                    QRect(x, y, self.dot_size, self.dot_size),
                    Qt.AlignCenter,
                    "单" if parity == PARITY_ODD else "双",
                )

"""珠盘路 - 标准矩阵走势图（纯单双）."""
from __future__ import annotations
from typing import List
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QBrush
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ..core.analyzer import PARITY_EVEN, PARITY_ODD, Period
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_SUB


class BeadRoadCanvas(QWidget):
    def __init__(self, rows=6, cols=30, dot_size=24, parent=None):
        super().__init__(parent)
        self.rows, self.cols, self.dot_size = rows, cols, dot_size
        self._periods: List[Period] = []
        self._gap = 3
        self.setMinimumHeight(rows * (dot_size + self._gap) + 10)

    def set_periods(self, periods: List[Period]) -> None:
        self._periods = list(periods)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLOR_BG))
        if not self._periods:
            p.setPen(QColor(COLOR_SUB))
            p.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            return
        step = self.dot_size + self._gap
        max_cells = self.rows * self.cols
        display = self._periods[-max_cells:]
        font = QFont(self.font())
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)
        for idx, period in enumerate(display):
            col = idx // self.rows
            row = idx % self.rows
            x, y = 5 + col * step, 5 + row * step
            color = QColor(COLOR_ODD if period.is_odd else COLOR_EVEN)
            text = "单" if period.is_odd else "双"
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color))
            p.drawEllipse(x, y, self.dot_size, self.dot_size)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(QRect(x, y, self.dot_size, self.dot_size), Qt.AlignCenter, text)


class BeadRoadView(QWidget):
    def __init__(self, rows=6, cols=30, dot_size=24, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        top = QHBoxLayout()
        title = QLabel("珠盘路")
        f = title.font(); f.setPointSize(13); f.setBold(True); title.setFont(f)
        top.addWidget(title)
        top.addStretch()
        root.addLayout(top)
        self.canvas = BeadRoadCanvas(rows=rows, cols=cols, dot_size=dot_size)
        root.addWidget(self.canvas, 1)

    def set_periods(self, periods: List[Period]) -> None:
        self.canvas.set_periods(periods)

    def append_period(self, period: Period) -> None:
        self.canvas._periods.append(period)
        self.canvas.update()

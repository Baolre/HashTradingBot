"""连珠走势图 - 参考截图中"区块走势"样式.

规则:
- 每列最多堆 column_max 个圆珠
- 来了新一期：若与当前列最顶同色则向上叠；否则开新列从底部开始
- 红 = 单 odd，绿 = 双 even；unknown 跳过
"""
from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core.analyzer import PARITY_EVEN, PARITY_ODD, Period
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_PANEL, COLOR_SUB, COLOR_TEXT


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
    def _needed_width(self) -> int:
        cols = max(1, len(self._columns))
        step = self.dot_size + self.column_gap
        return 20 + cols * step

    def sizeHint(self):
        return self.minimumSize().expandedTo(
            self.minimumSize().__class__(self._needed_width(), self.minimumHeight())
        )

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
        root.addWidget(self.board, 1)

        # 状态行
        self.status = QLabel("等待启动监控…")
        self.status.setObjectName("sub")
        root.addWidget(self.status)

    # ---------------- 对外 ----------------
    def apply_periods(self, periods: List[Period], odd_total: int, even_total: int) -> None:
        self.board.set_periods(periods)
        self.odd_pill.set_count(odd_total)
        self.even_pill.set_count(even_total)

    def on_new_period(self, period: Period, odd_total: int, even_total: int) -> None:
        self.board.append(period)
        self.odd_pill.set_count(odd_total)
        self.even_pill.set_count(even_total)

    def set_status(self, text: str) -> None:
        self.status.setText(text)


    def refresh(self, analyzer) -> None:
        """Placeholder for compatibility - stats shown elsewhere."""
        pass

    def update_ai_signal(self, prediction) -> None:
        """在走势页底部显示 AI 信号摘要（含预测区块号）."""
        if not hasattr(self, '_ai_label'):
            self._ai_label = QLabel("AI: 等待信号...")
            self._ai_label.setStyleSheet(
                f"color: {COLOR_SUB}; font-size: 12px; padding: 4px 8px; "
                f"background: #1C232C; border-radius: 4px;"
            )
            self.layout().insertWidget(self.layout().count() - 1, self._ai_label)

        if prediction is None or not prediction.has_signal:
            self._ai_label.setText("AI: 暂无高置信度信号")
            self._ai_label.setStyleSheet(
                "color: #8B949E; font-size: 12px; padding: 4px 8px; "
                "background: #1C232C; border-radius: 4px;"
            )
            return

        signal = prediction.best
        color = COLOR_ODD if signal.prediction == "odd" else COLOR_EVEN
        block_num = signal.next_block_number or prediction.next_block_number or 0
        block_text = f" | 预测区块 #{block_num}" if block_num else ""
        self._ai_label.setText(
            f"AI 信号: 预测下期 {signal.label} | 置信度 {signal.confidence_pct} | {signal.model}{block_text}"
        )
        self._ai_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold; padding: 4px 8px; "
            f"background: #1C232C; border: 1px solid {color}; border-radius: 4px;"
        )

"""UI 组件。"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, QRect, QSize, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QBrush
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ..core.analyzer import PARITY_EVEN, PARITY_ODD, Analyzer, Period
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_PANEL, COLOR_SUB, COLOR_TEXT


def _metric(title: str, value_label: QLabel) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet(f"color: {COLOR_SUB}; font-size: 11px;")
    lay.addWidget(t)
    lay.addWidget(value_label)
    return w


class CountPill(QFrame):
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

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(COLOR_PANEL)))
        p.drawRoundedRect(rect, radius, radius)
        dot_r = rect.height() - 10
        dot_rect = QRect(rect.left() + 6, rect.top() + 5, dot_r, dot_r)
        p.setBrush(QBrush(QColor(self._color)))
        p.drawEllipse(dot_rect)
        font = QFont(self.font())
        font.setPointSize(10)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        label_rect = QRect(dot_rect.right() + 6, rect.top(), 20, rect.height())
        p.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, self._label)
        num_font = QFont(self.font())
        num_font.setPointSize(12)
        num_font.setBold(True)
        p.setFont(num_font)
        num_rect = QRect(label_rect.right() + 2, rect.top(),
                         rect.right() - label_rect.right() - 8, rect.height())
        p.setPen(QColor(COLOR_TEXT))
        p.drawText(num_rect, Qt.AlignVCenter | Qt.AlignLeft, str(self._count))


class BeadBoard(QWidget):
    """红绿圆珠走势盘 - 最新在右侧."""

    def __init__(self, column_max: int = 6, dot_size: int = 30, column_gap: int = 6, parent=None):
        super().__init__(parent)
        self.column_max = max(3, column_max)
        self.dot_size = max(18, dot_size)
        self.column_gap = max(2, column_gap)
        self._columns: List[List[str]] = []
        self._min_height = self.column_max * (self.dot_size + 4) + 20
        self.setMinimumHeight(self._min_height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

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
        cols = max(1, len(self._columns))
        step = self.dot_size + self.column_gap
        self.setFixedSize(20 + cols * step, self._min_height)

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
        y_base = self.height() - 10 - self.dot_size
        for ci, col in enumerate(self._columns):
            x = x0 + ci * step_x
            for ri, parity in enumerate(col):
                y = y_base - ri * step_y
                color = QColor(COLOR_ODD if parity == PARITY_ODD else COLOR_EVEN)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                p.drawEllipse(x, y, self.dot_size, self.dot_size)
                font = QFont(self.font())
                font.setPointSize(10)
                font.setBold(True)
                p.setFont(font)
                p.setPen(QColor("#FFFFFF"))
                p.drawText(QRect(x, y, self.dot_size, self.dot_size),
                           Qt.AlignCenter, "单" if parity == PARITY_ODD else "双")


class TrendView(QWidget):
    """走势面板 - 走势图 + AI信号 + 统计（合并版）."""

    refresh_requested = Signal()

    def __init__(self, column_max: int = 6, dot_size: int = 30, column_gap: int = 6, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # ===== 顶栏：标题 + 计数胶囊 =====
        top = QHBoxLayout()
        title = QLabel("开奖走势")
        f = title.font(); f.setPointSize(13); f.setBold(True); title.setFont(f)
        top.addWidget(title)
        top.addStretch()
        self.even_pill = CountPill("双", COLOR_EVEN)
        self.odd_pill = CountPill("单", COLOR_ODD)
        top.addWidget(self.even_pill)
        top.addSpacing(6)
        top.addWidget(self.odd_pill)
        root.addLayout(top)

        # ===== AI 信号横幅 =====
        self._ai_label = QLabel("AI: 等待信号...")
        self._ai_label.setStyleSheet(
            f"color: {COLOR_SUB}; font-size: 12px; padding: 6px 10px; "
            f"background: #1C232C; border-radius: 4px;"
        )
        root.addWidget(self._ai_label)

        # ===== 珠盘 + 滚动 =====
        self.board = BeadBoard(column_max=column_max, dot_size=dot_size, column_gap=column_gap)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.board)
        self.scroll.setStyleSheet(f"QScrollArea {{ background: {COLOR_BG}; border: none; }}")
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll.setMinimumHeight(self.board._min_height + 20)
        root.addWidget(self.scroll, 1)

        # ===== 统计区 =====
        grp = QGroupBox("实时统计")
        grid = QGridLayout(grp)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)

        self.lbl_total = QLabel("0")
        self.lbl_odd = QLabel("0")
        self.lbl_even = QLabel("0")
        self.lbl_ratio = QLabel("-")
        self.lbl_streak = QLabel("-")
        self.lbl_longest_odd = QLabel("0")
        self.lbl_longest_even = QLabel("0")
        self.lbl_alt = QLabel("0")

        for lbl in (self.lbl_total, self.lbl_odd, self.lbl_even, self.lbl_ratio,
                    self.lbl_streak, self.lbl_longest_odd, self.lbl_longest_even, self.lbl_alt):
            f2 = lbl.font(); f2.setPointSize(12); f2.setBold(True); lbl.setFont(f2)

        self.lbl_odd.setStyleSheet(f"color: {COLOR_ODD};")
        self.lbl_even.setStyleSheet(f"color: {COLOR_EVEN};")

        grid.addWidget(_metric("总期数", self.lbl_total), 0, 0)
        grid.addWidget(_metric("单", self.lbl_odd), 0, 1)
        grid.addWidget(_metric("双", self.lbl_even), 0, 2)
        grid.addWidget(_metric("占比", self.lbl_ratio), 0, 3)
        grid.addWidget(_metric("当前连号", self.lbl_streak), 1, 0)
        grid.addWidget(_metric("最长单连", self.lbl_longest_odd), 1, 1)
        grid.addWidget(_metric("最长双连", self.lbl_longest_even), 1, 2)
        grid.addWidget(_metric("交叉长度", self.lbl_alt), 1, 3)
        root.addWidget(grp)

        # ===== 状态行 =====
        self.status = QLabel("等待启动监控…")
        self.status.setStyleSheet(f"color: {COLOR_SUB};")
        root.addWidget(self.status)

    # ==================== 公开方法 ====================

    def _scroll_to_right(self) -> None:
        QTimer.singleShot(50, lambda: self.scroll.horizontalScrollBar().setValue(
            self.scroll.horizontalScrollBar().maximum()
        ))

    def apply_periods(self, periods: List[Period], odd_total: int, even_total: int) -> None:
        self.board.set_periods(periods)
        self.odd_pill.set_count(odd_total)
        self.even_pill.set_count(even_total)
        self._scroll_to_right()

    def on_new_period(self, period: Period, odd_total: int, even_total: int) -> None:
        self.board.append(period)
        self.odd_pill.set_count(odd_total)
        self.even_pill.set_count(even_total)
        self._scroll_to_right()

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def refresh(self, analyzer: Analyzer) -> None:
        """刷新统计区."""
        s = analyzer.stats
        self.lbl_total.setText(str(s.total))
        self.lbl_odd.setText(str(s.odd_total))
        self.lbl_even.setText(str(s.even_total))
        if s.total:
            self.lbl_ratio.setText(f"{s.odd_total*100//s.total}% / {s.even_total*100//s.total}%")
        else:
            self.lbl_ratio.setText("-")
        if s.current_streak_parity == PARITY_ODD:
            self.lbl_streak.setText(f"单×{s.current_streak_len}")
            self.lbl_streak.setStyleSheet(f"color: {COLOR_ODD};")
        elif s.current_streak_parity == PARITY_EVEN:
            self.lbl_streak.setText(f"双×{s.current_streak_len}")
            self.lbl_streak.setStyleSheet(f"color: {COLOR_EVEN};")
        else:
            self.lbl_streak.setText("-")
        self.lbl_longest_odd.setText(str(s.longest_odd_streak))
        self.lbl_longest_even.setText(str(s.longest_even_streak))
        self.lbl_alt.setText(str(s.current_alternation_len))

    def update_ai_signal(self, prediction) -> None:
        """更新 AI 信号横幅（含预测区块号，带字段防御）."""
        if prediction is None:
            self._ai_label.setText("AI: 等待首批数据...")
            self._ai_label.setStyleSheet(
                f"color: {COLOR_SUB}; font-size: 12px; padding: 6px 10px; "
                f"background: #1C232C; border-radius: 4px;"
            )
            return

        best = getattr(prediction, "best", None)
        has_signal = bool(getattr(prediction, "has_signal", False))
        reason = getattr(prediction, "reason", "") or ""

        # 即便没有高置信度，也展示当前预测方向和置信度（灰色显示）
        if best is None:
            text = f"AI: 暂无预测（{reason})" if reason else "AI: 暂无预测"
            self._ai_label.setText(text)
            self._ai_label.setStyleSheet(
                f"color: {COLOR_SUB}; font-size: 12px; padding: 6px 10px; "
                f"background: #1C232C; border-radius: 4px;"
            )
            return

        label = getattr(best, "label", "?")
        confidence_pct = getattr(best, "confidence_pct", "-")
        model = getattr(best, "model", "-")
        prediction_dir = getattr(best, "prediction", "")
        block_num = (
            getattr(best, "next_block_number", None)
            or getattr(prediction, "next_block_number", None)
            or 0
        )
        block_text = f" | 预测区块 #{block_num}" if block_num else ""

        if has_signal:
            color = COLOR_ODD if prediction_dir == "odd" else COLOR_EVEN
            self._ai_label.setText(
                f"AI 预测下期: {label} | 置信度 {confidence_pct} | {model}{block_text}"
            )
            self._ai_label.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: bold; padding: 6px 10px; "
                f"background: #1C232C; border: 1px solid {color}; border-radius: 4px;"
            )
        else:
            # 低置信度：也显示出来，但用灰色提示
            note = f" ({reason})" if reason else ""
            self._ai_label.setText(
                f"AI 观察中: 倾向 {label} | 置信度 {confidence_pct}{note}"
            )
            self._ai_label.setStyleSheet(
                f"color: {COLOR_SUB}; font-size: 12px; padding: 6px 10px; "
                f"background: #1C232C; border-radius: 4px;"
            )

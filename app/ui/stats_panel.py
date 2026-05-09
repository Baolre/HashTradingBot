"""UI 组件。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..core.analyzer import Analyzer, PARITY_EVEN, PARITY_ODD
from .theme import COLOR_EVEN, COLOR_ODD, COLOR_SUB


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


class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 指标区
        grp = QGroupBox("实时统计")
        grid = QGridLayout(grp)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)

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
            f.setPointSize(14)
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

        root.addWidget(grp)

        # 最近期数表
        grp2 = QGroupBox("最近 20 期")
        inner = QVBoxLayout(grp2)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["区块号", "单/双", "末位数字", "区块哈希"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        inner.addWidget(self.table)
        root.addWidget(grp2, 1)

    # -------------- 刷新 --------------
    def refresh(self, analyzer: Analyzer) -> None:
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
        last = list(reversed(last))  # 最新在上
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

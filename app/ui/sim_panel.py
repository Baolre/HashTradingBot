"""模拟下注面板（纯单双）."""
from __future__ import annotations
from typing import List
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                                QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from ..core.simulator import BetRecord, SimState
from ..utils.config import SimConfig
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_SUB


class BalanceCurve(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[float] = []
        self.setMinimumHeight(100)

    def set_data(self, data: List[float]) -> None:
        self._data = data; self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLOR_BG))
        if len(self._data) < 2:
            p.setPen(QColor(COLOR_SUB)); p.drawText(self.rect(), Qt.AlignCenter, "等待数据..."); return
        w, h = self.width() - 20, self.height() - 20
        mn, mx = min(self._data), max(self._data)
        if mx == mn: mx = mn + 1
        step = w / max(1, len(self._data) - 1)
        pts = [(10 + i * step, 10 + h - (v - mn) / (mx - mn) * h) for i, v in enumerate(self._data)]
        color = QColor(COLOR_EVEN) if self._data[-1] >= self._data[0] else QColor(COLOR_ODD)
        p.setPen(QPen(color, 2))
        for i in range(len(pts) - 1):
            p.drawLine(int(pts[i][0]), int(pts[i][1]), int(pts[i+1][0]), int(pts[i+1][1]))


class SimPanel(QWidget):
    config_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(12, 12, 12, 12)
        grp = QGroupBox("策略配置")
        form = QFormLayout(grp)
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems(["平注", "马丁格尔", "达朗贝尔", "斐波那契", "帕罗利", "凯利"])
        form.addRow("策略:", self.combo_strategy)
        self.combo_target = QComboBox()
        self.combo_target.addItems(["跟走势", "反上期", "跟长龙", "AI信号"])
        form.addRow("目标:", self.combo_target)
        self.sp_initial = QDoubleSpinBox(); self.sp_initial.setRange(100, 1000000); self.sp_initial.setValue(10000)
        form.addRow("初始资金:", self.sp_initial)
        self.sp_base = QDoubleSpinBox(); self.sp_base.setRange(1, 100000); self.sp_base.setValue(100)
        form.addRow("基础注:", self.sp_base)
        self.sp_max = QDoubleSpinBox(); self.sp_max.setRange(10, 1000000); self.sp_max.setValue(5000)
        form.addRow("最大注:", self.sp_max)
        root.addWidget(grp)
        btns = QHBoxLayout()
        self.btn_start = QPushButton("开始模拟"); self.btn_stop = QPushButton("停止"); self.btn_stop.setEnabled(False)
        self.btn_reset = QPushButton("重置")
        btns.addWidget(self.btn_start); btns.addWidget(self.btn_stop); btns.addWidget(self.btn_reset); btns.addStretch()
        root.addLayout(btns)
        stats = QHBoxLayout()
        self.lbl_balance = QLabel("¥10000"); self.lbl_pnl = QLabel("¥0"); self.lbl_win_rate = QLabel("0%")
        for lbl in (self.lbl_balance, self.lbl_pnl, self.lbl_win_rate):
            f2 = lbl.font(); f2.setBold(True); f2.setPointSize(13); lbl.setFont(f2)
        stats.addWidget(QLabel("余额:")); stats.addWidget(self.lbl_balance)
        stats.addWidget(QLabel("盈亏:")); stats.addWidget(self.lbl_pnl)
        stats.addWidget(QLabel("胜率:")); stats.addWidget(self.lbl_win_rate); stats.addStretch()
        root.addLayout(stats)
        self.curve = BalanceCurve()
        root.addWidget(self.curve)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["区块号", "下注", "目标", "盈亏", "余额"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumHeight(180)
        root.addWidget(self.table)
        root.addStretch()

    def refresh(self, state: SimState) -> None:
        self.lbl_balance.setText(f"¥{state.balance:.0f}")
        initial = self.sp_initial.value()
        pnl = state.balance - initial
        self.lbl_pnl.setText(f"{'+'if pnl>=0 else ''}{pnl:.0f}")
        self.lbl_pnl.setStyleSheet(f"color: {COLOR_EVEN if pnl >= 0 else COLOR_ODD};")
        self.lbl_win_rate.setText(f"{state.win_rate*100:.1f}%")
        # 更新曲线起始值显示
        if state.total_bets == 0:
            self.lbl_balance.setText(f"¥{initial:.0f}")
            self.lbl_pnl.setText("¥0")

    def update_curve(self, data: List[float]) -> None:
        self.curve.set_data(data)

    def append_record(self, r: BetRecord) -> None:
        self.table.insertRow(0)
        self.table.setItem(0, 0, QTableWidgetItem(str(r.period_num)))
        self.table.setItem(0, 1, QTableWidgetItem(f"¥{r.bet_amount:.0f}"))
        self.table.setItem(0, 2, QTableWidgetItem("单" if r.bet_target == "odd" else "双"))
        pnl_item = QTableWidgetItem(f"{'+'if r.pnl>=0 else ''}{r.pnl:.0f}")
        pnl_item.setForeground(QColor(COLOR_EVEN if r.won else COLOR_ODD))
        self.table.setItem(0, 3, pnl_item)
        self.table.setItem(0, 4, QTableWidgetItem(f"¥{r.balance_after:.0f}"))
        while self.table.rowCount() > 50:
            self.table.removeRow(self.table.rowCount() - 1)

    def collect_config(self) -> SimConfig:
        strats = ["flat", "martingale", "dalembert", "fibonacci", "paroli", "kelly"]
        targets = ["follow_trend", "reverse", "follow_dragon", "ai"]
        return SimConfig(initial_balance=self.sp_initial.value(), base_bet=self.sp_base.value(),
                         max_bet=self.sp_max.value(), strategy=strats[self.combo_strategy.currentIndex()],
                         target=targets[self.combo_target.currentIndex()])

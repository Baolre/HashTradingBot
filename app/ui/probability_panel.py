"""AI 信号面板 - 展示预测详情、各模型置信度、转移矩阵、数字频率."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QProgressBar,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core.analyzer import PARITY_EVEN, PARITY_ODD
from .theme import COLOR_EVEN, COLOR_ODD, COLOR_SUB


def _big_label(text: str = "-", color: str = "") -> QLabel:
    lbl = QLabel(text)
    f = lbl.font(); f.setPointSize(18); f.setBold(True); lbl.setFont(f)
    if color:
        lbl.setStyleSheet(f"color: {color};")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class ProbabilityPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # 顶部：集成预测
        top = QGroupBox("综合 AI 预测")
        top_lay = QGridLayout(top)
        self.lbl_direction = _big_label("-")
        self.lbl_conf_pct = _big_label("-")
        self.lbl_reason = QLabel("-")
        self.lbl_reason.setStyleSheet(f"color: {COLOR_SUB};")
        self.lbl_reason.setWordWrap(True)

        self.bar_conf = QProgressBar()
        self.bar_conf.setRange(0, 100)
        self.bar_conf.setValue(0)
        self.bar_conf.setTextVisible(True)

        top_lay.addWidget(QLabel("方向:"), 0, 0)
        top_lay.addWidget(self.lbl_direction, 0, 1)
        top_lay.addWidget(QLabel("置信度:"), 0, 2)
        top_lay.addWidget(self.lbl_conf_pct, 0, 3)
        top_lay.addWidget(self.bar_conf, 1, 0, 1, 4)
        top_lay.addWidget(QLabel("说明:"), 2, 0)
        top_lay.addWidget(self.lbl_reason, 2, 1, 1, 3)
        root.addWidget(top)

        # 中部：各模型信号
        mid = QGroupBox("各模型信号")
        mid_lay = QVBoxLayout(mid)
        self.tbl_signals = QTableWidget(0, 3)
        self.tbl_signals.setHorizontalHeaderLabels(["模型", "预测方向", "置信度"])
        self.tbl_signals.horizontalHeader().setStretchLastSection(True)
        self.tbl_signals.verticalHeader().setVisible(False)
        self.tbl_signals.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_signals.setSelectionMode(QTableWidget.NoSelection)
        mid_lay.addWidget(self.tbl_signals)
        root.addWidget(mid)

        # 底部：单步转移矩阵 + 数字频率
        bottom = QHBoxLayout()

        grp_mx = QGroupBox("单步转移矩阵 (P(next | cur))")
        mx_lay = QVBoxLayout(grp_mx)
        self.tbl_matrix = QTableWidget(2, 2)
        self.tbl_matrix.setHorizontalHeaderLabels(["→ 单", "→ 双"])
        self.tbl_matrix.setVerticalHeaderLabels(["当前单", "当前双"])
        self.tbl_matrix.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_matrix.setSelectionMode(QTableWidget.NoSelection)
        mx_lay.addWidget(self.tbl_matrix)
        bottom.addWidget(grp_mx, 1)

        grp_freq = QGroupBox("末位数字频率（近 50 期）")
        freq_lay = QVBoxLayout(grp_freq)
        self.tbl_freq = QTableWidget(1, 10)
        self.tbl_freq.setHorizontalHeaderLabels([str(i) for i in range(10)])
        self.tbl_freq.setVerticalHeaderLabels(["次数"])
        self.tbl_freq.horizontalHeader().setStretchLastSection(False)
        self.tbl_freq.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_freq.setSelectionMode(QTableWidget.NoSelection)
        freq_lay.addWidget(self.tbl_freq)
        bottom.addWidget(grp_freq, 2)

        root.addLayout(bottom)
        root.addStretch()

    # ---------------- 刷新 ----------------
    def refresh(self, analyzer, prediction) -> None:
        # 1) 综合预测
        best = getattr(prediction, "best", None) if prediction is not None else None
        reason = getattr(prediction, "reason", "") if prediction is not None else ""
        has = bool(getattr(prediction, "has_signal", False)) if prediction is not None else False

        if best is None:
            self.lbl_direction.setText("-")
            self.lbl_direction.setStyleSheet("")
            self.lbl_conf_pct.setText("-")
            self.bar_conf.setValue(0)
            self.lbl_reason.setText(reason or "等待数据...")
        else:
            direction = getattr(best, "prediction", "")
            label = getattr(best, "label", "-")
            conf = float(getattr(best, "confidence", 0.0))
            color = COLOR_ODD if direction == PARITY_ODD else COLOR_EVEN
            self.lbl_direction.setText(label)
            self.lbl_direction.setStyleSheet(f"color: {color};")
            self.lbl_conf_pct.setText(f"{conf * 100:.1f}%")
            self.bar_conf.setValue(int(conf * 100))
            self.lbl_reason.setText(
                reason or ("高置信度信号已触发" if has else "当前为观察区间")
            )

        # 2) 各模型表格
        signals = list(getattr(prediction, "signals", []) or []) if prediction is not None else []
        self.tbl_signals.setRowCount(len(signals))
        for i, s in enumerate(signals):
            self.tbl_signals.setItem(i, 0, QTableWidgetItem(getattr(s, "model", "-")))
            pred = getattr(s, "prediction", "")
            lbl_cell = QTableWidgetItem(getattr(s, "label", "-"))
            if pred == PARITY_ODD:
                lbl_cell.setForeground(Qt.red)
            elif pred == PARITY_EVEN:
                lbl_cell.setForeground(Qt.green)
            lbl_cell.setTextAlignment(Qt.AlignCenter)
            self.tbl_signals.setItem(i, 1, lbl_cell)
            self.tbl_signals.setItem(i, 2, QTableWidgetItem(getattr(s, "confidence_pct", "-")))

        # 3) 转移矩阵
        try:
            mx = analyzer.get_transition_matrix(window=50)
        except Exception:
            mx = {}
        rows = [PARITY_ODD, PARITY_EVEN]
        cols = [PARITY_ODD, PARITY_EVEN]
        for i, r in enumerate(rows):
            for j, c in enumerate(cols):
                v = mx.get(r, {}).get(c, 0.0)
                cell = QTableWidgetItem(f"{v*100:.1f}%")
                cell.setTextAlignment(Qt.AlignCenter)
                self.tbl_matrix.setItem(i, j, cell)

        # 4) 数字频率
        try:
            dist = analyzer.frequency_distribution(window=50)
        except Exception:
            dist = {i: 0 for i in range(10)}
        for i in range(10):
            cell = QTableWidgetItem(str(dist.get(i, 0)))
            cell.setTextAlignment(Qt.AlignCenter)
            self.tbl_freq.setItem(0, i, cell)

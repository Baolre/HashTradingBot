"""AI 信号面板 - 展示预测详情、历史命中率、转移矩阵、数字频率."""
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

        # 历史命中率统计
        grp_acc = QGroupBox("历史命中率统计")
        acc_lay = QVBoxLayout(grp_acc)
        self.tbl_acc = QTableWidget(0, 8)
        self.tbl_acc.setHorizontalHeaderLabels([
            "模型", "总样本", "命中率", "对/错", "当前连续", "最大连对", "最大连错", "高置信命中率"
        ])
        self.tbl_acc.horizontalHeader().setStretchLastSection(True)
        self.tbl_acc.verticalHeader().setVisible(False)
        self.tbl_acc.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_acc.setSelectionMode(QTableWidget.NoSelection)
        self.tbl_acc.setMinimumHeight(110)
        acc_lay.addWidget(self.tbl_acc)
        root.addWidget(grp_acc)

        # 中部：各模型信号
        mid = QGroupBox("各模型当前信号")
        mid_lay = QVBoxLayout(mid)
        self.tbl_signals = QTableWidget(0, 3)
        self.tbl_signals.setHorizontalHeaderLabels(["模型", "预测方向", "置信度"])
        self.tbl_signals.horizontalHeader().setStretchLastSection(True)
        self.tbl_signals.verticalHeader().setVisible(False)
        self.tbl_signals.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_signals.setSelectionMode(QTableWidget.NoSelection)
        mid_lay.addWidget(self.tbl_signals)
        root.addWidget(mid)

        # 最近预测 vs 实际
        grp_recent = QGroupBox("最近预测 vs 实际（ensemble）")
        recent_lay = QVBoxLayout(grp_recent)
        self.tbl_recent = QTableWidget(0, 4)
        self.tbl_recent.setHorizontalHeaderLabels(["#", "预测", "实际", "置信度"])
        self.tbl_recent.horizontalHeader().setStretchLastSection(True)
        self.tbl_recent.verticalHeader().setVisible(False)
        self.tbl_recent.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_recent.setSelectionMode(QTableWidget.NoSelection)
        self.tbl_recent.setMinimumHeight(160)
        recent_lay.addWidget(self.tbl_recent)
        root.addWidget(grp_recent)

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
    def refresh(self, analyzer, prediction, tracker=None) -> None:
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

        # 2) 历史命中率
        self._refresh_accuracy(tracker)

        # 3) 各模型当前信号
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

        # 4) 最近预测 vs 实际
        self._refresh_recent(tracker)

        # 5) 转移矩阵
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

        # 6) 数字频率
        try:
            dist = analyzer.frequency_distribution(window=50)
        except Exception:
            dist = {i: 0 for i in range(10)}
        for i in range(10):
            cell = QTableWidgetItem(str(dist.get(i, 0)))
            cell.setTextAlignment(Qt.AlignCenter)
            self.tbl_freq.setItem(0, i, cell)

    # ---------------- 辅助 ----------------
    def _refresh_accuracy(self, tracker) -> None:
        if tracker is None:
            self.tbl_acc.setRowCount(0)
            return
        stats_map = tracker.all_stats()
        # 固定显示顺序：ensemble, markov, frequency，其余按字母
        ordered_keys = []
        for k in ("ensemble", "markov", "frequency"):
            if k in stats_map:
                ordered_keys.append(k)
        for k in sorted(stats_map.keys()):
            if k not in ordered_keys:
                ordered_keys.append(k)

        self.tbl_acc.setRowCount(len(ordered_keys))
        for i, k in enumerate(ordered_keys):
            st = stats_map[k]
            self.tbl_acc.setItem(i, 0, self._cell(k))
            self.tbl_acc.setItem(i, 1, self._cell(str(st.total)))
            self.tbl_acc.setItem(i, 2, self._cell(st.accuracy_pct))
            self.tbl_acc.setItem(i, 3, self._cell(f"{st.correct} / {st.wrong}"))
            streak_cell = self._cell(st.current_streak_label)
            if st.current_streak > 0:
                streak_cell.setForeground(Qt.green)
            elif st.current_streak < 0:
                streak_cell.setForeground(Qt.red)
            self.tbl_acc.setItem(i, 4, streak_cell)
            self.tbl_acc.setItem(i, 5, self._cell(str(st.max_correct_streak)))
            self.tbl_acc.setItem(i, 6, self._cell(str(st.max_wrong_streak)))
            hc_text = f"{st.hc_accuracy_pct} ({st.hc_total})" if st.hc_total else "-"
            self.tbl_acc.setItem(i, 7, self._cell(hc_text))

    def _refresh_recent(self, tracker) -> None:
        if tracker is None:
            self.tbl_recent.setRowCount(0)
            return
        records = [r for r in tracker.recent(50) if r.model == "ensemble"]
        # 倒序：最新在上
        records = list(reversed(records))
        self.tbl_recent.setRowCount(len(records))
        for i, r in enumerate(records):
            self.tbl_recent.setItem(i, 0, self._cell(str(i + 1)))
            pred_cell = self._cell(r.pred_label)
            if r.prediction == PARITY_ODD:
                pred_cell.setForeground(Qt.red)
            elif r.prediction == PARITY_EVEN:
                pred_cell.setForeground(Qt.green)
            self.tbl_recent.setItem(i, 1, pred_cell)
            actual_cell = self._cell(r.actual_label)
            if r.actual == PARITY_ODD:
                actual_cell.setForeground(Qt.red)
            elif r.actual == PARITY_EVEN:
                actual_cell.setForeground(Qt.green)
            self.tbl_recent.setItem(i, 2, actual_cell)
            conf_text = f"{r.confidence * 100:.1f}%"
            if r.has_signal:
                conf_text += " ★"
            conf_cell = self._cell(conf_text)
            # 对错着色整行背景太重，只给置信度列
            if r.correct is True:
                conf_cell.setForeground(Qt.green)
            elif r.correct is False:
                conf_cell.setForeground(Qt.red)
            self.tbl_recent.setItem(i, 3, conf_cell)

    @staticmethod
    def _cell(text: str) -> QTableWidgetItem:
        cell = QTableWidgetItem(text)
        cell.setTextAlignment(Qt.AlignCenter)
        return cell

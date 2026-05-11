"""Dashboard - 一屏聚合所有核心信息（除设置）."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QPushButton, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core.analyzer import PARITY_EVEN, PARITY_ODD, Analyzer
from ..core.alerter import AlertEvent
from ..storage.db import AlertRow
from .theme import COLOR_BORDER, COLOR_EVEN, COLOR_ODD, COLOR_SUB, COLOR_TEXT
from .trend_view import BeadBoard


# ==================== 通用卡片 ====================

class Card(QFrame):
    """通用卡片容器（深色 + 圆角 + 可选标题 + 右侧角落组件）."""

    def __init__(self, title: str = "", corner_widget: Optional[QWidget] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 12, 16, 14)
        self._layout.setSpacing(10)

        if title:
            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            head.setSpacing(8)
            lbl = QLabel(title)
            lbl.setObjectName("cardTitle")
            head.addWidget(lbl)
            head.addStretch()
            if corner_widget is not None:
                head.addWidget(corner_widget)
            self._layout.addLayout(head)

    def body(self) -> QVBoxLayout:
        return self._layout


def _cell(text: str, align=Qt.AlignCenter, color: Optional[str] = None) -> QTableWidgetItem:
    cell = QTableWidgetItem(text)
    cell.setTextAlignment(align)
    if color == "odd":
        cell.setForeground(Qt.red)
    elif color == "even":
        cell.setForeground(Qt.green)
    return cell


# ==================== AI 预测卡 ====================

class AICard(Card):
    """AI 预测卡：大方向 + 置信度进度条 + 各模型小表."""

    def __init__(self, parent=None):
        super().__init__("AI 预测", parent=parent)
        body = self.body()

        # 上半：方向 + 置信度
        top = QHBoxLayout()
        top.setSpacing(16)

        dir_box = QVBoxLayout(); dir_box.setSpacing(2)
        self.lbl_direction_cap = QLabel("下期方向")
        self.lbl_direction_cap.setObjectName("metricLabel")
        self.lbl_direction = QLabel("-")
        self.lbl_direction.setObjectName("bigNumber")
        dir_box.addWidget(self.lbl_direction_cap)
        dir_box.addWidget(self.lbl_direction)
        top.addLayout(dir_box)

        top.addSpacing(8)

        conf_box = QVBoxLayout(); conf_box.setSpacing(4)
        head = QHBoxLayout()
        cap = QLabel("置信度"); cap.setObjectName("metricLabel")
        self.lbl_conf_pct = QLabel("-")
        self.lbl_conf_pct.setStyleSheet("font-size: 16px; font-weight: bold;")
        head.addWidget(cap); head.addStretch(); head.addWidget(self.lbl_conf_pct)
        conf_box.addLayout(head)
        self.bar_conf = QProgressBar()
        self.bar_conf.setRange(0, 100); self.bar_conf.setValue(0); self.bar_conf.setTextVisible(False)
        conf_box.addWidget(self.bar_conf)
        top.addLayout(conf_box, 1)

        body.addLayout(top)

        # 中：理由说明
        self.lbl_reason = QLabel("等待数据...")
        self.lbl_reason.setObjectName("mutedSmall")
        self.lbl_reason.setWordWrap(True)
        body.addWidget(self.lbl_reason)

        # 下：各模型小表
        self.tbl_models = QTableWidget(0, 3)
        self.tbl_models.setHorizontalHeaderLabels(["模型", "方向", "置信度"])
        self.tbl_models.horizontalHeader().setStretchLastSection(True)
        self.tbl_models.verticalHeader().setVisible(False)
        self.tbl_models.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_models.setSelectionMode(QTableWidget.NoSelection)
        self.tbl_models.setFixedHeight(130)
        body.addWidget(self.tbl_models)

    def update_prediction(self, prediction) -> None:
        best = getattr(prediction, "best", None) if prediction is not None else None
        reason = getattr(prediction, "reason", "") if prediction is not None else ""
        has = bool(getattr(prediction, "has_signal", False)) if prediction is not None else False

        if best is None:
            self.lbl_direction.setText("-")
            self.lbl_direction.setStyleSheet("font-size: 28px; font-weight: bold;")
            self.lbl_conf_pct.setText("-")
            self.lbl_conf_pct.setStyleSheet(f"color: {COLOR_SUB}; font-size: 16px; font-weight: bold;")
            self.bar_conf.setValue(0)
            self.lbl_reason.setText(reason or "等待数据...")
        else:
            direction = getattr(best, "prediction", "")
            label = getattr(best, "label", "-")
            conf = float(getattr(best, "confidence", 0.0))
            color = COLOR_ODD if direction == PARITY_ODD else COLOR_EVEN
            self.lbl_direction.setText(label)
            self.lbl_direction.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color};")
            self.lbl_conf_pct.setText(f"{conf * 100:.1f}%")
            self.lbl_conf_pct.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            self.bar_conf.setValue(int(conf * 100))
            # 动态设置 chunk 颜色
            self.bar_conf.setStyleSheet(
                f"QProgressBar {{ background: #1C232C; border: 1px solid {COLOR_BORDER}; "
                f"border-radius: 6px; height: 10px; }} "
                f"QProgressBar::chunk {{ background: {color}; border-radius: 5px; }}"
            )
            self.lbl_reason.setText(
                reason or ("高置信度信号已触发" if has else "当前为观察区间")
            )

        # 各模型
        signals = list(getattr(prediction, "signals", []) or []) if prediction is not None else []
        self.tbl_models.setRowCount(len(signals))
        for i, s in enumerate(signals):
            self.tbl_models.setItem(i, 0, _cell(getattr(s, "model", "-"), Qt.AlignLeft | Qt.AlignVCenter))
            pred = getattr(s, "prediction", "")
            color_key = "odd" if pred == PARITY_ODD else ("even" if pred == PARITY_EVEN else None)
            self.tbl_models.setItem(i, 1, _cell(getattr(s, "label", "-"), color=color_key))
            self.tbl_models.setItem(i, 2, _cell(getattr(s, "confidence_pct", "-")))


# ==================== 命中率卡 ====================

class AccuracyCard(Card):
    """历史命中率：ensemble / markov / frequency 一张表."""

    def __init__(self, parent=None):
        super().__init__("历史命中率", parent=parent)
        body = self.body()

        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels([
            "模型", "样本", "命中率", "对/错", "当前", "最大连对", "最大连错"
        ])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionMode(QTableWidget.NoSelection)
        self.tbl.setMinimumHeight(120)
        body.addWidget(self.tbl)

        # 底部高置信度小字说明
        self.lbl_hint = QLabel("")
        self.lbl_hint.setObjectName("mutedSmall")
        body.addWidget(self.lbl_hint)

    def update_tracker(self, tracker) -> None:
        if tracker is None:
            self.tbl.setRowCount(0)
            self.lbl_hint.setText("")
            return

        stats_map = tracker.all_stats()
        order = []
        for k in ("ensemble", "markov", "frequency"):
            if k in stats_map:
                order.append(k)
        for k in sorted(stats_map.keys()):
            if k not in order:
                order.append(k)

        self.tbl.setRowCount(len(order))
        hc_summary = ""
        for i, k in enumerate(order):
            st = stats_map[k]
            self.tbl.setItem(i, 0, _cell(k, Qt.AlignLeft | Qt.AlignVCenter))
            self.tbl.setItem(i, 1, _cell(str(st.total)))
            acc_cell = _cell(st.accuracy_pct)
            if st.total >= 10:
                if st.accuracy >= 0.55:
                    acc_cell.setForeground(Qt.green)
                elif st.accuracy < 0.45:
                    acc_cell.setForeground(Qt.red)
            self.tbl.setItem(i, 2, acc_cell)
            self.tbl.setItem(i, 3, _cell(f"{st.correct} / {st.wrong}"))
            streak = _cell(st.current_streak_label)
            if st.current_streak > 0: streak.setForeground(Qt.green)
            elif st.current_streak < 0: streak.setForeground(Qt.red)
            self.tbl.setItem(i, 4, streak)
            self.tbl.setItem(i, 5, _cell(str(st.max_correct_streak)))
            self.tbl.setItem(i, 6, _cell(str(st.max_wrong_streak)))

            if k == "ensemble" and st.hc_total:
                hc_summary = (
                    f"高置信度预测：{st.hc_total} 次 | 命中率 {st.hc_accuracy_pct} "
                    f"| 最大连对 {st.hc_max_correct_streak} | 最大连错 {st.hc_max_wrong_streak}"
                )
        self.lbl_hint.setText(hc_summary or "尚无高置信度预测记录")


# ==================== 走势 + AI Banner 卡 ====================

class TrendCard(Card):
    """走势卡：顶部 AI banner + 珠盘 + 右上角单双计数 chip."""

    def __init__(self, column_max=6, dot_size=28, column_gap=6, parent=None):
        # 自带右上角 chip 组
        self.chip_even = QLabel("双  0")
        self.chip_odd = QLabel("单  0")
        self.chip_even.setObjectName("chipIdle")
        self.chip_odd.setObjectName("chipIdle")

        chips = QWidget()
        cl = QHBoxLayout(chips); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(6)
        cl.addWidget(self.chip_even); cl.addWidget(self.chip_odd)

        super().__init__("走势  ·  最新在最右", corner_widget=chips, parent=parent)
        body = self.body()

        # AI banner
        self.lbl_ai = QLabel("AI: 等待数据...")
        self.lbl_ai.setWordWrap(True)
        self.lbl_ai.setStyleSheet(
            "padding: 10px 14px; background: #1C232C; border-radius: 8px; "
            "border: 1px solid #232C38; font-size: 12px;"
        )
        body.addWidget(self.lbl_ai)

        # 珠盘 + 横向滚动
        from PySide6.QtCore import Qt as _Qt, QTimer as _QTimer  # noqa
        from PySide6.QtWidgets import QScrollArea

        self.board = BeadBoard(column_max=column_max, dot_size=dot_size, column_gap=column_gap)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.board)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: 1px solid #232C38; "
            "border-radius: 8px; }"
        )
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll.setMinimumHeight(self.board._min_height + 24)
        self.scroll.viewport().installEventFilter(self)
        body.addWidget(self.scroll, 1)

    # ---------- public ----------
    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport() and event.type() == event.Type.Resize:
            self.board.set_viewport_width(self.scroll.viewport().width())
            self._scroll_to_right()
        return super().eventFilter(obj, event)

    def _scroll_to_right(self) -> None:
        from PySide6.QtCore import QTimer
        def _go():
            bar = self.scroll.horizontalScrollBar()
            bar.setValue(bar.maximum())
        QTimer.singleShot(0, _go)
        QTimer.singleShot(80, _go)

    def apply_periods(self, periods, odd_total, even_total) -> None:
        self.board.set_viewport_width(self.scroll.viewport().width())
        self.board.set_periods(periods)
        self._update_chips(odd_total, even_total)
        self._scroll_to_right()

    def on_new_period(self, period, odd_total, even_total) -> None:
        self.board.set_viewport_width(self.scroll.viewport().width())
        self.board.append(period)
        self._update_chips(odd_total, even_total)
        self._scroll_to_right()

    def _update_chips(self, odd_total: int, even_total: int) -> None:
        self.chip_even.setText(f"双  {even_total}")
        self.chip_odd.setText(f"单  {odd_total}")
        self.chip_even.setStyleSheet(
            f"color: {COLOR_EVEN}; background: rgba(34,160,107,0.12); "
            f"border: 1px solid rgba(34,160,107,0.3); border-radius: 10px; "
            f"padding: 3px 12px; font-weight: bold; font-size: 11px;"
        )
        self.chip_odd.setStyleSheet(
            f"color: {COLOR_ODD}; background: rgba(229,62,62,0.12); "
            f"border: 1px solid rgba(229,62,62,0.3); border-radius: 10px; "
            f"padding: 3px 12px; font-weight: bold; font-size: 11px;"
        )

    def update_ai_signal(self, prediction) -> None:
        if prediction is None:
            self.lbl_ai.setText("AI: 等待首批数据...")
            self.lbl_ai.setStyleSheet(
                "padding: 10px 14px; background: #1C232C; border-radius: 8px; "
                "border: 1px solid #232C38; font-size: 12px; color: " + COLOR_SUB + ";"
            )
            return

        best = getattr(prediction, "best", None)
        has_signal = bool(getattr(prediction, "has_signal", False))
        reason = getattr(prediction, "reason", "") or ""

        if best is None:
            self.lbl_ai.setText(f"AI: 暂无预测" + (f"（{reason}）" if reason else ""))
            self.lbl_ai.setStyleSheet(
                "padding: 10px 14px; background: #1C232C; border-radius: 8px; "
                "border: 1px solid #232C38; font-size: 12px; color: " + COLOR_SUB + ";"
            )
            return

        label = getattr(best, "label", "?")
        conf_pct = getattr(best, "confidence_pct", "-")
        model = getattr(best, "model", "-")
        dir_ = getattr(best, "prediction", "")
        block_num = (
            getattr(best, "next_block_number", None)
            or getattr(prediction, "next_block_number", None)
            or 0
        )
        block_text = f"  ·  预测区块 #{block_num}" if block_num else ""
        color = COLOR_ODD if dir_ == PARITY_ODD else COLOR_EVEN

        if has_signal:
            self.lbl_ai.setText(
                f"<b>AI 预测下期：{label}</b>  置信度 {conf_pct}  ·  模型 {model}{block_text}"
            )
            self.lbl_ai.setStyleSheet(
                f"padding: 10px 14px; background: rgba(59,130,246,0.08); border-radius: 8px; "
                f"border: 1px solid {color}; font-size: 12px; color: {color};"
            )
        else:
            note = f"（{reason}）" if reason else ""
            self.lbl_ai.setText(
                f"AI 观察中：倾向 <b>{label}</b>  置信度 {conf_pct}{note}"
            )
            self.lbl_ai.setStyleSheet(
                f"padding: 10px 14px; background: #1C232C; border-radius: 8px; "
                f"border: 1px solid #232C38; font-size: 12px; color: {COLOR_SUB};"
            )


# ==================== 指标栏（多个 metric 卡的组合） ====================

class MetricStrip(QFrame):
    """横向 8 个指标：总期数 / 单 / 双 / 占比 / 当前连号 / 最长单连 / 最长双连 / 交叉长度."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QGridLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setHorizontalSpacing(22)
        lay.setVerticalSpacing(2)

        self._values = {}
        self._labels = {}
        specs = [
            ("total",       "总期数"),
            ("odd",         "单"),
            ("even",        "双"),
            ("ratio",       "单/双占比"),
            ("streak",      "当前连号"),
            ("longest_odd", "最长单连"),
            ("longest_even","最长双连"),
            ("alt",         "当前交叉"),
        ]
        for i, (key, cap) in enumerate(specs):
            val = QLabel("-")
            val.setObjectName("metricValue")
            lbl = QLabel(cap)
            lbl.setObjectName("metricLabel")
            lay.addWidget(val, 0, i)
            lay.addWidget(lbl, 1, i)
            lay.setColumnStretch(i, 1)
            self._values[key] = val
            self._labels[key] = lbl

        # 单/双上色
        self._values["odd"].setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLOR_ODD};")
        self._values["even"].setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLOR_EVEN};")

    def refresh(self, analyzer: Analyzer) -> None:
        s = analyzer.stats
        self._values["total"].setText(str(s.total))
        self._values["odd"].setText(str(s.odd_total))
        self._values["even"].setText(str(s.even_total))
        if s.total:
            self._values["ratio"].setText(
                f"{s.odd_total*100//s.total}% / {s.even_total*100//s.total}%"
            )
        else:
            self._values["ratio"].setText("-")

        if s.current_streak_parity == PARITY_ODD:
            self._values["streak"].setText(f"单×{s.current_streak_len}")
            self._values["streak"].setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {COLOR_ODD};"
            )
        elif s.current_streak_parity == PARITY_EVEN:
            self._values["streak"].setText(f"双×{s.current_streak_len}")
            self._values["streak"].setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {COLOR_EVEN};"
            )
        else:
            self._values["streak"].setText("-")
            self._values["streak"].setStyleSheet(
                "font-size: 22px; font-weight: bold;"
            )
        self._values["longest_odd"].setText(str(s.longest_odd_streak))
        self._values["longest_even"].setText(str(s.longest_even_streak))
        self._values["alt"].setText(str(s.current_alternation_len))


# ==================== 最近开奖对照表 ====================

class RecentBlocksCard(Card):
    """最近 N 期的：区块号 / 末位 / 实际 / AI 预测 / 置信度 / 命中."""

    def __init__(self, parent=None):
        super().__init__("最近开奖 & AI 对照（上 = 最新）", parent=parent)
        body = self.body()

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["区块号", "末位", "实际", "AI 预测", "置信度", "命中"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionMode(QTableWidget.NoSelection)
        body.addWidget(self.tbl)

    def refresh(self, analyzer: Analyzer, tracker) -> None:
        periods = list(reversed(analyzer.last(40)))  # 最新在上
        rec_list = []
        if tracker is not None:
            rec_list = [r for r in tracker.recent(200) if r.model == "ensemble"]
        self.tbl.setRowCount(len(periods))
        for row_i, p in enumerate(periods):
            # 区块号
            self.tbl.setItem(row_i, 0, _cell(str(p.block_number), Qt.AlignLeft | Qt.AlignVCenter))
            # 末位
            self.tbl.setItem(row_i, 1, _cell("-" if p.digit is None else str(p.digit)))
            # 实际
            color_actual = "odd" if p.parity == PARITY_ODD else ("even" if p.parity == PARITY_EVEN else None)
            self.tbl.setItem(row_i, 2, _cell(p.parity_label, color=color_actual))
            # AI 预测 + 置信度 + 命中
            rec = rec_list[-row_i - 1] if row_i < len(rec_list) else None
            if rec is not None:
                color_pred = "odd" if rec.prediction == PARITY_ODD else ("even" if rec.prediction == PARITY_EVEN else None)
                pred_text = rec.pred_label + (" ★" if rec.has_signal else "")
                self.tbl.setItem(row_i, 3, _cell(pred_text, color=color_pred))
                # 置信度列
                conf_text = f"{rec.confidence * 100:.0f}%"
                conf_cell = _cell(conf_text)
                if rec.confidence >= 0.70:
                    conf_cell.setForeground(Qt.green)
                elif rec.confidence >= 0.60:
                    conf_cell.setForeground(Qt.yellow)
                self.tbl.setItem(row_i, 4, conf_cell)
                # 命中列
                if rec.correct is True:
                    mark = _cell("✓")
                    mark.setForeground(Qt.green)
                elif rec.correct is False:
                    mark = _cell("✗")
                    mark.setForeground(Qt.red)
                else:
                    mark = _cell("-")
                self.tbl.setItem(row_i, 5, mark)
            else:
                self.tbl.setItem(row_i, 3, _cell("-"))
                self.tbl.setItem(row_i, 4, _cell("-"))
                self.tbl.setItem(row_i, 5, _cell("-"))


# ==================== 分析卡（矩阵 + 频率） ====================

class AnalysisCard(Card):
    """单步转移矩阵 + 末位数字频率."""

    def __init__(self, parent=None):
        super().__init__("模式分析（近 50 期）", parent=parent)
        body = self.body()

        row = QHBoxLayout(); row.setSpacing(16)

        # 转移矩阵
        mx_box = QVBoxLayout()
        mx_cap = QLabel("单步转移矩阵 P(next | cur)")
        mx_cap.setObjectName("mutedSmall")
        self.tbl_mx = QTableWidget(2, 2)
        self.tbl_mx.setHorizontalHeaderLabels(["→ 单", "→ 双"])
        self.tbl_mx.setVerticalHeaderLabels(["当前单", "当前双"])
        self.tbl_mx.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_mx.setSelectionMode(QTableWidget.NoSelection)
        self.tbl_mx.setFixedHeight(100)
        mx_box.addWidget(mx_cap)
        mx_box.addWidget(self.tbl_mx)
        row.addLayout(mx_box, 1)

        # 数字频率
        fr_box = QVBoxLayout()
        fr_cap = QLabel("末位数字 0~9 出现次数")
        fr_cap.setObjectName("mutedSmall")
        self.tbl_fr = QTableWidget(1, 10)
        self.tbl_fr.setHorizontalHeaderLabels([str(i) for i in range(10)])
        self.tbl_fr.setVerticalHeaderLabels(["次数"])
        self.tbl_fr.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_fr.setSelectionMode(QTableWidget.NoSelection)
        self.tbl_fr.setFixedHeight(80)
        fr_box.addWidget(fr_cap)
        fr_box.addWidget(self.tbl_fr)
        row.addLayout(fr_box, 2)

        body.addLayout(row)

    def refresh(self, analyzer: Analyzer) -> None:
        try:
            mx = analyzer.get_transition_matrix(window=50)
        except Exception:
            mx = {}
        rows_keys = [PARITY_ODD, PARITY_EVEN]
        cols_keys = [PARITY_ODD, PARITY_EVEN]
        for i, r in enumerate(rows_keys):
            for j, c in enumerate(cols_keys):
                v = mx.get(r, {}).get(c, 0.0)
                cell = _cell(f"{v*100:.1f}%")
                # 高占比高亮
                if v >= 0.6:
                    cell.setForeground(Qt.green)
                elif v <= 0.4 and v > 0:
                    cell.setForeground(Qt.red)
                self.tbl_mx.setItem(i, j, cell)

        try:
            dist = analyzer.frequency_distribution(window=50)
        except Exception:
            dist = {i: 0 for i in range(10)}
        for i in range(10):
            self.tbl_fr.setItem(0, i, _cell(str(dist.get(i, 0))))


# ==================== 预警卡 ====================

class AlertsCard(Card):
    """预警记录."""

    def __init__(self, parent=None):
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("chipIdle")
        super().__init__("预警记录", corner_widget=self.lbl_count, parent=parent)
        body = self.body()

        top = QHBoxLayout()
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setFixedHeight(26)
        top.addStretch()
        top.addWidget(self.btn_clear)
        body.addLayout(top)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(False)
        body.addWidget(self.list, 1)

        self.btn_clear.clicked.connect(self.list.clear)
        self.btn_clear.clicked.connect(self._refresh_count)
        self._refresh_count()

    def _refresh_count(self) -> None:
        n = self.list.count()
        if n == 0:
            self.lbl_count.setText("暂无")
            self.lbl_count.setObjectName("chipIdle")
        else:
            self.lbl_count.setText(f"{n} 条")
            self.lbl_count.setObjectName("chipErr")
        # 重新应用样式
        self.lbl_count.setStyleSheet(self.lbl_count.styleSheet())
        self.lbl_count.style().unpolish(self.lbl_count)
        self.lbl_count.style().polish(self.lbl_count)

    def prepend_event(self, event: AlertEvent) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = "交叉" if event.kind == "alternation" else event.kind
        text = f"  {ts}    [{prefix}]    #{event.block_number or '-'}    {event.message}"
        item = QListWidgetItem(text)
        item.setForeground(Qt.red)
        self.list.insertItem(0, item)
        if self.list.count() > 500:
            self.list.takeItem(self.list.count() - 1)
        self._refresh_count()

    def load_history(self, rows: List[AlertRow]) -> None:
        self.list.clear()
        for r in rows:
            ts = datetime.fromtimestamp(r.created_at).strftime("%m-%d %H:%M:%S")
            prefix = "交叉" if r.kind == "alternation" else r.kind
            text = f"  {ts}    [{prefix}]    #{r.block_number or '-'}    {r.message}"
            item = QListWidgetItem(text)
            item.setForeground(Qt.red)
            self.list.addItem(item)
        self._refresh_count()

    def show_popup(self, event, parent_window=None) -> None:
        """右下角自动消失浮窗."""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QFrame as _QFrame, QVBoxLayout as VLay

        popup = _QFrame(parent_window)
        popup.setStyleSheet(
            "QFrame { background: #141A22; border: 2px solid #E53E3E; "
            "border-radius: 10px; padding: 12px; }"
        )
        popup.setFixedSize(340, 80)
        lay = VLay(popup)
        lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(6)
        t = QLabel(f"⚠  交叉预警")
        t.setStyleSheet("color: #E53E3E; font-weight: bold; font-size: 13px;")
        lay.addWidget(t)
        m = QLabel(event.message)
        m.setStyleSheet("color: #E6EDF3; font-size: 12px;")
        m.setWordWrap(True)
        lay.addWidget(m)

        if parent_window:
            geo = parent_window.geometry()
            popup.move(geo.width() - 360, geo.height() - 140)
        popup.show()
        popup.raise_()
        QTimer.singleShot(5000, popup.deleteLater)


# ==================== Dashboard 主容器 ====================

class DashboardPanel(QWidget):
    """一屏聚合所有核心信息的 Dashboard."""

    def __init__(self, column_max=6, dot_size=28, column_gap=6, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # 第一排：指标条
        self.metrics = MetricStrip()
        root.addWidget(self.metrics)

        # 第二排：水平分栏 - 左（走势 + 分析）右（AI + 命中率 + 对照表 + 预警）
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # 左列
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0); left_lay.setSpacing(12)
        self.trend_card = TrendCard(column_max=column_max, dot_size=dot_size, column_gap=column_gap)
        self.analysis_card = AnalysisCard()
        left_lay.addWidget(self.trend_card, 2)
        left_lay.addWidget(self.analysis_card, 3)

        # 右列：使用垂直 Splitter，允许用户调整 4 个卡片高度
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setChildrenCollapsible(False)
        self.ai_card = AICard()
        self.accuracy_card = AccuracyCard()
        self.recent_card = RecentBlocksCard()
        self.alerts_card = AlertsCard()
        right_splitter.addWidget(self.ai_card)
        right_splitter.addWidget(self.accuracy_card)
        right_splitter.addWidget(self.recent_card)
        right_splitter.addWidget(self.alerts_card)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 3)
        right_splitter.setStretchFactor(2, 5)
        right_splitter.setStretchFactor(3, 3)

        splitter.addWidget(left)
        splitter.addWidget(right_splitter)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([700, 560])

        root.addWidget(splitter, 1)

    # ---------- 对外统一刷新 ----------
    def on_new_period(self, period, odd_total: int, even_total: int) -> None:
        self.trend_card.on_new_period(period, odd_total, even_total)

    def apply_history(self, analyzer: Analyzer) -> None:
        s = analyzer.stats
        self.trend_card.apply_periods(analyzer.history(), s.odd_total, s.even_total)
        self.metrics.refresh(analyzer)

    def refresh_all(self, analyzer: Analyzer, prediction, tracker) -> None:
        self.metrics.refresh(analyzer)
        self.trend_card.update_ai_signal(prediction)
        self.ai_card.update_prediction(prediction)
        self.accuracy_card.update_tracker(tracker)
        self.recent_card.refresh(analyzer, tracker)
        self.analysis_card.refresh(analyzer)

    # ---------- 预警相关（转发给内部 alerts_card） ----------
    def on_alert(self, event: AlertEvent) -> None:
        self.alerts_card.prepend_event(event)

    def load_alert_history(self, rows) -> None:
        self.alerts_card.load_history(rows)

    def show_alert_popup(self, event, parent_window=None) -> None:
        self.alerts_card.show_popup(event, parent_window)

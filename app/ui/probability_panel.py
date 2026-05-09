"""概率仪表盘 + AI 信号面板."""
from __future__ import annotations
from typing import Dict, Optional
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ..core.analyzer import Analyzer
from ..core.predictor import PredictionResult, Signal
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_BIG, COLOR_SMALL, COLOR_SUB, COLOR_TEXT


class GaugeWidget(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._title, self._value, self._label, self._color = title, 0.5, "", "#FFF"
        self.setFixedSize(110, 120)

    def set_value(self, value, label, color):
        self._value, self._label, self._color = max(0, min(1, value)), label, color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLOR_BG))
        cx, cy, r = self.width()//2, 60, 40
        p.setPen(QPen(QColor(COLOR_SUB), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r, cy-r, r*2, r*2, 210*16, -240*16)
        p.setPen(QPen(QColor(self._color), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r, cy-r, r*2, r*2, 210*16, int(-240*self._value*16))
        p.setPen(QColor(COLOR_TEXT))
        f = QFont(self.font()); f.setPointSize(13); f.setBold(True); p.setFont(f)
        p.drawText(QRect(0, cy-10, self.width(), 20), Qt.AlignCenter, f"{self._value*100:.0f}%")
        f.setPointSize(9); f.setBold(False); p.setFont(f)
        p.setPen(QColor(self._color))
        p.drawText(QRect(0, cy+18, self.width(), 16), Qt.AlignCenter, self._label)
        p.setPen(QColor(COLOR_SUB))
        p.drawText(QRect(0, 0, self.width(), 16), Qt.AlignCenter, self._title)


class SignalCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6)
        self.lbl_signal = QLabel("等待信号...")
        f = self.lbl_signal.font(); f.setPointSize(15); f.setBold(True); self.lbl_signal.setFont(f)
        lay.addWidget(self.lbl_signal)
        self.lbl_detail = QLabel(""); self.lbl_detail.setStyleSheet(f"color: {COLOR_SUB};")
        lay.addWidget(self.lbl_detail)

    def set_signal(self, signal: Optional[Signal]):
        if not signal:
            self.lbl_signal.setText("暂无高置信度信号")
            self.lbl_signal.setStyleSheet(f"color: {COLOR_SUB};")
            self.lbl_detail.setText("")
            return
        colors = {"odd": COLOR_ODD, "even": COLOR_EVEN, "big": COLOR_BIG, "small": COLOR_SMALL}
        c = colors.get(signal.prediction, COLOR_TEXT)
        dim = "单双" if signal.dimension == "parity" else "大小"
        self.lbl_signal.setText(f"预测: {signal.label} ({dim}) 置信度 {signal.confidence_pct}")
        self.lbl_signal.setStyleSheet(f"color: {c};")
        self.lbl_detail.setText(f"模型: {signal.model} | {signal.reason}")


class ProbabilityPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(12, 12, 12, 12)
        title = QLabel("概率分析 & AI 信号")
        f = title.font(); f.setPointSize(13); f.setBold(True); title.setFont(f)
        root.addWidget(title)
        self.signal_card = SignalCard()
        root.addWidget(self.signal_card)
        gauge_row = QHBoxLayout()
        self.g_odd = GaugeWidget("单"); self.g_even = GaugeWidget("双")
        self.g_big = GaugeWidget("大"); self.g_small = GaugeWidget("小")
        for g in (self.g_odd, self.g_even, self.g_big, self.g_small):
            gauge_row.addWidget(g)
        gauge_row.addStretch()
        root.addLayout(gauge_row)
        root.addStretch()

    def refresh(self, analyzer: Analyzer, prediction: Optional[PredictionResult] = None):
        s = analyzer.stats
        if s.total:
            self.g_odd.set_value(s.odd_total/s.total, f"单 {s.odd_total}", COLOR_ODD)
            self.g_even.set_value(s.even_total/s.total, f"双 {s.even_total}", COLOR_EVEN)
            self.g_big.set_value(s.big_total/s.total, f"大 {s.big_total}", COLOR_BIG)
            self.g_small.set_value(s.small_total/s.total, f"小 {s.small_total}", COLOR_SMALL)
        self.signal_card.set_signal(prediction.best if prediction else None)

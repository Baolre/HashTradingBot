"""概率仪表盘 + AI 信号面板（纯单双 + 显示预测区块号）."""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ..core.analyzer import Analyzer
from ..core.predictor import PredictionResult, Signal
from .theme import COLOR_BG, COLOR_EVEN, COLOR_ODD, COLOR_SUB, COLOR_TEXT


class GaugeWidget(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._title, self._value, self._label, self._color = title, 0.5, "", "#FFF"
        self.setFixedSize(130, 130)

    def set_value(self, value, label, color):
        self._value, self._label, self._color = max(0, min(1, value)), label, color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLOR_BG))
        cx, cy, r = self.width()//2, 65, 45
        p.setPen(QPen(QColor(COLOR_SUB), 8, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r, cy-r, r*2, r*2, 210*16, -240*16)
        p.setPen(QPen(QColor(self._color), 8, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r, cy-r, r*2, r*2, 210*16, int(-240*self._value*16))
        p.setPen(QColor(COLOR_TEXT))
        f = QFont(self.font()); f.setPointSize(14); f.setBold(True); p.setFont(f)
        p.drawText(QRect(0, cy-12, self.width(), 24), Qt.AlignCenter, f"{self._value*100:.0f}%")
        f.setPointSize(10); f.setBold(False); p.setFont(f)
        p.setPen(QColor(self._color))
        p.drawText(QRect(0, cy+20, self.width(), 16), Qt.AlignCenter, self._label)
        p.setPen(QColor(COLOR_SUB))
        p.drawText(QRect(0, 2, self.width(), 16), Qt.AlignCenter, self._title)


class SignalCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(4)
        self.lbl_signal = QLabel("等待信号...")
        f = self.lbl_signal.font(); f.setPointSize(15); f.setBold(True); self.lbl_signal.setFont(f)
        lay.addWidget(self.lbl_signal)
        self.lbl_detail = QLabel(""); self.lbl_detail.setStyleSheet(f"color: {COLOR_SUB};")
        lay.addWidget(self.lbl_detail)
        self.lbl_block = QLabel(""); self.lbl_block.setStyleSheet(f"color: {COLOR_SUB}; font-size: 11px;")
        lay.addWidget(self.lbl_block)

    def set_signal(self, signal: Optional[Signal], next_block: int = 0):
        if not signal:
            self.lbl_signal.setText("暂无高置信度信号")
            self.lbl_signal.setStyleSheet(f"color: {COLOR_SUB};")
            self.lbl_detail.setText("")
            self.lbl_block.setText("")
            return
        c = COLOR_ODD if signal.prediction == "odd" else COLOR_EVEN
        self.lbl_signal.setText(f"预测下期: {signal.label} | 置信度 {signal.confidence_pct}")
        self.lbl_signal.setStyleSheet(f"color: {c};")
        self.lbl_detail.setText(f"模型: {signal.model} | {signal.reason}")
        block_num = signal.next_block_number or next_block
        self.lbl_block.setText(f"预测区块: #{block_num}" if block_num else "")


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
        self.g_odd = GaugeWidget("单")
        self.g_even = GaugeWidget("双")
        gauge_row.addWidget(self.g_odd)
        gauge_row.addWidget(self.g_even)
        gauge_row.addStretch()
        root.addLayout(gauge_row)
        # 模型准确率
        self.lbl_accuracy = QLabel("")
        self.lbl_accuracy.setStyleSheet(f"color: {COLOR_SUB}; font-size: 11px;")
        root.addWidget(self.lbl_accuracy)
        root.addStretch()

    def refresh(self, analyzer: Analyzer, prediction: Optional[PredictionResult] = None):
        s = analyzer.stats
        if s.total:
            self.g_odd.set_value(s.odd_total/s.total, f"单 {s.odd_total}", COLOR_ODD)
            self.g_even.set_value(s.even_total/s.total, f"双 {s.even_total}", COLOR_EVEN)
        next_block = prediction.next_block_number if prediction else 0
        self.signal_card.set_signal(prediction.best if prediction else None, next_block)
        if prediction and prediction.model_weights:
            acc_str = " | ".join(f"{k}: {v*100:.0f}%" for k, v in prediction.model_weights.items())
            self.lbl_accuracy.setText(f"模型准确率: {acc_str}")

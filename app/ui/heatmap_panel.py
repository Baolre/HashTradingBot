"""热力图面板."""
from __future__ import annotations
from typing import Dict, List
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QBrush
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ..core.analyzer import Analyzer, Period
from .theme import COLOR_BG, COLOR_SUB


class HeatmapCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[List[float]] = []
        self._rows: List[str] = []
        self._cols: List[str] = []
        self.setMinimumHeight(180)

    def set_data(self, data, rows, cols):
        self._data, self._rows, self._cols = data, rows, cols
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLOR_BG))
        if not self._data or not self._data[0]:
            p.setPen(QColor(COLOR_SUB)); p.drawText(self.rect(), Qt.AlignCenter, "等待数据..."); return
        rows, cols = len(self._data), len(self._data[0])
        ml, mt, mr, mb = 50, 20, 10, 30
        cw, ch = (self.width()-ml-mr)/cols, (self.height()-mt-mb)/rows
        for r in range(rows):
            for c in range(cols):
                v = self._data[r][c]
                color = QColor(int(30+v*200), int(60+v*100), int(80-v*60))
                p.setPen(Qt.NoPen); p.setBrush(QBrush(color))
                p.drawRoundedRect(int(ml+c*cw+1), int(mt+r*ch+1), int(cw-2), int(ch-2), 3, 3)
                if cw > 25:
                    p.setPen(QColor("#FFF"))
                    font = QFont(self.font()); font.setPointSize(8); p.setFont(font)
                    p.drawText(QRect(int(ml+c*cw), int(mt+r*ch), int(cw), int(ch)), Qt.AlignCenter, f"{int(v*100)}%")
        p.setPen(QColor(COLOR_SUB))
        font = QFont(self.font()); font.setPointSize(9); p.setFont(font)
        for r, lbl in enumerate(self._rows[:rows]):
            p.drawText(QRect(0, int(mt+r*ch), ml-5, int(ch)), Qt.AlignVCenter|Qt.AlignRight, lbl)
        for c, lbl in enumerate(self._cols[:cols]):
            p.drawText(QRect(int(ml+c*cw), self.height()-mb+2, int(cw), 20), Qt.AlignHCenter, lbl)


class HeatmapPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        top = QHBoxLayout()
        title = QLabel("热力图"); f = title.font(); f.setPointSize(13); f.setBold(True); title.setFont(f)
        top.addWidget(title); top.addStretch()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["数字频率", "组合转移"])
        self.mode_combo.currentIndexChanged.connect(self._refresh_mode)
        top.addWidget(self.mode_combo)
        root.addLayout(top)
        self.canvas = HeatmapCanvas()
        root.addWidget(self.canvas, 1)
        self._analyzer = None

    def _refresh_mode(self, idx):
        if self._analyzer: self.refresh(self._analyzer)

    def refresh(self, analyzer: Analyzer) -> None:
        self._analyzer = analyzer
        history = analyzer.history()
        if not history: return
        if self.mode_combo.currentIndex() == 0:
            self._digit_heatmap(history)
        else:
            self._combo_heatmap(history)

    def _digit_heatmap(self, history):
        ws = max(20, len(history)//5)
        windows, col_labels = [], []
        for i in range(0, len(history), ws):
            chunk = history[i:i+ws]
            if len(chunk) >= 5: windows.append(chunk); col_labels.append(f"W{len(col_labels)+1}")
        if not windows: return
        data = []
        for d in range(10):
            row = [sum(1 for p in w if p.digit == d)/len(w) for w in windows]
            data.append(row)
        mx = max(max(r) for r in data) or 1
        data = [[v/mx for v in row] for row in data]
        self.canvas.set_data(data, [str(d) for d in range(10)], col_labels)

    def _combo_heatmap(self, history):
        combos = ["单大","单小","双大","双小"]
        trans = {c: {c2: 0 for c2 in combos} for c in combos}
        for i in range(1, len(history)):
            prev, cur = history[i-1].combo_label, history[i].combo_label
            if prev in trans and cur in trans[prev]: trans[prev][cur] += 1
        data = []
        for c in combos:
            total = sum(trans[c].values())
            data.append([trans[c][c2]/total if total else 0 for c2 in combos])
        self.canvas.set_data(data, combos, combos)

"""长龙雷达面板（纯单双）."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from ..core.analyzer import PARITY_EVEN, PARITY_ODD, Analyzer
from .theme import COLOR_BORDER, COLOR_EVEN, COLOR_ODD, COLOR_PANEL, COLOR_SUB


@dataclass
class DragonEntry:
    rule_label: str
    value: str
    run_length: int
    source: str
    latest_block: Optional[int] = None

    @property
    def label(self) -> str:
        return {"odd": "单", "even": "双"}.get(self.value, "?")

    @property
    def color(self) -> str:
        return {"odd": COLOR_ODD, "even": COLOR_EVEN}.get(self.value, COLOR_SUB)


class DragonPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        top = QHBoxLayout()
        title = QLabel("长龙雷达")
        f = title.font(); f.setPointSize(13); f.setBold(True); title.setFont(f)
        top.addWidget(title); top.addStretch()
        self.count_label = QLabel("0 条")
        self.count_label.setStyleSheet(f"color: {COLOR_SUB};")
        top.addWidget(self.count_label)
        root.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        scroll.setWidget(self.grid_widget)
        root.addWidget(scroll, 1)
        self.empty_label = QLabel("暂无活跃长龙")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {COLOR_SUB}; font-size: 14px;")
        root.addWidget(self.empty_label)

    def refresh(self, entries: List[DragonEntry]) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.count_label.setText(f"{len(entries)} 条")
        self.empty_label.setVisible(len(entries) == 0)
        entries.sort(key=lambda e: e.run_length, reverse=True)
        for i, entry in enumerate(entries):
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {COLOR_PANEL}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; padding: 8px; }}")
            card.setFixedHeight(70)
            lay = QVBoxLayout(card); lay.setContentsMargins(8, 4, 8, 4)
            top_l = QLabel(f"{entry.rule_label} | {entry.source}")
            top_l.setStyleSheet(f"color: {COLOR_SUB}; font-size: 10px;")
            lay.addWidget(top_l)
            mid = QHBoxLayout()
            t = QLabel(f"● {entry.label}")
            t.setStyleSheet(f"color: {entry.color}; font-size: 14px; font-weight: bold;")
            mid.addWidget(t); mid.addStretch()
            c = QLabel(f"连 {entry.run_length} 期")
            c.setStyleSheet(f"color: {entry.color}; font-size: 16px; font-weight: bold;")
            mid.addWidget(c)
            lay.addLayout(mid)
            self.grid_layout.addWidget(card, i // 3, i % 3)

    @staticmethod
    def scan_dragons(analyzer: Analyzer, rule_label: str = "", threshold: int = 3) -> List[DragonEntry]:
        entries: List[DragonEntry] = []
        history = analyzer.history()
        if not history:
            return entries
        latest_block = history[-1].block_number
        val, run = analyzer.same_run_length()
        if run >= threshold and val in (PARITY_ODD, PARITY_EVEN):
            entries.append(DragonEntry(rule_label=rule_label, value=val,
                                       run_length=run, source="走势路", latest_block=latest_block))
        return entries

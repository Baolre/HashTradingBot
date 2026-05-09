"""预警面板."""
from __future__ import annotations

from datetime import datetime
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from ..core.alerter import AlertEvent
from ..storage.db import AlertRow
from .theme import COLOR_ODD


class AlertPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("预警记录")
        f = title.font()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        top.addWidget(title)
        top.addStretch()
        self.btn_clear = QPushButton("清屏")
        top.addWidget(self.btn_clear)
        root.addLayout(top)

        self.list = QListWidget()
        root.addWidget(self.list, 1)

        self.btn_clear.clicked.connect(self.list.clear)

    # -------------- 填充 --------------
    def prepend_event(self, event: AlertEvent) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = "[交叉]" if event.kind == "alternation" else f"[{event.kind}]"
        text = f"{ts}  {prefix}  区块 #{event.block_number or '-'}  {event.message}"
        item = QListWidgetItem(text)
        item.setForeground(Qt.red)
        self.list.insertItem(0, item)
        if self.list.count() > 500:
            self.list.takeItem(self.list.count() - 1)

    def load_history(self, rows: List[AlertRow]) -> None:
        self.list.clear()
        # rows 已经是倒序
        for r in rows:
            ts = datetime.fromtimestamp(r.created_at).strftime("%m-%d %H:%M:%S")
            prefix = "[交叉]" if r.kind == "alternation" else f"[{r.kind}]"
            text = f"{ts}  {prefix}  区块 #{r.block_number or '-'}  {r.message}"
            item = QListWidgetItem(text)
            item.setForeground(Qt.red)
            self.list.addItem(item)

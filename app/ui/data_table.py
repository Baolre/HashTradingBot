"""数据明细表 - CSV导出 + TronScan链接."""
from __future__ import annotations
import csv, os
from datetime import datetime
from typing import List
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                                QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from ..core.analyzer import Analyzer, Period
from .theme import COLOR_BIG, COLOR_EVEN, COLOR_ODD, COLOR_SMALL, COLOR_SUB


class DataTablePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        top = QHBoxLayout()
        title = QLabel("区块明细"); f = title.font(); f.setPointSize(13); f.setBold(True); title.setFont(f)
        top.addWidget(title); top.addStretch()
        top.addWidget(QLabel("数量:"))
        self.sp_count = QSpinBox(); self.sp_count.setRange(10, 500); self.sp_count.setValue(50)
        self.sp_count.valueChanged.connect(lambda: self.refresh(self._analyzer) if self._analyzer else None)
        top.addWidget(self.sp_count)
        self.btn_export = QPushButton("导出CSV"); self.btn_export.clicked.connect(self._export)
        top.addWidget(self.btn_export)
        root.addLayout(top)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["区块号","哈希","末位","单双","大小","时间"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._open_tronscan)
        root.addWidget(self.table, 1)
        self._analyzer = None

    def refresh(self, analyzer: Analyzer) -> None:
        self._analyzer = analyzer
        periods = list(reversed(analyzer.last(self.sp_count.value())))
        self.table.setRowCount(len(periods))
        for i, p in enumerate(periods):
            self.table.setItem(i, 0, QTableWidgetItem(str(p.block_number)))
            h = p.block_hash[:10]+"..." if len(p.block_hash) > 12 else p.block_hash
            self.table.setItem(i, 1, QTableWidgetItem(h))
            self.table.setItem(i, 2, QTableWidgetItem(str(p.digit) if p.digit is not None else "-"))
            pi = QTableWidgetItem(p.parity_label); pi.setForeground(QColor(COLOR_ODD if p.is_odd else COLOR_EVEN))
            self.table.setItem(i, 3, pi)
            si = QTableWidgetItem(p.size_label); si.setForeground(QColor(COLOR_BIG if p.is_big else COLOR_SMALL))
            self.table.setItem(i, 4, si)
            ts = datetime.fromtimestamp(p.timestamp_ms/1000).strftime("%m-%d %H:%M:%S") if p.timestamp_ms else "-"
            self.table.setItem(i, 5, QTableWidgetItem(ts))

    def _open_tronscan(self, row, col):
        item = self.table.item(row, 0)
        if item: QDesktopServices.openUrl(QUrl(f"https://tronscan.org/#/block/{item.text()}"))

    def _export(self):
        if not self._analyzer: return
        path, _ = QFileDialog.getSaveFileName(self, "导出", f"blocks_{datetime.now():%Y%m%d}.csv", "CSV (*.csv)")
        if not path: return
        periods = list(reversed(self._analyzer.last(self.sp_count.value())))
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["区块号","哈希","末位","单双","大小","时间"])
            for p in periods:
                ts = datetime.fromtimestamp(p.timestamp_ms/1000).strftime("%Y-%m-%d %H:%M:%S") if p.timestamp_ms else ""
                w.writerow([p.block_number, p.block_hash, p.digit, p.parity_label, p.size_label, ts])

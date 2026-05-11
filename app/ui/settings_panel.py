"""UI 组件。"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from ..utils.config import AppConfig


class SettingsPanel(QWidget):
    saved = Signal(object)  # AppConfig

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # API 设置
        grp_api = QGroupBox("TRON API")
        form_api = QFormLayout(grp_api)
        self.ed_endpoint = QLineEdit(cfg.api.trongrid_endpoint)
        self.ed_api_key = QLineEdit(cfg.api.trongrid_api_key)
        self.ed_api_key.setEchoMode(QLineEdit.Password)
        self.ed_api_key.setPlaceholderText("请输入 TronGrid API Key（header: TRON-PRO-API-KEY）")
        self.sp_interval = QSpinBox(); self.sp_interval.setRange(1, 60)
        self.sp_interval.setValue(cfg.api.poll_interval)
        self.sp_interval.setSuffix(" 秒")
        self.sp_timeout = QSpinBox(); self.sp_timeout.setRange(3, 60)
        self.sp_timeout.setValue(cfg.api.timeout)
        self.sp_timeout.setSuffix(" 秒")

        form_api.addRow("Endpoint:", self.ed_endpoint)
        form_api.addRow("API Key:", self.ed_api_key)
        form_api.addRow("轮询间隔:", self.sp_interval)
        form_api.addRow("请求超时:", self.sp_timeout)
        root.addWidget(grp_api)

        # 过滤设置
        grp_filter = QGroupBox("区块过滤")
        form_filter = QFormLayout(grp_filter)
        self.sp_mult = QSpinBox(); self.sp_mult.setRange(1, 10000)
        self.sp_mult.setValue(cfg.filter.block_multiple)
        form_filter.addRow("仅统计区块号为其倍数:", self.sp_mult)
        form_filter.addRow(QLabel("<span style='color:#8B949E'>默认 20，即只处理 blockNumber % 20 == 0 的区块</span>"))
        root.addWidget(grp_filter)

        # 预警设置
        grp_alert = QGroupBox("预警规则")
        form_alert = QFormLayout(grp_alert)
        self.cb_alt = QCheckBox("启用单双交叉预警（单双单双…）")
        self.cb_alt.setChecked(cfg.alert.alternation_enabled)
        self.sp_alt_threshold = QSpinBox(); self.sp_alt_threshold.setRange(2, 50)
        self.sp_alt_threshold.setValue(cfg.alert.alternation_threshold)
        self.sp_cooldown = QSpinBox(); self.sp_cooldown.setRange(0, 50)
        self.sp_cooldown.setValue(cfg.alert.cooldown_periods)

        form_alert.addRow(self.cb_alt)
        form_alert.addRow("交叉触发阈值:", self.sp_alt_threshold)
        form_alert.addRow("触发冷却(期):", self.sp_cooldown)
        root.addWidget(grp_alert)

        # 按钮
        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_save = QPushButton("保存设置")
        btns.addWidget(self.btn_save)
        root.addLayout(btns)

        root.addStretch()

        self.btn_save.clicked.connect(self._on_save)

    def _collect(self) -> AppConfig:
        cfg = self._cfg
        cfg.api.trongrid_endpoint = self.ed_endpoint.text().strip() or "https://api.trongrid.io"
        cfg.api.trongrid_api_key = self.ed_api_key.text().strip()
        cfg.api.poll_interval = int(self.sp_interval.value())
        cfg.api.timeout = int(self.sp_timeout.value())
        cfg.filter.block_multiple = int(self.sp_mult.value())
        cfg.alert.alternation_enabled = self.cb_alt.isChecked()
        cfg.alert.alternation_threshold = int(self.sp_alt_threshold.value())
        cfg.alert.cooldown_periods = int(self.sp_cooldown.value())
        return cfg

    def _on_save(self) -> None:
        cfg = self._collect()
        self.saved.emit(cfg)

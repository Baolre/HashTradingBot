"""设置面板 - API / 过滤 / 预警 / 推送."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
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
        self.cb_sound = QCheckBox("触发时播放提示音")
        self.cb_sound.setChecked(getattr(cfg.alert, "sound_enabled", True))
        self.cb_bark = QCheckBox("触发时推送到手机（Bark）")
        self.cb_bark.setChecked(getattr(cfg.alert, "bark_enabled", True))

        form_alert.addRow(self.cb_alt)
        form_alert.addRow("交叉触发阈值:", self.sp_alt_threshold)
        form_alert.addRow("触发冷却(期):", self.sp_cooldown)
        form_alert.addRow(self.cb_sound)
        form_alert.addRow(self.cb_bark)
        root.addWidget(grp_alert)

        # DeepSeek AI 预测
        grp_ds = QGroupBox("DeepSeek V4 Flash AI 预测")
        form_ds = QFormLayout(grp_ds)
        self.cb_ds_enabled = QCheckBox("启用 DeepSeek AI 预测模型")
        self.cb_ds_enabled.setChecked(getattr(cfg.deepseek, "enabled", True))
        self.ed_ds_key = QLineEdit(getattr(cfg.deepseek, "api_key", ""))
        self.ed_ds_key.setEchoMode(QLineEdit.Password)
        self.ed_ds_key.setPlaceholderText("在 platform.deepseek.com 获取 API Key")
        self.ed_ds_base_url = QLineEdit(getattr(cfg.deepseek, "base_url", "https://api.deepseek.com"))
        self.ed_ds_model = QLineEdit(getattr(cfg.deepseek, "model", "deepseek-v4-flash"))
        self.sp_ds_timeout = QSpinBox(); self.sp_ds_timeout.setRange(5, 60)
        self.sp_ds_timeout.setValue(getattr(cfg.deepseek, "timeout", 15))
        self.sp_ds_timeout.setSuffix(" 秒")
        self.sp_ds_history = QSpinBox(); self.sp_ds_history.setRange(20, 500)
        self.sp_ds_history.setValue(getattr(cfg.deepseek, "max_history", 100))
        self.sp_ds_history.setSuffix(" 期")

        form_ds.addRow(self.cb_ds_enabled)
        form_ds.addRow("API Key:", self.ed_ds_key)
        form_ds.addRow("Base URL:", self.ed_ds_base_url)
        form_ds.addRow("模型:", self.ed_ds_model)
        form_ds.addRow("超时:", self.sp_ds_timeout)
        form_ds.addRow("历史期数:", self.sp_ds_history)
        form_ds.addRow(QLabel(
            "<span style='color:#8B949E'>利用上下文缓存，token 消耗极低（~¥0.15/天）</span>"
        ))
        root.addWidget(grp_ds)

        # Bark 手机推送
        grp_push = QGroupBox("Bark 手机推送（iOS）")
        form_push = QFormLayout(grp_push)
        self.ed_bark_key = QLineEdit(cfg.push.bark_key)
        self.ed_bark_key.setPlaceholderText("Bark App 首页复制的设备 Key")
        self.ed_bark_server = QLineEdit(cfg.push.bark_server or "https://api.day.app")
        self.ed_bark_server.setPlaceholderText("https://api.day.app（自建可替换）")
        self.cb_bark_sound = QComboBox()
        self.cb_bark_sound.setEditable(True)
        self.cb_bark_sound.addItems([
            "alarm", "bell", "minuet", "calypso", "chime", "glass",
            "horn", "ladder", "multiwayinvitation", "newmail",
            "newsflash", "suspense", "telegraph", "tweet", "update",
        ])
        self.cb_bark_sound.setCurrentText(cfg.push.bark_sound or "alarm")
        self.ed_bark_group = QLineEdit(cfg.push.bark_group or "hash_alert")

        form_push.addRow("Bark Key:", self.ed_bark_key)
        form_push.addRow("服务器:", self.ed_bark_server)
        form_push.addRow("铃声:", self.cb_bark_sound)
        form_push.addRow("分组:", self.ed_bark_group)
        form_push.addRow(QLabel(
            "<span style='color:#8B949E'>留空 Bark Key 则不推送；支持自建 Bark Server</span>"
        ))
        root.addWidget(grp_push)

        # 按钮
        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_test_bark = QPushButton("测试 Bark 推送")
        self.btn_save = QPushButton("保存设置")
        btns.addWidget(self.btn_test_bark)
        btns.addWidget(self.btn_save)
        root.addLayout(btns)

        root.addStretch()

        self.btn_save.clicked.connect(self._on_save)
        self.btn_test_bark.clicked.connect(self._on_test_bark)

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
        cfg.alert.sound_enabled = self.cb_sound.isChecked()
        cfg.alert.bark_enabled = self.cb_bark.isChecked()
        cfg.push.bark_key = self.ed_bark_key.text().strip()
        cfg.push.bark_server = self.ed_bark_server.text().strip() or "https://api.day.app"
        cfg.push.bark_sound = self.cb_bark_sound.currentText().strip() or "alarm"
        cfg.push.bark_group = self.ed_bark_group.text().strip() or "hash_alert"
        cfg.deepseek.enabled = self.cb_ds_enabled.isChecked()
        cfg.deepseek.api_key = self.ed_ds_key.text().strip()
        cfg.deepseek.base_url = self.ed_ds_base_url.text().strip() or "https://api.deepseek.com"
        cfg.deepseek.model = self.ed_ds_model.text().strip() or "deepseek-v4-flash"
        cfg.deepseek.timeout = int(self.sp_ds_timeout.value())
        cfg.deepseek.max_history = int(self.sp_ds_history.value())
        return cfg

    def _on_save(self) -> None:
        cfg = self._collect()
        self.saved.emit(cfg)

    def _on_test_bark(self) -> None:
        """不落盘地直接用当前表单里的 Bark 配置发一条测试推送."""
        from ..utils.notifier import Notifier  # 延迟 import 防循环
        key = self.ed_bark_key.text().strip()
        if not key:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先填写 Bark Key")
            return
        notifier = Notifier(self)
        notifier.push_bark(
            title="Hash Trading Bot 测试推送",
            body="如果你收到这条通知，说明 Bark 配置正常 ✅",
            key=key,
            server=self.ed_bark_server.text().strip() or "https://api.day.app",
            sound=self.cb_bark_sound.currentText().strip() or "alarm",
            group=self.ed_bark_group.text().strip() or "hash_alert",
        )

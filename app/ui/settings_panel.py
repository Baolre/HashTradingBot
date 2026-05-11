"""设置面板 - 紧凑多列布局."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from ..utils.config import AppConfig


def _line(text: str = "", placeholder: str = "", password: bool = False, max_w: int = 260) -> QLineEdit:
    ed = QLineEdit(text)
    if placeholder:
        ed.setPlaceholderText(placeholder)
    if password:
        ed.setEchoMode(QLineEdit.Password)
    ed.setMaximumWidth(max_w)
    return ed


def _spin(value: int, lo: int, hi: int, suffix: str = "", max_w: int = 120) -> QSpinBox:
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(value)
    if suffix:
        sp.setSuffix(suffix)
    sp.setMaximumWidth(max_w)
    return sp


class SettingsPanel(QWidget):
    saved = Signal(object)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ===== TRON API =====
        grp_api = QGroupBox("TRON API")
        g = QGridLayout(grp_api)
        g.setHorizontalSpacing(14); g.setVerticalSpacing(8)
        g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)

        self.ed_endpoint = _line(cfg.api.trongrid_endpoint, max_w=320)
        self.ed_api_key = _line(cfg.api.trongrid_api_key, "TronGrid API Key", password=True, max_w=320)
        self.sp_interval = _spin(cfg.api.poll_interval, 1, 60, " 秒")
        self.sp_timeout = _spin(cfg.api.timeout, 3, 60, " 秒")

        g.addWidget(QLabel("Endpoint:"), 0, 0)
        g.addWidget(self.ed_endpoint, 0, 1, 1, 3)
        g.addWidget(QLabel("API Key:"), 1, 0)
        g.addWidget(self.ed_api_key, 1, 1, 1, 3)
        g.addWidget(QLabel("轮询:"), 2, 0)
        g.addWidget(self.sp_interval, 2, 1)
        g.addWidget(QLabel("超时:"), 2, 2)
        g.addWidget(self.sp_timeout, 2, 3)
        root.addWidget(grp_api)

        # ===== 区块过滤 + 预警（并排） =====
        row1 = QHBoxLayout(); row1.setSpacing(16)

        grp_f = QGroupBox("区块过滤")
        fl = QHBoxLayout(grp_f); fl.setSpacing(8)
        fl.addWidget(QLabel("倍数:"))
        self.sp_mult = _spin(cfg.filter.block_multiple, 1, 10000, max_w=100)
        fl.addWidget(self.sp_mult); fl.addStretch()
        row1.addWidget(grp_f, 1)

        grp_a = QGroupBox("交叉预警")
        al = QGridLayout(grp_a); al.setHorizontalSpacing(10); al.setVerticalSpacing(6)
        self.cb_alt = QCheckBox("启用")
        self.cb_alt.setChecked(cfg.alert.alternation_enabled)
        self.sp_alt_threshold = _spin(cfg.alert.alternation_threshold, 2, 50, max_w=70)
        self.sp_cooldown = _spin(cfg.alert.cooldown_periods, 0, 50, max_w=70)
        self.cb_sound = QCheckBox("声音")
        self.cb_sound.setChecked(getattr(cfg.alert, "sound_enabled", True))
        self.cb_bark = QCheckBox("Bark")
        self.cb_bark.setChecked(getattr(cfg.alert, "bark_enabled", True))

        al.addWidget(self.cb_alt, 0, 0)
        al.addWidget(self.cb_sound, 0, 1)
        al.addWidget(self.cb_bark, 0, 2)
        al.addWidget(QLabel("阈值:"), 1, 0)
        al.addWidget(self.sp_alt_threshold, 1, 1)
        al.addWidget(QLabel("冷却:"), 1, 2)
        al.addWidget(self.sp_cooldown, 1, 3)
        row1.addWidget(grp_a, 2)
        root.addLayout(row1)

        # ===== DeepSeek + Bark（并排） =====
        row2 = QHBoxLayout(); row2.setSpacing(16)

        grp_ds = QGroupBox("DeepSeek V4 Flash")
        dl = QGridLayout(grp_ds); dl.setHorizontalSpacing(10); dl.setVerticalSpacing(6)
        dl.setColumnStretch(1, 1)
        self.cb_ds_enabled = QCheckBox("启用")
        self.cb_ds_enabled.setChecked(getattr(cfg.deepseek, "enabled", True))
        self.ed_ds_key = _line(getattr(cfg.deepseek, "api_key", ""), "API Key", password=True, max_w=220)
        self.ed_ds_base_url = _line(getattr(cfg.deepseek, "base_url", "https://api.deepseek.com"), max_w=220)
        self.ed_ds_model = _line(getattr(cfg.deepseek, "model", "deepseek-v4-flash"), max_w=160)
        self.sp_ds_timeout = _spin(getattr(cfg.deepseek, "timeout", 15), 5, 60, " 秒")
        self.sp_ds_history = _spin(getattr(cfg.deepseek, "max_history", 100), 20, 500, " 期")

        dl.addWidget(self.cb_ds_enabled, 0, 0, 1, 2)
        dl.addWidget(QLabel("Key:"), 1, 0); dl.addWidget(self.ed_ds_key, 1, 1)
        dl.addWidget(QLabel("URL:"), 2, 0); dl.addWidget(self.ed_ds_base_url, 2, 1)
        dl.addWidget(QLabel("模型:"), 3, 0); dl.addWidget(self.ed_ds_model, 3, 1)
        dl.addWidget(QLabel("超时:"), 4, 0); dl.addWidget(self.sp_ds_timeout, 4, 1)
        dl.addWidget(QLabel("历史:"), 5, 0); dl.addWidget(self.sp_ds_history, 5, 1)
        row2.addWidget(grp_ds, 1)

        grp_p = QGroupBox("Bark 推送")
        pl = QGridLayout(grp_p); pl.setHorizontalSpacing(10); pl.setVerticalSpacing(6)
        pl.setColumnStretch(1, 1)
        self.ed_bark_key = _line(cfg.push.bark_key, "设备 Key", max_w=200)
        self.ed_bark_server = _line(cfg.push.bark_server or "https://api.day.app", max_w=200)
        self.cb_bark_sound = QComboBox()
        self.cb_bark_sound.setEditable(True); self.cb_bark_sound.setMaximumWidth(130)
        self.cb_bark_sound.addItems(["alarm", "bell", "minuet", "calypso", "chime", "glass", "horn", "newmail", "telegraph"])
        self.cb_bark_sound.setCurrentText(cfg.push.bark_sound or "alarm")
        self.ed_bark_group = _line(cfg.push.bark_group or "hash_alert", max_w=130)

        pl.addWidget(QLabel("Key:"), 0, 0); pl.addWidget(self.ed_bark_key, 0, 1)
        pl.addWidget(QLabel("服务器:"), 1, 0); pl.addWidget(self.ed_bark_server, 1, 1)
        pl.addWidget(QLabel("铃声:"), 2, 0); pl.addWidget(self.cb_bark_sound, 2, 1)
        pl.addWidget(QLabel("分组:"), 3, 0); pl.addWidget(self.ed_bark_group, 3, 1)
        row2.addWidget(grp_p, 1)
        root.addLayout(row2)

        # ===== 按钮 =====
        btns = QHBoxLayout(); btns.addStretch()
        self.btn_test_bark = QPushButton("测试 Bark")
        self.btn_save = QPushButton("保存设置")
        self.btn_save.setObjectName("primary")
        btns.addWidget(self.btn_test_bark); btns.addSpacing(12); btns.addWidget(self.btn_save)
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
        cfg.deepseek.enabled = self.cb_ds_enabled.isChecked()
        cfg.deepseek.api_key = self.ed_ds_key.text().strip()
        cfg.deepseek.base_url = self.ed_ds_base_url.text().strip() or "https://api.deepseek.com"
        cfg.deepseek.model = self.ed_ds_model.text().strip() or "deepseek-v4-flash"
        cfg.deepseek.timeout = int(self.sp_ds_timeout.value())
        cfg.deepseek.max_history = int(self.sp_ds_history.value())
        cfg.push.bark_key = self.ed_bark_key.text().strip()
        cfg.push.bark_server = self.ed_bark_server.text().strip() or "https://api.day.app"
        cfg.push.bark_sound = self.cb_bark_sound.currentText().strip() or "alarm"
        cfg.push.bark_group = self.ed_bark_group.text().strip() or "hash_alert"
        return cfg

    def _on_save(self) -> None:
        self.saved.emit(self._collect())

    def _on_test_bark(self) -> None:
        from ..utils.notifier import Notifier
        key = self.ed_bark_key.text().strip()
        if not key:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先填写 Bark Key")
            return
        Notifier(self).push_bark(
            title="Hash Trading Bot 测试", body="Bark 配置正常",
            key=key,
            server=self.ed_bark_server.text().strip() or "https://api.day.app",
            sound=self.cb_bark_sound.currentText().strip() or "alarm",
            group=self.ed_bark_group.text().strip() or "hash_alert",
        )

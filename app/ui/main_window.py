"""主窗口: 走势 / 统计 / 预警 / 设置 Tab."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QStatusBar, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..core.alerter import AlertEvent, Alerter
from ..core.analyzer import Analyzer
from ..core.monitor import MonitorController
from ..storage.db import Storage
from ..utils.config import AppConfig, save_config
from ..utils.logger import get_logger
from ..utils.notifier import Notifier
from .alert_panel import AlertPanel
from .settings_panel import SettingsPanel
from .theme import COLOR_EVEN, COLOR_ODD, QSS
from .trend_view import TrendView

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg

        self.setWindowTitle("Hash Trading Bot - 区块单双监控")
        self.resize(1024, 700)
        self.setStyleSheet(QSS)

        # ---- 业务对象 ----
        self.storage = Storage(cfg.storage.db_path)
        self.analyzer = Analyzer(max_history=cfg.analyzer.max_history)
        self.alerter = Alerter(cfg.alert)
        self.notifier = Notifier(self)
        self.monitor = MonitorController(cfg, self.analyzer, self.alerter, self.storage)

        # 从 DB 恢复最近历史
        try:
            prev = self.storage.load_recent_blocks(cfg.analyzer.max_history)
            for p in prev:
                self.analyzer.ingest(p)
        except Exception as e:  # noqa: BLE001
            logger.warning("加载历史失败: %s", e)

        # ---- UI ----
        self._build_ui()
        self._connect_signals()
        self._refresh_all_views()

    # -------------------- UI 构建 --------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部控制栏
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 10, 12, 10)

        title = QLabel("Hash Trading Bot")
        tf = title.font(); tf.setBold(True); tf.setPointSize(14)
        title.setFont(tf)
        top_bar.addWidget(title)

        self.lbl_conn = QLabel("未启动")
        self.lbl_conn.setStyleSheet("color: #8B949E;")
        top_bar.addSpacing(12)
        top_bar.addWidget(self.lbl_conn)

        top_bar.addStretch()

        self.btn_start = QPushButton("开始监控")
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        top_bar.addWidget(self.btn_start)
        top_bar.addWidget(self.btn_stop)

        top_wrap = QWidget(); top_wrap.setLayout(top_bar)
        root.addWidget(top_wrap)

        # Tab
        self.tabs = QTabWidget()
        self.trend_view = TrendView(
            column_max=self.cfg.ui.column_max,
            dot_size=self.cfg.ui.dot_size,
            column_gap=self.cfg.ui.column_gap,
        )
        self.alert_panel = AlertPanel()
        self.settings_panel = SettingsPanel(self.cfg)

        self.tabs.addTab(self.trend_view, "走势")
        self.tabs.addTab(self.alert_panel, "预警")
        self.tabs.addTab(self.settings_panel, "设置")
        root.addWidget(self.tabs, 1)

        self.setCentralWidget(central)

        # 状态栏
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage("就绪")

    # -------------------- 信号 --------------------
    def _connect_signals(self) -> None:
        self.btn_start.clicked.connect(self.start_monitor)
        self.btn_stop.clicked.connect(self.stop_monitor)

        self.monitor.block_received.connect(self._on_block)
        self.monitor.alert_triggered.connect(self._on_alert)
        self.monitor.status_changed.connect(self._on_status)
        self.monitor.error_occurred.connect(self._on_error)

        self.settings_panel.saved.connect(self._on_settings_saved)

        # 加载已有预警
        try:
            self.alert_panel.load_history(self.storage.load_recent_alerts(200))
        except Exception as e:  # noqa: BLE001
            logger.warning("加载预警历史失败: %s", e)

    # -------------------- 动作 --------------------
    def start_monitor(self) -> None:
        if not self.cfg.api.trongrid_api_key:
            QMessageBox.warning(self, "提示", "请先在【设置】页填写 TronGrid API Key，然后保存。")
            self.tabs.setCurrentWidget(self.settings_panel)
            return
        self.monitor.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_conn.setText("● 运行中")
        self.lbl_conn.setStyleSheet(f"color: {COLOR_EVEN};")

    def stop_monitor(self) -> None:
        self.monitor.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_conn.setText("● 已停止")
        self.lbl_conn.setStyleSheet(f"color: {COLOR_ODD};")

    # -------------------- 事件回调 --------------------
    def _on_block(self, period) -> None:
        self.trend_view.on_new_period(
            period,
            self.analyzer.stats.odd_total,
            self.analyzer.stats.even_total,
        )
        self.trend_view.refresh(self.analyzer)
        self.statusBar().showMessage(
            f"最新一期 区块 #{period.block_number}  末位 {period.digit}  "
            f"{'单' if period.parity == 'odd' else '双' if period.parity == 'even' else '?'}"
        )

    def _on_alert(self, event: AlertEvent) -> None:
        self.alert_panel.prepend_event(event)
        if self.cfg.alert.toast_enabled:
            self.notifier.toast("预警", event.message)
        if self.cfg.alert.sound_enabled:
            self.notifier.beep()

    def _on_status(self, text: str) -> None:
        self.trend_view.set_status(text)

    def _on_error(self, text: str) -> None:
        self.statusBar().showMessage(f"⚠ {text}", 5000)

    def _on_settings_saved(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        try:
            save_config(cfg)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "保存失败", str(e))
            return
        # 热更新
        self.monitor.update_config(cfg)
        self.alerter.update_config(cfg.alert)
        self.statusBar().showMessage("设置已保存", 3000)

    # -------------------- 其他 --------------------
    def _refresh_all_views(self) -> None:
        history = self.analyzer.history()
        self.trend_view.apply_periods(
            history,
            self.analyzer.stats.odd_total,
            self.analyzer.stats.even_total,
        )
        self.trend_view.refresh(self.analyzer)

    def closeEvent(self, event) -> None:  # noqa: D401
        try:
            self.monitor.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.storage.close()
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)

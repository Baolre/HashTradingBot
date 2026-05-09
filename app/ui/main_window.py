"""主窗口 - 走势/珠盘/长龙/AI信号/模拟/热力图/明细/预警/设置 + 倒计时+网络灯+懒加载."""
from __future__ import annotations
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
                                QStatusBar, QTabWidget, QVBoxLayout, QWidget)
from ..core.alerter import AlertEvent, Alerter
from ..core.analyzer import Analyzer
from ..core.monitor import MonitorController
from ..core.predictor import Predictor
from ..core.simulator import Simulator
from ..storage.db import Storage
from ..utils.config import AppConfig, save_config
from ..utils.logger import get_logger
from ..utils.notifier import Notifier
from .alert_panel import AlertPanel
from .data_table import DataTablePanel
from .dragon_panel import DragonPanel
from .heatmap_panel import HeatmapPanel
from .probability_panel import ProbabilityPanel
from .settings_panel import SettingsPanel
from .sim_panel import SimPanel
from .theme import COLOR_EVEN, COLOR_ODD, COLOR_SUB, COLOR_BIG, QSS
from .trend_view import TrendView

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Hash Trading Bot - 区块单双监控")
        self.resize(1200, 800)
        self.setStyleSheet(QSS)

        self.storage = Storage(cfg.storage.db_path)
        self.analyzer = Analyzer(max_history=cfg.analyzer.max_history)
        self.alerter = Alerter(cfg.alert)
        self.predictor = Predictor(cfg.predictor)
        self.simulator = Simulator(cfg.sim, self.predictor)
        self.notifier = Notifier(self)
        self.monitor = MonitorController(cfg, self.analyzer, self.alerter, self.storage)

        self._countdown = 0
        self._network_ok = False
        self._alert_unread = 0
        self._last_prediction = None

        try:
            for p in self.storage.load_recent_blocks(cfg.analyzer.max_history):
                self.analyzer.ingest(p)
        except Exception as e:
            logger.warning("加载历史失败: %s", e)

        self._build_ui()
        self._connect_signals()
        self._refresh_all()

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部栏
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 8, 12, 8)
        title = QLabel("Hash Trading Bot")
        tf = title.font(); tf.setBold(True); tf.setPointSize(14); title.setFont(tf)
        top_bar.addWidget(title)

        self.lbl_network = QLabel("---")
        self.lbl_network.setStyleSheet("font-size: 12px;")
        top_bar.addSpacing(8); top_bar.addWidget(self.lbl_network)

        self.lbl_conn = QLabel("未启动")
        self.lbl_conn.setStyleSheet(f"color: {COLOR_SUB};")
        top_bar.addSpacing(4); top_bar.addWidget(self.lbl_conn)
        top_bar.addSpacing(16)

        self.lbl_countdown = QLabel("-- s")
        self.lbl_countdown.setStyleSheet(f"color: {COLOR_BIG}; font-weight: bold; font-size: 13px;")
        top_bar.addWidget(self.lbl_countdown)
        top_bar.addStretch()

        self.lbl_total = QLabel("0 期")
        self.lbl_total.setStyleSheet(f"color: {COLOR_SUB};")
        top_bar.addWidget(self.lbl_total)
        top_bar.addSpacing(12)

        self.btn_start = QPushButton("开始监控")
        self.btn_start.setStyleSheet("QPushButton{background:#1f6feb;color:white;font-weight:bold;padding:6px 16px;border-radius:4px;}")
        self.btn_stop = QPushButton("停止"); self.btn_stop.setEnabled(False)
        top_bar.addWidget(self.btn_start); top_bar.addWidget(self.btn_stop)

        top_wrap = QWidget(); top_wrap.setLayout(top_bar)
        root.addWidget(top_wrap)

        # Tabs
        self.tabs = QTabWidget()
        self.trend_view = TrendView(column_max=self.cfg.ui.column_max, dot_size=self.cfg.ui.dot_size, column_gap=self.cfg.ui.column_gap)
        self.dragon_panel = DragonPanel()
        self.prob_panel = ProbabilityPanel()
        self.sim_panel = SimPanel()
        self.heatmap_panel = HeatmapPanel()
        self.data_table = DataTablePanel()
        self.alert_panel = AlertPanel()
        self.settings_panel = SettingsPanel(self.cfg)

        self.tabs.addTab(self.trend_view, "走势")
        self.tabs.addTab(self.dragon_panel, "长龙")
        self.tabs.addTab(self.prob_panel, "AI信号")
        self.tabs.addTab(self.sim_panel, "模拟")
        self.tabs.addTab(self.heatmap_panel, "热力图")
        self.tabs.addTab(self.data_table, "明细")
        self._alert_tab_idx = self.tabs.addTab(self.alert_panel, "预警")
        self.tabs.addTab(self.settings_panel, "设置")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")

    def _connect_signals(self):
        self.btn_start.clicked.connect(self.start_monitor)
        self.btn_stop.clicked.connect(self.stop_monitor)
        self.monitor.block_received.connect(self._on_block)
        self.monitor.alert_triggered.connect(self._on_alert)
        self.monitor.status_changed.connect(self._on_status)
        self.monitor.error_occurred.connect(self._on_error)
        self.settings_panel.saved.connect(self._on_settings_saved)
        self.sim_panel.btn_start.clicked.connect(self._sim_start)
        self.sim_panel.btn_stop.clicked.connect(self._sim_stop)
        self.sim_panel.btn_reset.clicked.connect(self._sim_reset)
        try:
            self.alert_panel.load_history(self.storage.load_recent_alerts(200))
        except Exception:
            pass

    # ==================== 监控 ====================
    def start_monitor(self):
        if not self.cfg.api.trongrid_api_key:
            QMessageBox.warning(self, "提示", "请先在【设置】页填写 API Key。")
            self.tabs.setCurrentWidget(self.settings_panel)
            return
        self.monitor.start()
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.lbl_conn.setText("运行中"); self.lbl_conn.setStyleSheet(f"color:{COLOR_EVEN};")
        self._set_network(True)
        self._countdown = max(1, self.cfg.filter.block_multiple) * 3
        self._countdown_timer.start()

    def stop_monitor(self):
        self.monitor.stop()
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)
        self.lbl_conn.setText("已停止"); self.lbl_conn.setStyleSheet(f"color:{COLOR_ODD};")
        self._set_network(False)
        self._countdown_timer.stop()
        self.lbl_countdown.setText("-- s")

    # ==================== 倒计时 ====================
    def _tick_countdown(self):
        if self._countdown > 0:
            self._countdown -= 1
        self.lbl_countdown.setText(f"{self._countdown}s")
        c = COLOR_ODD if self._countdown <= 10 else COLOR_BIG
        self.lbl_countdown.setStyleSheet(f"color:{c};font-weight:bold;font-size:13px;")

    def _reset_countdown(self):
        self._countdown = max(1, self.cfg.filter.block_multiple) * 3

    # ==================== 网络灯 ====================
    def _set_network(self, ok: bool):
        self._network_ok = ok
        if ok:
            self.lbl_network.setText("[OK]")
            self.lbl_network.setStyleSheet(f"color:{COLOR_EVEN};font-size:12px;font-weight:bold;")
        else:
            self.lbl_network.setText("[X]")
            self.lbl_network.setStyleSheet(f"color:{COLOR_ODD};font-size:12px;font-weight:bold;")

    # ==================== 预警角标 ====================
    def _update_alert_badge(self):
        text = f"预警 ({self._alert_unread})" if self._alert_unread > 0 else "预警"
        self.tabs.setTabText(self._alert_tab_idx, text)

    def _on_tab_changed(self, index: int):
        if index == self._alert_tab_idx:
            self._alert_unread = 0
            self._update_alert_badge()

    # ==================== 数据到达 ====================
    def _on_block(self, period):
        self._set_network(True)
        self._reset_countdown()
        s = self.analyzer.stats
        self.lbl_total.setText(f"{s.total} 期")

        # 走势页（始终刷新）
        self.trend_view.on_new_period(period, s.odd_total, s.even_total)
        self.trend_view.refresh(self.analyzer)

        # AI 预测
        self._last_prediction = self.predictor.predict(self.analyzer)
        self.trend_view.update_ai_signal(self._last_prediction)

        # 珠盘路（始终追加数据）

        # 模拟（始终处理下注，不管是否在模拟Tab）
        if self.simulator.is_running:
            record = self.simulator.on_new_period(period, self.analyzer)
            if record:
                self.sim_panel.append_record(record)
                self.sim_panel.refresh(self.simulator.state)
                self.sim_panel.update_curve(self.simulator.balance_curve())

        # 懒加载：只刷新当前可见Tab
        current = self.tabs.currentWidget()
        if current is self.dragon_panel:
            dragons = DragonPanel.scan_dragons(self.analyzer, f"{self.cfg.filter.block_multiple}区块", threshold=4)
            self.dragon_panel.refresh(dragons)
        elif current is self.prob_panel:
            self.prob_panel.refresh(self.analyzer, self._last_prediction)
        elif current is self.heatmap_panel:
            self.heatmap_panel.refresh(self.analyzer)
        elif current is self.data_table:
            self.data_table.refresh(self.analyzer)

        self.statusBar().showMessage(
            f"#{period.block_number} 末位={period.digit} {period.parity_label}"
        )

    def _on_alert(self, event: AlertEvent):
        self.alert_panel.prepend_event(event)
        if self.tabs.currentWidget() is not self.alert_panel:
            self._alert_unread += 1
            self._update_alert_badge()
        self.alert_panel.show_popup(event, self)
        if self.cfg.alert.toast_enabled:
            self.notifier.toast("预警", event.message)
        if self.cfg.alert.sound_enabled:
            self.notifier.beep()
        self.notifier.push_to_phone(f"预警: {event.kind}",
                                     f"{event.message}\n区块 #{event.block_number or '-'}", block_url)

    def _on_status(self, text):
        self.trend_view.set_status(text)

    def _on_error(self, text):
        self._set_network(False)
        self.statusBar().showMessage(f"⚠ {text}", 8000)

    def _on_settings_saved(self, cfg: AppConfig):
        self.cfg = cfg
        try:
            save_config(cfg)
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e)); return
        self.monitor.update_config(cfg)
        self.alerter.update_config(cfg.alert)
        self.predictor.update_config(cfg.predictor)
        self.statusBar().showMessage("设置已保存", 3000)

    # ==================== 模拟 ====================
    def _sim_start(self):
        self.simulator.update_config(self.sim_panel.collect_config())
        self.simulator.start()
        self.sim_panel.btn_start.setEnabled(False); self.sim_panel.btn_stop.setEnabled(True)

    def _sim_stop(self):
        self.simulator.stop()
        self.sim_panel.btn_start.setEnabled(True); self.sim_panel.btn_stop.setEnabled(False)

    def _sim_reset(self):
        self.simulator.reset(self.sim_panel.collect_config())
        self.sim_panel.refresh(self.simulator.state)
        self.sim_panel.update_curve(self.simulator.balance_curve())

    # ==================== 全量刷新 ====================
    def _refresh_all(self):
        history = self.analyzer.history()
        s = self.analyzer.stats
        self.trend_view.apply_periods(history, s.odd_total, s.even_total)
        self.trend_view.refresh(self.analyzer)
        self.data_table.refresh(self.analyzer)
        self.lbl_total.setText(f"{s.total} 期")
        dragons = DragonPanel.scan_dragons(self.analyzer, f"{self.cfg.filter.block_multiple}区块", threshold=4)
        self.dragon_panel.refresh(dragons)
        if s.total > 15:
            self._last_prediction = self.predictor.predict(self.analyzer)
            self.prob_panel.refresh(self.analyzer, self._last_prediction)
            self.trend_view.update_ai_signal(self._last_prediction)

    def closeEvent(self, event):
        self._countdown_timer.stop()
        try: self.monitor.stop()
        except: pass
        try: self.storage.close()
        except: pass
        super().closeEvent(event)

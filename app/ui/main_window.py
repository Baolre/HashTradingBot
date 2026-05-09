"""主窗口 - 集成所有面板: 走势/珠盘/长龙/AI/模拟/热力图/明细/预警/设置."""
from __future__ import annotations
from PySide6.QtCore import Qt
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
from .bead_road import BeadRoadView
from .data_table import DataTablePanel
from .dragon_panel import DragonPanel
from .heatmap_panel import HeatmapPanel
from .probability_panel import ProbabilityPanel
from .settings_panel import SettingsPanel
from .sim_panel import SimPanel
from .theme import COLOR_EVEN, COLOR_ODD, QSS
from .trend_view import TrendView

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Hash Trading Bot - 区块单双监控")
        self.resize(1200, 800)
        self.setStyleSheet(QSS)

        # 业务对象
        self.storage = Storage(cfg.storage.db_path)
        self.analyzer = Analyzer(max_history=cfg.analyzer.max_history)
        self.alerter = Alerter(cfg.alert)
        self.predictor = Predictor(cfg.predictor)
        self.simulator = Simulator(cfg.sim, self.predictor)
        self.notifier = Notifier(self)
        self.monitor = MonitorController(cfg, self.analyzer, self.alerter, self.storage)

        # 从 DB 恢复历史
        try:
            for p in self.storage.load_recent_blocks(cfg.analyzer.max_history):
                self.analyzer.ingest(p)
        except Exception as e:
            logger.warning("加载历史失败: %s", e)

        self._build_ui()
        self._connect_signals()
        self._refresh_all()

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部栏
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 10, 12, 10)
        title = QLabel("Hash Trading Bot")
        tf = title.font(); tf.setBold(True); tf.setPointSize(14); title.setFont(tf)
        top_bar.addWidget(title)
        self.lbl_conn = QLabel("● 未启动")
        self.lbl_conn.setStyleSheet("color: #8B949E;")
        top_bar.addSpacing(12); top_bar.addWidget(self.lbl_conn)
        top_bar.addStretch()
        self.btn_start = QPushButton("开始监控")
        self.btn_stop = QPushButton("停止"); self.btn_stop.setEnabled(False)
        top_bar.addWidget(self.btn_start); top_bar.addWidget(self.btn_stop)
        top_wrap = QWidget(); top_wrap.setLayout(top_bar)
        root.addWidget(top_wrap)

        # Tab
        self.tabs = QTabWidget()
        self.trend_view = TrendView(column_max=self.cfg.ui.column_max, dot_size=self.cfg.ui.dot_size, column_gap=self.cfg.ui.column_gap)
        self.bead_road = BeadRoadView()
        self.dragon_panel = DragonPanel()
        self.prob_panel = ProbabilityPanel()
        self.sim_panel = SimPanel()
        self.heatmap_panel = HeatmapPanel()
        self.data_table = DataTablePanel()
        self.alert_panel = AlertPanel()
        self.settings_panel = SettingsPanel(self.cfg)

        self.tabs.addTab(self.trend_view, "走势")
        self.tabs.addTab(self.bead_road, "珠盘路")
        self.tabs.addTab(self.dragon_panel, "长龙")
        self.tabs.addTab(self.prob_panel, "AI信号")
        self.tabs.addTab(self.sim_panel, "模拟")
        self.tabs.addTab(self.heatmap_panel, "热力图")
        self.tabs.addTab(self.data_table, "明细")
        self.tabs.addTab(self.alert_panel, "预警")
        self.tabs.addTab(self.settings_panel, "设置")
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

    def start_monitor(self):
        if not self.cfg.api.trongrid_api_key:
            QMessageBox.warning(self, "提示", "请先在【设置】页填写 API Key。")
            self.tabs.setCurrentWidget(self.settings_panel)
            return
        self.monitor.start()
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.lbl_conn.setText("● 运行中"); self.lbl_conn.setStyleSheet(f"color: {COLOR_EVEN};")

    def stop_monitor(self):
        self.monitor.stop()
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)
        self.lbl_conn.setText("● 已停止"); self.lbl_conn.setStyleSheet(f"color: {COLOR_ODD};")

    def _on_block(self, period):
        s = self.analyzer.stats
        self.trend_view.on_new_period(period, s.odd_total, s.even_total)
        self.trend_view.refresh(self.analyzer)
        self.bead_road.append_period(period)
        self.data_table.refresh(self.analyzer)
        self.heatmap_panel.refresh(self.analyzer)

        # 长龙
        dragons = DragonPanel.scan_dragons(self.analyzer, f"{self.cfg.filter.block_multiple}区块", threshold=4)
        self.dragon_panel.refresh(dragons)

        # AI
        prediction = self.predictor.predict(self.analyzer)
        self.prob_panel.refresh(self.analyzer, prediction)

        # 模拟
        if self.simulator.is_running:
            record = self.simulator.on_new_period(period, self.analyzer)
            if record:
                self.sim_panel.append_record(record)
                self.sim_panel.refresh(self.simulator.state)
                self.sim_panel.update_curve(self.simulator.balance_curve())

        self.statusBar().showMessage(
            f"#{period.block_number} 末位={period.digit} {period.parity_label} {period.size_label}"
        )

    def _on_alert(self, event: AlertEvent):
        self.alert_panel.prepend_event(event)
        if self.cfg.alert.toast_enabled: self.notifier.toast("预警", event.message)
        if self.cfg.alert.sound_enabled: self.notifier.beep()

    def _on_status(self, text): self.trend_view.set_status(text)
    def _on_error(self, text): self.statusBar().showMessage(f"⚠ {text}", 5000)

    def _on_settings_saved(self, cfg: AppConfig):
        self.cfg = cfg
        try: save_config(cfg)
        except Exception as e: QMessageBox.warning(self, "保存失败", str(e)); return
        self.monitor.update_config(cfg)
        self.alerter.update_config(cfg.alert)
        self.predictor.update_config(cfg.predictor)
        self.statusBar().showMessage("设置已保存", 3000)

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

    def _refresh_all(self):
        history = self.analyzer.history()
        s = self.analyzer.stats
        self.trend_view.apply_periods(history, s.odd_total, s.even_total)
        self.trend_view.refresh(self.analyzer)
        self.bead_road.set_periods(history)
        self.data_table.refresh(self.analyzer)
        self.heatmap_panel.refresh(self.analyzer)
        dragons = DragonPanel.scan_dragons(self.analyzer, f"{self.cfg.filter.block_multiple}区块")
        self.dragon_panel.refresh(dragons)
        if s.total > 15:
            self.prob_panel.refresh(self.analyzer, self.predictor.predict(self.analyzer))

    def closeEvent(self, event):
        try: self.monitor.stop()
        except: pass
        try: self.storage.close()
        except: pass
        super().closeEvent(event)

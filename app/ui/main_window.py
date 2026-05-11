"""主窗口 - 一屏 Dashboard + 设置两个 Tab."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from ..core.alerter import AlertEvent, Alerter
from ..core.analyzer import Analyzer
from ..core.monitor import MonitorController
from ..core.prediction_tracker import PredictionTracker
from ..core.predictor import Predictor
from ..core.simulator import Simulator
from ..storage.db import Storage
from ..utils.config import AppConfig, save_config
from ..utils.logger import get_logger
from ..utils.notifier import Notifier
from .dashboard_panel import DashboardPanel
from .settings_panel import SettingsPanel
from .theme import (
    COLOR_ACCENT, COLOR_BIG, COLOR_EVEN, COLOR_ODD, COLOR_SUB, COLOR_TEXT, QSS,
)

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Hash Trading Bot  ·  区块单双监控")
        self.resize(1360, 860)
        self.setStyleSheet(QSS)

        # ---- 业务对象 ----
        self.storage = Storage(cfg.storage.db_path)
        self.analyzer = Analyzer(max_history=cfg.analyzer.max_history)
        self.alerter = Alerter(cfg.alert)
        self.predictor = Predictor(cfg.predictor, deepseek_cfg=cfg.deepseek)
        self.tracker = PredictionTracker(
            max_history=max(1000, cfg.analyzer.max_history)
        )
        self.simulator = Simulator(cfg.sim, self.predictor)
        self.notifier = Notifier(self)
        self.monitor = MonitorController(cfg, self.analyzer, self.alerter, self.storage)

        self._countdown = 0
        self._network_ok = False
        self._last_prediction = None

        # 本地历史
        try:
            for p in self.storage.load_recent_blocks(cfg.analyzer.max_history):
                self.analyzer.ingest(p)
        except Exception as e:
            logger.warning("加载历史失败: %s", e)

        # 基于历史做一次命中率回测
        try:
            self.tracker.backtest(self.predictor, self.analyzer)
        except Exception as e:
            logger.warning("命中率回测失败: %s", e)

        self._build_ui()
        self._connect_signals()
        self._refresh_all()

        # 倒计时
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)

    # ====================== UI ======================
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- 顶部栏（状态 chip + 倒计时 + 进度 + 启停按钮） ---
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(60)
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(20, 10, 20, 10)
        tb.setSpacing(14)

        title = QLabel("Hash Trading Bot")
        title.setObjectName("h1")
        tb.addWidget(title)

        self.lbl_status_chip = QLabel("未启动")
        self.lbl_status_chip.setObjectName("chipIdle")
        tb.addWidget(self.lbl_status_chip)

        self.lbl_network = QLabel("链路  ·  未连接")
        self.lbl_network.setObjectName("mutedSmall")
        tb.addWidget(self.lbl_network)

        tb.addStretch()

        # 倒计时
        cd_box = QVBoxLayout(); cd_box.setSpacing(0); cd_box.setContentsMargins(0, 0, 0, 0)
        cap = QLabel("下一期")
        cap.setObjectName("metricLabel")
        cap.setAlignment(Qt.AlignRight)
        self.lbl_countdown = QLabel("--")
        self.lbl_countdown.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {COLOR_BIG};"
        )
        self.lbl_countdown.setAlignment(Qt.AlignRight)
        cd_box.addWidget(cap); cd_box.addWidget(self.lbl_countdown)
        tb.addLayout(cd_box)

        tb.addSpacing(20)

        # 总期数
        tot_box = QVBoxLayout(); tot_box.setSpacing(0); tot_box.setContentsMargins(0, 0, 0, 0)
        cap2 = QLabel("累计期数")
        cap2.setObjectName("metricLabel"); cap2.setAlignment(Qt.AlignRight)
        self.lbl_total = QLabel("0")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.lbl_total.setAlignment(Qt.AlignRight)
        tot_box.addWidget(cap2); tot_box.addWidget(self.lbl_total)
        tb.addLayout(tot_box)

        tb.addSpacing(20)

        # 回补进度条（默认隐藏）
        self.backfill_bar = QProgressBar()
        self.backfill_bar.setFixedWidth(220)
        self.backfill_bar.setVisible(False)
        self.backfill_bar.setRange(0, 100)
        self.backfill_bar.setFormat("补齐中 %p%")
        tb.addWidget(self.backfill_bar)

        tb.addSpacing(12)

        # 启停按钮
        self.btn_start = QPushButton("开始监控")
        self.btn_start.setObjectName("primary")
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setEnabled(False)
        tb.addWidget(self.btn_start)
        tb.addWidget(self.btn_stop)

        root.addWidget(topbar)

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.dashboard = DashboardPanel(
            column_max=self.cfg.ui.column_max,
            dot_size=self.cfg.ui.dot_size,
            column_gap=self.cfg.ui.column_gap,
        )
        self.settings_panel = SettingsPanel(self.cfg)
        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.settings_panel, "设置")
        root.addWidget(self.tabs, 1)

        self.setCentralWidget(central)

        # 状态栏
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪  ·  点击右上角【开始监控】开始")

    def _connect_signals(self) -> None:
        self.btn_start.clicked.connect(self.start_monitor)
        self.btn_stop.clicked.connect(self.stop_monitor)
        self.monitor.block_received.connect(self._on_block)
        self.monitor.alert_triggered.connect(self._on_alert)
        self.monitor.status_changed.connect(self._on_status)
        self.monitor.error_occurred.connect(self._on_error)
        self.monitor.backfill_progress.connect(self._on_backfill_progress)
        self.settings_panel.saved.connect(self._on_settings_saved)
        try:
            self.dashboard.load_alert_history(
                self.storage.load_recent_alerts(200)
            )
        except Exception:
            pass

    # ====================== 监控控制 ======================
    def start_monitor(self) -> None:
        if not self.cfg.api.trongrid_api_key:
            QMessageBox.warning(self, "提示", "请先在【设置】页填写 TronGrid API Key。")
            self.tabs.setCurrentWidget(self.settings_panel)
            return
        self.monitor.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status_chip.setText("● 运行中")
        self.lbl_status_chip.setObjectName("chipOk")
        self._repolish(self.lbl_status_chip)
        self._set_network(True)
        self._countdown = max(1, self.cfg.filter.block_multiple) * 3
        self._countdown_timer.start()

    def stop_monitor(self) -> None:
        self.monitor.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status_chip.setText("● 已停止")
        self.lbl_status_chip.setObjectName("chipErr")
        self._repolish(self.lbl_status_chip)
        self._set_network(False)
        self._countdown_timer.stop()
        self.lbl_countdown.setText("--")

    # ====================== 倒计时 ======================
    def _tick_countdown(self) -> None:
        if self._countdown > 0:
            self._countdown -= 1
        self.lbl_countdown.setText(f"{self._countdown}s")
        color = COLOR_ODD if self._countdown <= 10 else COLOR_BIG
        self.lbl_countdown.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {color};"
        )

    def _reset_countdown(self) -> None:
        self._countdown = max(1, self.cfg.filter.block_multiple) * 3

    # ====================== 网络状态 ======================
    def _set_network(self, ok: bool) -> None:
        self._network_ok = ok
        if ok:
            self.lbl_network.setText("● 链路  ·  已连接")
            self.lbl_network.setStyleSheet(f"color: {COLOR_EVEN}; font-size: 11px;")
        else:
            self.lbl_network.setText("● 链路  ·  未连接")
            self.lbl_network.setStyleSheet(f"color: {COLOR_SUB}; font-size: 11px;")

    @staticmethod
    def _repolish(w: QWidget) -> None:
        w.style().unpolish(w)
        w.style().polish(w)

    # ====================== 数据回调 ======================
    def _on_block(self, period) -> None:
        self._set_network(True)
        self._reset_countdown()

        s = self.analyzer.stats
        self.lbl_total.setText(str(s.total))

        # 走势卡增量刷新
        self.dashboard.on_new_period(period, s.odd_total, s.even_total)

        # 预测 tracker 顺序：先 settle 上一次，再跑新预测
        try:
            self.tracker.settle(period)
            # 动态权重反馈：把上一期各模型的对错喂给 predictor
            for rec in self.tracker.recent(10):
                if rec.actual is not None and rec.correct is not None:
                    self.predictor.feed_result(rec.model, rec.correct)
        except Exception as e:
            logger.warning("tracker.settle 失败: %s", e)

        self._last_prediction = self.predictor.predict(self.analyzer)
        try:
            self.tracker.record(self._last_prediction)
        except Exception as e:
            logger.warning("tracker.record 失败: %s", e)

        # 模拟（保留后端逻辑，无 UI）
        if self.simulator.is_running:
            try:
                self.simulator.on_new_period(period, self.analyzer)
            except Exception as e:
                logger.warning("simulator.on_new_period 失败: %s", e)

        # Dashboard 其他部分全量刷新（都在一个页面，不需要懒加载了）
        self.dashboard.refresh_all(self.analyzer, self._last_prediction, self.tracker)

        self.statusBar().showMessage(
            f"#{period.block_number}  末位={period.digit}  {period.parity_label}"
        )

    def _on_alert(self, event: AlertEvent) -> None:
        self.dashboard.on_alert(event)
        self.dashboard.show_alert_popup(event, self)

        # 交叉预警 → 声音 + Bark 手机推送
        if getattr(event, "kind", "") == "alternation":
            try:
                if getattr(self.cfg.alert, "sound_enabled", True):
                    self.notifier.beep()
            except Exception as e:
                logger.warning("声音提醒失败: %s", e)
            try:
                if getattr(self.cfg.alert, "bark_enabled", True) and self.cfg.push.bark_key:
                    block_no = event.block_number or "-"
                    url = (
                        f"https://tronscan.org/#/block/{event.block_number}"
                        if event.block_number else ""
                    )
                    self.notifier.push_bark(
                        title=f"交叉预警 (#{block_no})",
                        body=event.message,
                        key=self.cfg.push.bark_key,
                        server=self.cfg.push.bark_server or "https://api.day.app",
                        sound=self.cfg.push.bark_sound or "alarm",
                        group=self.cfg.push.bark_group or "hash_alert",
                        url=url,
                    )
            except Exception as e:
                logger.warning("Bark 推送调用失败: %s", e)

    def _on_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _on_backfill_progress(self, done: int, total: int) -> None:
        if total <= 0:
            self.backfill_bar.setVisible(False)
            return
        pct = int(done * 100 / total)
        self.backfill_bar.setVisible(True)
        self.backfill_bar.setValue(pct)
        self.statusBar().showMessage(f"历史补齐  {done}/{total}  ({pct}%)")
        if done >= total:
            # 结束：延迟 1 秒后隐藏进度条，全量刷新一次
            QTimer.singleShot(1000, lambda: self.backfill_bar.setVisible(False))
            try:
                self._refresh_all()
            except Exception:
                pass

    def _on_error(self, text: str) -> None:
        self._set_network(False)
        self.statusBar().showMessage(f"⚠  {text}", 8000)

    def _on_settings_saved(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        try:
            save_config(cfg)
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return
        self.monitor.update_config(cfg)
        self.alerter.update_config(cfg.alert)
        self.predictor.update_config(cfg.predictor)
        self.predictor.update_deepseek_config(cfg.deepseek)
        self.statusBar().showMessage("设置已保存", 3000)

    # ====================== 全量刷新 ======================
    def _refresh_all(self) -> None:
        s = self.analyzer.stats
        self.lbl_total.setText(str(s.total))
        self.dashboard.apply_history(self.analyzer)
        # Predictor 内部自己判断数据是否足够
        self._last_prediction = self.predictor.predict(self.analyzer)
        self.dashboard.refresh_all(self.analyzer, self._last_prediction, self.tracker)

    # ====================== 关闭 ======================
    def closeEvent(self, event) -> None:
        self._countdown_timer.stop()
        try: self.monitor.stop()
        except Exception: pass
        try: self.storage.close()
        except Exception: pass
        super().closeEvent(event)

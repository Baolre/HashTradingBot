"""后台监控：Qt 线程里轮询 TronGrid，过滤 20 倍数区块，推入 Analyzer/Storage."""
from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ..api.trongrid import BlockInfo, TronGridClient
from ..utils.config import AppConfig
from ..utils.logger import get_logger
from .alerter import AlertEvent, Alerter
from .analyzer import Analyzer, Period

logger = get_logger(__name__)


class MonitorWorker(QObject):
    """在独立 QThread 中跑的轮询 Worker."""

    # 信号
    block_received = Signal(object)   # Period
    alert_triggered = Signal(object)  # AlertEvent
    status_changed = Signal(str)      # 文本状态
    error_occurred = Signal(str)
    backfill_progress = Signal(int, int)  # done, total
    stopped = Signal()

    def __init__(self, cfg: AppConfig, analyzer: Analyzer, alerter: Alerter, storage=None):
        super().__init__()
        self.cfg = cfg
        self.analyzer = analyzer
        self.alerter = alerter
        self.storage = storage

        self._client = TronGridClient(
            endpoint=cfg.api.trongrid_endpoint,
            api_key=cfg.api.trongrid_api_key,
            timeout=cfg.api.timeout,
        )
        self._running = False
        # 启动时若 analyzer 里已有历史，则从最后一块之后开始继续
        latest = analyzer.latest()
        self._last_processed: Optional[int] = latest.block_number if latest else None

        # 将预警事件转发给 GUI
        self.alerter.on_alert(self._on_alert)

    # ------------------- 控制 -------------------
    def stop(self) -> None:
        self._running = False

    def update_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._client = TronGridClient(
            endpoint=cfg.api.trongrid_endpoint,
            api_key=cfg.api.trongrid_api_key,
            timeout=cfg.api.timeout,
        )
        self.alerter.update_config(cfg.alert)

    # ------------------- 回调 -------------------
    def _on_alert(self, event: AlertEvent) -> None:
        if self.storage is not None:
            try:
                self.storage.save_alert(event.kind, event.message, event.block_number)
            except Exception as e:  # noqa: BLE001
                logger.warning("存储预警失败: %s", e)
        self.alert_triggered.emit(event)

    # ------------------- 主循环 -------------------
    def run(self) -> None:
        self._running = True
        self.status_changed.emit("monitor 已启动")
        logger.info("monitor started")

        # 启动时自动补齐（按 BackfillConfig；若 backfill 未启用则跳过）
        try:
            if getattr(self.cfg, "backfill", None) and self.cfg.backfill.enabled:
                self._backfill()
        except Exception as e:  # noqa: BLE001
            logger.exception("backfill error")
            self.error_occurred.emit(f"历史补齐失败: {e}")

        while self._running:
            try:
                self._tick()
            except Exception as e:  # noqa: BLE001
                logger.exception("monitor tick error")
                self.error_occurred.emit(str(e))

            # 分段 sleep 以便尽快响应 stop
            interval = max(1, int(self.cfg.api.poll_interval))
            for _ in range(interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)

        self.status_changed.emit("monitor 已停止")
        logger.info("monitor stopped")
        self.stopped.emit()

    # ------------------- 历史补齐 -------------------
    def _backfill(self) -> None:
        """启动时从链上回补历史。
        - 若 analyzer 里已有历史：补齐 _last_processed 之后到 target_high 之间的所有倍数块
        - 若没有历史：按 backfill.days 估算需要多少期（TRON 出块 ~3s），最多 max_blocks_per_run
        """
        if not self.cfg.api.trongrid_api_key:
            self.error_occurred.emit("未配置 API Key，跳过历史补齐")
            return

        multiple = max(1, int(self.cfg.filter.block_multiple))
        latest: Optional[BlockInfo] = self._client.get_now_block()
        if latest is None:
            self.error_occurred.emit("获取最新区块失败，无法补齐")
            return
        target_high = (latest.number // multiple) * multiple
        if target_high < multiple:
            return

        max_blocks = max(1, int(self.cfg.backfill.max_blocks_per_run))
        days = max(0, int(self.cfg.backfill.days))

        if self._last_processed is None:
            # 首次运行：按 days 估算要补的期数
            # 每 multiple 块一期；TRON 出块约 3s → 每天约 86400/3/multiple 期
            periods_per_day = max(1, 86400 // 3 // multiple)
            want_periods = days * periods_per_day if days > 0 else max_blocks
            want_periods = min(want_periods, max_blocks)
            start = target_high - (want_periods - 1) * multiple
            if start < multiple:
                start = multiple
        else:
            # 断点续跑
            start = self._last_processed + multiple
            total_periods = max(0, (target_high - self._last_processed) // multiple)
            if total_periods > max_blocks:
                start = target_high - (max_blocks - 1) * multiple
                logger.info("补齐超过 max=%s 期，跳过较早区块，从 #%s 开始", max_blocks, start)

        if start > target_high:
            return

        total = (target_high - start) // multiple + 1
        self.status_changed.emit(f"正在补齐历史: 共 {total} 期（#{start} ~ #{target_high}）")
        self.backfill_progress.emit(0, total)

        n = start
        done = 0
        while n <= target_high and self._running:
            self._process_block_number(n)
            self._last_processed = n
            done += 1
            # 每 10 期推送一次进度，减少信号抖动
            if done % 10 == 0 or done == total:
                self.backfill_progress.emit(done, total)
                self.status_changed.emit(f"补齐进度 {done}/{total}")
            n += multiple

        self.backfill_progress.emit(done, total)
        self.status_changed.emit(f"历史补齐完成: {done}/{total} 期")

    # ------------------- 单次轮询 -------------------
    def _tick(self) -> None:
        if not self.cfg.api.trongrid_api_key:
            self.error_occurred.emit("未配置 TronGrid API Key")
            return

        latest: Optional[BlockInfo] = self._client.get_now_block()
        if latest is None:
            self.error_occurred.emit("获取最新区块失败")
            return

        self.status_changed.emit(
            f"当前链上最新: #{latest.number}  tx={latest.tx_count}"
        )

        multiple = max(1, int(self.cfg.filter.block_multiple))
        target_high = (latest.number // multiple) * multiple
        if target_high < multiple:
            return

        if self._last_processed is None:
            # backfill 被禁用或失败时的兜底：仅取最近一期
            self._process_block_number(target_high)
            self._last_processed = target_high
            return

        # 正常补齐 last_processed 之后的所有倍数块，限制一轮最多 50 个以防拖慢
        n = self._last_processed + multiple
        gap = (target_high - self._last_processed) // multiple
        if gap > 50:
            n = target_high - 50 * multiple + multiple
            logger.info("单轮追赶过多，跳过较早区块，从 #%s 开始", n)
        while n <= target_high and self._running:
            self._process_block_number(n)
            self._last_processed = n
            n += multiple

    def _process_block_number(self, num: int) -> None:
        if self.analyzer.contains_block(num):
            return
        info = self._client.get_block_by_num(num)
        if info is None or not info.hash:
            logger.warning("取区块 #%s 失败", num)
            self.error_occurred.emit(f"取区块 #{num} 失败")
            return
        period: Period = self.analyzer.build_period(
            block_number=info.number,
            block_hash=info.hash,
            timestamp_ms=info.timestamp_ms,
        )
        self.analyzer.ingest(period)
        if self.storage is not None:
            try:
                self.storage.save_block(period)
            except Exception as e:  # noqa: BLE001
                logger.warning("保存区块失败: %s", e)

        logger.info("新区块 #%s 末位=%s %s (总 %d 期)",
                    period.block_number, period.digit, period.parity_label,
                    self.analyzer.stats.total)
        self.block_received.emit(period)
        # 触发预警检查
        self.alerter.check(self.analyzer, period)


class MonitorController(QObject):
    """对外门面：启动/停止，内部管理 QThread + Worker."""

    block_received = Signal(object)
    alert_triggered = Signal(object)
    status_changed = Signal(str)
    error_occurred = Signal(str)
    backfill_progress = Signal(int, int)

    def __init__(self, cfg: AppConfig, analyzer: Analyzer, alerter: Alerter, storage=None):
        super().__init__()
        self.cfg = cfg
        self.analyzer = analyzer
        self.alerter = alerter
        self.storage = storage
        self._thread: Optional[QThread] = None
        self._worker: Optional[MonitorWorker] = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self) -> None:
        if self.is_running():
            return
        self._thread = QThread()
        self._worker = MonitorWorker(self.cfg, self.analyzer, self.alerter, self.storage)
        self._worker.moveToThread(self._thread)

        # 信号桥接
        self._worker.block_received.connect(self.block_received)
        self._worker.alert_triggered.connect(self.alert_triggered)
        self._worker.status_changed.connect(self.status_changed)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.backfill_progress.connect(self.backfill_progress)

        self._thread.started.connect(self._worker.run)
        self._worker.stopped.connect(self._thread.quit)
        self._worker.stopped.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        self._thread = None
        self._worker = None

    def update_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        if self._worker is not None:
            self._worker.update_config(cfg)

"""预警引擎.

当前规则:
- alternation: 监测尾部连续"奇偶交替"长度 >= 阈值时触发
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from ..utils.config import AlertConfig
from ..utils.logger import get_logger
from .analyzer import Analyzer, Period

logger = get_logger(__name__)


ALERT_ALTERNATION = "alternation"


@dataclass
class AlertEvent:
    kind: str
    message: str
    block_number: Optional[int] = None
    run_len: int = 0


AlertHandler = Callable[[AlertEvent], None]


class Alerter:
    """根据最新一期检查各类预警. 维护冷却以防刷屏."""

    def __init__(self, cfg: AlertConfig):
        self.cfg = cfg
        self._handlers: List[AlertHandler] = []
        # 冷却：key = alert_kind，value = 距上次触发已累计的期数
        # 初始设为一个很大的值，以便第一次命中就能触发
        self._since_last: dict[str, int] = {ALERT_ALTERNATION: 10**9}

    # ------------------- 订阅 -------------------
    def on_alert(self, handler: AlertHandler) -> None:
        self._handlers.append(handler)

    def _emit(self, event: AlertEvent) -> None:
        for h in list(self._handlers):
            try:
                h(event)
            except Exception as e:  # noqa: BLE001
                logger.warning("alert handler error: %s", e)

    # ------------------- 检查 -------------------
    def check(self, analyzer: Analyzer, latest: Period) -> List[AlertEvent]:
        """每进来一期就调用一次."""
        events: List[AlertEvent] = []

        # 全部计数器先加一（不管是否触发）
        for k in self._since_last:
            self._since_last[k] += 1

        if self.cfg.alternation_enabled and latest.is_valid:
            run = analyzer.alternation_run_length()
            threshold = max(2, int(self.cfg.alternation_threshold or 2))
            if run >= threshold and self._since_last[ALERT_ALTERNATION] >= max(1, self.cfg.cooldown_periods):
                msg = f"检测到连续交叉 {run} 期（阈值 {threshold}）"
                events.append(AlertEvent(
                    kind=ALERT_ALTERNATION,
                    message=msg,
                    block_number=latest.block_number,
                    run_len=run,
                ))
                self._since_last[ALERT_ALTERNATION] = 0

        for ev in events:
            self._emit(ev)
        return events

    def update_config(self, cfg: AlertConfig) -> None:
        self.cfg = cfg

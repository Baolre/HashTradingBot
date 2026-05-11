"""预警引擎 - 仅交叉预警（单双单双…连续交替）."""
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
    def __init__(self, cfg: AlertConfig):
        self.cfg = cfg
        self._handlers: List[AlertHandler] = []
        self._since_last: int = 10**9  # 距上次触发的期数

    def on_alert(self, handler: AlertHandler) -> None:
        self._handlers.append(handler)

    def _emit(self, event: AlertEvent) -> None:
        for h in list(self._handlers):
            try:
                h(event)
            except Exception as e:
                logger.warning("alert handler error: %s", e)

    def check(self, analyzer: Analyzer, latest: Period) -> List[AlertEvent]:
        events: List[AlertEvent] = []
        self._since_last += 1

        cooldown = max(1, self.cfg.cooldown_periods)

        if self.cfg.alternation_enabled and latest.is_valid:
            run = analyzer.alternation_run_length()
            threshold = max(2, self.cfg.alternation_threshold)
            if run >= threshold and self._since_last >= cooldown:
                events.append(AlertEvent(
                    kind=ALERT_ALTERNATION,
                    message=f"单双交叉 连续 {run} 期（阈值 {threshold}）",
                    block_number=latest.block_number,
                    run_len=run,
                ))
                self._since_last = 0

        for ev in events:
            self._emit(ev)
        return events

    def update_config(self, cfg: AlertConfig) -> None:
        self.cfg = cfg

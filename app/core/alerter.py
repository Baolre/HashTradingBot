"""预警引擎 - 4种预警规则: 单双交叉/连号/大小交叉/遗漏."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from ..utils.config import AlertConfig
from ..utils.logger import get_logger
from .analyzer import Analyzer, Period, PARITY_ODD, PARITY_EVEN, SIZE_BIG, SIZE_SMALL

logger = get_logger(__name__)

ALERT_ALTERNATION = "alternation"
ALERT_STREAK = "streak"
ALERT_SIZE_ALTERNATION = "size_alternation"
ALERT_MISS = "miss"


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
        self._since_last: Dict[str, int] = {
            ALERT_ALTERNATION: 10**9,
            ALERT_STREAK: 10**9,
            ALERT_SIZE_ALTERNATION: 10**9,
            ALERT_MISS: 10**9,
        }

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
        for k in self._since_last:
            self._since_last[k] += 1

        cooldown = max(1, self.cfg.cooldown_periods)

        # 1. 单双交叉
        if self.cfg.alternation_enabled and latest.is_valid:
            run = analyzer.alternation_run_length("parity")
            threshold = max(2, self.cfg.alternation_threshold)
            if run >= threshold and self._since_last[ALERT_ALTERNATION] >= cooldown:
                events.append(AlertEvent(
                    kind=ALERT_ALTERNATION,
                    message=f"单双交叉 连续 {run} 期（阈值 {threshold}）",
                    block_number=latest.block_number, run_len=run,
                ))
                self._since_last[ALERT_ALTERNATION] = 0

        # 2. 连号
        if getattr(self.cfg, 'streak_enabled', True) and latest.is_valid:
            val, run = analyzer.same_run_length("parity")
            threshold = getattr(self.cfg, 'streak_threshold', 6)
            if run >= threshold and self._since_last[ALERT_STREAK] >= cooldown:
                label = "单" if val == PARITY_ODD else "双"
                events.append(AlertEvent(
                    kind=ALERT_STREAK,
                    message=f"{label} 连出 {run} 期（阈值 {threshold}）",
                    block_number=latest.block_number, run_len=run,
                ))
                self._since_last[ALERT_STREAK] = 0

        # 3. 大小交叉
        if getattr(self.cfg, 'size_alternation_enabled', True) and latest.is_valid:
            run = analyzer.alternation_run_length("size")
            threshold = getattr(self.cfg, 'size_alternation_threshold', 6)
            if run >= threshold and self._since_last[ALERT_SIZE_ALTERNATION] >= cooldown:
                events.append(AlertEvent(
                    kind=ALERT_SIZE_ALTERNATION,
                    message=f"大小交叉 连续 {run} 期（阈值 {threshold}）",
                    block_number=latest.block_number, run_len=run,
                ))
                self._since_last[ALERT_SIZE_ALTERNATION] = 0

        # 4. 遗漏
        if getattr(self.cfg, 'miss_enabled', True) and latest.is_valid:
            threshold = getattr(self.cfg, 'miss_threshold', 10)
            s = analyzer.stats
            missed = []
            if s.odd_miss >= threshold:
                missed.append(f"单遗漏{s.odd_miss}期")
            if s.even_miss >= threshold:
                missed.append(f"双遗漏{s.even_miss}期")
            if s.big_miss >= threshold:
                missed.append(f"大遗漏{s.big_miss}期")
            if s.small_miss >= threshold:
                missed.append(f"小遗漏{s.small_miss}期")
            if missed and self._since_last[ALERT_MISS] >= cooldown:
                events.append(AlertEvent(
                    kind=ALERT_MISS,
                    message=f"遗漏预警: {', '.join(missed)}",
                    block_number=latest.block_number,
                    run_len=max(s.odd_miss, s.even_miss, s.big_miss, s.small_miss),
                ))
                self._since_last[ALERT_MISS] = 0

        for ev in events:
            self._emit(ev)
        return events

    def update_config(self, cfg: AlertConfig) -> None:
        self.cfg = cfg

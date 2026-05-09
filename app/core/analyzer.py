"""核心分析：单双判定 + 连号 / 遗漏 / 交叉 统计."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple


# 边枚举
PARITY_ODD = "odd"   # 单
PARITY_EVEN = "even"  # 双
PARITY_UNKNOWN = "unknown"


def last_digit_of_hash(block_hash: str) -> Optional[int]:
    """从区块哈希里，从右往左找第一个数字字符，返回对应数字.

    - 忽略字母 a-f
    - 如果整条哈希没有数字字符（理论上极少），返回 None
    """
    if not block_hash:
        return None
    for ch in reversed(block_hash):
        if ch.isdigit():
            return int(ch)
    return None


def parity_of_block_hash(block_hash: str) -> str:
    d = last_digit_of_hash(block_hash)
    if d is None:
        return PARITY_UNKNOWN
    return PARITY_ODD if (d % 2 == 1) else PARITY_EVEN


@dataclass
class Period:
    """一期记录."""
    block_number: int
    block_hash: str
    digit: Optional[int]      # 判定所用数字
    parity: str               # odd / even / unknown
    timestamp_ms: int = 0

    @property
    def is_odd(self) -> bool:
        return self.parity == PARITY_ODD

    @property
    def is_even(self) -> bool:
        return self.parity == PARITY_EVEN

    @property
    def is_valid(self) -> bool:
        return self.parity in (PARITY_ODD, PARITY_EVEN)


@dataclass
class Stats:
    odd_total: int = 0
    even_total: int = 0
    total: int = 0
    current_streak_parity: str = PARITY_UNKNOWN
    current_streak_len: int = 0
    longest_odd_streak: int = 0
    longest_even_streak: int = 0
    # 最近一次交叉长度（单双单双...）
    current_alternation_len: int = 0


class Analyzer:
    """维护一个有界历史 + 实时统计."""

    def __init__(self, max_history: int = 200):
        self.max_history = max_history
        self._history: Deque[Period] = deque(maxlen=max_history)
        self.stats = Stats()

    # ------------------- API -------------------
    def build_period(
        self,
        block_number: int,
        block_hash: str,
        timestamp_ms: int = 0,
    ) -> Period:
        d = last_digit_of_hash(block_hash)
        parity = PARITY_UNKNOWN
        if d is not None:
            parity = PARITY_ODD if (d % 2 == 1) else PARITY_EVEN
        return Period(
            block_number=block_number,
            block_hash=block_hash,
            digit=d,
            parity=parity,
            timestamp_ms=timestamp_ms,
        )

    def ingest(self, period: Period) -> Period:
        """追加一期并更新统计. 返回同一个 Period 方便链式."""
        self._history.append(period)
        self._recompute_stats()
        return period

    def history(self) -> List[Period]:
        return list(self._history)

    def last(self, n: int) -> List[Period]:
        if n <= 0:
            return []
        return list(self._history)[-n:]

    def latest(self) -> Optional[Period]:
        return self._history[-1] if self._history else None

    def contains_block(self, block_number: int) -> bool:
        return any(p.block_number == block_number for p in self._history)

    def clear(self) -> None:
        self._history.clear()
        self.stats = Stats()

    # ------------------- 预警辅助 -------------------
    def alternation_run_length(self) -> int:
        """返回当前从最后一期向前回看，连续"奇偶交替"的期数（含最后一期）.

        例：... 单 双 单 双 单 → 返回 5
             ... 单 单 双 单     → 返回 3（单双单）
        仅统计 is_valid 期.
        """
        run = 0
        prev_parity: Optional[str] = None
        for p in reversed(self._history):
            if not p.is_valid:
                break
            if prev_parity is None:
                run = 1
                prev_parity = p.parity
                continue
            if p.parity != prev_parity:
                run += 1
                prev_parity = p.parity
            else:
                break
        return run

    def same_run_length(self) -> Tuple[str, int]:
        """返回 (最后一期的 parity, 与之相同的连续期数)."""
        parity = PARITY_UNKNOWN
        run = 0
        for p in reversed(self._history):
            if not p.is_valid:
                break
            if parity == PARITY_UNKNOWN:
                parity = p.parity
                run = 1
            elif p.parity == parity:
                run += 1
            else:
                break
        return parity, run

    # ------------------- 内部 -------------------
    def _recompute_stats(self) -> None:
        s = Stats()
        prev_parity: Optional[str] = None
        cur_len = 0
        longest_odd = 0
        longest_even = 0

        for p in self._history:
            if p.is_odd:
                s.odd_total += 1
            elif p.is_even:
                s.even_total += 1
            if p.is_valid:
                s.total += 1
                if prev_parity == p.parity:
                    cur_len += 1
                else:
                    cur_len = 1
                    prev_parity = p.parity
                if p.is_odd:
                    longest_odd = max(longest_odd, cur_len)
                else:
                    longest_even = max(longest_even, cur_len)

        s.current_streak_parity = prev_parity or PARITY_UNKNOWN
        s.current_streak_len = cur_len
        s.longest_odd_streak = longest_odd
        s.longest_even_streak = longest_even
        s.current_alternation_len = self.alternation_run_length()
        self.stats = s

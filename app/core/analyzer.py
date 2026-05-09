"""核心分析：单双 + 大小 判定 + 连号 / 遗漏 / 交叉 统计."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple


# ===== 枚举常量 =====
PARITY_ODD = "odd"       # 单
PARITY_EVEN = "even"     # 双
PARITY_UNKNOWN = "unknown"

SIZE_BIG = "big"         # 大 (>=5)
SIZE_SMALL = "small"     # 小 (<5)
SIZE_UNKNOWN = "unknown"


def last_digit_of_hash(block_hash: str) -> Optional[int]:
    """从区块哈希里，从右往左找第一个数字字符，返回对应数字."""
    if not block_hash:
        return None
    for ch in reversed(block_hash):
        if ch.isdigit():
            return int(ch)
    return None


def parity_of_digit(d: Optional[int]) -> str:
    if d is None:
        return PARITY_UNKNOWN
    return PARITY_ODD if (d % 2 == 1) else PARITY_EVEN


def size_of_digit(d: Optional[int]) -> str:
    if d is None:
        return SIZE_UNKNOWN
    return SIZE_BIG if d >= 5 else SIZE_SMALL


@dataclass
class Period:
    """一期记录."""
    block_number: int
    block_hash: str
    digit: Optional[int]
    parity: str
    size: str = SIZE_UNKNOWN
    timestamp_ms: int = 0

    @property
    def is_odd(self) -> bool:
        return self.parity == PARITY_ODD

    @property
    def is_even(self) -> bool:
        return self.parity == PARITY_EVEN

    @property
    def is_big(self) -> bool:
        return self.size == SIZE_BIG

    @property
    def is_small(self) -> bool:
        return self.size == SIZE_SMALL

    @property
    def is_valid(self) -> bool:
        return self.parity in (PARITY_ODD, PARITY_EVEN)

    @property
    def parity_label(self) -> str:
        return "单" if self.is_odd else ("双" if self.is_even else "?")

    @property
    def size_label(self) -> str:
        return "大" if self.is_big else ("小" if self.is_small else "?")

    @property
    def combo_label(self) -> str:
        return f"{self.parity_label}{self.size_label}"


@dataclass
class Stats:
    total: int = 0
    odd_total: int = 0
    even_total: int = 0
    big_total: int = 0
    small_total: int = 0
    odd_big: int = 0
    odd_small: int = 0
    even_big: int = 0
    even_small: int = 0
    current_streak_parity: str = PARITY_UNKNOWN
    current_streak_len: int = 0
    longest_odd_streak: int = 0
    longest_even_streak: int = 0
    current_streak_size: str = SIZE_UNKNOWN
    current_size_streak_len: int = 0
    longest_big_streak: int = 0
    longest_small_streak: int = 0
    current_alternation_len: int = 0
    current_size_alternation_len: int = 0
    odd_miss: int = 0
    even_miss: int = 0
    big_miss: int = 0
    small_miss: int = 0


class Analyzer:
    """维护一个有界历史 + 实时统计."""

    def __init__(self, max_history: int = 200):
        self.max_history = max_history
        self._history: Deque[Period] = deque(maxlen=max_history)
        self.stats = Stats()

    def build_period(self, block_number: int, block_hash: str, timestamp_ms: int = 0) -> Period:
        d = last_digit_of_hash(block_hash)
        return Period(
            block_number=block_number,
            block_hash=block_hash,
            digit=d,
            parity=parity_of_digit(d),
            size=size_of_digit(d),
            timestamp_ms=timestamp_ms,
        )

    def ingest(self, period: Period) -> Period:
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
    def alternation_run_length(self, attr: str = "parity") -> int:
        run = 0
        prev_val: Optional[str] = None
        for p in reversed(self._history):
            if not p.is_valid:
                break
            val = getattr(p, attr, "unknown")
            if val in (PARITY_UNKNOWN, SIZE_UNKNOWN, "unknown"):
                break
            if prev_val is None:
                run = 1
                prev_val = val
                continue
            if val != prev_val:
                run += 1
                prev_val = val
            else:
                break
        return run

    def same_run_length(self, attr: str = "parity") -> Tuple[str, int]:
        value = "unknown"
        run = 0
        for p in reversed(self._history):
            if not p.is_valid:
                break
            val = getattr(p, attr, "unknown")
            if val in (PARITY_UNKNOWN, SIZE_UNKNOWN, "unknown"):
                break
            if value == "unknown":
                value = val
                run = 1
            elif val == value:
                run += 1
            else:
                break
        return value, run

    def get_transition_matrix(self, attr: str = "parity", window: int = 50) -> Dict[str, Dict[str, float]]:
        last_n = self.last(window)
        counts: Dict[str, Dict[str, int]] = {}
        for i in range(len(last_n) - 1):
            cur = getattr(last_n[i], attr, "unknown")
            nxt = getattr(last_n[i + 1], attr, "unknown")
            if cur == "unknown" or nxt == "unknown":
                continue
            if cur not in counts:
                counts[cur] = {}
            counts[cur][nxt] = counts[cur].get(nxt, 0) + 1
        matrix: Dict[str, Dict[str, float]] = {}
        for state, transitions in counts.items():
            total = sum(transitions.values())
            matrix[state] = {k: v / total for k, v in transitions.items()} if total else {}
        return matrix

    def frequency_distribution(self, window: int = 50) -> Dict[int, int]:
        dist: Dict[int, int] = {i: 0 for i in range(10)}
        for p in self.last(window):
            if p.digit is not None:
                dist[p.digit] += 1
        return dist

    # ------------------- 内部 -------------------
    def _recompute_stats(self) -> None:
        s = Stats()
        prev_parity: Optional[str] = None
        prev_size: Optional[str] = None
        cur_parity_len = 0
        cur_size_len = 0
        longest_odd = longest_even = longest_big = longest_small = 0

        for p in self._history:
            if not p.is_valid:
                continue
            s.total += 1
            if p.is_odd:
                s.odd_total += 1
            else:
                s.even_total += 1
            if p.is_big:
                s.big_total += 1
            else:
                s.small_total += 1
            if p.is_odd and p.is_big:
                s.odd_big += 1
            elif p.is_odd and p.is_small:
                s.odd_small += 1
            elif p.is_even and p.is_big:
                s.even_big += 1
            elif p.is_even and p.is_small:
                s.even_small += 1

            if prev_parity == p.parity:
                cur_parity_len += 1
            else:
                cur_parity_len = 1
                prev_parity = p.parity
            if p.is_odd:
                longest_odd = max(longest_odd, cur_parity_len)
            else:
                longest_even = max(longest_even, cur_parity_len)

            if prev_size == p.size:
                cur_size_len += 1
            else:
                cur_size_len = 1
                prev_size = p.size
            if p.is_big:
                longest_big = max(longest_big, cur_size_len)
            else:
                longest_small = max(longest_small, cur_size_len)

        s.current_streak_parity = prev_parity or PARITY_UNKNOWN
        s.current_streak_len = cur_parity_len
        s.longest_odd_streak = longest_odd
        s.longest_even_streak = longest_even
        s.current_streak_size = prev_size or SIZE_UNKNOWN
        s.current_size_streak_len = cur_size_len
        s.longest_big_streak = longest_big
        s.longest_small_streak = longest_small
        s.current_alternation_len = self.alternation_run_length("parity")
        s.current_size_alternation_len = self.alternation_run_length("size")

        # 遗漏计算
        s.odd_miss = s.even_miss = s.big_miss = s.small_miss = 0
        for p in reversed(self._history):
            if not p.is_valid:
                break
            if p.is_odd:
                break
            s.odd_miss += 1
        for p in reversed(self._history):
            if not p.is_valid:
                break
            if p.is_even:
                break
            s.even_miss += 1
        for p in reversed(self._history):
            if not p.is_valid:
                break
            if p.is_big:
                break
            s.big_miss += 1
        for p in reversed(self._history):
            if not p.is_valid:
                break
            if p.is_small:
                break
            s.small_miss += 1

        self.stats = s

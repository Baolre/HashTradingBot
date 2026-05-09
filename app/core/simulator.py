"""模拟下注系统 - 6种策略（纯单双）."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .analyzer import PARITY_EVEN, PARITY_ODD, Analyzer, Period
from .predictor import Predictor
from ..utils.config import SimConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)
_FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]


@dataclass
class BetRecord:
    period_num: int
    bet_amount: float
    bet_target: str
    actual: str
    won: bool
    pnl: float
    balance_after: float
    strategy: str = ""


@dataclass
class SimState:
    balance: float = 10000.0
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    max_balance: float = 10000.0
    max_drawdown: float = 0.0
    current_streak: int = 0
    _fib_idx: int = 0
    _paroli_wins: int = 0
    _dalembert_level: int = 0
    history: List[BetRecord] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_bets if self.total_bets > 0 else 0.0


class Simulator:
    def __init__(self, cfg: SimConfig, predictor: Optional[Predictor] = None):
        self.cfg = cfg
        self.predictor = predictor
        self.state = SimState(balance=cfg.initial_balance, max_balance=cfg.initial_balance)
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self): self._running = True
    def stop(self): self._running = False

    def reset(self, cfg: Optional[SimConfig] = None):
        if cfg: self.cfg = cfg
        self.state = SimState(balance=self.cfg.initial_balance, max_balance=self.cfg.initial_balance)

    def update_config(self, cfg: SimConfig): self.cfg = cfg

    def on_new_period(self, period: Period, analyzer: Analyzer) -> Optional[BetRecord]:
        if not self._running or not period.is_valid:
            return None
        target = self._select_target(analyzer)
        if not target:
            return None
        bet = min(self._calc_bet(), self.state.balance, self.cfg.max_bet)
        if bet <= 0:
            self._running = False
            return None
        won = (target == period.parity)
        pnl = bet if won else -bet
        self.state.balance += pnl
        self.state.total_bets += 1
        if won:
            self.state.wins += 1
            self.state.current_streak = max(0, self.state.current_streak) + 1
        else:
            self.state.losses += 1
            self.state.current_streak = min(0, self.state.current_streak) - 1
        self.state.max_balance = max(self.state.max_balance, self.state.balance)
        dd = (self.state.max_balance - self.state.balance) / self.state.max_balance if self.state.max_balance > 0 else 0
        self.state.max_drawdown = max(self.state.max_drawdown, dd)
        self._update_strategy(won)
        record = BetRecord(period_num=period.block_number, bet_amount=bet, bet_target=target,
                           actual=period.parity, won=won, pnl=pnl, balance_after=self.state.balance,
                           strategy=self.cfg.strategy)
        self.state.history.append(record)
        if len(self.state.history) > 500:
            self.state.history = self.state.history[-500:]
        if self.state.balance <= 0:
            self._running = False
        return record

    def _select_target(self, analyzer: Analyzer) -> Optional[str]:
        latest = analyzer.latest()
        if not latest:
            return None
        t = self.cfg.target
        if t == "follow_trend":
            return latest.parity
        elif t == "reverse":
            return PARITY_EVEN if latest.is_odd else PARITY_ODD
        elif t == "follow_dragon":
            val, run = analyzer.same_run_length()
            return val if run >= 3 and val in (PARITY_ODD, PARITY_EVEN) else latest.parity
        elif t == "ai" and self.predictor:
            result = self.predictor.predict(analyzer)
            if result.best:
                return result.best.prediction
        return latest.parity

    def _calc_bet(self) -> float:
        base = self.cfg.base_bet
        s = self.cfg.strategy
        if s == "flat": return base
        elif s == "martingale": return base * (2 ** max(0, abs(min(0, self.state.current_streak))))
        elif s == "dalembert": return base * (1 + max(0, self.state._dalembert_level))
        elif s == "fibonacci": return base * _FIB[min(self.state._fib_idx, len(_FIB) - 1)]
        elif s == "paroli": return base * (2 ** min(self.state._paroli_wins, 3)) if self.state._paroli_wins > 0 else base
        elif s == "kelly":
            p = self.state.win_rate if self.state.total_bets >= 10 else 0.5
            f = max(0, min(0.25, (p - (1 - p))))
            return self.state.balance * f if f > 0 else base
        return base

    def _update_strategy(self, won: bool):
        s = self.cfg.strategy
        if s == "dalembert":
            self.state._dalembert_level = max(0, self.state._dalembert_level + (-1 if won else 1))
        elif s == "fibonacci":
            self.state._fib_idx = max(0, self.state._fib_idx + (-2 if won else 1))
        elif s == "paroli":
            if won:
                self.state._paroli_wins += 1
                if self.state._paroli_wins >= 3: self.state._paroli_wins = 0
            else:
                self.state._paroli_wins = 0

    def balance_curve(self) -> List[float]:
        curve = [self.cfg.initial_balance]
        for r in self.state.history:
            curve.append(r.balance_after)
        return curve

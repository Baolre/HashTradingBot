"""AI/信号引擎 - 4种统计模型融合预测."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .analyzer import PARITY_EVEN, PARITY_ODD, SIZE_BIG, SIZE_SMALL, Analyzer, Period
from ..utils.config import PredictorConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Signal:
    model: str
    dimension: str
    prediction: str
    confidence: float
    reason: str = ""

    @property
    def label(self) -> str:
        return {"odd": "单", "even": "双", "big": "大", "small": "小"}.get(self.prediction, "?")

    @property
    def confidence_pct(self) -> str:
        return f"{self.confidence * 100:.1f}%"


@dataclass
class PredictionResult:
    signals: List[Signal] = field(default_factory=list)
    best: Optional[Signal] = None

    @property
    def has_signal(self) -> bool:
        return self.best is not None


class Predictor:
    def __init__(self, cfg: PredictorConfig):
        self.cfg = cfg

    def update_config(self, cfg: PredictorConfig) -> None:
        self.cfg = cfg

    def predict(self, analyzer: Analyzer) -> PredictionResult:
        if not self.cfg.enabled:
            return PredictionResult()
        history = analyzer.history()
        if len(history) < 15:
            return PredictionResult()

        signals: List[Signal] = []
        for attr in ("parity", "size"):
            s = self._markov(history, attr)
            if s:
                signals.append(s)
            s = self._bayesian(history, attr)
            if s:
                signals.append(s)
            s = self._cycle(history, attr)
            if s:
                signals.append(s)
            s = self._density(history, attr)
            if s:
                signals.append(s)

        valid = [s for s in signals if s.confidence >= self.cfg.confidence_threshold]
        best = max(valid, key=lambda x: x.confidence) if valid else None
        return PredictionResult(signals=signals, best=best)

    def _markov(self, history: List[Period], attr: str) -> Optional[Signal]:
        data = history[-self.cfg.markov_window:]
        if len(data) < 10:
            return None
        trans: Dict[str, Dict[str, int]] = {}
        for i in range(len(data) - 1):
            cur = getattr(data[i], attr, "unknown")
            nxt = getattr(data[i + 1], attr, "unknown")
            if cur == "unknown" or nxt == "unknown":
                continue
            trans.setdefault(cur, {})[nxt] = trans.get(cur, {}).get(nxt, 0) + 1
        latest_val = getattr(data[-1], attr, "unknown")
        if latest_val == "unknown" or latest_val not in trans:
            return None
        t = trans[latest_val]
        total = sum(t.values())
        if total < 5:
            return None
        best_state = max(t, key=t.get)
        prob = t[best_state] / total
        if prob < 0.55:
            return None
        return Signal(model="markov", dimension=attr, prediction=best_state,
                      confidence=prob, reason=f"{latest_val}→{best_state}: {prob:.0%}")

    def _bayesian(self, history: List[Period], attr: str) -> Optional[Signal]:
        data = history[-self.cfg.bayesian_window:]
        if len(data) < 15:
            return None
        states = [PARITY_ODD, PARITY_EVEN] if attr == "parity" else [SIZE_BIG, SIZE_SMALL]
        counts = {s: sum(1 for p in data if getattr(p, attr) == s) for s in states}
        total = sum(counts.values())
        if total < 10:
            return None
        ratios = {s: c / total for s, c in counts.items()}
        minority = min(ratios, key=ratios.get)
        deviation = (0.5 - ratios[minority]) / 0.5
        if deviation < 0.15:
            return None
        confidence = min(0.92, 0.5 + deviation * 0.55)
        return Signal(model="bayesian", dimension=attr, prediction=minority,
                      confidence=confidence, reason=f"偏差回归 {minority} {ratios[minority]:.0%}")

    def _cycle(self, history: List[Period], attr: str) -> Optional[Signal]:
        data = history[-100:]
        if len(data) < 20:
            return None
        if attr == "parity":
            seq = [1 if getattr(p, attr) == PARITY_ODD else 0 for p in data if p.is_valid]
        else:
            seq = [1 if getattr(p, attr) == SIZE_BIG else 0 for p in data if p.is_valid]
        if len(seq) < 20:
            return None
        best_period, best_corr = 0, 0.0
        for period in range(2, min(self.cfg.cycle_max_period + 1, len(seq) // 3)):
            matches = sum(1 for i in range(period, len(seq)) if seq[i] == seq[i - period])
            corr = matches / (len(seq) - period)
            if corr > best_corr:
                best_corr = corr
                best_period = period
        if best_corr < 0.68 or best_period == 0:
            return None
        predicted_val = seq[-best_period]
        if attr == "parity":
            prediction = PARITY_ODD if predicted_val == 1 else PARITY_EVEN
        else:
            prediction = SIZE_BIG if predicted_val == 1 else SIZE_SMALL
        return Signal(model="cycle", dimension=attr, prediction=prediction,
                      confidence=best_corr, reason=f"周期{best_period}, 相关{best_corr:.0%}")

    def _density(self, history: List[Period], attr: str) -> Optional[Signal]:
        if len(history) < 20:
            return None
        short = history[-self.cfg.density_window:]
        long_data = history[-60:]
        states = [PARITY_ODD, PARITY_EVEN] if attr == "parity" else [SIZE_BIG, SIZE_SMALL]
        short_counts = {s: sum(1 for p in short if getattr(p, attr) == s) for s in states}
        long_counts = {s: sum(1 for p in long_data if getattr(p, attr) == s) for s in states}
        st = sum(short_counts.values())
        lt = sum(long_counts.values())
        if st < 5 or lt < 20:
            return None
        hot = max(short_counts, key=short_counts.get)
        sr = short_counts[hot] / st
        lr = long_counts[hot] / lt
        if lr <= 0 or lr >= 1:
            return None
        std = math.sqrt(lr * (1 - lr) / st)
        if std == 0:
            return None
        z = (sr - lr) / std
        if abs(z) < 1.5:
            return None
        if z > 0:
            prediction = hot
            confidence = min(0.88, 0.5 + z * 0.1)
            reason = f"热号{hot} z={z:.1f}"
        else:
            cold = [s for s in states if s != hot][0]
            prediction = cold
            confidence = min(0.88, 0.5 + abs(z) * 0.1)
            reason = f"冷号回归{cold} z={z:.1f}"
        return Signal(model="density", dimension=attr, prediction=prediction,
                      confidence=confidence, reason=reason)

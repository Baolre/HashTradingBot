"""AI/信号引擎 v2.0 - 6种模型 纯单双预测 + 显示预测区块号.

模型: markov1, markov2, bayesian, cycle, density, pattern
融合: 滑动回测 + 动态权重 + 投票一致性 + 时间衰减
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .analyzer import PARITY_EVEN, PARITY_ODD, Analyzer, Period
from ..utils.config import PredictorConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Signal:
    model: str
    prediction: str
    confidence: float
    reason: str = ""
    next_block_number: int = 0  # 预测的下一个区块号

    @property
    def label(self) -> str:
        return {"odd": "单", "even": "双"}.get(self.prediction, "?")

    @property
    def confidence_pct(self) -> str:
        return f"{self.confidence * 100:.1f}%"


@dataclass
class PredictionResult:
    signals: List[Signal] = field(default_factory=list)
    best: Optional[Signal] = None
    vote_summary: Dict[str, int] = field(default_factory=dict)
    model_weights: Dict[str, float] = field(default_factory=dict)
    next_block_number: int = 0  # 预测的区块号

    @property
    def has_signal(self) -> bool:
        return self.best is not None


def _time_decay_weights(n: int, decay: float = 0.02) -> List[float]:
    weights = [math.exp(-decay * (n - 1 - i)) for i in range(n)]
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else [1.0 / n] * n


def _extract_sequence(history: List[Period]) -> List[str]:
    return [p.parity for p in history if p.is_valid]


class MarkovOrder1:
    def predict(self, history: List[Period], window: int = 50, decay: float = 0.02) -> Optional[Signal]:
        seq = _extract_sequence(history[-window:])
        if len(seq) < 10:
            return None
        weights = _time_decay_weights(len(seq) - 1, decay)
        trans: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for i in range(len(seq) - 1):
            trans[seq[i]][seq[i + 1]] += weights[i]
        latest = seq[-1]
        if latest not in trans:
            return None
        t = trans[latest]
        total = sum(t.values())
        if total < 0.01:
            return None
        best_state = max(t, key=t.get)
        prob = t[best_state] / total
        if prob < 0.54:
            return None
        return Signal(model="markov1", prediction=best_state, confidence=prob,
                      reason=f"{latest}→{best_state}: {prob:.0%}")


class MarkovOrder2:
    def predict(self, history: List[Period], window: int = 80, decay: float = 0.02) -> Optional[Signal]:
        seq = _extract_sequence(history[-window:])
        if len(seq) < 20:
            return None
        weights = _time_decay_weights(len(seq) - 2, decay)
        trans: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for i in range(len(seq) - 2):
            trans[(seq[i], seq[i + 1])][seq[i + 2]] += weights[i]
        current_state = (seq[-2], seq[-1])
        if current_state not in trans:
            return None
        t = trans[current_state]
        total = sum(t.values())
        if total < 0.01:
            return None
        best_state = max(t, key=t.get)
        prob = t[best_state] / total
        if prob < 0.55:
            return None
        return Signal(model="markov2", prediction=best_state, confidence=prob,
                      reason=f"({current_state[0]},{current_state[1]})→{best_state}: {prob:.0%}")


class BayesianRegression:
    def predict(self, history: List[Period], window: int = 30, decay: float = 0.03) -> Optional[Signal]:
        seq = _extract_sequence(history[-window:])
        if len(seq) < 15:
            return None
        weights = _time_decay_weights(len(seq), decay)
        counts = {PARITY_ODD: 0.0, PARITY_EVEN: 0.0}
        for i, val in enumerate(seq):
            if val in counts:
                counts[val] += weights[i]
        total = sum(counts.values())
        if total < 0.01:
            return None
        ratios = {s: c / total for s, c in counts.items()}
        minority = min(ratios, key=ratios.get)
        deviation = (0.5 - ratios[minority]) / 0.5
        if deviation < 0.12:
            return None
        confidence = min(0.90, 0.5 + deviation * 0.5)
        return Signal(model="bayesian", prediction=minority, confidence=confidence,
                      reason=f"偏差回归 {minority} 占{ratios[minority]:.0%}")


class CycleDetector:
    def predict(self, history: List[Period], max_period: int = 20) -> Optional[Signal]:
        seq = _extract_sequence(history[-120:])
        if len(seq) < 25:
            return None
        binary = [1 if v == PARITY_ODD else 0 for v in seq]
        best_period, best_corr = 0, 0.0
        for period in range(2, min(max_period + 1, len(binary) // 3)):
            matches = sum(1 for i in range(period, len(binary)) if binary[i] == binary[i - period])
            corr = matches / (len(binary) - period)
            if corr > best_corr:
                best_corr = corr
                best_period = period
        if best_corr < 0.65 or best_period == 0:
            return None
        predicted_val = binary[-best_period]
        prediction = PARITY_ODD if predicted_val == 1 else PARITY_EVEN
        return Signal(model="cycle", prediction=prediction, confidence=min(0.92, best_corr),
                      reason=f"周期{best_period} 相关{best_corr:.0%}")


class DensityDetector:
    def predict(self, history: List[Period], short_window: int = 10, long_window: int = 60) -> Optional[Signal]:
        if len(history) < long_window:
            return None
        short = history[-short_window:]
        long_data = history[-long_window:]
        states = [PARITY_ODD, PARITY_EVEN]
        short_counts = {s: sum(1 for p in short if p.parity == s) for s in states}
        long_counts = {s: sum(1 for p in long_data if p.parity == s) for s in states}
        st, lt = sum(short_counts.values()), sum(long_counts.values())
        if st < 5 or lt < 20:
            return None
        hot = max(short_counts, key=short_counts.get)
        sr, lr = short_counts[hot] / st, long_counts[hot] / lt
        if lr <= 0 or lr >= 1:
            return None
        std = math.sqrt(lr * (1 - lr) / st)
        if std == 0:
            return None
        z = (sr - lr) / std
        if abs(z) < 1.5:
            return None
        if z > 0:
            return Signal(model="density", prediction=hot, confidence=min(0.88, 0.5 + z * 0.08),
                          reason=f"热号{hot} z={z:.2f}")
        else:
            cold = [s for s in states if s != hot][0]
            return Signal(model="density", prediction=cold, confidence=min(0.88, 0.5 + abs(z) * 0.08),
                          reason=f"冷号回归{cold} z={z:.2f}")


class PatternMatcher:
    def predict(self, history: List[Period], pattern_len: int = 5, min_matches: int = 2) -> Optional[Signal]:
        seq = _extract_sequence(history)
        if len(seq) < pattern_len + 20:
            return None
        target = seq[-pattern_len:]
        search_range = seq[:-pattern_len]
        next_values: Dict[str, int] = defaultdict(int)
        total_found = 0
        for i in range(len(search_range) - pattern_len):
            if search_range[i:i + pattern_len] == target:
                next_idx = i + pattern_len
                if next_idx < len(search_range):
                    next_values[search_range[next_idx]] += 1
                    total_found += 1
        if total_found < min_matches:
            return None
        best_next = max(next_values, key=next_values.get)
        prob = next_values[best_next] / total_found
        if prob < 0.55:
            return None
        pattern_str = "".join("单" if v == PARITY_ODD else "双" for v in target)
        return Signal(model="pattern", prediction=best_next, confidence=min(0.90, prob),
                      reason=f"模式[{pattern_str}]→{best_next} ({next_values[best_next]}/{total_found})")


class BacktestEngine:
    def __init__(self):
        self._model_accuracy: Dict[str, float] = {}
        self._last_count: int = 0

    @property
    def model_accuracy(self) -> Dict[str, float]:
        return dict(self._model_accuracy)

    def run_backtest(self, history: List[Period], models: Dict[str, object],
                     test_window: int = 25, min_train: int = 40) -> Dict[str, float]:
        if len(history) < min_train + test_window:
            return {}
        results: Dict[str, List[bool]] = {name: [] for name in models}
        for i in range(len(history) - test_window, len(history) - 1):
            sub = history[:i + 1]
            actual = history[i + 1].parity
            if actual == "unknown":
                continue
            for name, model in models.items():
                try:
                    signal = model.predict(sub)
                    if signal and signal.confidence >= 0.55:
                        results[name].append(signal.prediction == actual)
                except Exception:
                    pass
        accuracy = {}
        for name, hits in results.items():
            accuracy[name] = sum(hits) / len(hits) if len(hits) >= 5 else 0.5
        self._model_accuracy = accuracy
        self._last_count = len(history)
        return accuracy

    def needs_update(self, current_count: int, interval: int = 15) -> bool:
        return current_count - self._last_count >= interval


class Predictor:
    def __init__(self, cfg: PredictorConfig):
        self.cfg = cfg
        self._markov1 = MarkovOrder1()
        self._markov2 = MarkovOrder2()
        self._bayesian = BayesianRegression()
        self._cycle = CycleDetector()
        self._density = DensityDetector()
        self._pattern = PatternMatcher()
        self._backtest = BacktestEngine()
        self._model_map = {
            "markov1": self._markov1, "markov2": self._markov2,
            "bayesian": self._bayesian, "cycle": self._cycle,
            "density": self._density, "pattern": self._pattern,
        }

    def update_config(self, cfg: PredictorConfig) -> None:
        self.cfg = cfg

    def predict(self, analyzer: Analyzer) -> PredictionResult:
        if not self.cfg.enabled:
            return PredictionResult()
        history = analyzer.history()
        if len(history) < 20:
            return PredictionResult()

        # 计算预测的下一个区块号
        latest = analyzer.latest()
        multiple = 20  # 默认
        next_block = (latest.block_number + multiple) if latest else 0

        # 定期回测
        if self._backtest.needs_update(len(history)):
            try:
                self._backtest.run_backtest(history, self._model_map)
            except Exception as e:
                logger.warning("回测失败: %s", e)

        model_weights = self._backtest.model_accuracy or {k: 0.5 for k in self._model_map}

        # 收集信号（仅单双）
        signals: List[Signal] = []
        for name, model in self._model_map.items():
            try:
                if name == "markov1":
                    s = model.predict(history, self.cfg.markov_window)
                elif name == "markov2":
                    s = model.predict(history, window=80)
                elif name == "bayesian":
                    s = model.predict(history, self.cfg.bayesian_window)
                elif name == "cycle":
                    s = model.predict(history, self.cfg.cycle_max_period)
                elif name == "density":
                    s = model.predict(history, self.cfg.density_window)
                elif name == "pattern":
                    s = model.predict(history)
                else:
                    s = None
                if s:
                    s.next_block_number = next_block
                    signals.append(s)
            except Exception:
                pass

        if not signals:
            return PredictionResult(model_weights=model_weights, next_block_number=next_block)

        valid = [s for s in signals if s.confidence >= self.cfg.confidence_threshold]
        if not valid:
            return PredictionResult(signals=signals, model_weights=model_weights, next_block_number=next_block)

        # 投票一致性加分
        for s in valid:
            same_dir = sum(1 for s2 in valid if s2.prediction == s.prediction)
            if len(valid) >= 2 and same_dir / len(valid) > 0.6:
                bonus = 0.05 * (same_dir - 1)
                s.confidence = min(0.95, s.confidence + bonus)
                if bonus > 0:
                    s.reason += f" [一致+{bonus:.0%}]"

        # 加权选最优
        best: Optional[Signal] = None
        best_score = 0.0
        for s in valid:
            score = model_weights.get(s.model, 0.5) * s.confidence
            if score > best_score:
                best_score = score
                best = s

        vote_summary: Dict[str, int] = {}
        for s in valid:
            vote_summary[s.prediction] = vote_summary.get(s.prediction, 0) + 1

        return PredictionResult(
            signals=signals, best=best, vote_summary=vote_summary,
            model_weights=model_weights, next_block_number=next_block,
        )

    def get_model_accuracy(self) -> Dict[str, float]:
        return self._backtest.model_accuracy

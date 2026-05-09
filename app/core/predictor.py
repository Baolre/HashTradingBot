"""AI/信号引擎 v2.0 - 6种模型 + 滑动回测 + 动态权重 + 投票一致性 + 时间衰减.

模型:
1. 一阶马尔可夫 (Markov-1): 状态转移概率
2. 二阶马尔可夫 (Markov-2): 前两期→下一期
3. 贝叶斯偏差回归 (Bayesian): 少数方回归
4. 周期检测 (Cycle): 自相关 + 多周期叠加
5. 密度聚类 (Density): 短窗口频率异常
6. 模式匹配 (Pattern): 历史相似片段搜索

融合机制:
- 滑动回测: 自动计算各模型最近 N 期准确率
- 动态权重: 准确率越高的模型权重越大
- 投票一致性: 多模型同方向预测时加分
- 时间衰减: 近期数据权重更高
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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
    vote_summary: Dict[str, int] = field(default_factory=dict)
    model_weights: Dict[str, float] = field(default_factory=dict)

    @property
    def has_signal(self) -> bool:
        return self.best is not None


# ==================== 工具函数 ====================

def _time_decay_weights(n: int, decay: float = 0.02) -> List[float]:
    """生成时间衰减权重，索引越大（越新）权重越高."""
    weights = [math.exp(-decay * (n - 1 - i)) for i in range(n)]
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else [1.0 / n] * n


def _extract_sequence(history: List[Period], attr: str) -> List[str]:
    """提取有效的属性序列."""
    seq = []
    for p in history:
        if not p.is_valid:
            continue
        val = getattr(p, attr, "unknown")
        if val not in ("unknown",):
            seq.append(val)
    return seq


# ==================== 模型实现 ====================

class MarkovOrder1:
    """一阶马尔可夫链."""

    def predict(self, history: List[Period], attr: str, window: int = 50,
                decay: float = 0.02) -> Optional[Signal]:
        seq = _extract_sequence(history[-window:], attr)
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

        return Signal(model="markov1", dimension=attr, prediction=best_state,
                      confidence=prob, reason=f"{latest}→{best_state}: {prob:.0%}")


class MarkovOrder2:
    """二阶马尔可夫链 - 看前两期预测下一期."""

    def predict(self, history: List[Period], attr: str, window: int = 80,
                decay: float = 0.02) -> Optional[Signal]:
        seq = _extract_sequence(history[-window:], attr)
        if len(seq) < 20:
            return None

        weights = _time_decay_weights(len(seq) - 2, decay)
        trans: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for i in range(len(seq) - 2):
            state = (seq[i], seq[i + 1])
            trans[state][seq[i + 2]] += weights[i]

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

        s1, s2 = current_state
        return Signal(model="markov2", dimension=attr, prediction=best_state,
                      confidence=prob, reason=f"({s1},{s2})→{best_state}: {prob:.0%}")


class BayesianRegression:
    """贝叶斯偏差回归 - 带时间衰减."""

    def predict(self, history: List[Period], attr: str, window: int = 30,
                decay: float = 0.03) -> Optional[Signal]:
        seq = _extract_sequence(history[-window:], attr)
        if len(seq) < 15:
            return None

        if attr == "parity":
            states = [PARITY_ODD, PARITY_EVEN]
        else:
            states = [SIZE_BIG, SIZE_SMALL]

        weights = _time_decay_weights(len(seq), decay)
        weighted_counts = {s: 0.0 for s in states}
        for i, val in enumerate(seq):
            if val in weighted_counts:
                weighted_counts[val] += weights[i]

        total = sum(weighted_counts.values())
        if total < 0.01:
            return None

        ratios = {s: c / total for s, c in weighted_counts.items()}
        minority = min(ratios, key=ratios.get)
        deviation = (0.5 - ratios[minority]) / 0.5

        if deviation < 0.12:
            return None

        # 贝塔分布后验
        alpha = weighted_counts[minority] * len(seq) + 1
        beta_p = (total - weighted_counts[minority]) * len(seq) + 1
        posterior_mean = alpha / (alpha + beta_p)

        confidence = min(0.90, 0.5 + deviation * 0.5)
        return Signal(model="bayesian", dimension=attr, prediction=minority,
                      confidence=confidence,
                      reason=f"偏差回归 {minority} 占{ratios[minority]:.0%} 偏差{deviation:.0%}")


class CycleDetector:
    """周期检测 - 多周期叠加分析."""

    def predict(self, history: List[Period], attr: str, max_period: int = 20) -> Optional[Signal]:
        seq = _extract_sequence(history[-120:], attr)
        if len(seq) < 25:
            return None

        if attr == "parity":
            binary = [1 if v == PARITY_ODD else 0 for v in seq]
        else:
            binary = [1 if v == SIZE_BIG else 0 for v in seq]

        # 检测多个周期，取最强的
        best_period, best_corr = 0, 0.0
        period_scores: List[Tuple[int, float]] = []

        for period in range(2, min(max_period + 1, len(binary) // 3)):
            matches = 0
            total_check = len(binary) - period
            for i in range(period, len(binary)):
                if binary[i] == binary[i - period]:
                    matches += 1
            corr = matches / total_check if total_check > 0 else 0
            period_scores.append((period, corr))
            if corr > best_corr:
                best_corr = corr
                best_period = period

        if best_corr < 0.65 or best_period == 0:
            return None

        # 用最强周期预测
        predicted_val = binary[-best_period]

        # 检查是否有第二强周期也支持同一方向（多周期叠加）
        period_scores.sort(key=lambda x: x[1], reverse=True)
        support_count = 0
        for p, c in period_scores[:3]:
            if c >= 0.60 and binary[-p] == predicted_val:
                support_count += 1

        # 多周期支持加分
        bonus = 0.03 * max(0, support_count - 1)
        confidence = min(0.92, best_corr + bonus)

        if attr == "parity":
            prediction = PARITY_ODD if predicted_val == 1 else PARITY_EVEN
        else:
            prediction = SIZE_BIG if predicted_val == 1 else SIZE_SMALL

        return Signal(model="cycle", dimension=attr, prediction=prediction,
                      confidence=confidence,
                      reason=f"周期{best_period} 相关{best_corr:.0%} 支持{support_count}个周期")


class DensityDetector:
    """密度聚类 - 短窗口频率异常检测."""

    def predict(self, history: List[Period], attr: str, short_window: int = 10,
                long_window: int = 60) -> Optional[Signal]:
        if len(history) < long_window:
            return None

        short = history[-short_window:]
        long_data = history[-long_window:]

        if attr == "parity":
            states = [PARITY_ODD, PARITY_EVEN]
        else:
            states = [SIZE_BIG, SIZE_SMALL]

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
            confidence = min(0.88, 0.5 + z * 0.08)
            reason = f"热号持续 {hot} z={z:.2f}"
        else:
            cold = [s for s in states if s != hot][0]
            prediction = cold
            confidence = min(0.88, 0.5 + abs(z) * 0.08)
            reason = f"冷号回归 {cold} z={z:.2f}"

        return Signal(model="density", dimension=attr, prediction=prediction,
                      confidence=confidence, reason=reason)


class PatternMatcher:
    """模式匹配 - 在历史中搜索与最近 N 期最相似的片段."""

    def predict(self, history: List[Period], attr: str,
                pattern_len: int = 5, min_matches: int = 3) -> Optional[Signal]:
        seq = _extract_sequence(history, attr)
        if len(seq) < pattern_len + 20:
            return None

        # 取最近 pattern_len 期作为目标模式
        target = seq[-pattern_len:]

        # 在历史中搜索相同模式（排除最后 pattern_len 期本身）
        search_range = seq[:-pattern_len]
        next_values: Dict[str, int] = defaultdict(int)
        total_found = 0

        for i in range(len(search_range) - pattern_len):
            candidate = search_range[i:i + pattern_len]
            if candidate == target:
                # 找到匹配，看这个模式后面紧跟的值
                next_idx = i + pattern_len
                if next_idx < len(search_range):
                    next_values[search_range[next_idx]] += 1
                    total_found += 1

        if total_found < min_matches:
            return None

        # 取出现最多的下一个值
        best_next = max(next_values, key=next_values.get)
        prob = next_values[best_next] / total_found

        if prob < 0.55:
            return None

        pattern_str = "".join({"odd": "单", "even": "双", "big": "大", "small": "小"}.get(v, "?") for v in target)
        return Signal(model="pattern", dimension=attr, prediction=best_next,
                      confidence=min(0.90, prob),
                      reason=f"模式[{pattern_str}]后出{best_next} {total_found}次中{next_values[best_next]}次")


# ==================== 滑动回测器 ====================

class BacktestEngine:
    """滑动回测 - 计算各模型在最近 N 期的准确率."""

    def __init__(self):
        self._model_accuracy: Dict[str, float] = {}
        self._last_backtest_count: int = 0

    @property
    def model_accuracy(self) -> Dict[str, float]:
        return dict(self._model_accuracy)

    def run_backtest(self, history: List[Period], models: Dict[str, object],
                     attr: str = "parity", test_window: int = 30,
                     min_train: int = 50) -> Dict[str, float]:
        """在最近 test_window 期上回测各模型."""
        if len(history) < min_train + test_window:
            return {}

        results: Dict[str, List[bool]] = {name: [] for name in models}

        for i in range(len(history) - test_window, len(history) - 1):
            sub_history = history[:i + 1]
            actual_next = history[i + 1]
            actual_val = getattr(actual_next, attr, "unknown")
            if actual_val == "unknown":
                continue

            for name, model in models.items():
                try:
                    signal = model.predict(sub_history, attr)
                    if signal and signal.confidence >= 0.55:
                        results[name].append(signal.prediction == actual_val)
                except Exception:
                    pass

        accuracy: Dict[str, float] = {}
        for name, hits in results.items():
            if len(hits) >= 5:
                accuracy[name] = sum(hits) / len(hits)
            else:
                accuracy[name] = 0.5  # 样本不足默认50%

        self._model_accuracy = accuracy
        self._last_backtest_count = len(history)
        return accuracy

    def needs_update(self, current_count: int, interval: int = 20) -> bool:
        """是否需要重新回测（每 interval 期更新一次）."""
        return current_count - self._last_backtest_count >= interval


# ==================== 主预测器 ====================

class Predictor:
    """信号引擎主类 - 6模型 + 动态权重 + 投票机制."""

    def __init__(self, cfg: PredictorConfig):
        self.cfg = cfg
        self._markov1 = MarkovOrder1()
        self._markov2 = MarkovOrder2()
        self._bayesian = BayesianRegression()
        self._cycle = CycleDetector()
        self._density = DensityDetector()
        self._pattern = PatternMatcher()
        self._backtest = BacktestEngine()
        self._model_map: Dict[str, object] = {
            "markov1": self._markov1,
            "markov2": self._markov2,
            "bayesian": self._bayesian,
            "cycle": self._cycle,
            "density": self._density,
            "pattern": self._pattern,
        }

    def update_config(self, cfg: PredictorConfig) -> None:
        self.cfg = cfg

    def predict(self, analyzer: Analyzer) -> PredictionResult:
        if not self.cfg.enabled:
            return PredictionResult()

        history = analyzer.history()
        if len(history) < 20:
            return PredictionResult()

        # 定期更新回测
        if self._backtest.needs_update(len(history), interval=15):
            try:
                self._backtest.run_backtest(history, self._model_map, "parity",
                                            test_window=25, min_train=40)
            except Exception as e:
                logger.warning("回测失败: %s", e)

        model_weights = self._backtest.model_accuracy or {k: 0.5 for k in self._model_map}

        # 收集所有信号
        signals: List[Signal] = []
        for attr in ("parity", "size"):
            s = self._markov1.predict(history, attr, self.cfg.markov_window, decay=0.02)
            if s:
                signals.append(s)

            s = self._markov2.predict(history, attr, window=80, decay=0.02)
            if s:
                signals.append(s)

            s = self._bayesian.predict(history, attr, self.cfg.bayesian_window, decay=0.03)
            if s:
                signals.append(s)

            s = self._cycle.predict(history, attr, self.cfg.cycle_max_period)
            if s:
                signals.append(s)

            s = self._density.predict(history, attr, self.cfg.density_window, long_window=60)
            if s:
                signals.append(s)

            s = self._pattern.predict(history, attr, pattern_len=5, min_matches=2)
            if s:
                signals.append(s)

        if not signals:
            return PredictionResult(model_weights=model_weights)

        # 过滤低于阈值的信号
        valid_signals = [s for s in signals if s.confidence >= self.cfg.confidence_threshold]
        if not valid_signals:
            return PredictionResult(signals=signals, model_weights=model_weights)

        # ===== 投票机制 =====
        # 按维度分组统计投票
        vote_groups: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for s in valid_signals:
            # 加权: 模型准确率 × 信号置信度
            weight = model_weights.get(s.model, 0.5) * s.confidence
            vote_groups[s.dimension][s.prediction] += weight

        # 一致性加分
        for s in valid_signals:
            dim = s.dimension
            same_direction = sum(1 for s2 in valid_signals
                                 if s2.dimension == dim and s2.prediction == s.prediction)
            total_in_dim = sum(1 for s2 in valid_signals if s2.dimension == dim)

            if total_in_dim >= 2:
                consistency_ratio = same_direction / total_in_dim
                # 一致性 > 60% 时加分
                if consistency_ratio > 0.6:
                    bonus = 0.05 * (same_direction - 1)
                    s.confidence = min(0.95, s.confidence + bonus)
                    if bonus > 0:
                        s.reason += f" [一致+{bonus:.0%}]"

        # 选出最终最优信号（加权后最高）
        best: Optional[Signal] = None
        best_score = 0.0
        for s in valid_signals:
            weight = model_weights.get(s.model, 0.5)
            score = weight * s.confidence
            if score > best_score:
                best_score = score
                best = s

        # 投票摘要
        vote_summary: Dict[str, int] = {}
        for s in valid_signals:
            key = f"{s.dimension}:{s.prediction}"
            vote_summary[key] = vote_summary.get(key, 0) + 1

        return PredictionResult(
            signals=signals,
            best=best,
            vote_summary=vote_summary,
            model_weights=model_weights,
        )

    def get_model_accuracy(self) -> Dict[str, float]:
        """获取各模型最新准确率."""
        return self._backtest.model_accuracy

    def backtest_summary(self, analyzer: Analyzer) -> Dict[str, float]:
        """手动触发一次完整回测."""
        history = analyzer.history()
        if len(history) < 70:
            return {}
        return self._backtest.run_backtest(
            history, self._model_map, "parity",
            test_window=30, min_train=40,
        )

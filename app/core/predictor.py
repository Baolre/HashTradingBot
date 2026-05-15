"""AI 预测器 - 纯本地模型集成预测.

模型列表：
- Markov: 1阶转移概率
- N-gram3: 3阶马尔可夫（前3期组合）
- N-gram5: 5阶马尔可夫（前5期组合，50期窗口）
- Frequency: 近窗口频率反转（均值回归）
- Streak: 连号反转（连续越长反转概率越高）
- Alternation: 交替模式检测（单双单双...持续性）
- Ensemble: 动态加权投票
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..utils.config import DeepSeekConfig, PredictorConfig
from ..utils.logger import get_logger
from .analyzer import Analyzer, PARITY_EVEN, PARITY_ODD, PARITY_UNKNOWN

logger = get_logger(__name__)


@dataclass
class Signal:
    """单个模型的预测输出."""

    prediction: str          # "odd" / "even"
    confidence: float        # 0.0 ~ 1.0
    model: str               # "markov" / "ngram3" / "ngram5" / "frequency" / "streak" / "alternation" / "ensemble"
    next_block_number: Optional[int] = None
    reason: str = ""

    @property
    def label(self) -> str:
        return "单" if self.prediction == PARITY_ODD else "双"

    @property
    def confidence_pct(self) -> str:
        return f"{self.confidence * 100:.1f}%"


@dataclass
class Prediction:
    """一次预测结果（可能包含多个模型信号）."""

    signals: List[Signal] = field(default_factory=list)
    best: Optional[Signal] = None
    has_signal: bool = False
    next_block_number: Optional[int] = None
    reason: str = ""


# ==================== 动态权重管理 ====================

class DynamicWeights:
    """根据各模型近期命中率动态调整权重."""

    def __init__(self):
        self._base_weights = {
            "markov": 1.0,
            "ngram3": 1.2,
            "ngram5": 1.5,
            "frequency": 0.8,
            "streak": 1.0,
            "alternation": 1.0,
            "bayesian": 1.3,
        }
        self._history: Dict[str, List[bool]] = defaultdict(list)
        self._max_history = 50

    def record(self, model: str, correct: bool) -> None:
        h = self._history[model]
        h.append(correct)
        if len(h) > self._max_history:
            h.pop(0)

    def get_weight(self, model: str) -> float:
        base = self._base_weights.get(model, 1.0)
        h = self._history.get(model)
        if not h or len(h) < 20:
            return base
        accuracy = sum(h) / len(h)
        if accuracy > 0.55:
            return base * 1.3
        elif accuracy < 0.45:
            return base * 0.5
        return base

    def get_accuracy(self, model: str) -> Optional[float]:
        h = self._history.get(model)
        if not h or len(h) < 5:
            return None
        return sum(h) / len(h)

    def all_weights(self) -> Dict[str, float]:
        return {m: self.get_weight(m) for m in self._base_weights}


class Predictor:
    """纯本地集成预测器（无外部 API 依赖）."""

    def __init__(self, cfg: PredictorConfig, deepseek_cfg: Optional[DeepSeekConfig] = None):
        self.cfg = cfg
        self.deepseek_cfg = deepseek_cfg  # 保留接口兼容，但不使用
        self.dynamic_weights = DynamicWeights()

    def update_config(self, cfg: PredictorConfig) -> None:
        self.cfg = cfg

    def update_deepseek_config(self, cfg: DeepSeekConfig) -> None:
        self.deepseek_cfg = cfg  # 接口兼容，不使用

    def feed_result(self, model: str, correct: bool) -> None:
        """每期结算后外部调用，更新动态权重."""
        self.dynamic_weights.record(model, correct)

    # ==================== 本地模型 ====================

    def _markov(self, analyzer: Analyzer) -> Optional[Signal]:
        """1阶 Markov: P(next | current)."""
        latest = analyzer.latest()
        if latest is None or not latest.is_valid:
            return None
        matrix: Dict[str, Dict[str, float]] = analyzer.get_transition_matrix(
            window=max(10, self.cfg.markov_window)
        )
        row = matrix.get(latest.parity)
        if not row:
            return None
        p_odd = row.get(PARITY_ODD, 0.0)
        p_even = row.get(PARITY_EVEN, 0.0)
        if p_odd == 0 and p_even == 0:
            return None
        if p_odd >= p_even:
            return Signal(PARITY_ODD, p_odd, model="markov")
        return Signal(PARITY_EVEN, p_even, model="markov")

    def _ngram3(self, analyzer: Analyzer) -> Optional[Signal]:
        """3阶 N-gram: P(next | 前3期组合)."""
        history = [p.parity for p in analyzer.last(200) if p.is_valid]
        if len(history) < 10:
            return None

        counts: Dict[Tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for i in range(len(history) - 3):
            key = (history[i], history[i + 1], history[i + 2])
            nxt = history[i + 3]
            if nxt in (PARITY_ODD, PARITY_EVEN):
                counts[key][nxt] += 1

        if len(history) < 3:
            return None
        current_key = (history[-3], history[-2], history[-1])
        dist = counts.get(current_key)
        if not dist:
            return None

        total = sum(dist.values())
        if total < 3:
            return None

        p_odd = dist.get(PARITY_ODD, 0) / total
        p_even = dist.get(PARITY_EVEN, 0) / total

        if p_odd > p_even:
            return Signal(PARITY_ODD, p_odd, model="ngram3", reason=f"3-gram {total}样本")
        elif p_even > p_odd:
            return Signal(PARITY_EVEN, p_even, model="ngram3", reason=f"3-gram {total}样本")
        return None

    def _ngram5(self, analyzer: Analyzer) -> Optional[Signal]:
        """5阶 N-gram: P(next | 前5期组合)，使用最近50期数据窗口."""
        history = [p.parity for p in analyzer.last(50) if p.is_valid]
        if len(history) < 15:  # 至少15期才有足够5-gram样本
            return None

        counts: Dict[Tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for i in range(len(history) - 5):
            key = (history[i], history[i + 1], history[i + 2], history[i + 3], history[i + 4])
            nxt = history[i + 5]
            if nxt in (PARITY_ODD, PARITY_EVEN):
                counts[key][nxt] += 1

        if len(history) < 5:
            return None
        current_key = (history[-5], history[-4], history[-3], history[-2], history[-1])
        dist = counts.get(current_key)
        if not dist:
            return None

        total = sum(dist.values())
        if total < 2:  # 5-gram 样本天然少，2 次就够
            return None

        p_odd = dist.get(PARITY_ODD, 0) / total
        p_even = dist.get(PARITY_EVEN, 0) / total

        if p_odd > p_even:
            return Signal(PARITY_ODD, p_odd, model="ngram5", reason=f"5-gram {total}样本")
        elif p_even > p_odd:
            return Signal(PARITY_EVEN, p_even, model="ngram5", reason=f"5-gram {total}样本")
        return None

    def _frequency(self, analyzer: Analyzer) -> Optional[Signal]:
        """近窗口频率反转（均值回归）."""
        window = max(5, self.cfg.density_window * 3)
        recent = [p for p in analyzer.last(window) if p.is_valid]
        if not recent:
            return None
        odd_n = sum(1 for p in recent if p.is_odd)
        total = len(recent)
        p_odd = odd_n / total
        p_even = 1.0 - p_odd
        if p_odd <= p_even:
            return Signal(PARITY_ODD, 0.5 + (p_even - 0.5), model="frequency")
        return Signal(PARITY_EVEN, 0.5 + (p_odd - 0.5), model="frequency")

    def _streak(self, analyzer: Analyzer) -> Optional[Signal]:
        """连号反转：连续出现同一方向越长，反转概率越高."""
        parity, run = analyzer.same_run_length()
        if parity == PARITY_UNKNOWN or run < 3:
            return None
        # 连号越长置信度越高（3连=0.55, 5连=0.65, 7连=0.75, 上限0.85）
        conf = min(0.85, 0.50 + run * 0.05)
        # 预测反转
        direction = PARITY_EVEN if parity == PARITY_ODD else PARITY_ODD
        return Signal(direction, conf, model="streak", reason=f"连{run}反转")

    def _alternation(self, analyzer: Analyzer) -> Optional[Signal]:
        """交替模式检测：单双单双...持续时预测继续交替."""
        alt_len = analyzer.alternation_run_length()
        if alt_len < 4:
            return None
        # 交替越长置信度越高（4=0.58, 6=0.68, 8=0.78, 上限0.80）
        conf = min(0.80, 0.48 + alt_len * 0.05)
        # 预测继续交替：取最后一期的反方向
        latest = analyzer.latest()
        if latest is None or not latest.is_valid:
            return None
        direction = PARITY_EVEN if latest.parity == PARITY_ODD else PARITY_ODD
        return Signal(direction, conf, model="alternation", reason=f"交替{alt_len}期")

    def _bayesian(self, analyzer: Analyzer) -> Optional[Signal]:
        """贝叶斯推断：基于先验(历史基准) + 近期证据动态更新后验概率.

        原理：
        - 先验: 全局单双比例（如 50.2% vs 49.8%）
        - 似然: 近 20 期的单双比例作为最新证据
        - 后验: prior * likelihood 归一化
        置信度取决于后验偏离 0.5 的程度。
        """
        history = [p for p in analyzer.last(200) if p.is_valid]
        if len(history) < 30:
            return None

        # 先验：全局比例
        total_all = len(history)
        odd_all = sum(1 for p in history if p.is_odd)
        prior_odd = odd_all / total_all
        prior_even = 1.0 - prior_odd

        # 似然：最近 20 期的比例（近期趋势）
        recent = history[-20:]
        odd_recent = sum(1 for p in recent if p.is_odd)
        total_recent = len(recent)
        # 拉普拉斯平滑，避免 0 概率
        likelihood_odd = (odd_recent + 1) / (total_recent + 2)
        likelihood_even = 1.0 - likelihood_odd

        # 后验 = prior * likelihood（未归一化）
        post_odd = prior_odd * likelihood_odd
        post_even = prior_even * likelihood_even

        # 归一化
        post_total = post_odd + post_even
        if post_total == 0:
            return None
        post_odd /= post_total
        post_even /= post_total

        # 置信度：后验偏离 0.5 的程度映射到 [0.5, 0.8]
        bias = abs(post_odd - 0.5)  # 0~0.5
        conf = 0.5 + bias * 0.6  # 映射到 0.5~0.8
        conf = min(0.80, max(0.50, conf))

        if post_odd > post_even:
            return Signal(PARITY_ODD, conf, model="bayesian",
                          reason=f"后验P(单)={post_odd:.2f}")
        elif post_even > post_odd:
            return Signal(PARITY_EVEN, conf, model="bayesian",
                          reason=f"后验P(双)={post_even:.2f}")
        return None

    # ==================== 集成预测 ====================

    def predict(self, analyzer: Analyzer) -> Prediction:
        min_required = 5
        if analyzer.stats.total < min_required:
            return Prediction(
                signals=[], best=None, has_signal=False,
                reason=f"数据不足（需至少 {min_required} 期，当前 {analyzer.stats.total}）",
            )

        signals: List[Signal] = []

        # 所有本地模型
        for sig in (
            self._markov(analyzer),
            self._ngram3(analyzer),
            self._ngram5(analyzer),
            self._frequency(analyzer),
            self._streak(analyzer),
            self._alternation(analyzer),
            self._bayesian(analyzer),
        ):
            if sig is not None:
                signals.append(sig)

        if not signals:
            return Prediction(signals=[], best=None, has_signal=False, reason="暂无可用模型输出")

        # 动态加权投票集成
        odd_score = 0.0
        even_score = 0.0
        total_weight = 0.0
        for s in signals:
            w = self.dynamic_weights.get_weight(s.model)
            if s.prediction == PARITY_ODD:
                odd_score += s.confidence * w
            else:
                even_score += s.confidence * w
            total_weight += w

        if total_weight == 0:
            return Prediction(signals=signals, best=None, has_signal=False, reason="权重异常")

        if odd_score >= even_score:
            direction = PARITY_ODD
            conf = odd_score / total_weight
        else:
            direction = PARITY_EVEN
            conf = even_score / total_weight

        # 下一区块号
        latest = analyzer.latest()
        next_block = (latest.block_number + 1) if latest else None

        best = Signal(
            prediction=direction,
            confidence=conf,
            model="ensemble",
            next_block_number=next_block,
        )
        has = conf >= float(self.cfg.confidence_threshold)
        models_str = "+".join(s.model for s in signals)
        logger.info("预测: %s conf=%.2f models=[%s] has_signal=%s",
                    best.label, conf, models_str, has)
        return Prediction(
            signals=signals,
            best=best,
            has_signal=has,
            next_block_number=next_block,
            reason="" if has else f"置信度 {conf*100:.1f}% 低于阈值 {self.cfg.confidence_threshold*100:.0f}%",
        )

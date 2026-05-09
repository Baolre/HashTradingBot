"""AI 预测器 - 基于马尔可夫转移 + 窗口频率的简单预测.

返回的 Prediction 对象有稳定字段，UI 用 getattr 也能防御。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.config import PredictorConfig
from .analyzer import Analyzer, PARITY_EVEN, PARITY_ODD, PARITY_UNKNOWN


@dataclass
class Signal:
    """单个模型的预测输出."""

    prediction: str          # "odd" / "even"
    confidence: float        # 0.0 ~ 1.0
    model: str               # "markov" / "frequency" / "ensemble"
    next_block_number: Optional[int] = None

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
    reason: str = ""         # 无信号时的说明（"数据不足"等）


class Predictor:
    """轻量级集成预测器：
    - Markov: 用 last_n 期建单步转移，取 P(next=odd|cur) 与 0.5 的偏离
    - Frequency: 最近窗口奇偶出现频率
    组合输出 ensemble 置信度；低于 cfg.confidence_threshold 时 has_signal=False。
    """

    def __init__(self, cfg: PredictorConfig):
        self.cfg = cfg

    def update_config(self, cfg: PredictorConfig) -> None:
        self.cfg = cfg

    # ------- 内部：两个模型 -------
    def _markov(self, analyzer: Analyzer) -> Optional[Signal]:
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

    def _frequency(self, analyzer: Analyzer) -> Optional[Signal]:
        window = max(5, self.cfg.density_window * 3)
        recent = [p for p in analyzer.last(window) if p.is_valid]
        if not recent:
            return None
        odd_n = sum(1 for p in recent if p.is_odd)
        total = len(recent)
        p_odd = odd_n / total
        p_even = 1.0 - p_odd
        # 反转策略：近期出现越少的一方，置信度越高（均值回归）
        if p_odd <= p_even:
            return Signal(PARITY_ODD, 0.5 + (p_even - 0.5), model="frequency")
        return Signal(PARITY_EVEN, 0.5 + (p_odd - 0.5), model="frequency")

    # ------- 对外 -------
    def predict(self, analyzer: Analyzer) -> Prediction:
        # 数据量门槛：至少 5 期才出信号，低于则 has_signal=False 但仍返回对象
        min_required = 5
        if analyzer.stats.total < min_required:
            return Prediction(
                signals=[], best=None, has_signal=False,
                reason=f"数据不足（需至少 {min_required} 期，当前 {analyzer.stats.total}）",
            )

        signals: List[Signal] = []
        for sig in (self._markov(analyzer), self._frequency(analyzer)):
            if sig is not None:
                signals.append(sig)
        if not signals:
            return Prediction(signals=[], best=None, has_signal=False, reason="暂无可用模型输出")

        # 集成：按预测方向投票 + 置信度平均
        odd_confs = [s.confidence for s in signals if s.prediction == PARITY_ODD]
        even_confs = [s.confidence for s in signals if s.prediction == PARITY_EVEN]
        if len(odd_confs) >= len(even_confs):
            conf = sum(odd_confs) / max(1, len(odd_confs)) if odd_confs else 0.0
            direction = PARITY_ODD
        else:
            conf = sum(even_confs) / max(1, len(even_confs)) if even_confs else 0.0
            direction = PARITY_EVEN

        # 计算下一目标区块号（当前区块 + 过滤倍数；倍数由 Analyzer 不知道，故交给调用方补）
        latest = analyzer.latest()
        next_block = None
        if latest is not None:
            # 没有 multiple 信息时，这里只做 +1 占位，MainWindow 可覆盖
            next_block = latest.block_number + 1

        best = Signal(
            prediction=direction,
            confidence=conf,
            model="ensemble",
            next_block_number=next_block,
        )
        has = conf >= float(self.cfg.confidence_threshold)
        return Prediction(
            signals=signals,
            best=best,
            has_signal=has,
            next_block_number=next_block,
            reason="" if has else f"置信度 {conf*100:.1f}% 低于阈值 {self.cfg.confidence_threshold*100:.0f}%",
        )

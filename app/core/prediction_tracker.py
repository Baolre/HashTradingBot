"""AI 预测命中跟踪器.

- 每次预测：record() 暂存各模型的 pending 预测
- 每期实际到达：settle() 比对 pending 预测并累加统计
- backtest()：用历史数据一次性回测得到初始统计
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from .analyzer import Analyzer, Period


@dataclass
class PredictionRecord:
    """一次预测的完整记录（预测 + 实际）."""

    model: str
    prediction: str                # "odd" / "even"
    confidence: float
    has_signal: bool               # 是否达到置信度阈值（仅 ensemble 有意义）
    actual: Optional[str] = None   # 实际开奖（settle 后填）
    correct: Optional[bool] = None

    @property
    def pred_label(self) -> str:
        return "单" if self.prediction == "odd" else "双"

    @property
    def actual_label(self) -> str:
        if self.actual == "odd":
            return "单"
        if self.actual == "even":
            return "双"
        return "?"


@dataclass
class AccuracyStats:
    """单个模型的命中率统计."""

    total: int = 0
    correct: int = 0
    wrong: int = 0
    # current_streak 正为连续对，负为连续错，0 为初始
    current_streak: int = 0
    max_correct_streak: int = 0
    max_wrong_streak: int = 0
    # 仅高置信度子集
    hc_total: int = 0
    hc_correct: int = 0
    hc_wrong: int = 0
    hc_current_streak: int = 0
    hc_max_correct_streak: int = 0
    hc_max_wrong_streak: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def accuracy_pct(self) -> str:
        return f"{self.accuracy * 100:.1f}%" if self.total else "-"

    @property
    def hc_accuracy(self) -> float:
        return self.hc_correct / self.hc_total if self.hc_total else 0.0

    @property
    def hc_accuracy_pct(self) -> str:
        return f"{self.hc_accuracy * 100:.1f}%" if self.hc_total else "-"

    @property
    def current_streak_label(self) -> str:
        if self.current_streak > 0:
            return f"对×{self.current_streak}"
        if self.current_streak < 0:
            return f"错×{-self.current_streak}"
        return "-"


class PredictionTracker:
    """跟踪每次 AI 预测的命中情况.

    用法：
      tracker = PredictionTracker()
      # 数据到达：先 settle(实际期)，再 record(新预测)
      tracker.settle(period)
      tracker.record(prediction)

    查询：
      tracker.get_stats("ensemble") -> AccuracyStats
      tracker.recent(50) -> List[PredictionRecord]
    """

    def __init__(self, max_history: int = 5000):
        self._history: Deque[PredictionRecord] = deque(maxlen=max_history)
        self._pending: Dict[str, PredictionRecord] = {}  # model -> 单个 pending
        self._stats_by_model: Dict[str, AccuracyStats] = {}

    # ---------------- 内部 ----------------
    def _stats(self, model: str) -> AccuracyStats:
        if model not in self._stats_by_model:
            self._stats_by_model[model] = AccuracyStats()
        return self._stats_by_model[model]

    def _apply(self, rec: PredictionRecord) -> None:
        """把一条已结算的 record 累加到统计中."""
        self._history.append(rec)
        st = self._stats(rec.model)
        st.total += 1
        if rec.correct:
            st.correct += 1
            st.current_streak = st.current_streak + 1 if st.current_streak >= 0 else 1
            if st.current_streak > st.max_correct_streak:
                st.max_correct_streak = st.current_streak
        else:
            st.wrong += 1
            st.current_streak = st.current_streak - 1 if st.current_streak <= 0 else -1
            if -st.current_streak > st.max_wrong_streak:
                st.max_wrong_streak = -st.current_streak

        if rec.has_signal:
            st.hc_total += 1
            if rec.correct:
                st.hc_correct += 1
                st.hc_current_streak = (
                    st.hc_current_streak + 1 if st.hc_current_streak >= 0 else 1
                )
                if st.hc_current_streak > st.hc_max_correct_streak:
                    st.hc_max_correct_streak = st.hc_current_streak
            else:
                st.hc_wrong += 1
                st.hc_current_streak = (
                    st.hc_current_streak - 1 if st.hc_current_streak <= 0 else -1
                )
                if -st.hc_current_streak > st.hc_max_wrong_streak:
                    st.hc_max_wrong_streak = -st.hc_current_streak

    # ---------------- 对外 ----------------
    def reset(self) -> None:
        self._history.clear()
        self._pending.clear()
        self._stats_by_model.clear()

    def record(self, prediction) -> None:
        """每次做出预测时调用（analyzer.ingest 之后）."""
        if prediction is None:
            return
        best = getattr(prediction, "best", None)
        if best is not None:
            self._pending["ensemble"] = PredictionRecord(
                model="ensemble",
                prediction=getattr(best, "prediction", ""),
                confidence=float(getattr(best, "confidence", 0.0)),
                has_signal=bool(getattr(prediction, "has_signal", False)),
            )
        for s in getattr(prediction, "signals", None) or []:
            conf = float(getattr(s, "confidence", 0.0))
            self._pending[getattr(s, "model", "?")] = PredictionRecord(
                model=getattr(s, "model", "?"),
                prediction=getattr(s, "prediction", ""),
                confidence=conf,
                has_signal=conf >= 0.6,  # 单模型本身没有 threshold，按 0.6 简单划分
            )

    def settle(self, period: Period) -> None:
        """每期实际到达时调用，把 pending 中的各模型预测与实际结果比对."""
        if period is None or not getattr(period, "is_valid", False):
            return
        for model, rec in list(self._pending.items()):
            rec.actual = period.parity
            rec.correct = rec.prediction == period.parity
            self._apply(rec)
            del self._pending[model]

    def backtest(self, predictor, analyzer: Analyzer) -> int:
        """用已有历史数据回测所有模型，返回结算次数.

        原理：从头到尾重放 history，对每个节点先基于前面已知数据做预测，
        再用当前期作为"实际"结算。这给出一份开机就能看到的命中率快照。
        """
        history: List[Period] = list(analyzer.history())
        if not history:
            return 0
        self.reset()
        tmp = Analyzer(max_history=max(analyzer.max_history, len(history) + 10))
        settled = 0
        for p in history:
            # 基于 tmp（不含 p）做预测
            pred = predictor.predict(tmp)
            self.record(pred)
            self.settle(p)  # 用 p 作为"下一期"结算
            settled += 1
            tmp.ingest(p)
        return settled

    # ---------------- 查询 ----------------
    def get_stats(self, model: str) -> AccuracyStats:
        return self._stats(model)

    def all_stats(self) -> Dict[str, AccuracyStats]:
        return dict(self._stats_by_model)

    def recent(self, n: int = 50) -> List[PredictionRecord]:
        return list(self._history)[-n:]

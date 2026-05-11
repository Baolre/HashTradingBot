"""AI 预测器 - 本地模型(Markov+频率) + DeepSeek V4 Flash LLM 集成.

- 本地模型：同步调用，<1ms
- DeepSeek：异步 HTTP，利用上下文缓存降低 token 消耗
- Ensemble：加权投票产出最终信号
"""
from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from ..utils.config import DeepSeekConfig, PredictorConfig
from .analyzer import Analyzer, PARITY_EVEN, PARITY_ODD, PARITY_UNKNOWN

logger = logging.getLogger(__name__)

# DeepSeek 调用用的线程池（全局单例，避免重复创建线程）
_deepseek_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="deepseek")


@dataclass
class Signal:
    """单个模型的预测输出."""

    prediction: str          # "odd" / "even"
    confidence: float        # 0.0 ~ 1.0
    model: str               # "markov" / "frequency" / "deepseek" / "ensemble"
    next_block_number: Optional[int] = None
    reason: str = ""         # DeepSeek 模型会给出的思考理由

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
    reason: str = ""         # 无信号时的说明


# ==================== DeepSeek Prompt ====================

_SYSTEM_PROMPT = """你是一个专业的二元序列分析和预测专家。你的任务是分析TRON区块链区块哈希末位数字的奇偶(单双)序列，预测下一期的结果。

规则：
- 序列中 1=单(奇数), 0=双(偶数)
- 你需要寻找序列中的统计规律、周期性、趋势反转等模式
- 注意：区块哈希本质接近随机，不要过度自信

请严格按以下JSON格式回复，不要输出其他内容：
{"prediction": 1, "confidence": 0.62, "reason": "简短理由"}

其中：
- prediction: 1=单, 0=双
- confidence: 0.50~0.95 之间的浮点数（0.5=完全不确定）
- reason: 10字以内的简短理由"""


def _build_user_prompt(sequence: List[int]) -> str:
    """构造用户消息。保持前缀尽可能稳定以触发 DeepSeek 上下文缓存."""
    seq_str = ",".join(str(x) for x in sequence)
    return f"最近{len(sequence)}期结果（从旧到新）：[{seq_str}]\n请预测下一期。"


class Predictor:
    """集成预测器：
    - Markov: 单步转移概率
    - Frequency: 近窗口频率反转
    - DeepSeek V4 Flash: LLM 模式识别（异步、可选、带超时 fallback）
    """

    def __init__(self, cfg: PredictorConfig, deepseek_cfg: Optional[DeepSeekConfig] = None):
        self.cfg = cfg
        self.deepseek_cfg = deepseek_cfg
        # DeepSeek 最后一次有效返回（缓存，当 API 超时/失败时用旧结果）
        self._deepseek_last_signal: Optional[Signal] = None
        self._deepseek_lock = threading.Lock()

    def update_config(self, cfg: PredictorConfig) -> None:
        self.cfg = cfg

    def update_deepseek_config(self, cfg: DeepSeekConfig) -> None:
        self.deepseek_cfg = cfg

    # ==================== 本地模型 ====================

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

    # ==================== DeepSeek V4 Flash ====================

    def _deepseek_call(self, analyzer: Analyzer) -> Optional[Signal]:
        """同步调用 DeepSeek API（在线程池中运行）."""
        cfg = self.deepseek_cfg
        if cfg is None or not cfg.enabled or not cfg.api_key:
            return None

        # 构造序列（1=单，0=双）
        history = analyzer.last(max(20, cfg.max_history))
        sequence = []
        for p in history:
            if p.is_odd:
                sequence.append(1)
            elif p.is_even:
                sequence.append(0)
        if len(sequence) < 10:
            return None

        user_msg = _build_user_prompt(sequence)

        try:
            url = f"{cfg.base_url.rstrip('/')}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": cfg.temperature,
                "max_tokens": 100,
                "stream": False,
            }

            with httpx.Client(timeout=cfg.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            # 解析回复
            content = data["choices"][0]["message"]["content"].strip()
            # 尝试提取 JSON（可能被 markdown 包裹）
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content)

            pred_val = int(result.get("prediction", -1))
            conf = float(result.get("confidence", 0.5))
            reason = str(result.get("reason", ""))[:50]

            # 合法性检查
            if pred_val not in (0, 1):
                logger.warning("DeepSeek 返回非法 prediction=%s", pred_val)
                return None
            conf = max(0.5, min(0.95, conf))  # 钳制到合理范围

            direction = PARITY_ODD if pred_val == 1 else PARITY_EVEN
            sig = Signal(
                prediction=direction,
                confidence=conf,
                model="deepseek",
                reason=reason,
            )

            # 缓存成功结果
            with self._deepseek_lock:
                self._deepseek_last_signal = sig

            # 记录 token 使用（日志级别 DEBUG）
            usage = data.get("usage", {})
            cache_hit = usage.get("prompt_cache_hit_tokens", 0)
            cache_miss = usage.get("prompt_cache_miss_tokens", 0)
            logger.info(
                "DeepSeek 预测: %s conf=%.2f reason=%s | tokens: cache_hit=%d miss=%d output=%d",
                sig.label, conf, reason, cache_hit, cache_miss,
                usage.get("completion_tokens", 0),
            )
            return sig

        except json.JSONDecodeError as e:
            logger.warning("DeepSeek 返回 JSON 解析失败: %s", e)
            return None
        except httpx.TimeoutException:
            logger.warning("DeepSeek API 超时 (>%ds)", cfg.timeout)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning("DeepSeek API HTTP 错误: %s", e.response.status_code)
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("DeepSeek 调用异常: %s", e)
            return None

    def _deepseek(self, analyzer: Analyzer) -> Optional[Signal]:
        """带超时的异步包装：提交到线程池，最多等 timeout 秒."""
        cfg = self.deepseek_cfg
        if cfg is None or not cfg.enabled or not cfg.api_key:
            return None

        try:
            future = _deepseek_pool.submit(self._deepseek_call, analyzer)
            result = future.result(timeout=cfg.timeout + 2)
            return result
        except FutureTimeout:
            logger.warning("DeepSeek 线程池超时，使用缓存结果")
            with self._deepseek_lock:
                return self._deepseek_last_signal
        except Exception as e:  # noqa: BLE001
            logger.warning("DeepSeek 线程池异常: %s", e)
            with self._deepseek_lock:
                return self._deepseek_last_signal

    # ==================== 集成预测 ====================

    def predict(self, analyzer: Analyzer) -> Prediction:
        # 数据量门槛
        min_required = 5
        if analyzer.stats.total < min_required:
            return Prediction(
                signals=[], best=None, has_signal=False,
                reason=f"数据不足（需至少 {min_required} 期，当前 {analyzer.stats.total}）",
            )

        signals: List[Signal] = []

        # 本地模型（同步，极快）
        for sig in (self._markov(analyzer), self._frequency(analyzer)):
            if sig is not None:
                signals.append(sig)

        # DeepSeek（同步但带超时 fallback）
        ds_sig = self._deepseek(analyzer)
        if ds_sig is not None:
            signals.append(ds_sig)

        if not signals:
            return Prediction(signals=[], best=None, has_signal=False, reason="暂无可用模型输出")

        # 加权投票集成
        ds_weight = float(getattr(self.deepseek_cfg, "weight", 1.5)) if self.deepseek_cfg else 1.0
        odd_score = 0.0
        even_score = 0.0
        total_weight = 0.0
        for s in signals:
            w = ds_weight if s.model == "deepseek" else 1.0
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
        return Prediction(
            signals=signals,
            best=best,
            has_signal=has,
            next_block_number=next_block,
            reason="" if has else f"置信度 {conf*100:.1f}% 低于阈值 {self.cfg.confidence_threshold*100:.0f}%",
        )

"""AI 预测器 - 本地模型(Markov+3-gram+频率) + DeepSeek V4 Flash LLM 集成.

- 本地模型：同步调用，<1ms
- DeepSeek：异步 HTTP，利用上下文缓存降低 token 消耗
- Ensemble：动态权重投票（根据近期命中率自适应调整）
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx

from ..utils.config import DeepSeekConfig, PredictorConfig
from ..utils.logger import get_logger
from .analyzer import Analyzer, PARITY_EVEN, PARITY_ODD, PARITY_UNKNOWN

logger = get_logger(__name__)

# DeepSeek 调用用的线程池（全局单例，避免重复创建线程）
_deepseek_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="deepseek")


@dataclass
class Signal:
    """单个模型的预测输出."""

    prediction: str          # "odd" / "even"
    confidence: float        # 0.0 ~ 1.0
    model: str               # "markov" / "ngram3" / "frequency" / "deepseek" / "ensemble"
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


# ==================== DeepSeek Prompt (优化版) ====================

_SYSTEM_PROMPT = """你是一个专业的二元序列分析和预测专家。你的任务是分析TRON区块链区块哈希末位数字的奇偶(单双)序列，预测下一期的结果。

分析方法：
1. 观察近期趋势（最后10期的走向）
2. 检测交替模式（单双单双...）
3. 检测连号趋势（连续单或连续双后的反转概率）
4. 统计近期单双比例偏离度
5. 观察3-gram模式出现频率

规则：
- 序列中 1=单(奇数), 0=双(偶数)
- confidence 应反映你的真实把握，50%=完全猜测，70%+=有一定把握
- 不要过度自信，区块哈希接近随机

示例：
输入: [1,0,1,0,1,0,1,0,1,0]
输出: {"prediction": 1, "confidence": 0.68, "reason": "强交替模式"}

输入: [1,1,1,0,0,0,1,1,1,0]
输出: {"prediction": 0, "confidence": 0.62, "reason": "3连后反转"}

输入: [0,1,0,0,1,1,0,1,0,1]
输出: {"prediction": 0, "confidence": 0.55, "reason": "近期单多回归"}

请严格按以下JSON格式回复，不要输出其他内容：
{"prediction": 1, "confidence": 0.62, "reason": "简短理由"}"""


def _build_user_prompt(sequence: List[int], recent_accuracy: Optional[float] = None) -> str:
    """构造用户消息。保持前缀尽可能稳定以触发 DeepSeek 上下文缓存.

    增加反馈循环：告知模型最近的命中率，让它自适应调整策略。
    """
    seq_str = ",".join(str(x) for x in sequence)
    msg = f"最近{len(sequence)}期结果（从旧到新）：[{seq_str}]"
    if recent_accuracy is not None:
        msg += f"\n[反馈] 你最近50次预测命中率: {recent_accuracy*100:.1f}%"
        if recent_accuracy < 0.45:
            msg += "（偏低，请尝试不同策略）"
        elif recent_accuracy > 0.55:
            msg += "（不错，继续当前策略）"
    msg += "\n请预测下一期。"
    return msg


# ==================== 动态权重管理 ====================

class DynamicWeights:
    """根据各模型近期命中率动态调整权重.

    - 基础权重: markov=1.0, ngram3=1.0, frequency=1.0, deepseek=1.5
    - 近50期命中率 > 55%: 权重 * 1.3
    - 近50期命中率 < 45%: 权重 * 0.5
    - 样本不足(<20期): 使用基础权重
    """

    def __init__(self):
        self._base_weights = {
            "markov": 1.0,
            "ngram3": 1.2,
            "frequency": 0.8,
            "deepseek": 1.5,
        }
        # 记录各模型的对错历史（用于计算动态权重）
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
        """返回近期命中率，样本不足时返回 None."""
        h = self._history.get(model)
        if not h or len(h) < 5:
            return None
        return sum(h) / len(h)

    def all_weights(self) -> Dict[str, float]:
        return {m: self.get_weight(m) for m in self._base_weights}


class Predictor:
    """集成预测器：
    - Markov: 单步转移概率 (window=50)
    - N-gram3: 3阶马尔可夫（看前3期组合模式）
    - Frequency: 近窗口频率反转
    - DeepSeek V4 Flash: LLM 模式识别（带 few-shot + 反馈循环）
    - Ensemble: 动态加权投票
    """

    def __init__(self, cfg: PredictorConfig, deepseek_cfg: Optional[DeepSeekConfig] = None):
        self.cfg = cfg
        self.deepseek_cfg = deepseek_cfg
        self.dynamic_weights = DynamicWeights()
        # DeepSeek 最后一次有效返回（缓存，当 API 超时/失败时用旧结果）
        self._deepseek_last_signal: Optional[Signal] = None
        self._deepseek_lock = threading.Lock()
        # DeepSeek 调用频率控制：最少间隔 10 秒，避免频繁请求被限流
        self._deepseek_min_interval = 10.0  # 秒
        self._deepseek_last_call_time: float = 0.0

    def update_config(self, cfg: PredictorConfig) -> None:
        self.cfg = cfg

    def update_deepseek_config(self, cfg: DeepSeekConfig) -> None:
        self.deepseek_cfg = cfg

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
        """3阶 N-gram Markov: P(next | 前3期组合).

        比如前3期是"单双单"，统计历史上这个pattern后面出单和出双的概率。
        """
        history = [p.parity for p in analyzer.last(200) if p.is_valid]
        if len(history) < 10:
            return None

        # 统计所有3-gram后面跟什么
        counts: Dict[Tuple[str, str, str], Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for i in range(len(history) - 3):
            key = (history[i], history[i + 1], history[i + 2])
            nxt = history[i + 3]
            if nxt in (PARITY_ODD, PARITY_EVEN):
                counts[key][nxt] += 1

        # 查最近3期
        if len(history) < 3:
            return None
        current_key = (history[-3], history[-2], history[-1])
        dist = counts.get(current_key)
        if not dist:
            return None

        total = sum(dist.values())
        if total < 3:  # 样本太少不可靠
            return None

        p_odd = dist.get(PARITY_ODD, 0) / total
        p_even = dist.get(PARITY_EVEN, 0) / total

        if p_odd > p_even:
            return Signal(PARITY_ODD, p_odd, model="ngram3",
                          reason=f"3-gram {total}样本")
        elif p_even > p_odd:
            return Signal(PARITY_EVEN, p_even, model="ngram3",
                          reason=f"3-gram {total}样本")
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
        # 反转策略：近期出现越少的一方，置信度越高（均值回归）
        if p_odd <= p_even:
            return Signal(PARITY_ODD, 0.5 + (p_even - 0.5), model="frequency")
        return Signal(PARITY_EVEN, 0.5 + (p_odd - 0.5), model="frequency")

    # ==================== DeepSeek V4 Flash ====================

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """从 DeepSeek 返回的文本中健壮提取 JSON 对象.

        支持以下格式：
        1. 纯 JSON: {"prediction": 1, ...}
        2. markdown 包裹: ```json\n{...}\n```
        3. JSON 前后有多余文字: "分析如下\n{...}\n以上"
        4. 带思考标签: <think>...</think>\n{...}
        """
        if not text:
            return None

        # 1) 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2) 尝试从 markdown 代码块提取
        if "```" in text:
            parts = text.split("```")
            for part in parts[1::2]:  # 取奇数段（代码块内容）
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    continue

        # 3) 尝试用正则找第一个 {...} 对象
        match = re.search(r'\{[^{}]*"prediction"[^{}]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 4) 更宽松：找任意 {...}
        match = re.search(r'\{[^{}]+\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

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

        # 获取 deepseek 最近命中率用于反馈循环
        recent_acc = self.dynamic_weights.get_accuracy("deepseek")
        user_msg = _build_user_prompt(sequence, recent_accuracy=recent_acc)

        try:
            url = f"{cfg.base_url.rstrip('/')}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": cfg.temperature,
                "max_tokens": 150,
                "stream": False,
                "response_format": {"type": "json_object"},
            }
            # model 字段：如果配置了就传，中转站可能不需要
            if cfg.model:
                payload["model"] = cfg.model

            with httpx.Client(timeout=cfg.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                # 如果中转站不支持 response_format，去掉后重试
                if resp.status_code == 400:
                    logger.info("中转站不支持 response_format，去掉后重试")
                    payload.pop("response_format", None)
                    resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            # 解析回复
            content = data["choices"][0]["message"]["content"]
            if not content or not content.strip():
                logger.warning("DeepSeek 返回空 content (model=%s)", cfg.model)
                return None
            content = content.strip()

            # 健壮的 JSON 提取：处理多种返回格式
            result = self._extract_json(content)
            if result is None:
                logger.warning("DeepSeek 返回内容无法提取 JSON: %s", content[:100])
                return None

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

            # 记录 token 使用
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
            if cfg is not None and cfg.enabled and not cfg.api_key:
                logger.info("DeepSeek 跳过：未配置 API Key")
            return None

        # 频率控制：距上次调用不足 min_interval 秒则跳过，使用缓存结果
        now = time.time()
        if now - self._deepseek_last_call_time < self._deepseek_min_interval:
            with self._deepseek_lock:
                return self._deepseek_last_signal
        self._deepseek_last_call_time = now

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
        for sig in (self._markov(analyzer), self._ngram3(analyzer), self._frequency(analyzer)):
            if sig is not None:
                signals.append(sig)

        # DeepSeek（同步但带超时 fallback）
        ds_sig = self._deepseek(analyzer)
        if ds_sig is not None:
            signals.append(ds_sig)

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

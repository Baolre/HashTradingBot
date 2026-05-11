"""配置加载与保存工具 - 纯单双版."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


@dataclass
class ApiConfig:
    trongrid_api_key: str = ""
    trongrid_endpoint: str = "https://api.trongrid.io"
    poll_interval: int = 3
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class FilterConfig:
    block_multiple: int = 20


@dataclass
class AnalyzerConfig:
    max_history: int = 500
    streak_window: int = 100


@dataclass
class AlertConfig:
    alternation_enabled: bool = True
    alternation_threshold: int = 6
    cooldown_periods: int = 3
    # 交叉预警的通知方式
    sound_enabled: bool = True
    bark_enabled: bool = True


@dataclass
class PredictorConfig:
    enabled: bool = True
    confidence_threshold: float = 0.70
    markov_window: int = 50
    bayesian_window: int = 30
    cycle_max_period: int = 20
    density_window: int = 10


@dataclass
class SimConfig:
    initial_balance: float = 10000.0
    base_bet: float = 100.0
    max_bet: float = 5000.0
    strategy: str = "flat"
    target: str = "follow_trend"


@dataclass
class BackfillConfig:
    enabled: bool = True
    days: int = 7
    max_blocks_per_run: int = 5000


@dataclass
class PushConfig:
    bark_enabled: bool = True
    bark_key: str = ""
    bark_server: str = "https://api.day.app"
    bark_sound: str = "alarm"
    bark_group: str = "hash_alert"


@dataclass
class StorageConfig:
    db_path: str = "data/hash_trading.db"


@dataclass
class UIConfig:
    column_max: int = 6
    dot_size: int = 30
    column_gap: int = 6


@dataclass
class AppConfig:
    api: ApiConfig = field(default_factory=ApiConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    analyzer: AnalyzerConfig = field(default_factory=AnalyzerConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)
    predictor: PredictorConfig = field(default_factory=PredictorConfig)
    sim: SimConfig = field(default_factory=SimConfig)
    backfill: BackfillConfig = field(default_factory=BackfillConfig)
    push: PushConfig = field(default_factory=PushConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        data = data or {}
        return cls(
            api=ApiConfig(**(data.get("api") or {})),
            filter=FilterConfig(**(data.get("filter") or {})),
            analyzer=AnalyzerConfig(**(data.get("analyzer") or {})),
            alert=AlertConfig(**(data.get("alert") or {})),
            predictor=PredictorConfig(**(data.get("predictor") or {})),
            sim=SimConfig(**(data.get("sim") or {})),
            backfill=BackfillConfig(**(data.get("backfill") or {})),
            push=PushConfig(**(data.get("push") or {})),
            storage=StorageConfig(**(data.get("storage") or {})),
            ui=UIConfig(**(data.get("ui") or {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_config(path: str | os.PathLike | None = None) -> AppConfig:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        return AppConfig()
    with open(p, "r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    return AppConfig.from_dict(data)


def save_config(cfg: AppConfig, path: str | os.PathLike | None = None) -> None:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fp:
        yaml.safe_dump(cfg.to_dict(), fp, allow_unicode=True, sort_keys=False)

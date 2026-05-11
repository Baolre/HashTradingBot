"""统一日志.

所有模块通过 get_logger(__name__) 获取 logger，实际返回的是
"hashbot.<module_name>" 子 logger，日志通过 propagate 冒泡到
根 "hashbot" logger 的 handler（控制台 + 文件）。
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "app.log"

_initialized = False
_ROOT_NAME = "hashbot"


def get_logger(name: str = "hashbot") -> logging.Logger:
    """获取 logger。

    - 首次调用时初始化根 "hashbot" logger 的 handler（控制台 + 文件）
    - 其他模块传入 __name__（如 "app.core.predictor"）时返回 "hashbot.app.core.predictor"
      这是 "hashbot" 的子 logger，日志自动冒泡到根 handler
    """
    global _initialized

    if not _initialized:
        # 初始化根 logger（只做一次）
        root_logger = logging.getLogger(_ROOT_NAME)
        root_logger.setLevel(logging.INFO)

        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 控制台
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        root_logger.addHandler(ch)

        # 文件
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                _LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            fh.setFormatter(fmt)
            root_logger.addHandler(fh)
        except Exception:  # noqa: BLE001
            pass

        _initialized = True

    # 返回子 logger（propagate=True 默认，日志会冒泡到 "hashbot" 根 logger）
    if name == _ROOT_NAME or name == "":
        return logging.getLogger(_ROOT_NAME)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")

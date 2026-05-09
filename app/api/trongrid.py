"""TronScan HTTP 客户端（替代原 TronGrid）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BlockInfo:
    number: int
    hash: str
    timestamp_ms: int
    parent_hash: str = ""
    tx_count: int = 0

    @property
    def timestamp_s(self) -> float:
        return self.timestamp_ms / 1000.0


class TronGridClient:
    """最小可用的 TronScan 客户端：拿最新块 / 按高度拿块。"""

    def __init__(
        self,
        endpoint: str = "https://apilist.tronscan.org",
        api_key: str = "",
        timeout: float = 10.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ---------- 内部 ----------
    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["TRON-PRO-API-KEY"] = self.api_key
        return h

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{self.endpoint}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(), params=params or {})
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _parse(block: dict) -> Optional[BlockInfo]:
        if not block:
            return None
        number = block.get("number")
        block_hash = block.get("hash") or block.get("blockID") or ""
        ts = block.get("timestamp", 0)
        parent = block.get("parentHash", "")
        txs = block.get("transactions") or []
        if number is None or not block_hash:
            return None
        return BlockInfo(
            number=int(number),
            hash=block_hash,
            timestamp_ms=int(ts),
            parent_hash=parent,
            tx_count=len(txs),
        )

    # ---------- 公开 ----------
    def get_now_block(self) -> Optional[BlockInfo]:
        """获取最新区块（取第一条）。"""
        try:
            data = self._get("/api/block", {"sort": "-number", "limit": 1})
            blocks = data.get("data") or []
            return self._parse(blocks[0]) if blocks else None
        except Exception as e:  # noqa: BLE001
            logger.warning("get_now_block 失败: %s", e)
            return None

    def get_block_by_num(self, num: int) -> Optional[BlockInfo]:
        """按高度获取指定区块。"""
        try:
            data = self._get("/api/block", {"number": int(num)})
            blocks = data.get("data") or []
            return self._parse(blocks[0]) if blocks else None
        except Exception as e:  # noqa: BLE001
            logger.warning("get_block_by_num(%s) 失败: %s", num, e)
            return None

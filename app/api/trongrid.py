"""TronGrid HTTP 客户端.

参考:
- https://developers.tron.network/reference/wallet-getnowblock
- https://docs.tronscan.org/zh/api/api-keys  (TRON-PRO-API-KEY header)
"""
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
    """最小可用的 TronGrid 客户端：拿最新块 / 按高度拿块."""

    def __init__(
        self,
        endpoint: str = "https://api.trongrid.io",
        api_key: str = "",
        timeout: float = 10.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ---------- 内部 ----------
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            h["TRON-PRO-API-KEY"] = self.api_key
        return h

    def _post(self, path: str, payload: Optional[dict] = None) -> dict:
        url = f"{self.endpoint}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self._headers(), json=payload or {})
            resp.raise_for_status()
            return resp.json()

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
        # 支持两种格式：TronGrid 原格式和新 API 格式
        # TronGrid 格式
        if "block_header" in block:
            header = (block.get("block_header") or {}).get("raw_data") or {}
            number = header.get("number")
            ts = header.get("timestamp", 0)
            parent = header.get("parentHash", "")
            block_hash = block.get("blockID") or ""
            txs = block.get("transactions") or []
        else:
            # 新 API 格式（tronscanapi）
            number = block.get("number")
            ts = block.get("timestamp", 0)
            parent = block.get("parentHash", "")
            block_hash = block.get("hash") or ""
            txs = []  # 新 API 不返回交易列表
        
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
        """获取最新区块."""
        try:
            # 先尝试新 API 格式
            if "tronscanapi" in self.endpoint:
                data = self._get("/api/block")
                if data and "data" in data and len(data["data"]) > 0:
                    return self._parse(data["data"][0])
            else:
                data = self._post("/wallet/getnowblock")
                return self._parse(data)
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("get_now_block 失败: %s", e)
            return None

    def get_block_by_num(self, num: int) -> Optional[BlockInfo]:
        """按高度获取指定区块."""
        try:
            # 先尝试新 API 格式
            if "tronscanapi" in self.endpoint:
                data = self._get("/api/block", {"number": int(num)})
                if data and "data" in data and len(data["data"]) > 0:
                    return self._parse(data["data"][0])
            else:
                data = self._post("/wallet/getblockbynum", {"num": int(num)})
                return self._parse(data)
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("get_block_by_num(%s) 失败: %s", num, e)
            return None

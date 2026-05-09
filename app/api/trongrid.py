"""TronGrid/TronScan HTTP 客户端 - 带重试 + LRU 缓存.

兼容两种 endpoint:
- TronGrid: https://api.trongrid.io (POST /wallet/getnowblock)
- TronScan: https://apilist.tronscanapi.com (GET /api/block)
"""
from __future__ import annotations

import time
from collections import OrderedDict
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


class LRUCache:
    """简单 LRU 缓存."""

    def __init__(self, capacity: int = 500):
        self._capacity = capacity
        self._cache: OrderedDict[int, BlockInfo] = OrderedDict()

    def get(self, key: int) -> Optional[BlockInfo]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: int, value: BlockInfo) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        while len(self._cache) > self._capacity:
            self._cache.popitem(last=False)

    def size(self) -> int:
        return len(self._cache)


class TronGridClient:
    """兼容 TronGrid 和 TronScan 的客户端."""

    def __init__(
        self,
        endpoint: str = "https://api.trongrid.io",
        api_key: str = "",
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cache = LRUCache(capacity=500)
        self._last_error: str = ""
        self._is_tronscan = "tronscan" in self.endpoint.lower()

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def cache_hit_size(self) -> int:
        return self._cache.size()

    @property
    def request_count(self) -> int:
        return getattr(self, "_request_count", 0)

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["TRON-PRO-API-KEY"] = self.api_key
        if not self._is_tronscan:
            h["Content-Type"] = "application/json"
        return h

    def _request_with_retry(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        url = f"{self.endpoint}{path}"
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                self._request_count = getattr(self, "_request_count", 0) + 1
                with httpx.Client(timeout=self.timeout) as client:
                    if method == "GET":
                        resp = client.get(url, headers=self._headers(), params=payload)
                    else:
                        resp = client.post(url, headers=self._headers(), json=payload or {})

                    if resp.status_code == 429:
                        wait = self.retry_delay * (2 ** attempt)
                        logger.warning("429 限流, %.1fs 后重试", wait)
                        time.sleep(wait)
                        continue

                    resp.raise_for_status()
                    return resp.json()

            except httpx.TimeoutException as e:
                last_err = e
                wait = self.retry_delay * (2 ** attempt)
                logger.warning("超时 %s, %.1fs 后重试 (%d)", path, wait, attempt + 1)
                time.sleep(wait)
            except httpx.HTTPStatusError as e:
                last_err = e
                if e.response.status_code >= 500:
                    wait = self.retry_delay * (2 ** attempt)
                    time.sleep(wait)
                else:
                    break
            except Exception as e:
                last_err = e
                wait = self.retry_delay * (2 ** attempt)
                time.sleep(wait)

        if last_err:
            raise last_err
        raise RuntimeError(f"请求 {path} 失败")

    # ========== TronGrid 解析 ==========
    @staticmethod
    def _parse_trongrid_block(block: dict) -> Optional[BlockInfo]:
        if not block:
            return None
        header = (block.get("block_header") or {}).get("raw_data") or {}
        number = header.get("number")
        ts = header.get("timestamp", 0)
        parent = header.get("parentHash", "")
        block_hash = block.get("blockID") or ""
        txs = block.get("transactions") or []
        if number is None or not block_hash:
            return None
        return BlockInfo(number=int(number), hash=block_hash, timestamp_ms=int(ts),
                         parent_hash=parent, tx_count=len(txs))

    # ========== TronScan 解析 ==========
    @staticmethod
    def _parse_tronscan_block(data: dict) -> Optional[BlockInfo]:
        if not data:
            return None
        number = data.get("number") or data.get("block_id")
        block_hash = data.get("hash") or data.get("blockID") or ""
        ts = data.get("timestamp", 0)
        parent = data.get("parentHash", "")
        tx_count = data.get("nrOfTrx", 0) or data.get("txTrieRoot_len", 0)
        if number is None or not block_hash:
            return None
        return BlockInfo(number=int(number), hash=block_hash, timestamp_ms=int(ts),
                         parent_hash=parent, tx_count=int(tx_count))

    # ========== 公开 API ==========
    def get_now_block(self) -> Optional[BlockInfo]:
        try:
            if self._is_tronscan:
                data = self._request_with_retry("GET", "/api/block", {"sort": "-number", "limit": "1", "start": "0"})
                items = data.get("data") or []
                if items:
                    info = self._parse_tronscan_block(items[0])
                else:
                    info = self._parse_tronscan_block(data)
            else:
                data = self._request_with_retry("POST", "/wallet/getnowblock")
                info = self._parse_trongrid_block(data)

            if info:
                self._cache.put(info.number, info)
                self._last_error = ""
            return info
        except Exception as e:
            self._last_error = str(e)
            logger.warning("get_now_block 失败: %s", e)
            return None

    def get_block_by_num(self, num: int) -> Optional[BlockInfo]:
        cached = self._cache.get(num)
        if cached is not None:
            return cached
        try:
            if self._is_tronscan:
                data = self._request_with_retry("GET", "/api/block", {"number": str(num)})
                items = data.get("data") or []
                if items:
                    info = self._parse_tronscan_block(items[0])
                else:
                    info = self._parse_tronscan_block(data)
            else:
                data = self._request_with_retry("POST", "/wallet/getblockbynum", {"num": int(num)})
                info = self._parse_trongrid_block(data)

            if info:
                self._cache.put(info.number, info)
                self._last_error = ""
            return info
        except Exception as e:
            self._last_error = str(e)
            logger.warning("get_block_by_num(%s) 失败: %s", num, e)
            return None

"""SQLite 存储层.

只做两件事:
1. 持久化已确认的区块（便于断点续跑 / 历史回看）
2. 持久化预警记录
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..core.analyzer import Period
from ..utils.logger import get_logger

logger = get_logger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS blocks (
    block_number INTEGER PRIMARY KEY,
    block_hash   TEXT    NOT NULL,
    digit        INTEGER,
    parity       TEXT    NOT NULL,
    timestamp_ms INTEGER NOT NULL DEFAULT 0,
    created_at   INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_blocks_created_at ON blocks(created_at);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT    NOT NULL,
    message      TEXT    NOT NULL,
    block_number INTEGER,
    created_at   INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
"""


@dataclass
class AlertRow:
    id: int
    kind: str
    message: str
    block_number: Optional[int]
    created_at: int


class Storage:
    def __init__(self, db_path: str = "data/hash_trading.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------- blocks -------------------
    def save_block(self, p: Period) -> bool:
        """插入一条区块记录；已存在返回 False."""
        with self._lock:
            try:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO blocks(block_number, block_hash, digit, parity, timestamp_ms) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (p.block_number, p.block_hash, p.digit, p.parity, p.timestamp_ms),
                )
                self._conn.commit()
                return cur.rowcount > 0
            except Exception as e:  # noqa: BLE001
                logger.warning("save_block 失败: %s", e)
                return False

    def load_recent_blocks(self, limit: int = 200) -> List[Period]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT block_number, block_hash, digit, parity, timestamp_ms "
                "FROM blocks ORDER BY block_number DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        rows.reverse()
        out: List[Period] = []
        for r in rows:
            out.append(Period(
                block_number=r["block_number"],
                block_hash=r["block_hash"],
                digit=r["digit"],
                parity=r["parity"],
                timestamp_ms=r["timestamp_ms"],
            ))
        return out

    def latest_block_number(self) -> Optional[int]:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(block_number) AS mx FROM blocks"
            ).fetchone()
        if not row or row["mx"] is None:
            return None
        return int(row["mx"])

    def block_exists(self, block_number: int) -> bool:
        """检查指定区块是否已存在于数据库中."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM blocks WHERE block_number = ?",
                (block_number,)
            ).fetchone()
            return row is not None

    # ------------------- alerts -------------------
    def save_alert(self, kind: str, message: str, block_number: Optional[int] = None) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alerts(kind, message, block_number) VALUES (?, ?, ?)",
                (kind, message, block_number),
            )
            self._conn.commit()
            return cur.lastrowid

    def load_recent_alerts(self, limit: int = 100) -> List[AlertRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, kind, message, block_number, created_at "
                "FROM alerts ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            AlertRow(
                id=r["id"],
                kind=r["kind"],
                message=r["message"],
                block_number=r["block_number"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

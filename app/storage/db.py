"""SQLite 存储层 - 支持 size 列 + 自动迁移."""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..core.analyzer import Period, size_of_digit, parity_of_digit
from ..utils.logger import get_logger

logger = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS blocks (
    block_number INTEGER PRIMARY KEY,
    block_hash   TEXT NOT NULL,
    digit        INTEGER,
    parity       TEXT NOT NULL,
    size         TEXT NOT NULL DEFAULT 'unknown',
    timestamp_ms INTEGER NOT NULL DEFAULT 0,
    created_at   INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_blocks_created ON blocks(created_at);
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,
    message      TEXT NOT NULL,
    block_number INTEGER,
    created_at   INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);
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
        self._migrate()

    def _migrate(self) -> None:
        try:
            cols = [r["name"] for r in self._conn.execute("PRAGMA table_info(blocks)").fetchall()]
            if "size" not in cols:
                self._conn.execute("ALTER TABLE blocks ADD COLUMN size TEXT NOT NULL DEFAULT 'unknown'")
                self._conn.commit()
                logger.info("DB迁移: 添加 size 列")
        except Exception as e:
            logger.warning("DB迁移检查: %s", e)

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def save_block(self, p: Period) -> bool:
        with self._lock:
            try:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO blocks(block_number, block_hash, digit, parity, size, timestamp_ms) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (p.block_number, p.block_hash, p.digit, p.parity, p.size, p.timestamp_ms),
                )
                self._conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                logger.warning("save_block: %s", e)
                return False

    def load_recent_blocks(self, limit: int = 500) -> List[Period]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT block_number, block_hash, digit, parity, size, timestamp_ms "
                "FROM blocks ORDER BY block_number DESC LIMIT ?", (int(limit),)
            ).fetchall()
        rows.reverse()
        out: List[Period] = []
        for r in rows:
            size = r["size"] if "size" in r.keys() else "unknown"
            if size == "unknown" and r["digit"] is not None:
                size = size_of_digit(r["digit"])
            out.append(Period(block_number=r["block_number"], block_hash=r["block_hash"],
                              digit=r["digit"], parity=r["parity"], size=size,
                              timestamp_ms=r["timestamp_ms"]))
        return out

    def latest_block_number(self) -> Optional[int]:
        with self._lock:
            row = self._conn.execute("SELECT MAX(block_number) AS mx FROM blocks").fetchone()
        return int(row["mx"]) if row and row["mx"] is not None else None

    def block_exists(self, block_number: int) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM blocks WHERE block_number = ?", (block_number,)).fetchone()
            return row is not None

    def save_alert(self, kind: str, message: str, block_number: Optional[int] = None) -> int:
        with self._lock:
            cur = self._conn.execute("INSERT INTO alerts(kind, message, block_number) VALUES (?, ?, ?)",
                                     (kind, message, block_number))
            self._conn.commit()
            return cur.lastrowid

    def load_recent_alerts(self, limit: int = 200) -> List[AlertRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, kind, message, block_number, created_at FROM alerts ORDER BY id DESC LIMIT ?",
                (int(limit),)).fetchall()
        return [AlertRow(id=r["id"], kind=r["kind"], message=r["message"],
                         block_number=r["block_number"], created_at=r["created_at"]) for r in rows]

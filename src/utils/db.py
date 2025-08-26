import os
import aiosqlite
from typing import Any, Dict

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT NOT NULL,
  symbol TEXT NOT NULL,
  entry_price REAL NOT NULL,
  size REAL NOT NULL,
  base_spent REAL NOT NULL,
  strategy TEXT NOT NULL,
  entry_ts TEXT NOT NULL,
  stop_loss REAL NOT NULL,
  ttl_sec INTEGER NOT NULL,
  trailing_pct REAL,
  tp_layers TEXT,           -- JSON list of targets or single pct
  status TEXT NOT NULL,     -- OPEN/CLOSED
  peak_price REAL DEFAULT NULL,
  notes TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT NOT NULL,
  symbol TEXT NOT NULL,
  strategy TEXT NOT NULL,
  entry_ts TEXT NOT NULL,
  exit_ts TEXT NOT NULL,
  entry_price REAL NOT NULL,
  exit_price REAL NOT NULL,
  size REAL NOT NULL,
  pnl_amount REAL NOT NULL,
  pnl_pct REAL NOT NULL,
  reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seen_tokens (
  token TEXT PRIMARY KEY,
  first_seen_ts TEXT NOT NULL,
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS equity (
  ts TEXT PRIMARY KEY,
  equity REAL NOT NULL,
  peak_equity REAL NOT NULL,
  day_str TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
"""

async def init_db(cfg):
    async with aiosqlite.connect(cfg.database.path) as db:
        for stmt in SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                await db.execute(s)
        await db.commit()

def ensure_dirs(cfg):
    os.makedirs(os.path.dirname(cfg.logging.log_file), exist_ok=True)

def open_sqlite(cfg):
    return aiosqlite.connect(cfg.database.path)

async def kv_get(db, key: str):
    async with db.execute("SELECT v FROM kv WHERE k=?", (key,)) as cur:
        row = await cur.fetchone()
        return None if not row else row[0]

async def kv_set(db, key: str, val: str):
    await db.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, val))
    await db.commit()

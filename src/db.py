"""SQLite relational mirror of Valet's extracted facts.

This is the structured, queryable store the user explicitly asked for. Mem0 owns semantic
recall; this owns precise, filterable, relational fact storage.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL,
    entity          TEXT,
    fact_text       TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 0.5,
    status          TEXT NOT NULL DEFAULT 'extracted',
    source_message  TEXT,
    mem0_id         TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_status   ON facts(status);
CREATE INDEX IF NOT EXISTS idx_facts_entity   ON facts(entity);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    Path(config.VALET_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.VALET_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the schema if it doesn't exist. Idempotent (boot gate)."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def insert_fact(
    category: str,
    fact_text: str,
    *,
    entity: Optional[str] = None,
    confidence: float = 0.5,
    status: str = "extracted",
    source_message: Optional[str] = None,
    mem0_id: Optional[str] = None,
) -> int:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO facts
                (category, entity, fact_text, confidence, status, source_message, mem0_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (category, entity, fact_text, confidence, status, source_message, mem0_id, now, now),
        )
        return int(cur.lastrowid)


def list_facts(
    *,
    category: Optional[str] = None,
    entity: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    sql = "SELECT * FROM facts WHERE 1=1"
    params: list = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if entity:
        sql += " AND entity LIKE ?"
        params.append(f"%{entity}%")
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q:
        sql += " AND (fact_text LIKE ? OR entity LIKE ?)"
        params.append(f"%{q}%")
        params.append(f"%{q}%")
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_fact(fact_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
    return dict(row) if row else None


def count_facts() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM facts").fetchone()
        return int(row["c"]) if row else 0


def distinct_categories() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM facts ORDER BY category"
        ).fetchall()
    return [r["category"] for r in rows]

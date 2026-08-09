"""SQLite relational mirror of Jeeves's extracted facts.

This is the structured, queryable store the user explicitly asked for. Mem0 owns semantic
recall; this owns precise, filterable, relational fact storage.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
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
    quantity        REAL,
    unit            TEXT,
    period          TEXT,
    fact_date       TEXT,
    fact_time       TEXT,
    superseded_by   INTEGER,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_status   ON facts(status);
CREATE INDEX IF NOT EXISTS idx_facts_entity   ON facts(entity);
CREATE INDEX IF NOT EXISTS idx_facts_period   ON facts(category, entity, period);
"""


def _now() -> str:
    return config.local_now().isoformat()


def _connect() -> sqlite3.Connection:
    Path(config.JEEVES_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.JEEVES_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate() -> None:
    """Add derived/conflict columns to an existing facts table without losing data."""
    with _connect() as conn:
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(facts)").fetchall()}
        for col, ddl in [
            ("quantity", "REAL"),
            ("unit", "TEXT"),
            ("period", "TEXT"),
            ("fact_date", "TEXT"),
            ("fact_time", "TEXT"),
            ("superseded_by", "INTEGER"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE facts ADD COLUMN {col} {ddl}")


def init_db() -> None:
    """Create the schema if it doesn't exist. Idempotent (boot gate)."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    migrate()


def insert_fact(
    category: str,
    fact_text: str,
    *,
    entity: Optional[str] = None,
    confidence: float = 0.5,
    status: str = "extracted",
    source_message: Optional[str] = None,
    mem0_id: Optional[str] = None,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    period: Optional[str] = None,
    fact_date: Optional[str] = None,
    fact_time: Optional[str] = None,
) -> int:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO facts
                (category, entity, fact_text, confidence, status, source_message, mem0_id,
                 quantity, unit, period, fact_date, fact_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (category, entity, fact_text, confidence, status, source_message, mem0_id,
             quantity, unit, period, fact_date, fact_time, now, now),
        )
        return int(cur.lastrowid)


def update_fact(
    fact_id: int,
    *,
    fact_text: Optional[str] = None,
    category: Optional[str] = None,
    entity: Optional[str] = None,
    confidence: Optional[float] = None,
    status: Optional[str] = None,
) -> bool:
    fields = []
    params: list = []
    if fact_text is not None:
        fields.append("fact_text = ?"); params.append(fact_text)
    if category is not None:
        fields.append("category = ?"); params.append(category)
    if entity is not None:
        fields.append("entity = ?"); params.append(entity)
    if confidence is not None:
        fields.append("confidence = ?"); params.append(confidence)
    if status is not None:
        fields.append("status = ?"); params.append(status)
    if not fields:
        return False
    fields.append("updated_at = ?"); params.append(_now())
    params.append(fact_id)
    with _connect() as conn:
        cur = conn.execute(f"UPDATE facts SET {', '.join(fields)} WHERE id = ?", params)
        return cur.rowcount > 0


def supersede_fact(old_id: int, new_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE facts SET status = 'superseded', superseded_by = ?, updated_at = ? WHERE id = ?",
            (new_id, _now(), old_id),
        )


def facts_by_key(category: str, entity: Optional[str], period: Optional[str]) -> list[dict]:
    """Find active facts that a new fact likely conflicts with.

    Matching strategy (entity assignment from the LLM is noisy, so we don't require it):
    - If the new fact has a period, match on (category, period) — two "Workout / this week"
      statements are the same metric and should supersede.
    - Else if it has an entity, match on (category, entity).
    - Else match on category alone (weaker, still surfaces likely conflicts).
    """
    with _connect() as conn:
        if period:
            rows = conn.execute(
                "SELECT * FROM facts WHERE category = ? AND period = ? "
                "AND status IN ('extracted','active','verified')",
                (category, period),
            ).fetchall()
        elif entity:
            rows = conn.execute(
                "SELECT * FROM facts WHERE category = ? AND entity = ? "
                "AND status IN ('extracted','active','verified')",
                (category, entity),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM facts WHERE category = ? "
                "AND status IN ('extracted','active','verified')",
                (category,),
            ).fetchall()
    return [dict(r) for r in rows]


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


def delete_fact(fact_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        return cur.rowcount > 0


def delete_facts(
    *,
    category: Optional[str] = None,
    entity: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> int:
    """Bulk delete by the same filters as list_facts. Returns number deleted."""
    sql = "DELETE FROM facts WHERE 1=1"
    params: list = []
    if category:
        sql += " AND category = ?"; params.append(category)
    if entity:
        sql += " AND entity LIKE ?"; params.append(f"%{entity}%")
    if status:
        sql += " AND status = ?"; params.append(status)
    if q:
        sql += " AND (fact_text LIKE ? OR entity LIKE ?)"
        params.append(f"%{q}%"); params.append(f"%{q}%")
    with _connect() as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount


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

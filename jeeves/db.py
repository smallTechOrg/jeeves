"""Relational store for Jeeves's extracted structured facts.

This is the precise, filterable, queryable store (Mem0 owns fuzzy semantic recall).
Backed by **SQLAlchemy Core** so the same code runs on SQLite locally and Postgres
(Supabase) in prod — selected by `config.JEEVES_DB_URL` (`JEEVES_DB_PATH` SQLite
falls back when no URL is set).

Column types use generic SQLAlchemy types; SQLite/Postgres map them natively.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    MetaData, Table, Column, Integer, String, Float,
    select, insert, update, delete, text as sa_text, func,
)

from . import config

_metadata = MetaData()

facts = Table(
    "facts", _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("category", String, nullable=False),
    Column("entity", String, nullable=True),
    Column("fact_text", String, nullable=False),
    Column("confidence", Float, nullable=False, server_default="0.5"),
    Column("status", String, nullable=False, server_default="extracted"),
    Column("source_message", String, nullable=True),
    Column("mem0_id", String, nullable=True),
    Column("quantity", Float, nullable=True),
    Column("unit", String, nullable=True),
    Column("period", String, nullable=True),
    Column("fact_date", String, nullable=True),
    Column("fact_time", String, nullable=True),
    Column("superseded_by", Integer, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=True),
)

# Mirror of the legacy local-now for created/updated stamps (tz-aware, owner's local tz).
def _now() -> str:
    return config.local_now().isoformat()


def init_db() -> None:
    """Create the schema if it doesn't exist. Idempotent (boot gate)."""
    _metadata.create_all(config.ENGINE)
    # Ensure columns added after initial creation exist (covers upgrades on an existing DB).
    migrate()


def migrate() -> None:
    """Add any columns missing on an existing table (SQLite only; Postgres create_all covers it)."""
    if not config.ENGINE.dialect.name.startswith("sqlite"):
        return
    with config.ENGINE.connect() as conn:
        existing = {r[1] for r in conn.execute(sa_text("PRAGMA table_info(facts)")).fetchall()}
    for col in ["quantity", "unit", "period", "fact_date", "fact_time", "superseded_by"]:
        if col not in existing:
            with config.ENGINE.begin() as conn:
                conn.execute(sa_text(f"ALTER TABLE facts ADD COLUMN {col} {_SQLITE_COLTYPE[col]}"))


_SQLITE_COLTYPE = {
    "quantity": "REAL", "unit": "TEXT", "period": "TEXT",
    "fact_date": "TEXT", "fact_time": "TEXT", "superseded_by": "INTEGER",
}


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
    with config.ENGINE.begin() as conn:
        result = conn.execute(
            insert(facts).values(
                category=category, entity=entity, fact_text=fact_text,
                confidence=confidence, status=status, source_message=source_message,
                mem0_id=mem0_id, quantity=quantity, unit=unit, period=period,
                fact_date=fact_date, fact_time=fact_time,
                created_at=now, updated_at=now,
            )
        )
        return int(result.inserted_primary_key[0])


def update_fact(
    fact_id: int,
    *,
    fact_text: Optional[str] = None,
    category: Optional[str] = None,
    entity: Optional[str] = None,
    confidence: Optional[float] = None,
    status: Optional[str] = None,
) -> bool:
    fields = {}
    if fact_text is not None:
        fields["fact_text"] = fact_text
    if category is not None:
        fields["category"] = category
    if entity is not None:
        fields["entity"] = entity
    if confidence is not None:
        fields["confidence"] = confidence
    if status is not None:
        fields["status"] = status
    if not fields:
        return False
    fields["updated_at"] = _now()
    with config.ENGINE.begin() as conn:
        result = conn.execute(
            update(facts).where(facts.c.id == fact_id).values(**fields)
        )
        return result.rowcount > 0


def supersede_fact(old_id: int, new_id: int) -> None:
    with config.ENGINE.begin() as conn:
        conn.execute(
            update(facts)
            .where(facts.c.id == old_id)
            .values(status="superseded", superseded_by=new_id, updated_at=_now())
        )


def facts_by_key(category: str, entity: Optional[str], period: Optional[str]) -> list[dict]:
    """Find active facts a new fact likely conflicts with.

    Matching strategy (entity assignment from the LLM is noisy, so we don't require it):
    - If the new fact has a period, match on (category, period).
    - Else if it has an entity, match on (category, entity).
    - Else match on category alone (weaker, still surfaces likely conflicts).
    """
    stmt = select(facts).where(facts.c.category == category)
    if period:
        stmt = stmt.where(facts.c.period == period)
    elif entity:
        stmt = stmt.where(facts.c.entity == entity)
    stmt = stmt.where(facts.c.status.in_(["extracted", "active", "verified"]))
    with config.ENGINE.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [dict(r) for r in rows]


def list_facts(
    *,
    category: Optional[str] = None,
    entity: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(facts)
    if category:
        stmt = stmt.where(facts.c.category == category)
    if entity:
        stmt = stmt.where(facts.c.entity.like(f"%{entity}%"))
    if status:
        stmt = stmt.where(facts.c.status == status)
    if q:
        stmt = stmt.where(facts.c.fact_text.like(f"%{q}%") | facts.c.entity.like(f"%{q}%"))
    stmt = stmt.order_by(facts.c.created_at.desc()).limit(limit)
    with config.ENGINE.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [dict(r) for r in rows]


def get_fact(fact_id: int) -> dict | None:
    with config.ENGINE.connect() as conn:
        row = conn.execute(select(facts).where(facts.c.id == fact_id)).mappings().first()
    return dict(row) if row else None


def delete_fact(fact_id: int) -> bool:
    with config.ENGINE.begin() as conn:
        result = conn.execute(delete(facts).where(facts.c.id == fact_id))
        return result.rowcount > 0


def delete_facts(
    *,
    category: Optional[str] = None,
    entity: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> int:
    """Bulk delete by the same filters as list_facts. Returns number deleted."""
    stmt = delete(facts)
    if category:
        stmt = stmt.where(facts.c.category == category)
    if entity:
        stmt = stmt.where(facts.c.entity.like(f"%{entity}%"))
    if status:
        stmt = stmt.where(facts.c.status == status)
    if q:
        stmt = stmt.where(facts.c.fact_text.like(f"%{q}%") | facts.c.entity.like(f"%{q}%"))
    with config.ENGINE.begin() as conn:
        result = conn.execute(stmt)
        return result.rowcount


def count_facts() -> int:
    with config.ENGINE.connect() as conn:
        row = conn.execute(select(func.count()).select_from(facts)).first()
    return int(row[0]) if row else 0


def distinct_categories() -> list[str]:
    with config.ENGINE.connect() as conn:
        rows = conn.execute(
            select(facts.c.category).distinct().order_by(facts.c.category)
        ).fetchall()
    return [r[0] for r in rows]

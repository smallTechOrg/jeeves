-- Jeeves Supabase init (run once in the Supabase SQL Editor: dashboard → your project → SQL → New query → paste → Run)
-- This enables the pgvector extension (required for Mem0's semantic store) and pre-creates
-- the relational `facts` table that SQLAlchemy also auto-creates on boot (idempotent here).

create extension if not exists vector;

-- Relational facts mirror (the precise, queryable store). SQLAlchemy create_all covers this,
-- but declaring it here documents the schema and guarantees it exists before first request.
create table if not exists facts (
    id              bigserial primary key,
    category        text not null,
    entity          text,
    fact_text       text not null,
    confidence      real not null default 0.5,
    status          text not null default 'extracted',
    source_message  text,
    mem0_id         text,
    quantity        real,
    unit            text,
    period          text,
    fact_date       text,
    fact_time       text,
    superseded_by   bigint,
    created_at      text not null,
    updated_at      text,
    constraint facts_status_check check (status in ('extracted','active','verified','superseded','conflicted'))
);

create index if not exists idx_facts_category on facts(category);
create index if not exists idx_facts_status   on facts(status);
create index if not exists idx_facts_entity   on facts(entity);
create index if not exists idx_facts_period   on facts(category, entity, period);

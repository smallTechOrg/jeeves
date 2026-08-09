# Jeeves on Supabase + Render — 5-minute setup

Goal: durable memory in Supabase (Postgres + pgvector) + a public Render URL.
You do the clicks (your accounts); everything else is copy-paste.

---

## Step 1 — Create the Supabase project
1. Open **https://supabase.com/dashboard** → **New project**.
2. Name it `jeeves`, pick a region near you, set a strong DB password (save it!).
3. Wait ~1 min for it to spin up.

## Step 2 — Enable the vector extension (paste-once SQL)
1. In the Supabase dashboard → your project → **SQL** (left sidebar) → **New query**.
2. Paste the contents of `supabase/migrations/0001_init.sql` (also below) and click **Run**.
```sql
create extension if not exists vector;

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
    updated_at      text
);
create index if not exists idx_facts_category on facts(category);
create index if not exists idx_facts_status   on facts(status);
create index if not exists idx_facts_entity   on facts(entity);
```

## Step 3 — Copy your credentials
1. Supabase dashboard → **Project Settings** (gear) → **API**.
2. Copy:
   - **Project URL** → looks like `https://xxxxxxxx.supabase.co`
   - **Project API key** (the `service_role` key — keep secret) → long `eyJ…` string
3. Supabase dashboard → **Project Settings** → **Database** → **Connection string** →
   pick **URI** (or "Transaction pooler" / "Session pooler"). Copy the Postgres URL; it
   looks like:
   `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxx.supabase.co:5432/postgres`
   (If it shows `postgres://` or `postgresql://` without a driver, that's fine — Jeeves
   auto-adds `+psycopg`.)

## Step 4 — Deploy on Render
1. Open **https://dashboard.render.com/** → **New** → **Web Service** → **Connect a repository**
   → select **smallTechOrg/jeeves** (grant Render GitHub access if prompted).
2. Render reads `render.yaml` automatically. Set these **Environment Variables** (the ones
   marked `sync: false` need your values — paste from Step 3):
   | Key | Value |
   |---|---|
   | `JEEVES_DB_URL` | the Postgres URI from Step 3 (Supabase) |
   | `SUPABASE_URL` | `https://xxxxxxxx.supabase.co` |
   | `SUPABASE_KEY` | the service_role API key |
   | `NVIDIA_API_KEY` | your NVIDIA key |
   | `JEEVES_TZ` | e.g. `Asia/Kolkata` |
   (NVIDIA_BASE_URL / model slugs are pre-set in `render.yaml`.)
3. Click **Create Web Service**. Build + start takes ~1–2 min.
4. Open the Render URL (e.g. `https://jeeves.onrender.com`) → send
   "I signed up for a half marathon" → **reload the page** → the fact is still there.
   That proves Supabase persistence (not Render's ephemeral disk).

## Step 5 — Tell Jeeves to start accumulating real info
Just chat at the Render URL. Everything you tell it lands in Supabase `facts` — your
durable personal memory. Local `./jeeves.db` stays for dev only.

---

### Notes
- If Mem0's Supabase *semantic* store fails to init, Jeeves logs a warning and falls back to
  local Chroma for fuzzy recall only — **relational facts still persist in Supabase**. Fix the
  `MEM0_USE_SUPABASE` config if you want semantic search in prod.
- Never commit secrets. `.env` is gitignored. On Render, secrets live in the dashboard.

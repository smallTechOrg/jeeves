# Jeeves

A Jeeves-style personal memory agent. You tell Jeeves ordinary things about yourself —
"I did 3 workouts this week", "my goal is a sub-2h half marathon", "I'm feeling drained
today" — and it extracts **structured, queryable facts** into a relational database,
while Mem0 keeps a semantic memory for natural-language recall. Jeeves replies like a
curt, proactive valet: it notes what it stored, grounds a suggestion in what it remembers
about you, and asks an open question to keep the conversation going. It also keeps a
rolling sense of **what you're currently discussing**, so follow-ups stay on-thread.

## Stack
- **FastAPI** web UI (chat SPA, no build step)
- **Mem0** (v2) — semantic memory layer, NVIDIA OpenAI-compatible endpoint
- **Chroma** — local vector store (dev); **Supabase pgvector** in prod
- **SQLAlchemy Core** — one code path; **SQLite** for local/testing, **Supabase Postgres** for prod
- **NVIDIA Nemotron** — `nvidia/nemotron-3-super-120b-a12b` (chat) + `nvidia/nemotron-3-embed-1b` (embed)

## Setup (local)
```bash
# 1. Create the venv (Python 3.12)
uv venv --python 3.12.10 .venv
env -u PYTHONPATH .venv/bin/python -m pip install -e .

# 2. Add your NVIDIA key
cp .env.example .env
# edit .env: set NVIDIA_API_KEY=nvapi-...
# (model slugs in .env.example are already validated for this account)

# 3. Run
env -u PYTHONPATH .venv/bin/python -m jeeves.main
# open http://127.0.0.1:8000
```

> **Important:** always run with `env -u PYTHONPATH` so the agent's own Python venv doesn't
> shadow the project's. The server prints its URL on boot.

## What you can do
- **Tell Jeeves anything** in the chat box → it decides per message whether to *remember* it
  (extract structured facts incl. moods/feelings), *answer* a question from memory, or just chat.
- **See captured facts** in the right panel, filterable by text or category; verify, edit,
  delete one, or bulk-delete.
- **Time-zone aware** — set `JEEVES_TZ` so "today"/date-aware answers use *your* local day.
- **Conversation context** — a "Topic: …" chip shows what Jeeves thinks you're discussing;
  follow-ups like "what about tomorrow?" stay on-thread.
- **Query facts directly** via the API: `GET /api/facts?category=Goal&q=marathon`

## API
| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/health` | liveness |
| `POST` | `/api/chat` | `{text, session_id?}` → routes fact/question/feeling, returns reply + facts + topic |
| `GET`  | `/api/facts` | list/query facts (`category`, `entity`, `status`, `q`) |
| `DELETE` | `/api/facts/{id}` | delete one fact |
| `DELETE` | `/api/facts` | bulk delete by `category`/`q`/`status` |
| `POST` | `/api/facts/{id}/verify` | mark verified |
| `PATCH` | `/api/facts/{id}` | edit text/category/entity |
| `GET`  | `/api/sessions/{id}/context` | inspect rolling conversation topic + turns |
| `POST` | `/api/sessions/{id}/reset` | clear a session's context |
| `GET`  | `/api/summary` | total facts + categories |

## Deployment (Render + Supabase)
Local SQLite/Chroma are great for dev, but **Render's disk is ephemeral** — state there is
wiped on every redeploy. So in prod, all durable state lives in **Supabase**:
- **Relational facts** → Supabase Postgres, reached via `JEEVES_DB_URL` (SQLAlchemy switches
  automatically; same code as local SQLite).
- **Semantic memory** → Supabase **pgvector**, used by Mem0 when `SUPABASE_URL`/`SUPABASE_KEY`
  are set (falls back to local Chroma otherwise).

### One-time setup
1. Create a Supabase project. In the SQL editor, enable the vector extension:
   ```sql
   create extension if not exists vector;
   ```
2. Copy the **Project URL** and an API key (Settings → API) into Render's environment.
3. Push the repo to GitHub; in Render create a **Web Service** → connect the repo. Render reads
   `render.yaml` (start command `uvicorn jeeves.api:app --host 0.0.0.0 --port $PORT`).

### Render environment variables
| Var | Value |
|---|---|
| `JEEVES_DB_URL` | Supabase Postgres URL (pooler or direct). SQLAlchemy adds `+psycopg` automatically. |
| `SUPABASE_URL` | `https://YOUR-PROJECT.supabase.co` |
| `SUPABASE_KEY` | your Supabase key |
| `NVIDIA_API_KEY` | your NVIDIA key |
| `JEEVES_TZ` | e.g. `Asia/Kolkata` |
| `NVIDIA_BASE_URL` / `*_MODEL` | pre-set in `render.yaml` |

That's it — no local files needed in prod. Local dev keeps using `./jeeves.db` + Chroma.

## Roadmap
See `spec/roadmap.md`. Phases 1–4 (capture, grounded ask, memory hygiene, conversational
valet + context/delete/timezone) are done; deployment is the current focus.

## Notes on the design
Mem0 v2 returns only *cleaned memory strings*, not structured fields. So Jeeves performs its
**own single-LLM structured extraction** (category / entity / fact / confidence / period /
date / time) and mirrors that into the relational store — Mem0 handles fuzzy semantic recall.
This split is the heart of the "limits of factual memory" demo.

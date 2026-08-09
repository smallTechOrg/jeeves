# Valet — Architecture

## Overview
Valet is a Jeeves-style personal memory agent. You feed it ordinary statements about
yourself ("I did 3 workouts this week", "my goal is a sub-2h half marathon") and it
extracts **factual, structured memory** — not just blobs of text. You later ask it
natural-language questions and it answers from your accumulated facts.

The product is also a **demonstration of the limits of agentic factual memory**: every
extraction is recorded with what was said, what was inferred, and a confidence/status so
you can see where memory is solid vs. guessed.

## Stack
Assumed (no stack preference was stated — derived from requirements):

- **Language:** Python 3.12 (pinned via `.venv`, asdf 3.12.10)
- **Web framework:** FastAPI (async, simple, serves the SPA + JSON API)
- **Memory engine:** Mem0 `v2.0.17` — does the LLM fact-extraction + semantic retrieval
- **Vector store:** Chroma `v1.5.9` (local, LMDB/file-backed — effectively a local DB,
  satisfies "a little vector data", zero external services)
- **Relational store:** SQLite (the user's hard requirement: "factual data like a
  relational SQL database"). Valet **mirrors** extracted facts into a structured SQL
  schema the user can query directly.
- **Frontend:** Vanilla HTML + JS single-page chat (no build step, served by FastAPI) —
  keeps the scaffold lean and fully local.
- **LLM + embed:** NVIDIA API (OpenAI-compatible), validated:
  - chat: `nvidia/nemotron-3-super-120b-a12b`
  - embed: `nvidia/nemotron-3-embed-1b` (2048-dim, no extra params)

### Why this stack
- SQLite + Chroma are both file-backed → **nothing leaves the machine** except the
  (validated) NVIDIA API calls for extraction/answering. Matches the privacy posture.
- Mem0 owns the hard part (turning chatter into facts + semantic search). Valet adds the
  relational mirror + the UI + the "limits of memory" transparency layer.
- No Postgres/Docker needed → zero-setup local run, which the user picked.

## Memory model (the core idea)
**Verified API behaviour (Mem0 v2.0.17):** `add()` returns only a *cleaned memory string*
(e.g. "User completed 3 workouts this week and aims to run a sub-2-hour half marathon"),
not a structured fact. `get_all`/`search` return those memories with `memory`, `hash`,
`score`, `created_at`, `user_id`. Mem0 does **semantic recall only** — it abstracts away
the structured fields the user explicitly wants.

Therefore Valet does its **own structured extraction** in a single LLM call (reusing the
NVIDIA endpoint): it turns each message into one or more facts `{category, entity,
fact_text, confidence}`, writes them to SQLite (the relational mirror the user asked for),
and *also* pushes the message to Mem0 for semantic search. This is the honest design and
the core of the "limits of agentic factual memory" demonstration — the structured vs.
semantic split is made explicit.

Each extracted fact is a structured record:

- `fact_text` — the extracted statement
- `category` — auto-assigned type (Workout, Nutrition, Goal, Plan, Preference, Identity,
  Relationship, …) by the LLM during extraction
- `entity` — the subject the fact is about (e.g. "half marathon", "workout routine")
- `source_message_id` — which user utterance produced it
- `confidence` — model-supplied 0..1
- `status` — `extracted` (just pulled from a message) | `verified` (user confirmed) |
  `conflicted` (later info contradicts) | `superseded` (replaced by newer info)
- `created_at`, `updated_at`

Mem0 keeps its own vector store (for semantic recall). Valet's SQLite is the
**queryable relational mirror** — the artifact the user explicitly asked for. They are
kept in sync: every Mem0 `add` also writes the parsed facts to SQLite.

## Layout
```
valet/
  src/
    __init__.py
    config.py          # loads .env, exposes settings
    mem0_client.py     # builds Mem0 config from settings, single Memory instance
    memory.py          # add_message(), ask(), list_facts() — orchestrates Mem0 + SQLite
    db.py              # SQLite connection + schema (facts table) + CRUD
    schemas.py         # pydantic models for API
    api.py             # FastAPI app + routes
    main.py            # uvicorn entrypoint
  static/
    index.html         # chat SPA
    app.js
    style.css
  scripts/
    validate_provider.py
    probe_*.py         # dev probes (not shipped to user)
  spec/                # this design
  tests/
    test_memory.py     # unit + integration (real Mem0 round-trip, real SQLite)
  .env.example
  .gitignore
  README.md
  pyproject.toml
```

## Conventions
- `.venv` pinned; all runs via `env -u PYTHONPATH .venv/bin/python -m ...`
- `.env` never committed (gitignored); `.env.example` is the source of truth for vars
- SQLite DB path from `VALET_DB_PATH` (default `./valet.db`), gitignored
- Mem0's Chroma store lives in `./chroma_store/` (gitignored)
- One LLM call per artifact (never per-line) — pitfall §7
- API key value never read or printed in this repo's tooling

## API surface (Phase 1)
- `POST /api/message`  body: `{text}` → stores the message, extracts facts via Mem0,
  mirrors to SQLite, returns `{message_id, facts_extracted:[...], warnings}`
- `GET  /api/facts`    query params: `category`, `entity`, `status`, `q` (text filter)
  → returns structured facts (the relational query surface)
- `POST /api/ask`      body: `{question}` → retrieves relevant facts via Mem0 + composes
  a grounded answer with the LLM, returns `{answer, cited_facts:[...]}`
- `GET  /health`       → `{status:"ok"}`

## Phased plan — see roadmap.md

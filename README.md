# Jeeves

A Jeeves-style personal memory agent. You tell Jeeves ordinary things about yourself — "I did
3 workouts this week", "my goal is a sub-2h half marathon" — and it extracts **structured,
queryable facts** into a relational SQLite database, while Mem0 keeps a semantic memory for
natural-language recall. Jeeves is also a demonstration of the *limits of agentic factual
memory*: every extracted fact is shown with its category, the entity it's about, and a
confidence score, so you can see exactly what the agent decided was true.

## Stack
- **FastAPI** web UI (chat SPA, no build step)
- **Mem0** (v2) — semantic memory layer, NVIDIA OpenAI-compatible endpoint
- **Chroma** — local vector store (file-backed)
- **SQLite** — the relational mirror of extracted facts (the queryable store)
- **NVIDIA Nemotron** — `nvidia/nemotron-3-super-120b-a12b` (chat) + `nvidia/nemotron-3-embed-1b` (embed)

## Setup
```bash
# 1. Create the venv (Python 3.12 managed via asdf/uv)
uv venv --python 3.12.10 .venv
env -u PYTHONPATH .venv/bin/python -m pip install -e .

# 2. Add your NVIDIA key
cp .env.example .env
# edit .env: set NVIDIA_API_KEY=nvapi-...
# (the chat + embed model slugs in .env.example are already validated for this account)

# 3. Run
env -u PYTHONPATH .venv/bin/python -m jeeves.main
# open http://127.0.0.1:8000
```

> **Important:** always run with `env -u PYTHONPATH` so the agent's own Python venv doesn't
> shadow the project's. The server prints its URL on boot.

## What you can do (Phase 1)
- **Tell Jeeves anything** in the chat box → it extracts structured facts (category, entity,
  confidence) and stores them.
- **See captured facts** in the right panel, filterable by text or category.
- **Query facts directly** via the API: `GET /api/facts?category=Goal&q=marathon`

## API
| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/health` | liveness |
| `POST` | `/api/message` | `{text}` → extracts + stores facts, returns them |
| `GET`  | `/api/facts` | list/query facts (`category`, `entity`, `status`, `q`) |
| `GET`  | `/api/summary` | total facts + categories |

## Roadmap
See `spec/roadmap.md` — Phase 2 adds natural-language `ask` (grounded answers over your
memory); Phase 3 adds memory hygiene (verify / conflict / supersede); Phase 4 adds export
and history.

## Notes on the design
Mem0 v2 returns only *cleaned memory strings*, not structured fields. So Jeeves performs its
**own single-LLM structured extraction** (category / entity / fact / confidence) and mirrors
that into SQLite — Mem0 handles fuzzy semantic recall. This split is the heart of the
"limits of factual memory" demo.

# Jeeves — Roadmap (phased, user-testable)

Each phase ends with a **gate**: a real command I run and read the output of, then a
human testing step (you click around the live URL; you never run commands).

Branch convention: `feature/valet-<YYYYMMDD-HHMM>-v0.1`
PR base: `main`. The build never commits to `main` or merges PRs.

---

## Phase 1 — Capture & Query ✅ DONE
**Goal:** You talk to Jeeves in a web chat; it extracts structured facts; you can list/query
those facts. Proves the whole loop works end-to-end.

**Status:** Shipped. The loop (capture → structured facts → query → conversational reply →
delete → timezone-aware → conversation context) works locally on SQLite and is wired for
Supabase in prod (see Phase 5).

**Key files:** `jeeves/` (`api`, `ask`, `memory`, `db`, `extractor`, `config`, `mem0_client`,
`context`), `static/`.

---

## Phase 2 — Ask (grounded Q&A) ✅ DONE
**Goal:** `POST /api/ask` (now unified into `/api/chat`) retrieves relevant facts via Mem0 and
returns a grounded answer with cited fact IDs.

---

## Phase 3 — Memory hygiene (the limits demo) ✅ DONE
**Goal:** fact verification, conflict detection (`superseded`), editable structured view.
**Gate (passed):** add "5 workouts" → earlier "3 workouts" shows `superseded`; verify flips
status; derived attributes (qty/unit/period) populated.

---

## Phase 4 — Polish & persistence ✅ DONE
**Goal:** unified chat box (intent routing), conversational Jeeves (curt, proactive, no leaked
instructions), feeling capture, timezone-aware dates, delete + bulk-delete, rolling
**conversation context** (topic summary threaded across turns), and this deployment path.

---

## Phase 5 — Deployment (Render + Supabase) 🚧 IN PROGRESS
**Goal:** run Jeeves as a persistent web service where real info accumulates, with durable
state in Supabase (Postgres + pgvector). Local SQLite/Chroma remain for dev/testing.

**Slices:**
1. `db.py` → SQLAlchemy Core: one code path, `JEEVES_DB_URL` switches SQLite (local) ↔
   Postgres (prod). `create_all` on boot; public API unchanged. ✅ done
2. `mem0_client.py` → Supabase pgvector when `SUPABASE_URL`/`SUPABASE_KEY` set; local Chroma
   fallback. ✅ done
3. Render artifacts: `requirements.txt`, `render.yaml` (web service, `uvicorn jeeves.api:app`,
   env wiring), `.env.example` updated with prod vars. ✅ done
4. README + roadmap deployment docs. ✅ done
5. **Next (your action):** create the Supabase project, enable the `vector` extension, add the
   env vars in Render, and connect the GitHub repo. I can walk you through this or draft the
   exact steps once you've made the project.

**Why:** Render's filesystem is ephemeral — local SQLite/Chroma would be wiped each redeploy.
Supabase gives durable relational + vector storage so your memory persists.

**Gate:** deploy to Render → open the live URL → send "I signed up for a half marathon" →
reload the page → the fact is still there (proves Supabase persistence, not local disk).

---

## Open items
- Conversation history view (UI beyond the topic chip).
- Export facts (JSON/CSV).
- Settings page for model/slug overrides.
- Optionally: a Supabase SQL migration to pre-create the `facts` table + `vector` extension
  (the app auto-creates the table, but a migration documents the schema).

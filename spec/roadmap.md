# Valet — Roadmap (phased, user-testable)

Each phase ends with a **gate**: a real command I run and read the output of, then a
human testing step (you click around the live URL; you never run commands).

Branch convention: `feature/valet-<YYYYMMDD-HHMM>-v0.1`
PR base: `main`. The build never commits to `main` or merges PRs.

---

## Phase 1 — Capture & Query (the smallest testable win)
**Goal:** You talk to Valet in a web chat; it extracts structured facts into SQLite; you
can list/query those facts. Proves the whole loop works end-to-end.

**Independent slices:**
1. `db.py` — SQLite schema (`facts` table) + connection + CRUD. No external deps beyond
   stdlib `sqlite3`.
2. `config.py` + `mem0_client.py` — load `.env`, build the validated Mem0 config
   (NVIDIA chat+embed, Chroma local store). Single shared `Memory` instance.
3. `memory.py` — `add_message(text)`: call Mem0 `add`, parse returned facts, mirror to
   SQLite with category/entity/confidence/status. `list_facts(filters)`.
4. `api.py` + `main.py` — FastAPI: `POST /api/message`, `GET /api/facts`, `GET /health`.
   SPA served at `/`.
5. `static/` — chat UI: input box, message list, and a "facts captured" panel that shows
   extracted facts + their status after each message.

**Key files:** all under `src/`, `static/`.

**Gate command (I run, real keys):**
```
env -u PYTHONPATH .venv/bin/python -c "
from src.memory import add_message, list_facts
r = add_message('I did 3 workouts this week and my goal is a sub-2h half marathon.')
print('extracted:', len(r['facts']))
for f in r['facts']: print(' -', f['category'], '|', f['entity'], '|', f['fact_text'][:60])
print('query:', [f['category'] for f in list_facts(category='Goal')])
"
```
Must print >0 extracted facts with a populated `category` and `entity`, and the
category-filtered query must return the goal fact.

**How the user tests:** Open the live URL → type "I did 3 workouts this week, goal is a
sub-2h half marathon" → see the facts panel populate with categories → open
`/api/facts?category=Goal` (or the in-UI filter) and confirm it returns the goal.

**Deferred to later phases:** natural-language `ask` (Phase 2), verification/conflict
editing (Phase 3), categories management UI (Phase 3).

---

## Phase 2 — Ask (grounded Q&A)
**Goal:** `POST /api/ask` retrieves relevant facts via Mem0 and returns a grounded answer
with cited fact IDs. This is the "Jeeves answers about you" experience.

**Slices:** `memory.ask(question)` (retrieve + compose), `api.py` `/api/ask`,
UI "Ask Valet" box.

**Gate:** ask "what is my running goal and how many workouts did I log?" → answer cites the
facts from Phase 1.

---

## Phase 3 — Memory hygiene (the limits demo)
**Goal:** Fact verification (mark verified), conflict detection (later message contradicts
→ `conflicted`/`superseded`), and an editable structured view of all facts.

**Slices:** conflict detection in `add_message`, `POST /api/facts/<id>/verify`,
`PATCH /api/facts/<id>`, full facts browser UI.

**Gate:** add "I did 5 workouts this week" → earlier "3 workouts" shows `superseded`;
verify a fact → status flips to `verified`.

---

## Phase 4 — Polish & persistence
**Goal:** conversation history view, export (JSON/CSV of facts), README run docs,
settings page for model/slug overrides.

**Gate:** export returns a CSV of all facts; README run command boots the app.

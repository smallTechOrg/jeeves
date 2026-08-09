# Valet — Build Journal (harness notes)

Run started: 2026-08-09 ~21:49 PT

## Friction & lessons (harness-improving only)

- **NVIDIA function-gate 404.** The account's `nvidia/llama-3.1-nemotron-70b-instruct`
  returned `404 Function '...': Not found for account` even with a valid key (no 401). The
  `nvidia/nemotron-3-super-120b-a12b` chat model AND `nvidia/nemotron-3-embed-1b` embedding
  model both work. **Lesson:** when a provider returns 404 (not 401) on a model slug, it's an
  account-level asset gate, not a dead key — probe sibling models before concluding. The
  `70b` slug in common docs is gated; the `3-super-120b` is the callable one for this account.

- **Mem0 v2 API shape (documented, not a bug).** `add()` returns only a cleaned memory
  string (`{"results":[{"id","memory","event":"ADD"}]}`); it does NOT return structured
  category/entity/confidence. `get_all`/`search` take `filters={"user_id":...}` (NOT a
  `user_id=` kwarg — that raises ValueError). This forced the design to do its own
  structured extraction LLM call and treat Mem0 purely as the semantic layer. **Lesson:** for
  "structured facts" requirements, do not assume Mem0 emits structure — verify the return
  shape first (the skill's "verify, don't assume" paid off).

- **Mem0 reads key from env, not config dict.** `Memory.from_config` constructs its own
  `OpenAI(api_key=...)` where the key comes from `OPENAI_API_KEY`/`OPENAI_BASE_URL` env vars
  (not the config dict). The server process failed `stored_in_mem0` silently until we exported
  `OPENAI_API_KEY`/`OPENAI_BASE_URL` from `.env` at module load. **Lesson:** any OpenAI-backed
  library that re-instantiates a client will ignore config-dict keys — bridge them through env.

- **PYTHONPATH leak.** System `python3` is 3.9.6 and the hermes-agent venv (3.11) leaks via
  PYTHONPATH, breaking `pip`/imports. Fixed by `env -u PYTHONPATH` on every Python call and a
  pinned `.venv` (asdf 3.12.10). **Lesson:** always unshadow the agent venv on this box.

- **Chroma for "SQLite + a little vector".** No SQLite vector store exists in Mem0; Chroma
  (LMDB, file-backed) is the cleanest local vector option alongside the relational SQLite
  mirror. spaCy warnings are non-fatal (NLP normalization only).

- **`clarify` worked fine** this run; no fallback to plain text needed. Intake covered 5
  rounds + technical in one structured batch.

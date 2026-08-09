# Jeeves — Agentic Design (`spec/agent.md`)

This file is the **AI-native lens** on Jeeves. It records which agentic patterns are in
play, why, and where the product deliberately exposes the *limits* of agentic memory.

## Is AI a capability here? — YES (required by the user: "You have to use Mem0")
Jeeves is fundamentally an agentic-memory system. Mem0 is the memory substrate; the LLM
does fact-extraction and grounded answering. So this is not "no AI" — it is AI-centric.

## Patterns in use

### 1. Extract-and-mirror (core loop)
- **Pattern:** Every user utterance is sent to Mem0 `add()`. Mem0's LLM extracts discrete
  facts. Jeeves then parses the returned facts and **mirrors** them into a relational SQLite
  table. The vector store (Chroma) handles fuzzy recall; the SQL table handles precise,
  filterable, queryable fact retrieval.
- **Why:** The user explicitly wants *structured relational* memory, not just semantic
  blobs. The mirror is the deliverable; Mem0 is the extractor.

### 2. Grounded answering (retrieve-then-generate)
- **Pattern:** `POST /api/ask` retrieves top-k relevant facts from Mem0 (semantic search
  over the user's history), then the LLM composes an answer **constrained to those facts**
  and returns the cited fact IDs. No open-ended hallucination — answers are grounded in
  retrieved memory and traceable to specific facts.
- **Why:** Demonstrates faithful memory use; the "limits" story is about what was/wasn't
  captured, not about the model inventing answers.

### 3. Transparent memory state (the "limits" demo)
- **Pattern:** Every fact carries `confidence` and `status` (`extracted | verified |
  conflicted | superseded`). The UI shows extraction results after each message so the
  user sees *what the agent decided was a fact* — including low-confidence guesses and
  contradictions. This is the explicit research objective: "how can we convert normal
  conversations into factual memory over time?"
- **Why:** The product's secondary purpose is to surface where agentic memory succeeds
  and fails. Hiding the extraction is the opposite of the goal.

### 4. Category / entity auto-classification
- **Pattern:** During extraction, Jeeves asks the LLM (via Mem0's extraction prompt
  augmentation) to tag each fact with a `category` and `entity`. Categories are dynamic —
  the LLM invents sensible new ones rather than being forced into a fixed enum — matching
  the user's "dynamic, based on how I want it structured" intent.
- **Why:** Keeps the relational schema flexible while still queryable.

## Deliberate non-patterns (what Jeeves does NOT do)
- **No autonomous background agents.** Jeeves only acts on explicit user input. It does not
  proactively crawl or infer without a trigger.
- **No multi-agent debate / planner.** A single extraction + a single grounded answer is
  enough for Phase 1. Multi-step planning is deferred.
- **No tool-use / external writes** beyond its own stores in Phase 1.

## Honest limitations (the demo's value)
- Extraction quality is bounded by the LLM; the UI must make misses visible.
- Mem0's `category`/`entity` tagging is best-effort — the SQLite mirror may need manual
  correction later (a Phase 2 capability).
- Contradiction handling (`conflicted`/`superseded`) is heuristic in Phase 1 and improved
  in later phases.

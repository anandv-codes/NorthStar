# Chat & Retrieval Guardrails/Optimization Plan

Status: Phase 0 done. Phase 1 approved, in progress. Later phases are scoped/decided but not yet
started.
Scope note: this app is intentionally focused on **decision/status tracking**, not general
open-ended Q&A. Fact-checking / answer-groundedness / hallucination-scoring is explicitly
**out of scope** (see Decision Log). Guardrail work here is about routing correctness and
prompt-injection safety, not answer correctness.

## Phase 0 — Quick infra wins (done)

1. **Chroma singleton fix** ([vectorstore.py](../backend/app/infrastructure/vector/vectorstore.py))
   — `_collection()` was creating a brand-new `chromadb.PersistentClient` on every call (every
   query and every upsert re-opened the on-disk DB). Now cached at module level, built once.
2. **`rank_bm25` swap** ([sparse.py](../backend/app/domain/query_retrieval/strategies/sparse.py))
   — replaced the hand-rolled `IndexedDocument`/BM25 math (~90 lines) with `rank_bm25.BM25Okapi`,
   same `k1`/`b` defaults (1.5/0.75) so scoring behavior is unchanged. Added `rank_bm25` to
   [requirements.txt](../backend/requirements.txt).
3. **Cheaper cache fingerprint** ([utils.py](../backend/app/domain/query_retrieval/utils.py))
   — `fingerprint_notes()` previously SHA1-hashed every note's full combined text on every cache
   check (in addition to always fetching all notes). Now only hashes `note_id` + `updated_at` per
   note — same cache-invalidation guarantee (assumes `updated_at` changes whenever content
   changes), far less CPU per check. Note: this still requires a full fetch of the user's notes
   every call, since `NoteRepository` has no lighter-weight "has anything changed" query — see
   below for the fuller fix if note volume grows enough to matter.
4. **Logging module swap** — replaced ad-hoc `print()` calls with the standard `logging` module
   across [supabase_client.py](../backend/app/infrastructure/db/supabase_client.py),
   [prompt_logger.py](../backend/app/infrastructure/llm/prompt_logger.py),
   [gemini_client.py](../backend/app/infrastructure/llm/gemini_client.py),
   [sqs_client.py](../backend/app/infrastructure/queue/sqs_client.py),
   [handlers/notes.py](../backend/app/handlers/notes.py), and
   [api/routes/notes.py](../backend/app/api/routes/notes.py). `main.py` already had
   `logging.basicConfig(...)` configured to stdout, so these now flow through the same
   configuration instead of unconditionally printing.

### Why the fingerprint/cache exists, and how to go further later

The BM25 index (term frequencies, document stats) is expensive to rebuild from scratch on every
retrieval call, so `_get_index_for_user()` caches the built index per user and only rebuilds it
when the underlying notes have actually changed. The fingerprint is the mechanism that answers
"has anything changed since I last built this index?" — cheaply enough that checking it is
faster than just rebuilding unconditionally.

The current version (Phase 0) is a fetch-then-fingerprint-then-maybe-reuse strategy: it still
fetches the full note set every call to compute that fingerprint, just no longer hashes full note
text while doing so. The fuller fix, not implemented yet to avoid growing the `NoteRepository`
port surface in this pass, would be a **cache-key-only query**: add a lightweight repository
method (e.g. `count(*)` + `max(updated_at)` for the user) that answers "has anything changed"
without transferring any note content at all — only worth doing once note volumes are large
enough that the current full fetch is measurably slow (low priority at today's personal-project
scale).

## Phase 1 — Intent classifier: hybrid deterministic + embedding similarity

**Goal**: keep the existing keyword rules for high-stakes `tool` (write) intent, and replace/augment
the `retrieval` vs `direct` split with embedding-similarity matching against curated example
utterances, since keyword-only matching misses paraphrased read questions
(e.g. "any news on the deploy" matches no current hint word).

**Design decisions**
- Aggregation method: **kNN over individual example embeddings**, not class centroids — a centroid
  of diverse phrasings per class would wash out multi-modal phrasing patterns. Use top-`k` match
  (majority vote, start with `k=3`).
- Similarity metric: **cosine similarity**, implemented as a plain dot product over
  **unit-normalized** vectors (`model.encode(..., normalize_embeddings=True)` for the local
  `sentence-transformers` path in
  [embeddings.py](../backend/app/infrastructure/vector/embeddings.py)). Raw dot product without
  normalization is unreliable since embedding magnitude varies by input.
- Decision rule: **absolute similarity floor + margin over the runner-up class**, not a single
  threshold alone — avoids flip-flopping at the retrieval/direct boundary (mirrors the
  `runner_up_score` separation idea from the old grounding logic, reused here for intent instead).
- Combination with deterministic layer: **run both every time** (local embedding model is
  effectively free — in-process MiniLM, no network call), not a cascade:
  1. `KeywordIntentRule` (existing, [rules.py](../backend/app/domain/routing/rules.py)) stays
     authoritative for `tool` intent — action verbs (create/update/delete/mark/set) must remain
     deterministic; false positives/negatives on writes are higher stakes than on reads.
  2. Embedding kNN decides/reinforces `retrieval` vs `direct` when keyword retrieval hints are
     silent or weak.
  3. `mixed` stays as today: both signals present.
- Embedding provider: use `EMBEDDING_PROVIDER=local` for this classifier specifically to avoid
  adding an API round trip to every chat message before retrieval-need is even known.

**Implementation steps**
1. Add a curated seed example set per intent class (15–30 diverse phrasings to start), stored as
   plain data (not keyword logic) — e.g. `backend/app/domain/routing/intent_examples.py` or a
   JSON/YAML file, so it's easy to extend without touching classifier code.
2. Add an embedding-kNN scorer (new module, e.g.
   `backend/app/domain/routing/embedding_intent.py`): embeds the seed set once (cache in memory),
   embeds the incoming message, computes cosine similarity via normalized dot product, returns
   top-k label + score + margin.
3. Merge into `RuleBasedIntentClassifier._merge_signals` (or a new hybrid classifier class) so
   `tool` keyword signal always wins when present; otherwise embedding score decides
   `retrieval`/`direct`.
4. Add `evals/datasets/northstar_intent_v1.jsonl` — a **separate** labeled validation set (not the
   seed examples, to avoid overfitting) covering paraphrased retrieval questions, direct/small-talk
   messages, and tool-action phrasing.
5. Add `evals/scripts/run_intent_eval.py` — sweeps `k`, similarity floor, and margin against the
   validation set; reports accuracy/precision/recall per class, weighting `tool`-intent precision
   highest (highest-stakes class). Pick the config that maximizes accuracy without hurting `tool`
   precision.
6. Re-run the eval script whenever seed examples are added/changed.

**Files touched**
- `backend/app/domain/routing/intent_examples.py` (new) — seed utterances per class
- `backend/app/domain/routing/embedding_intent.py` (new) — kNN cosine-similarity scorer
- `backend/app/domain/routing/classifier.py` — wire embedding scorer into merge logic
- `backend/app/infrastructure/vector/embeddings.py` — ensure `normalize_embeddings=True` used for
  this path (local sentence-transformers `encode()` call)
- `evals/datasets/northstar_intent_v1.jsonl`, `evals/scripts/run_intent_eval.py` (new)

**Verification**
1. Run `run_intent_eval.py`; confirm accuracy improves over current keyword-only baseline on the
   validation set, especially for paraphrased retrieval questions.
2. `get_errors` on all modified files.
3. Manual `/message` tests: paraphrased retrieval question (e.g. "any news on the deploy"), an
   unambiguous write command ("mark task X as done"), and a general/direct message ("what's a
   good name for a project") — confirm each routes as expected.

---

## Phase 2 — Prompt injection guardrails (input / retrieval / output)

Decided approach: lightweight, heuristic/pattern-based only — **no fact-checking, no AlignScore,
no groundedness scoring** (explicitly out of scope, see Decision Log). Rely on Gemini's own
`safety_settings` for baseline toxicity/safety rather than hosting a separate classifier model.

- **Input rail**: jailbreak/prompt-injection heuristic check on the raw user message before
  routing starts ([chat/services.py](../backend/app/domain/chat/services.py)
  `handle_chat_message`).
- **Retrieval rail**: injection-pattern scan on retrieved note/chat/summary text right after
  `fuse_candidates`/reranking in
  [query_retrieval/services.py](../backend/app/domain/query_retrieval/services.py), before it
  reaches the prompt — this is the actual unique attack surface for this app (own notes/pasted
  content treated as trusted context).
- **Output rail**: check the generated answer doesn't leak/comply with injected instructions
  before returning it.
- Explicitly configure `safety_settings` on `ChatGoogleGenerativeAI` in
  [gemini_client.py](../backend/app/infrastructure/llm/gemini_client.py) rather than relying on
  silent defaults.
- Dialog rails: **excluded** — not a good fit for this app's open-ended chat.

*(Not yet broken into detailed steps — do this once Phase 1 lands.)*

## Phase 3 — Tool-execution gap for status/task mutation via chat

Confirmed gap: `needs_tools=True` messages (e.g. "mark task X as done") currently produce
`tool_context="No tool results."` with **no actual executor** wired to
`update_task_item`/`update_risk_item`/etc. This risks the LLM hallucinating a false success
confirmation — the highest-stakes failure mode for a status-tracking app.

Two options, not yet decided:
- **(a)** Implement a real tool executor that calls the existing
  [domain/memory/services.py](../backend/app/domain/memory/services.py) update functions, and only
  let the LLM report an outcome that actually happened.
- **(b)** Smaller stopgap: when `needs_tools=True` and nothing executed, force a fixed response
  ("I can't update tasks from chat yet") instead of letting the LLM free-generate over an empty
  tool result.

## Phase 4 — Grounding / allow_answer (decided: minimal change)

- Keep the existing hard-coded fallback message when no relevant context is found for
  retrieval-intent queries (no soft prompt-based abstention layer, no relevance-threshold rewrite).
- Keep the existing status-claim detection in
  [chat/guardrails.py](../backend/app/domain/chat/guardrails.py) largely as-is — it already fits
  this app's narrowed decision/status-tracking scope; no need to generalize to open-ended Q&A.
- No fact-checking, no AlignScore, no embedding-similarity groundedness/hallucination scoring.

---

## Decision Log (running)
- App scope is intentionally narrow: decision/status tracking, not general open-ended Q&A.
- No fact-checking or answer-groundedness scoring anywhere in the pipeline (ruled out AlignScore,
  ruled out embedding-similarity groundedness, ruled out LLM self-check-facts).
- No dialog rails (NeMo or otherwise).
- Toxicity/safety: rely on Gemini's built-in `safety_settings`, not a separate local classifier.
- Intent classifier: hybrid keyword (authoritative for `tool`) + embedding kNN (for
  `retrieval`/`direct`), using the local `sentence-transformers` embedding provider, cosine
  similarity via normalized dot product, kNN not centroid, margin-based decision rule.
- Eval harness convention: reuse `evals/datasets/*.jsonl` + `evals/scripts/run_*_eval.py` pattern
  for calibrating every new threshold (intent margin/k, injection detection, etc.).

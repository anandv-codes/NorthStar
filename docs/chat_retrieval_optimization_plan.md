# Chat & Retrieval Guardrails/Optimization Plan

Status (2026-10-30): Phase 0 done. Phase 1 code done; hybrid threshold eval pending. Phase 2 not
started. Phase 3 P2 tool slice done. Phase 4 done. Chat MVP gaps are listed below.

**Scope revision (2026-10-30):** chat is scoped to the user's notes plus approved typed views.
Small talk is allowed, but chat must not answer from general knowledge. Approved typed reads are
task/goal open loops and the recall due queue; question/concept reads and writes are deferred and
deprecated for the MVP. Intent labels are `conversation`, `note_content`, `note_status`, `action`,
and the rule-only `tool_read`. Note labels route to `note_search`; `note_status` uses
claim/conflict grounding, while `note_content` uses relevance grounding. Low-confidence input
becomes an `ambiguous` clarification rather than a general answer. Fact-checking / hallucination
scoring remains out of scope.

## Chat MVP status (2026-10-30)

### Implemented

- Notes-only grounded answers with note source refs and conversation/thread summaries.
- Hybrid intent routing: deterministic rules plus local MiniLM kNN for conversational and note
  intents; writes stay rule-gated.
- Deterministic `tool_read` routing for `get_open_loops` and `get_due_cards`; both execute inline
  and never create pending actions.
- Confirmation-gated writes: `create_task`, `complete_task`, `start_task`, `reopen_task`,
  `archive_task`, and `update_commitment_progress`.
- Task transition validation, `completed_at` preservation/clearing, and no-op tool failures.
- Due-card reads return questions only, never answers.
- Chat is the secondary "Ask" surface; dashboard is the default app route.

### Remaining before chat MVP is done

1. **Dependency-complete verification.** Run the targeted chat/tool/service tests and frontend
   `tsc --noEmit` with the full backend dependency set installed. Record results in CI or the PR.
2. **Hybrid intent evaluation.** Run the MiniLM hybrid sweep and record the chosen threshold/margin;
   the current recorded baseline is rules-only (`0.792` accuracy). Do not add `tool_read` to
   semantic training labels.
3. **Pending-action correctness.** Make confirmation resolution conditional/idempotent so two rapid
   "yes" messages cannot execute twice. Mark expired rows as `expired` and persist an execution
   result/audit timestamp. See `docs/interview_questions.md` Q21.
4. **Prompt-injection and safety rails (Phase 2).** Add input/retrieval/output checks and explicit
   Gemini `safety_settings`, or explicitly accept the risk for a private beta.
5. **Manual end-to-end pass.** Verify grounded note answers, source links, open-loops and due-card
   reads, every write transition, deny/expiry behavior, and absence of answer leakage against a
   seeded Supabase user and live Gemini.

### Deferred / not in the chat MVP

- Question/concept typed reads and writes. Their tool definitions remain dormant and disabled.
- External tools/MCP (GitHub, calendar) and general web access.
- Streaming responses, attachments, voice input, and multi-agent orchestration.
- Calendar integration: it belongs to the separate Act-stage MVP slice, not chat.

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

**Goal**: keep deterministic keyword rules for high-stakes write actions, and use
embedding-similarity matching for `conversation`, `note_content`, and `note_status` so
paraphrased note questions route correctly (e.g. "any news on the deploy" matches no hint word).

**Design decisions**
- Aggregation method: **kNN over individual example embeddings**, not class centroids. For each
  label, average the top two example similarities; choose the highest label score. This keeps
  diverse phrasings from being washed out while reducing sensitivity to one noisy example.
- Similarity metric: **cosine similarity**, implemented as a dot product over unit-normalized
  vectors so embedding magnitude does not affect ranking.
- Decision rule: **absolute similarity floor + margin over the runner-up label**, not a single
  threshold alone. Below either bound the result is `ambiguous` unless a deterministic rule wins.
- Combination with deterministic layer: run both every time (local MiniLM, no API call):
  1. Action rules stay authoritative for writes. A semantic `action` match never authorizes a
     write.
  2. Status rules take precedence over content when the user is asking about completion/open/
     blocked state, except for explicit summary requests ("summarize...", "recap...") which use
     relevance grounding.
  3. Exact high-precision conversation phrases (greetings/thanks/capability questions) route to
     `conversation` without retrieval.
- Embedding provider: local `sentence-transformers` MiniLM only, to avoid an API round trip before
  retrieval need is known. The model and index load lazily.

**Implementation status**
1. Done: curated seed examples in `intent_examples.py` (87 utterances across four labels).
2. Done: `embedding_intent.py` implements cached in-process MiniLM kNN over normalized vectors,
   with a similarity floor and runner-up margin. The model loads lazily; tests inject an embedder.
3. Done: `HybridIntentClassifier` runs deterministic rules and semantic matching every time.
   Action rules remain authoritative. Type, status, and summary-request precedence are covered by
   `backend/tests/test_intent_routing.py`.
4. Done: conversation and ambiguous routes skip retrieval and grounding; note routes select
   `relevance` or `claim` grounding. Grounding snapshots support `not_required`.
5. Done: `evals/datasets/northstar_intent_v1.jsonl` (48 cases, separate from seed data) and
   `evals/scripts/run_intent_eval.py` (per-label metrics, confusion, rules-only baseline).
   Rules-only baseline is `0.792` accuracy. Pending: run the hybrid threshold sweep with the local
   MiniLM model available. The current environment lacks `sentence-transformers`.
6. Done: typed read routing is limited to `get_open_loops` and `get_due_cards`; question/concept
   tools remain disabled. Pending: prompt-injection rails remain Phase 2.

**Files touched**
- `backend/app/domain/routing/intent_examples.py` (new) — seed utterances per label
- `backend/app/domain/routing/embedding_intent.py` (new) — kNN cosine-similarity scorer
- `backend/app/domain/routing/classifier.py` — hybrid merge logic
- `backend/app/domain/routing/rules.py`, `constants.py` — action/status/content/conversation rules
- `backend/app/domain/routing/contracts.py` — intent kinds and grounding modes
- `backend/app/domain/chat/orchestrator.py`, `guardrails.py`, `routing_contracts.py` — route and
  grounding wiring
- `backend/tests/test_intent_routing.py` (new) — classifier, routing, and grounding tests
- Done: `evals/datasets/northstar_intent_v1.jsonl`, `evals/scripts/run_intent_eval.py`
- `backend/app/domain/chat/read_tools.py` (new) — deterministic typed reads
- `backend/tests/test_chat_tools.py`, `test_chat_read_tools.py`,
  `test_chat_service_tool_routes.py`, `test_task_status_transitions.py`

**Verification**
1. Rules-only eval is recorded at `0.792` accuracy. Pending: run the hybrid sweep and confirm it
   improves paraphrased retrieval questions without regressing action precision.
2. Run `python -m compileall -q backend/app backend/tests` and the targeted pytest files.
3. Manual `/message` tests: paraphrased retrieval question (e.g. "any news on the deploy"), an
   unambiguous write command ("mark task X as done"), an open-loops read, a due-cards read, and a
   general/direct message ("what's a good name for a project") — confirm each routes as expected.

---

## Phase 2 — Prompt injection guardrails (input / retrieval / output) — not started

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

## Phase 3 — Tool execution via chat — P2 slice done

Implemented in the current P2 slice:

- Confirmation-gated task writes: `create_task`, `complete_task`, `start_task`, `reopen_task`,
  `archive_task`, and `update_commitment_progress`.
- Task status transitions are validated in the repository; reopening clears `completed_at`.
- Read-only `get_open_loops` (open/in-progress tasks + active goals) and `get_due_cards`
  (question-only view, no answers) execute inline without pending actions.
- `tool_read` is deterministic/rule-only so read requests do not incur an extra tool-selection
  LLM call or authorize writes.
- Question/concept chat tools remain defined but disabled.

Remaining:
- Question/concept typed reads and writes are deprecated for the MVP and remain disabled.
- External tools/MCP remain deferred; GitHub read-only is the first candidate, calendar last.

## Phase 4 — Grounding / allow_answer — done

- `note_content` uses relevance grounding: at least one retrieved note is required; thread summary
  or recent chat alone cannot satisfy a note lookup. Relevant note evidence is returned with note
  source refs.
- `note_status` keeps the existing status-claim detection and conflict/weak-evidence guards.
- Conversation/action/tool_read/ambiguous routes use `not_required` grounding and skip retrieval.
- Assistant messages render linked note source refs from routing metadata.
- No fact-checking, no AlignScore, no embedding-similarity groundedness/hallucination scoring.

---

## Decision Log (running)
- App scope is intentionally narrow: decision/status tracking, not general open-ended Q&A.
- No fact-checking or answer-groundedness scoring anywhere in the pipeline (ruled out AlignScore,
  ruled out embedding-similarity groundedness, ruled out LLM self-check-facts).
- No dialog rails (NeMo or otherwise).
- Toxicity/safety: rely on Gemini's built-in `safety_settings`, not a separate local classifier.
- Intent classifier: hybrid keyword (authoritative for `action`) + in-repo embedding kNN (for
  `conversation`/`note_content`/`note_status`), using the local `sentence-transformers` embedding
  provider, cosine similarity via normalized dot product, kNN not centroid, margin-based decision
  rule. No `semantic-router` dependency in P0.
- Chat scope: notes plus approved typed views. General knowledge is excluded; small talk is
  allowed. Typed reads are limited to task/goal open loops and due cards; question/concept tools are
  deprecated for the MVP.
- Chat MVP treats external tools/MCP, streaming, attachments, voice, and question/concept writes as
  out of scope. Calendar is a separate Act-stage slice.
- Eval harness convention: reuse `evals/datasets/*.jsonl` + `evals/scripts/run_*_eval.py` pattern
  for calibrating every new threshold (intent margin/k, injection detection, etc.).

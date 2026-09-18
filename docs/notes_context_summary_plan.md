# Notes + Retrieval Contextual Summary — Plan

Status: **Phase R ✅ COMPLETE | Phase A 🚀 IN-PROGRESS | Phase B→D pending**

## Implementation Progress

### ✅ Phase R — Consolidate hybrid retrieval (COMPLETE)
- [x] Created `HybridRetriever` class in `backend/app/domain/query_retrieval/hybrid_retriever.py`
- [x] Created `NoteContextRetriever` wrapper for note-specific concerns
- [x] Created singleton factories: `get_hybrid_retriever()`, `get_note_context_retriever()`
- [x] Refactored `retrieve_query_context()` in `services.py` to delegate to `HybridRetriever`
  (signature unchanged; chat behavior preserved)
- [x] Removed `ENABLE_RAG` conditional checks; RAG always-on in `note_processor.py`
- [x] Removed redundant `query_related_notes` direct call from `note_processor.py`
- [x] Verified: all modified files pass `get_errors` validation

### 🚀 Phase A — Entity-linked context lookup (IN-PROGRESS)
- [x] Created `backend/sql/phase3_phase_a_entity_queries.sql` with 3 deterministic join patterns
- [x] Added `MemoryRepository` protocol methods:
  - `query_entity_names_for_user(user_id) -> list[str]`
  - `query_source_notes_by_entity_names(user_id, entity_names, exclude_note_id) -> list[dict]`
  - `query_memory_items_by_entity_names(user_id, entity_names, exclude_note_id) -> list[dict]`
- [x] Implemented the three methods in `SupabaseMemoryRepository`
- [x] Created `entity_context_retriever.py` with:
  - Single-source `_find_matched_entity_names()` for case-insensitive substring matching
  - `EntityContextRetriever` class (no embeddings, deterministic join only)
  - Singleton factory: `get_entity_context_retriever()`
- [x] Created `note_context_provider.py` to merge hybrid + entity-linked results
- [x] Updated `note_processor.py` to call `fetch_note_context()` (combines both retrievers)
- [ ] Prompt tuning in `gemini_client.py` (Phase B)
- [ ] Persistence: add `notes.context_note_ids` column (Phase C)
- [ ] Dashboard redesign (Phase C)

### ⏳ Phase B — Prompt tuning (PENDING)
- [ ] Update extraction prompt to synthesize status (not restate) when related context exists
- [ ] Add grouped structured-items context block (tasks/questions/risks/concepts by status)
- [ ] Instruction: "never answer/resolve open questions — awareness only"

### ⏳ Phase C — Persistence + dashboard (PENDING)
- [ ] Add `notes.context_note_ids jsonb` migration
- [ ] Update `NoteStatusResponse` schemas
- [ ] Frontend: redesign card to show raw_text primary, summary secondary
- [ ] Add "Sourced from: [ids]" trail when `context_note_ids` non-empty

### ⏳ Phase D — Pause chat work (PENDING)
- [ ] Update `chat_retrieval_optimization_plan.md` header status

## Product direction & scope

**MVP Definition**: note-taking + retrieval/contextual summaries is the focused feature set.
Chat work is paused (see [chat_retrieval_optimization_plan.md](chat_retrieval_optimization_plan.md),
which keeps its own decision log for whenever chat resumes — not superseded by this doc).

## Goal

When a new note is processed, its `enriched_summary` should read as an updated status that
incorporates what's already known from related past notes/items about the same topic — not just
restate the new note in isolation. Example:

- Note 1 (new issue): *"Facing an issue with lambda service, root cause might be related to
  configuration."*
- Note 2 (root cause found, references note 1's issue): *"The lambda error raised earlier for
  4575 has been triaged — related to authorization tokens sent by onshore. Need to discuss via a
  scheduled call."*
- Note 3 (resolution, synthesizes 1+2): *"The lambda issue for work item 4575, related to
  incorrect credentials, has been fixed. A call was set up with onshore based on the triaged root
  cause, and the fix has been implemented."*

Summaries are generated **once, at processing time, and never retroactively rewritten** — note
1's summary stays as originally written even after notes 2/3 arrive.

## What already exists (verified in code, not being rebuilt)

- `notes.enriched_summary` already exists and is already displayed today (flat list) in
  [RecentMemorySection.tsx](../frontend/src/features/dashboard/components/RecentMemorySection.tsx).
- [note_processor.py](../backend/app/workers/note_processor.py) already does a **semantic**
  related-notes lookup (top-3 via Chroma) and passes it into the extraction prompt in
  [gemini_client.py](../backend/app/infrastructure/llm/gemini_client.py), which already
  instructs: *"use them only as context and do not invent unsupported facts."* Currently gated
  behind `ENABLE_RAG` (default `false`).
- `entities` + `memory_item_entities` tables
  ([phase3_work_memory.sql](../backend/sql/phase3_work_memory.sql)) already link notes and typed
  memory items (tasks/facts/questions/decisions/risks/concepts) to a shared named entity (e.g. an
  entity literally named "4575"). Not currently used for context-building.
- Deterministic task resolution
  (`apply_deterministic_task_resolution` in
  [domain/memory/services.py](../backend/app/domain/memory/services.py#L246)) already exists for
  **tasks only** — no equivalent exists for questions today (relevant to the questions decision
  below).

## Decisions

1. **Context sources — hybrid, not semantic-only.** Combine:
   - Semantic + lexical: **the same full hybrid pipeline chat uses** (BM25 + dense + RRF fusion +
     optional rerank, via the consolidated `HybridRetriever` from Phase R) — not the old
     standalone dense-only top-3 Chroma lookup, which is removed.
   - Entity-linked notes: deterministic substring-match of known entity names against the new
     note's raw text, then reverse-lookup of other notes sharing that entity via
     `memory_item_entities`.
   - **Entity-linked structured items (new, this session's addition)**: for the same matched
     entities, also pull the actual linked `tasks`/`facts`/`questions`/`decisions`/`risks`/
     `concepts` records — these are already-distilled, higher-signal context than re-parsing raw
     note text, and align directly with this app's decision/status-tracking scope.
2. **Structured items grouped by status**, not a flat list:
   - `tasks: {open: [...], closed: [...]}`
   - `questions: {open: [...], answered: [...]}`
   - `risks: {open: [...], resolved: [...]}`
   - `concepts: {open: [...], resolved: [...]}` (exact status values per `ConceptStatus` enum)
   - `decisions: [...]` and `facts: [...]` — flat, no status column exists for these.
   - Include **all statuses** (not just open) so the LLM sees full history, not just current
     open items.
3. **Open questions: surface, never answer.** Pass open questions into context for awareness, but
   explicitly instruct the model not to resolve/answer them — consistent with the earlier
   decision to keep chat's grounding guardrails free of fact-checking/hallucination risk. A
   question is only marked answered if the *current* note's own text explicitly states the
   resolution; the summary-generation call is not the mechanism for resolving old questions.
   Actual resolution stays a manual `PATCH` (or a future deterministic-resolution path modeled on
   `apply_deterministic_task_resolution`, out of scope here).
4. **Chat plan paused, not abandoned** — no changes to guardrails/routing work in this pass.
5. **Dashboard**: improve the existing per-note list only ([RecentMemorySection.tsx](../frontend/src/features/dashboard/components/RecentMemorySection.tsx)), no separate entity/topic rollup view.
   - Raw note text (`raw_text`) shown as the **primary** element.
   - `enriched_summary` shown **secondary**, below it.
   - A small **"Sourced from"** trail listing `context_note_ids` when non-empty.
   - Source-notes trail: **simple version** — show linked note IDs (resolve to a snippet only if
     that note happens to already be in the loaded recent-notes batch); no extra fetch-by-ids
     endpoint in this pass. Fuller resolution flagged as an easy fast-follow.

## Implementation phases

### Phase R — Consolidate hybrid retrieval, remove weak Mechanism B (HIGHEST PRIORITY, blocks Phase A)

Background (from prior discussion): there are currently 2 similarity-based retrieval call sites —
chat's full hybrid pipeline (`retrieve_query_context` in
[query_retrieval/services.py](../backend/app/domain/query_retrieval/services.py): BM25 + dense +
guarded LLM rewrite + RRF fusion + optional rerank) and note-ingestion's standalone dense-only
top-3 lookup (`query_related_notes` in
[vectorstore.py](../backend/app/infrastructure/vector/vectorstore.py), called directly from
[note_processor.py](../backend/app/workers/note_processor.py)). The second one is a strict subset
of the first's capability and exists only because it predates the hybrid pipeline. Consolidate
them so both callers share one implementation. Entity-linked lookup (Mechanism C) is a separate,
deterministic relational join — not similarity search — and is untouched by this refactor.

Applying SOLID/DI, reusing existing ports/classes, no new abstraction layers beyond what's needed:

1. **New `HybridRetriever` class** (new file, e.g.
   `backend/app/domain/query_retrieval/hybrid_retriever.py` — keeps `services.py` from growing
   further, single responsibility). Constructor-injected with the same ports already defined in
   `domain/ports.py`: `embedding_provider: EmbeddingProvider`, `vector_store: VectorStore`,
   `sparse_retriever: BaseRetrieval` (defaults to the existing `SparseBM25Retriever()`),
   `reranker: BaseReranker | None` (defaults per the existing `QUERY_RETRIEVAL_RERANKER` env
   logic). One method: `fetch(user_id, query_text, limit, alternate_query_text=None) -> list[dict]`
   — extracted **behavior-preserving** from today's `retrieve_query_context`: dense(original) +
   sparse + dense(alternate, if given) → `fuse_candidates` (RRF) → optional rerank. This is the
   single shared core (SRP: fusion/ranking only, no rewrite logic, no note-specific logic).
2. **`get_hybrid_retriever() -> HybridRetriever`** singleton factory in the same module,
   following the existing `get_x()` singleton pattern already used throughout infra (e.g.
   `get_vector_store()`, `get_chat_model()`, `get_embedding_provider()`) — this is the DIP seam:
   callers depend on the factory/abstraction, not a concrete construction inline.
3. **Refactor `retrieve_query_context(user_id, query, limit, ...)`** — chat's existing public
   entry point, **signature unchanged**, no behavior change for chat callers. Keeps the
   chat-only concerns (query-quality scoring, rewrite decision, risk detection via
   `detect_rewrite_risks`) exactly as today, then delegates the actual fetch to
   `get_hybrid_retriever().fetch(user_id, query, limit, alternate_query_text=expanded_query)`
   when a rewrite is accepted, or without `alternate_query_text` otherwise.
4. **New `NoteContextRetriever` class** (small, same file as `HybridRetriever` or a sibling
   module) — constructor-injected with a `HybridRetriever` (defaults to `get_hybrid_retriever()`).
   One method: `fetch_related_context(user_id, raw_text, limit, exclude_note_id=None) ->
   list[dict]`, calling `hybrid_retriever.fetch(user_id, raw_text, limit)` — **no rewrite
   dependency at all** (ISP/SRP: note-ingestion has no reason to know query-rewrite exists).
5. **Update `note_processor.py`**: replace the direct `query_related_notes` call (Mechanism B)
   with `get_note_context_retriever().fetch_related_context(...)` (mirrors the existing
   factory-injection pattern used elsewhere in the codebase, so it stays swappable/fakeable in
   tests). **Remove Mechanism B's call site** — `vectorstore.py`'s `query_related_notes`/
   `ChromaVectorStore` themselves are not deleted (still the underlying dense-search primitive
   used inside `HybridRetriever`), only the direct bypassing call from `note_processor.py` goes
   away.
6. Entity-linked lookup (Mechanism C, Phase A below) is called **alongside**
   `NoteContextRetriever`, not merged into it — it stays a separate class/function since it's a
   fundamentally different mechanism (deterministic join, not ranked similarity search).

SOLID mapping for reference:
- **SRP**: `HybridRetriever` = fusion/ranking only; rewrite decision stays chat-only inside
  `retrieve_query_context`; entity linking stays its own class.
- **OCP**: swapping the reranker or sparse strategy = constructor injection only, no edits to
  either caller.
- **LSP**: both callers (`retrieve_query_context` and `NoteContextRetriever`) consume the exact
  same `HybridRetriever.fetch()` contract.
- **ISP**: reuse the existing small `EmbeddingProvider`/`VectorStore`/`BaseRetrieval`/
  `BaseReranker` ports as-is — no new bloated interfaces.
- **DIP**: `note_processor.py` and the chat orchestrator depend on `HybridRetriever`/
  `NoteContextRetriever` via factory functions, never on concrete construction inline.

### Phase A — Entity-linked context lookup (backend) — depends on Phase R
1. Add `MemoryRepository` port methods (mirroring the existing `query_entities_by_source_note`
   pattern, reversed direction):
   - `query_entity_names_for_user(user_id)` — cheap select over the small `entities` table.
   - `query_source_notes_by_entity_names(user_id, entity_names, exclude_note_id)`.
   - `query_memory_items_by_entity_names(user_id, entity_names, exclude_note_id)` — returns the
     linked tasks/facts/questions/decisions/risks/concepts grouped by type (new, for the
     structured-items addition).
2. In `note_processor.py`, before `call_gemini_api`: deterministic pre-pass — fetch the user's
   known entity names, substring-match (case-insensitive) against the new note's raw text, then
   reverse-lookup (a) other notes and (b) structured items linked to matched entities. Merge (a)
   with the `NoteContextRetriever`-sourced hybrid results from Phase R (dedupe by `note_id`).
3. Set `ENABLE_RAG=true` as the default for this MVP (currently defaults `false`).

### Phase B — Prompt tuning (depends on Phase A)
4. Update the extraction prompt in `gemini_client.py`:
   - Accept the new grouped structured-items context block (tasks/questions/risks/concepts by
     status, decisions/facts flat).
   - Instruct: synthesize a status update when related context covers the same
     issue/entity (root cause → discussion → resolution), rather than restating the new note in
     isolation.
   - Instruct: never answer/resolve open questions — awareness only.

### Phase C — Persistence + dashboard (depends on Phase A/B for data quality; schema/UI work is independent)
5. Add `notes.context_note_ids jsonb` column (migration in `phase3_work_memory.sql`).
6. `note_processor.py`: include `"context_note_ids": [n.get("note_id") for n in related_notes]`
   in the `updates` dict passed to `update_note_item`.
7. `schemas/models.py`: add `context_note_ids: List[str] = Field(default_factory=list)` to
   `NoteStatusResponse` and `RecentNoteResponse`.
8. `frontend/src/shared/api/httpClient.ts`: add `context_note_ids?: string[]` to the `NoteStatus`
   interface.
9. `RecentMemorySection.tsx`: redesign card — `raw_text` primary, `enriched_summary` secondary,
   "Sourced from: [ids]" trail if `context_note_ids` non-empty.

### Phase D — Pause chat work
10. Update `chat_retrieval_optimization_plan.md` header to a paused status only (already noted
    there as a pending edit) — no content changes to its Decision Log.

## Relevant files
- `backend/app/domain/query_retrieval/hybrid_retriever.py` (new) — `HybridRetriever`,
  `NoteContextRetriever`, `get_hybrid_retriever()`, `get_note_context_retriever()`
- `backend/app/domain/query_retrieval/services.py` — `retrieve_query_context` refactored to
  delegate to `HybridRetriever`, signature unchanged
- `backend/app/infrastructure/vector/vectorstore.py` — unchanged (still used internally by
  `HybridRetriever`); only the direct call site from `note_processor.py` is removed
- `backend/app/domain/ports.py`, `backend/app/infrastructure/db/memory_repository.py` — new
  entity-reverse-lookup + structured-item-lookup methods
- `backend/app/domain/memory/services.py` — thin wrapper functions for the new repo methods
- `backend/app/workers/note_processor.py` — swap Mechanism B for `NoteContextRetriever`,
  pre-pass entity match, merge related notes/items, persist `context_note_ids`
- `backend/app/infrastructure/llm/gemini_client.py` — prompt changes (grouped structured context,
  synthesis instruction, "don't answer questions" instruction)
- `backend/sql/phase3_work_memory.sql` — `context_note_ids` column migration
- `backend/app/schemas/models.py` — new response field
- `frontend/src/shared/api/httpClient.ts`, `frontend/src/features/dashboard/components/RecentMemorySection.tsx` — dashboard changes

## Verification
1. Confirm chat retrieval behavior is unchanged after Phase R (same eval numbers as
   [northstar_rag_v1_rewrite.md](../evals/results/northstar_rag_v1_rewrite.md) etc. — Phase R is
   a refactor, not a behavior change, for the chat path).
2. Confirm note-ingestion now returns hybrid (BM25+dense+RRF+rerank) results via
   `NoteContextRetriever` where it previously only had dense-only top-3 results.
3. Replay the note1/note2/note3 example end-to-end with `ENABLE_RAG=true`; confirm note3's
   `enriched_summary` synthesizes the full history.
4. Confirm the entity pre-pass finds note1 from note2 even when semantic similarity alone
   wouldn't (reworded note2 sharing only the identifier).
5. Confirm an open question from an earlier note appears in context but is never marked
   "answered" unless the current note's own text resolves it.
6. `get_errors` on all modified files.
7. Manual dashboard check: raw text primary, summary secondary, source trail renders correctly
   for notes with and without `context_note_ids`.

## Optional enhancement (backlog, not required for MVP)

**Regenerate summary for previous notes.** Summaries are otherwise generated once and never
retroactively rewritten (see Goal section) — this would be an explicit, user-triggered exception,
not automatic background rewriting. A new endpoint (e.g. `POST /notes/{note_id}/regenerate`)
would re-run the same context-gathering (`NoteContextRetriever` + entity-linked lookup, both as of
*now*, not as of original processing time) and the same extraction prompt against the note's
original `raw_text`, then overwrite `enriched_summary`/`context_note_ids` for that note only.
Useful when a user wants an older note's summary refreshed after much more related context has
since accumulated. Explicitly opt-in per note, not a batch job — keeps the "never silently
rewritten" guarantee intact for anyone who hasn't asked for a refresh.

## Open follow-ups (explicitly out of scope for this pass)
- Fuller "source notes" resolution (fetch full snippets for `context_note_ids` outside the
  currently loaded recent-notes batch).
- Deterministic question-resolution path analogous to `apply_deterministic_task_resolution`.

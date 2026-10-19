# NorthStar Recall Pivot — Architecture Review and Implementation Plan

Source of truth for the pivot: [`final.md`](../final.md).
Review date: 2026-10-19.
Scope reviewed: `backend/app/`, `backend/sql/`, `frontend/src/`, `evals/`, and the current deployment path.

---

## 1. Executive summary

NorthStar already has a credible **note capture → LLM extraction → typed work-memory → hybrid retrieval → grounded chat → daily/weekly summary** pipeline. The pivot does **not** require throwing that away. It requires changing what the system optimizes for:

| Today | After pivot |
| --- | --- |
| Notes are the product output | Memory is the product output |
| Chat is the default experience | Review is the default experience |
| Extraction displays everything | Extraction scores and selects what is worth remembering |
| Retrieval is note-level and chat-only | Retrieval is chunk-level and shared by chat + recall |
| Summaries are passive recaps | Summaries close the loop into cards and commitments |
| No retention mechanism | Spaced-repetition review + provenance |
| No action mechanism | Commitment extraction + calendar confirmation |

The largest missing subsystem is the **Recall Engine**: candidate scoring, card generation, spaced-repetition scheduling, review history, and the review UI. The second largest is the **data/vector foundation**: the current data model has no `recall_cards`, `review_history`, `note_entities`, entity importance, task due dates, or chunk embeddings, and Chroma is used as a local on-disk store that is not reliable across Lambda/API instances.

Recommended sequence:

1. **Foundation first** — fix prompt/config defects, add idempotency/status, add tests.
2. **Data + vector foundation** — recall schema, note-entity links, chunking, pgvector behind the existing `VectorStore` port.
3. **Understand stage** — importance/durability scoring, knowledge units, commitments/due dates.
4. **Remember stage** — candidate lifecycle, question-first card generation, Anki-style scheduler, review APIs and UI.
5. **Act stage** — commitment confirmation + Google Calendar (stub first).
6. **Re-center the product** — Today/Review become the default routes; chat becomes “Ask”, deliberately secondary.
7. **Harden and evaluate** — recall/retrieval evals, metrics, cost, DLQ, security.

Estimated solo-developer effort: **~8–10 weeks** at full-time pace, matching `final.md`, with existing chat/summary/retrieval code saving roughly 2–3 weeks versus a greenfield build.

### 1.1 Locked decisions (2026-10-19)

These decisions are fixed for the MVP unless explicitly revisited:

| Area | Decision |
| --- | --- |
| Runtime vector store | **pgvector only.** Remove Chroma from the application path. Keep the isolated Chroma eval harness only until the eval suite is migrated to pgvector fixtures. |
| Platform | Responsive **web only**. No native mobile app in MVP. |
| Initial users | **Developers** — precise technical language, code/technology entities, developer-friendly review cards. |
| Calendar | **Last implementation feature.** Build commitments/due dates earlier, but leave MCP/Google Calendar integration until the recall loop is complete. |
| Note sensitivity | Notes are **not sensitive for now.** Use normal logging hygiene; do not build end-to-end encryption or self-hosting in MVP. |
| Timezone | **UTC-only for MVP.** Store and schedule in UTC; document the limitation. |
| Multi-user sharing | **Disabled.** No workspaces, collaboration, or sharing. |
| Delivery order | Implement **PR1–PR5 first**, review each before starting the next, and only then start the Anki-style recall feature. |
| Scheduling model | **Anki-style with learning steps** (Again/Hard/Good/Easy), not SM-2. Scheduler behind a `Scheduler` port with a deterministic `Clock`. |
| Grade mapping | Again=**1**, Hard=**3**, Good=**4**, Easy=**5**. Grade `2` is not used and is rejected by the API. |
| Durability | Stored as a **numeric 0–1** score (not an enum). |
| Candidate policy | **No per-note or per-week caps.** A single eligibility threshold decides candidacy; the review queue itself limits load. |
| Question flow | **Question-first:** generate and show only the question; the answer is generated only after the user accepts the suggestion. |
| Recall opt-in | Per-note `recall_enabled` toggle. Candidates are scored for every note (pure/cheap); questions (the only LLM cost) are generated only when the toggle is ON, eagerly in the note-processing worker. |
| Architecture style | Follow existing layered patterns, SOLID, KISS, reusable modules, and readable code. |

---

## 2. Current architecture review

### 2.1 Implemented architecture

The backend is a pragmatic layered monolith with an event-driven ingestion path:

```text
React SPA
  → FastAPI routers (backend/app/api/routes)
  → domain services (backend/app/domain)
  → ports (backend/app/domain/ports.py)
  → infrastructure adapters (Supabase, Chroma, Gemini, SQS)
  → note worker (backend/app/workers/note_processor.py)
```

Key implemented paths:

| Path | Current implementation | Evidence |
| --- | --- | --- |
| Auth | JWT access tokens, argon2 passwords, rotating refresh tokens, bearer dependency | `backend/app/api/deps.py`, `backend/app/api/routes/auth.py`, `backend/app/infrastructure/auth/jwt_service.py` |
| Note capture | `POST /notes` saves a `processing` note; SQS or inline processing | `backend/app/api/routes/notes.py:29-69` |
| Note enrichment | Retrieves related context, embeds note, calls Gemini extraction, persists typed items, entity links, deterministic task resolution, Chroma upsert | `backend/app/workers/note_processor.py:28-224` |
| Typed memory | `notes`, `extraction_runs`, `tasks`, `facts`, `questions`, `decisions`, `risks`, `concepts`, `entities`, `memory_item_entities`, `period_summaries` | `backend/sql/phase3_work_memory.sql` |
| Hybrid retrieval | Chroma dense + user-scoped BM25 + RRF + optional cross-encoder, guarded query rewrite | `backend/app/domain/query_retrieval/hybrid_retriever.py`, `services.py` |
| Chat | Persistent threads, rule-based intent, planner, retrieval, grounding guardrail, Gemini answer, pending tool confirmation | `backend/app/domain/chat/services.py`, `orchestrator.py`, `guardrails.py`, `tools.py` |
| Summaries | Daily/weekly prose recaps from notes + typed items; weekly composes daily | `backend/app/domain/summary/services.py` |
| Frontend | Single `App.tsx` with hash routes for login/register/dashboard/add-note/chat; dashboard sections for tasks/questions/risks/concepts/recent/summaries | `frontend/src/app/App.tsx` |
| Evaluation | Retrieval-only offline harness: BM25, dense, RRF, rerank, rewrite | `evals/` |

### 2.2 Alignment against the pivot

| Pivot requirement (`final.md`) | Current support | Gap / decision |
| --- | --- | --- |
| Capture notes quickly | Yes | Keep; add quick capture on Today |
| Async note processing | Yes, SQS + Lambda-compatible worker | Add stage separation, idempotency, DLQ, retries, per-stage status |
| Summary of note | Yes (`enriched_summary`) | Keep; expose as `summary` in API/UI |
| Extract facts/concepts/tasks/decisions/risks/questions/entities | Yes | Add importance/durability; add commitments and due dates |
| Hybrid BM25 + vector retrieval | Yes | Reuse pipeline; add chunk-level retrieval and pgvector |
| Shared retrieval for chat + recall | Partially (note ingestion + chat share `HybridRetriever`) | Add recall context retrieval through the same module |
| Recall engine (candidate selection, scoring, lifecycle) | **Missing** | Build new `domain/recall` subsystem + tables |
| Auto-generate Q/A cards with cross-note context | **Missing** | Build card generator using source note + hybrid-retrieved related snippets |
| Spaced repetition (Anki-style/FSRS) | **Missing** | Build scheduler port + Anki-style learning steps first |
| Review session UI + grading | **Missing** | Build Review route and session state machine |
| Card provenance (`source_notes`, `entity_ids`) | Provenance exists for typed items, not cards | Add to `recall_cards` |
| Candidate review workflow | **Missing** | Build candidate/card states and accept/reject endpoints |
| Daily/weekly summaries | Yes | Extend with recall load and “what to remember” |
| Calendar commitments | **Missing** | Extract due dates + confirmation flow + calendar provider |
| Chat deemphasized | No; chat is the default route | Change default route to Today/Review; chat becomes “Ask” |
| pgvector / unified Postgres | No; Chroma local on-disk | Replace runtime retrieval with pgvector; pgvector-only for the app |
| Chunking | No; one embedding per note | Add `note_chunks` + chunk embeddings |
| Entity importance / consolidation | No; entities only name/type | Add `importance`, `mention_count`, `user_interest`, `embedding` |
| Note ↔ entity join | No direct join; entity links are per typed item | Add `note_entities`; backfill from `memory_item_entities` |
| Metrics/observability | Logs only, mostly file-based | Add structured metrics + queue/LLM/recall metrics |
| Automated tests | **None found** | Add pytest suite before/alongside recall work |

### 2.3 Reusable assets (do not rebuild)

- `HybridRetriever` already exposes composable dense/sparse/fusion/rerank functions and is shared by chat and note ingestion. This is exactly the “single Retrieval Module” the pivot asks for.
- Domain ports (`EmbeddingProvider`, `VectorStore`, `QueryRewriter`, `ChatModel`, repositories) make the Chroma → pgvector replacement feasible without rewriting retrieval logic.
- The chat stack already has grounding, citations, pending action confirmation, and tool execution. Reuse the confirmation pattern for calendar.
- Daily/weekly summary generation and persistence are already implemented; extend rather than replace.
- Typed work-memory tables are richer than `final.md`’s minimum schema. Keep them; do not regress to JSON-only storage.
- The eval harness is a strong base for retrieval regression testing.

### 2.4 Defects and risks found during review

These are implementation issues that will interfere with the pivot if not fixed first.

1. **Extraction prompt placeholder drift.** `backend/app/prompts/phase3-v1/00-gemini_extraction_prompt.txt` uses `{normalized_text}`, `{action_items_json}`, and `{questions_json}`, but `generate_gemini_prompt` only replaces `{note_text}`, `{related_notes_context}`, and `{structured_items_context}`. When the external prompt file is loaded, the note text is never inserted. Add a prompt-rendering test that asserts no unresolved `{placeholder}` remains.
2. **No idempotency or stage status.** A retried SQS message re-runs extraction and can duplicate tasks/facts/entities. There is no unique processing key, no per-stage status, and no DLQ evidence in the repo.
3. **Partial-write failure.** The worker writes the note update, extraction run, six item tables, entity links, task resolution, and Chroma in sequence with no transaction or resumable state machine.
4. **Chroma is process-local and on-disk.** `backend/app/infrastructure/vector/vectorstore.py:5-19` defaults to `./chroma_data`. This is not a reliable shared store for multiple API instances or Lambda invocations. It also means Supabase is the source of truth while the derived index can diverge.
5. **Entity-linked retrieval implementation is fragile.** `SupabaseMemoryRepository.query_memory_items_by_entity_names` builds a dynamic `<item>_id` column and selects a nonexistent `concepts.label` field, and performs an N+1 entity lookup per item. This should be replaced with a single SQL/RPC query over `memory_item_entities`.
6. **No chunking.** Whole-note embeddings make long notes a single vector and reduce retrieval precision. There are no source offsets for citations.
7. **Chat-first routing.** `App.getRouteFromHash()` falls through to `chat`, and login/registration redirect to `#/chat`. This contradicts the pivot’s “recall first, chat secondary” positioning.
8. **CORS is wide open.** `backend/app/main.py:24-30` uses `allow_origins=["*"]` with credentials. Replace with an explicit allowlist.
9. **Prompt logs persist raw notes to disk.** `backend/app/infrastructure/llm/prompt_logger.py` writes full note text, prompts, and responses to a file and overwrites it on each extraction. This is useful locally but unsafe for real users; gate it behind an explicit env flag and redact/disable in production.
10. **No recall schema or scheduler.** This is the main build item, not a defect.
11. **No tests.** Retrieval evals exist, but there are no unit/integration/API tests. The pivoted core loop is too stateful to ship without tests.
12. **No transaction boundary for calendar/commitment actions.** Calendar event creation must be idempotent and recorded before/after the external call.
13. **Documentation drift.** `docs/Project_Architecture_Blueprint.md` still says authorization is incomplete, while routes now use `get_current_user_id`. Keep the blueprint current as part of the plan.
14. **Reranker default mismatch.** Code defaults to `semantic` (`hybrid_retriever.py:42`) while README documents `off`. Decide one default; for Lambda, default should be off.

---

## 3. Target architecture

### 3.1 Product loop

```text
Capture ──► Understand ──────────────► Remember ──────────────► Act
  │             │                          │                      │
  │             ├─ summary                 ├─ recall candidates   ├─ commitments
  │             ├─ typed memory items      ├─ recall cards        ├─ due dates
  │             ├─ entities + importance   ├─ review scheduling   ├─ calendar prompts
  │             └─ embeddings + chunks     └─ review history      └─ calendar events
  │
  └──────────────► Retrieval Module ◄──── Ask Northstar / Recall context / Summaries
```

### 3.2 Target module layout

```text
backend/app/
  api/routes/
    auth.py                  (existing)
    notes.py                 (extend: memory snapshot, reprocess)
    memory.py                (keep typed-memory CRUD)
    retrieval.py             (keep)
    chat.py                  (keep, reposition as Ask)
    summaries.py             (keep, extend)
    recall.py                (new)
    calendar.py              (new)
    dashboard.py             (new: Today aggregate)
  domain/
    ports.py                 (extend)
    memory/                  (existing extraction persistence)
    recall/                  (new)
      candidate_scoring.py
      candidate_service.py
      card_generation.py
      scheduling/
        base.py              (Scheduler protocol)
        scheduler.py
        clock.py
      services.py
    calendar/                (new)
      commitment_service.py
      provider.py
      services.py
    query_retrieval/         (existing; add chunk-aware retrieval)
    chat/                    (existing; no functional rewrite)
    summary/                 (existing; extend stats/prompts)
    dashboard/               (new: read-only aggregator)
  infrastructure/
    db/
      memory_repository.py   (extend/fix entity queries)
      recall_repository.py   (new)
      calendar_repository.py (new)
      note_chunk_repository.py (new)
      supabase_client.py
    vector/
      vectorstore.py         (factory: pgvector/chroma)
      pgvector_store.py      (new)
      embeddings.py
    llm/
      gemini_client.py       (extend, or split per use case)
      prompt_loader.py
  workers/
    note_processor.py        (refactor into stages)
    recall_processor.py      (new)
  prompts/
    recall-v1/
      00-gemini_extraction_prompt.txt   (updated)
      03-recall-card_prompt.txt         (new)
      04-commitment_extraction_prompt.txt (optional)
```

### 3.3 Dependency rules to preserve

- API routes stay thin: validate, authenticate, delegate, map errors.
- Domain depends on ports, not concrete Supabase/pgvector/Gemini modules.
- Infrastructure owns provider-specific behavior.
- Supabase remains the source of truth; vector stores and BM25 indexes are derived and rebuildable.
- Preserve `user_id`, source-note, extraction-run, prompt-version, and model provenance on every generated artifact.
- All LLM output passes through typed Pydantic validation before persistence.
- All background work must be retry-safe before adding new job types.

---

## 4. Methodology changes

The pivot is as much a methodology change as a feature change.

| Area | Current method | Pivot method |
| --- | --- | --- |
| Product focus | Chat-first AI notes | Recall-first personal memory |
| Extraction | Extract everything, display everything | Extract, score importance/durability, then select |
| Selection | None | Deterministic eligibility formula + candidate lifecycle; the user accepts or skips each suggested question |
| Retrieval unit | Whole note | Paragraph/semantic chunk + note-level aggregation |
| Retrieval consumers | Chat + note enrichment | Chat + recall context + summaries + dashboard, one shared module |
| Card creation | None | Cross-note LLM Q/A generation grounded in source snippets |
| Scheduling | None | Anki-style learning steps first; FSRS behind a port later |
| Calendar | None | Detect commitment intent, confirm with user, create event idempotently |
| Human-in-the-loop | Chat tool confirmation | Suggestion accept/skip + calendar confirmation |
| UX hierarchy | Chat → Dashboard | Today/Review → Notes → Ask |
| Evaluation | Retrieval only | Retrieval + candidate quality + card quality + scheduler simulation + review outcomes |
| Quality control | Heuristic rewrites/grounding | Same, plus deterministic scoring tests and recall acceptance thresholds |
| Delivery | Feature-by-feature | Vertical slices with fixtures and acceptance criteria per slice |
| ML scope | LLM APIs only | LLM APIs only; no custom model training |

### 4.1 Design principles for the pivot

1. **Deterministic before learned.** Eligibility scoring, dedupe thresholds, scheduling, and candidate states are deterministic and auditable. No training pipeline in MVP.
2. **Provenance is mandatory.** Every card must resolve to source notes and, where possible, entity IDs.
3. **Augment, do not overwhelm.** No card caps: every eligible unit can be suggested, but the user only sees the queue when they choose to review. Question generation is opt-in per note.
4. **Ground every generated answer.** Card answers must be supported by the supplied source snippets; validation rejects unsupported text.
5. **One retrieval module.** Chat, recall context, and card generation all use `HybridRetriever`/`QueryRetrievalService`.
6. **Evolve schema, do not rewrite.** Keep the existing typed tables and text IDs; add recall-specific tables and projections.
7. **Measure before tuning.** Use synthetic fixtures and simulated review workload to tune thresholds and intervals.

---

## 5. Data model changes

### 5.1 Migration strategy

- Add **idempotent SQL migrations** under `backend/sql/`:
  - `phase4_recall.sql` — recall tables, note-entity links, entity scores, task commitments, indexes.
  - `phase4_pgvector.sql` — `vector` extension, embeddings, chunk table, HNSW indexes, match functions.
  - `phase5_calendar.sql` — calendar event tracking and any OAuth metadata.
- Do not rename existing columns (`note_id`, `raw_text`, `enriched_summary`, `source_note_id`). Add compatibility aliases at the API/DTO layer instead.
- Keep **text IDs** for now. `final.md` specifies UUIDs, but the existing schema uses text IDs throughout and a UUID migration adds risk without product value. Use `text[]` for `source_notes` rather than `UUID[]`; document the deviation.
- Backfill existing data where possible:
  - `note_entities` from `memory_item_entities`.
  - Entity `mention_count`/`importance` from existing links.
  - `note_chunks` by chunking existing `notes.raw_text`.
  - No backfill for cards; generate only for new/eligible notes.

### 5.2 Table-by-table changes

#### `notes` (existing, extend)

Current columns: `note_id`, `user_id`, `status`, `created_at`, `raw_text`, `enriched_summary`, `context_note_ids`, `action_items`, `questions`, `insights`, `metadata`, `processed_at`.

Add:

| Column | Type | Purpose |
| --- | --- | --- |
| `updated_at` | `timestamptz` | Editing/reprocessing |
| `content_hash` | `text` | Idempotency / change detection |
| `extraction_version` | `text` | Prompt/schema version used |
| `recall_enabled` | `boolean default false` | Per-note opt-in for question generation |
| `recall_status` | `text default 'off'` | `off / pending / ready / failed` |
| `metadata` | `jsonb` (already exists) | Projection of extracted knowledge units, diagnostics, commitment flags |
| `embedding` | `vector(768)` | Optional note-level embedding; chunks remain the retrieval unit |

Status semantics (implemented):

```text
notes.status:          processing -> completed | failed
notes.recall_status:   off -> pending -> ready | failed
```

When `recall_enabled` is on, the worker keeps the note `processing` until questions are generated, then sets `status='completed'` and `recall_status='ready'`. A note with recall off becomes `completed` + `recall_status='off'`. Toggling recall on for an already-completed note runs synchronously and sets `pending` → `ready`/`failed`.

#### `note_chunks` (new)

| Column | Type | Notes |
| --- | --- | --- |
| `chunk_id` | `uuid` PK | |
| `note_id` | `text` FK → `notes` | cascade delete |
| `user_id` | `text` | tenant scope |
| `chunk_index` | `int` | ordering |
| `content` | `text` | chunk text |
| `start_offset` | `int` | source offset |
| `end_offset` | `int` | source offset |
| `token_count` | `int` | |
| `embedding` | `vector(768)` | must match `EMBEDDING_DIMENSION` |
| `metadata` | `jsonb` | section/heading/etc. |
| `created_at` | `timestamptz` | |

Unique `(note_id, chunk_index)`; HNSW index on `embedding vector_cosine_ops`.

#### `entities` (existing, extend)

Add:

| Column | Type | Purpose |
| --- | --- | --- |
| `importance` | `double precision default 0.5` | Eloquent importance score |
| `mention_count` | `int default 1` | Cross-note mentions |
| `user_interest` | `double precision default 0` | Tags/pins/query interest |
| `embedding` | `vector(768)` | Consolidation and dedupe |

Keep `unique(user_id, name)`; normalize names consistently.

#### `note_entities` (new)

| Column | Type | Purpose |
| --- | --- | --- |
| `note_id` | `text` FK → `notes` | |
| `entity_id` | `uuid` FK → `entities` | |
| `user_id` | `text` | |
| `snippet` | `text` | context around the mention |
| `mention_count` | `int default 1` | per-note count |
| `created_at` | `timestamptz` | |

PK `(note_id, entity_id)`. Backfill from `memory_item_entities` plus extracted entity mentions.

#### `tasks` (existing, extend)

Implemented additions:

| Column | Type | Purpose |
| --- | --- | --- |
| `due_date` | `date` nullable | Commitment/deadline |
| `importance` | `numeric` nullable | Optional ranking |
| `durability` | `numeric` nullable | 0–1 numeric durability |

Index `(user_id, due_date) where status = 'open' and due_date is not null`.

Implemented divergence: there is **no `is_commitment` flag**. Commitments are a separate `commitments` table (`commitment_id`, `source_note_id`, `task_id`, `title`, `due_date`, `status`, `confidence`, `calendar_provider`, `calendar_event_id`, `confirmed_at`) so a task can exist without being a calendar-worthy commitment.

#### `recall_candidates` (implemented in `phase4_recall.sql`)

| Column | Type | Purpose |
| --- | --- | --- |
| `candidate_id` | `uuid` PK | |
| `user_id` | `text` | |
| `item_type` | `text` | `task / fact / concept / question / decision / risk` |
| `item_id` | `uuid` | typed-table row id when matchable |
| `source_note_id` | `text` FK → `notes` | primary source |
| `text` | `text` | the knowledge unit (added by ALTER for existing DBs) |
| `prompt` | `text` | generated question (null until generation) |
| `answer` | `text` | reserved; answers live on cards |
| `importance` | `numeric` | extraction score |
| `durability` | `numeric` | 0–1 numeric durability |
| `mention_count` | `int default 1` | normalized input |
| `related_note_count` | `int default 1` | distinct notes |
| `recency_score`, `user_interest_score` | `numeric` | scoring inputs |
| `score` | `numeric` | final score |
| `status` | `text` | `eligible / suggested / carded / rejected` |
| `dedupe_key` | `text` | unique per user (prevents duplicate candidates) |
| `rationale` | `jsonb` | scoring diagnostics |
| `created_at`, `updated_at`, `decided_at` | `timestamptz` | |

Indexes: `(user_id, status, score desc)`, `(user_id, item_type, item_id)`, `source_note_id`, and unique `(user_id, dedupe_key)`. Per-note `notes.recall_enabled` / `notes.recall_status` gate question generation.

#### `recall_cards` (implemented in `phase4_recall.sql` + `phase4_recall_scheduler.sql`)

| Column | Type | Purpose |
| --- | --- | --- |
| `card_id` | `uuid` PK | |
| `user_id` | `text` | |
| `candidate_id` | `uuid` FK → `recall_candidates` | provenance |
| `question` | `text` | |
| `answer` | `text` | generated only after acceptance |
| `source_note_ids` | `text[]` | note IDs |
| `entity_ids` | `uuid[]` | optional |
| `status` | `text default 'active'` | `active / suspended` |
| `state` | `text default 'new'` | `new / learning / review / relearning` |
| `learning_step` | `int default 0` | index into learning/relearning steps |
| `interval` | `int default 0` | review interval in days (0 while learning) |
| `easiness` | `numeric default 2.5` | ease factor |
| `repetitions` | `int default 0` | |
| `lapses` | `int default 0` | |
| `review_count` | `int default 0` | |
| `last_reviewed` | `timestamptz` | |
| `next_due` | `timestamptz default now()` | due queue (timestamps support learning steps) |
| `created_at`, `updated_at` | `timestamptz` | |

Indexes: `(user_id, status, next_due)`, `(user_id, state, next_due)`, `(user_id, created_at desc)`, and unique `(user_id, candidate_id)` where `candidate_id is not null`.

#### `review_history` (implemented)

| Column | Type | Purpose |
| --- | --- | --- |
| `review_id` | `uuid` PK | |
| `user_id` | `text` | |
| `card_id` | `uuid` FK → `recall_cards` | |
| `reviewed_at` | `timestamptz` | |
| `grade` | `smallint check (1..5)` | 1=Again, 3=Hard, 4=Good, 5=Easy (2 rejected in API) |
| `previous_interval` | `int` | days |
| `new_interval` | `int` | days |
| `previous_easiness` | `numeric` | |
| `new_easiness` | `numeric` | |
| `elapsed_ms` | `int` | response time |

Indexes: `(card_id, reviewed_at desc)` and `(user_id, reviewed_at desc)`.

#### `calendar_events` (new; idempotency for Act stage)

| Column | Type | Purpose |
| --- | --- | --- |
| `event_id` | `uuid` PK | |
| `user_id` | `text` | |
| `task_id` | `uuid` FK → `tasks` | |
| `provider` | `text` | `google / stub` |
| `external_event_id` | `text` | provider event ID |
| `status` | `text` | `pending / created / failed / cancelled` |
| `payload` | `jsonb` | sanitized event payload |
| `created_at`, `updated_at` | `timestamptz` | |

Unique `(user_id, task_id, provider)` to make retries idempotent.

#### Existing `facts`, `questions`, `decisions`, `risks`, `concepts`, `memory_item_entities`, `period_summaries`

Keep as-is. Extend only where needed:

- Add `due_date` only if a question/decision is time-bound; otherwise commitments live on `tasks`.
- Keep `memory_item_entities` for item-level links; `note_entities` is the note-level projection.
- Extend `period_summaries.stats` with recall metrics (`cards_due`, `cards_reviewed`, `review_success_rate`) without schema changes.

### 5.3 Idempotency constraints

Add unique keys or upsert targets:

- `extraction_runs`: `(note_id, content_hash, prompt_version)` or a separate `idempotency_key`.
- `recall_candidates`: `dedupe_key`.
- `recall_cards`: `dedupe_key`.
- `calendar_events`: `(user_id, task_id, provider)`.
- `note_chunks`: `(note_id, chunk_index)`.
- `note_entities`: `(note_id, entity_id)`.

Workers update a stage marker **before** doing expensive work and use upserts so a retry is safe.

---

## 6. Backend and API changes

### 6.1 New domain services

#### Recall candidate scoring

`backend/app/domain/recall/candidate_scoring.py`

```text
score = 0.30 * importance
      + 0.20 * normalized_mention_count
      + 0.20 * related_note_count_score
      + 0.15 * recency_score
      + 0.15 * user_interest_score
```

Normalization rules (all to `[0, 1]`):

- `importance`: LLM 0–1, or confidence × unit-type weight.
- `normalized_mention_count`: `log1p(mention_count) / log1p(cap)` with `cap=10`.
- `related_note_count_score`: `min(1, distinct_notes / 3)`.
- `recency_score`: `exp(-age_days / 30)`.
- `user_interest_score`: max of entity pin/tag/edit signals and normalized query-hit count; starts at 0 for new users.

State rules (implemented):

- `score >= eligibility_threshold` **and** `confidence >= min_confidence`: candidate is persisted as `eligible`.
- Below either bar: not persisted as a candidate (the engine can optionally return rejected rows for diagnostics).
- **No auto-approve tier and no per-note/weekly caps.** The user opted out of caps; the review queue is the limiter. There is a single threshold.
- Default `RECALL_ELIGIBILITY_THRESHOLD=0.45` (not 0.65). Rationale: on a first note there are no related-note or interest signals, so even a perfect unit scores ≈0.57; 0.65 rejected every candidate for new users.
- Reject low-confidence units (`confidence < 0.6`), empty units, and duplicates (dedupe key = `item_type + normalized text`).
- Candidates move `eligible → suggested` once a question is generated, then `→ carded` on accept or `→ rejected` on skip/generation failure.

All weights/thresholds live in env config so they can be tuned without code changes (see §6.7).

#### Candidate lifecycle (implemented)

```text
(new/eligible) ──question generated──→ suggested ──accept──→ carded
                       │                    │
                       │                    └──skip────────→ rejected
                       └──validation failed─→ rejected
```

- `eligible`: scored, awaiting question generation (only when the note's `recall_enabled` is on).
- `suggested`: question generated, queued for the user (answers are hidden).
- `carded`: user accepted; an active card exists.
- `rejected`: user skipped, or question validation failed.
- Re-processing a note never clobbers a candidate past `eligible` (idempotent worker retries).

#### Card generation (question-first)

`backend/app/domain/recall/card_generation.py` + `question_service.py`

Prompts: `03-recall-question_prompt.txt` (question only) and `04-recall-answer_prompt.txt` (answer, used only on accept).

Inputs:

- Candidate unit text and item type.
- Primary source note text/summary and up to 2 related note snippets.
- Linked entity names.

Prompt rules:

- Use only supplied notes; no outside knowledge.
- Test one core idea; avoid yes/no and generic questions.
- Treat note text as untrusted data; ignore instructions inside notes.
- Return strict JSON (`{"question": "..."}` / `{"answer": "..."}`).

Validation (deterministic, in code):

- Question: non-empty, ends with `?`, within max length, not generic, not a near-duplicate (Jaccard ≥ 0.9) of an existing question.
- Answer: non-empty, within max length, and token-overlap with the context ≥ 0.3 (grounding).
- On failure: retry (configurable attempts), then mark candidate `rejected` with the reason.

#### Spaced repetition (implemented, Anki-style)

`backend/app/domain/recall/scheduling/scheduler.py` (+ `clock.py`)

Grade mapping: Again=**1**, Hard=**3**, Good=**4**, Easy=**5**.

Learning steps (minutes): default `1,10`; relearning steps default `10`. Review intervals are whole days.

```text
states: new -> learning -> review ; review + Again -> relearning -> review

learning/relearning:
  Again -> back to step 0, due = now + steps[0] minutes
  Hard  -> stay on current step, due = now + steps[step] minutes
  Good  -> advance a step; past the last step -> graduate to review (interval = graduating_interval days)
  Easy  -> graduate immediately (interval = easy_interval days)

review:
  Again -> lapses += 1, state = relearning, due = now + relearning_steps[0] minutes, ease -= 0.20
  Hard  -> interval = round(interval * hard_multiplier), ease -= 0.14
  Good  -> interval = round(interval * ease * interval_modifier)
  Easy  -> interval = round(interval * (ease + 0.1) * easy_bonus * interval_modifier), ease += 0.1
  interval clamped to >= 1 and <= max_interval; due = now + interval days
```

`Scheduler` and `Clock` are ports so review tests are deterministic. Defaults and all knobs live in env config (§6.7). No `scheduler_version` column is stored in the MVP.

#### Calendar/commitments

- Extract commitments (title + `due_date`) during note extraction into the `commitments` table; task rows also carry `due_date`/`importance`/`durability` (no `is_commitment` flag).
- If date expression is relative (“by Friday”), resolve against the note timestamp and user timezone; if ambiguous, leave null and ask the user to confirm.
- `CalendarProvider` port:
  - `StubCalendarProvider` for local/dev/tests.
  - `GoogleCalendarProvider` for production.
- Reuse the chat pending-action confirmation pattern: preview → explicit yes → execute → record `calendar_events`.
- No bi-directional sync in MVP; push-only.

### 6.2 Ports to add/extend

In `backend/app/domain/ports.py`:

```python
class RecallRepository(Protocol):
    # candidates
    def insert_candidates(user_id, candidates) -> list[dict]: ...
    def upsert_candidate(user_id, candidate) -> dict: ...
    def get_candidate(user_id, candidate_id) -> dict | None: ...
    def query_candidates(user_id, status=None, limit=100, source_note_id=None) -> list[dict]: ...
    def update_candidate(user_id, candidate_id, updates) -> dict: ...
    # cards
    def create_card(user_id, card) -> dict: ...
    def get_card(user_id, card_id) -> dict | None: ...
    def query_cards(user_id, status=None, due_before=None, limit=100) -> list[dict]: ...
    def update_card(user_id, card_id, updates) -> dict: ...
    # reviews
    def insert_review_history(user_id, entry) -> dict: ...
    def query_review_history(user_id, card_id) -> list[dict]: ...
    # commitments (Act stage; repository ready, API not wired yet)
    def upsert_commitment(user_id, commitment) -> dict: ...
    def query_commitments(user_id, status=None) -> list[dict]: ...
    def update_commitment(user_id, commitment_id, updates) -> dict: ...

class Scheduler(Protocol):
    def schedule(card: dict, grade: int, now: datetime) -> dict: ...

class Clock(Protocol):
    def now() -> datetime: ...

class CalendarRepository(Protocol): ...   # planned
class CalendarProvider(Protocol): ...     # planned
class QueuePublisher(Protocol): ...       # planned
```

Generation is implemented as functions (`generate_question`/`generate_answer` in `card_generation.py`) rather than a `CardGenerator` class; the chat model is injected as a `ChatModel` port. This keeps prompts/validation testable without extra indirection.

Extend `MemoryRepository` only minimally; prefer new repositories to avoid an 1,000-line interface.

### 6.3 Worker pipeline

Refactor `process_sqs_message` into explicit stages:

```text
SQS message: { job_type, note_id, user_id, idempotency_key, attempt }

job_type = extract_note   (implemented)
  1. mark notes.status = processing (idempotent)
  2. fetch related context (existing)
  3. extract summary/typed items/commitments/knowledge units
  4. upsert extraction run, typed items, note_entities, memory_item_entities
  5. apply deterministic task resolution
  6. score + persist candidates (pure, cheap; always)
  7. re-read notes.recall_enabled
  8. if enabled: generate questions via the LLM (question-first)
  9. set notes.status = completed
 10. set notes.recall_status = ready | failed | off
 11. chunk + embed note, then index into pgvector
```

Operational rules:

- Single worker run: there is no second `generate_recall` job. Answers are generated on acceptance, inside the API request.
- Extraction retries: worker's existing retry policy; question generation retries `RECALL_GENERATION_ATTEMPTS` (default 2) per candidate.
- Failed stages go to the DLQ after `maxReceiveCount`; preserve diagnostic metadata.
- If question generation fails, the note still completes with `recall_status='failed'`; toggling recall or reprocessing retries it.
- Use content hash to skip unchanged notes.
- Never let a recall failure invalidate a successful extraction.

### 6.4 API surface

Implemented (PR6–PR8, all `Depends(get_current_user_id)` + repository ownership):

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/recall/candidates` | List candidates by status (default `suggested`), highest score first; only questions returned |
| `POST` | `/recall/candidates/{candidate_id}/accept` | Generate the answer, create + schedule a card, mark the candidate `carded` |
| `POST` | `/recall/candidates/{candidate_id}/reject` | Mark the candidate `rejected` |
| `GET` | `/recall/due` | Due review queue (active cards with `next_due <= now`) |
| `POST` | `/recall/cards/{card_id}/review` | Submit a grade (`1/3/4/5`) + `elapsed_ms`; updates scheduling state and history |
| `PATCH` | `/notes/{note_id}/recall` | Toggle per-note recall; enabling generates questions for scored candidates synchronously |

Planned (later phases):

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/dashboard/today` | Today’s due cards, commitments, highlights, summary status |
| `GET` | `/recall/cards` | List cards by state |
| `PATCH` | `/recall/cards/{card_id}` | Edit question/answer/state |
| `GET` | `/recall/stats` | Review analytics |
| `GET` | `/commitments` | Tasks flagged as commitments |
| `POST` | `/commitments/{task_id}/calendar/preview` | Preview event payload |
| `POST` | `/commitments/{task_id}/calendar/confirm` | Create calendar event |
| `GET` | `/calendar/events` | List created events |
| `POST` | `/notes/{note_id}/reprocess` | Re-run extraction/recall |
| `GET` | `/notes/{note_id}/memory` | Extend response with knowledge units, cards, commitments |

All routes use `Depends(get_current_user_id)` and enforce ownership in repository queries.

### 6.5 Pydantic schema additions

In `backend/app/schemas/models.py`:

- `ExtractedKnowledgeUnit`
- `ExtractedCommitment`
- `RecallCandidateResponse`
- `RecallCardResponse`
- `ReviewRequest` / `ReviewResult`
- `DueReviewResponse`
- `CommitmentResponse`
- `CalendarPreviewResponse`
- `CalendarEventResponse`
- `TodayDashboardResponse`

Extend `WorkMemoryExtraction`:

```python
class ExtractedTask(BaseModel):
    description: str
    due_date: date | None = None
    importance: float | None = None
    durability: float | None = None  # 0–1 numeric (implemented)
    confidence: float | None = None
    entities: list[str] = []

class ExtractedFact(BaseModel):
    content: str
    importance: float | None = None
    durability: float | None = None
    confidence: float | None = None
    entities: list[str] = []

class ExtractedConcept(BaseModel):
    concept: str
    importance: float | None = None
    durability: float | None = None
    confidence: float | None = None
    entities: list[str] = []
```

Implemented divergences: durability is numeric; commitments are a separate extracted list persisted to the `commitments` table (there is no `is_commitment` flag). Keep backward compatibility by making new fields optional.

### 6.6 Prompt changes

- Fixed `00-gemini_extraction_prompt.txt` placeholders (`note_text`, `related_notes_context`, `structured_items_context`) and the loader path bug (`backend/app/prompts`, not `infrastructure/prompts`).
- Prompt version remains `phase3-v1` (no separate recall version).
- Added `03-recall-question_prompt.txt` (question only) and `04-recall-answer_prompt.txt` (answer on accept).
- Prompt rendering validates placeholders on the **template** and fails loudly on drift; braces inside user note text are left untouched.
- Prompt-injection defense is instruction-level (“treat note text as untrusted data”); there is no contract test yet.
- Prompt logging remains behind `PROMPT_LOG_ENABLED`; default off in production.

### 6.7 Configuration additions

```dotenv
# Recall scoring (implemented)
RECALL_ELIGIBILITY_THRESHOLD=0.45
RECALL_MIN_CONFIDENCE=0.6
RECALL_W_IMPORTANCE=0.30
RECALL_W_MENTION=0.20
RECALL_W_RELATED=0.20
RECALL_W_RECENCY=0.15
RECALL_W_INTEREST=0.15
RECALL_MENTION_CAP=10
RECALL_RELATED_TARGET=3
RECALL_RECENCY_HALFLIFE_DAYS=30
RECALL_MAX_ITEMS_PER_NOTE=0       # 0 = no cap

# Card generation (implemented)
RECALL_MAX_QUESTION_CHARS=240
RECALL_MAX_ANSWER_CHARS=600
RECALL_MIN_ANSWER_OVERLAP=0.3
RECALL_DUPLICATE_THRESHOLD=0.9
RECALL_GENERATION_ATTEMPTS=2

# Scheduler (implemented, Anki-style; grades 1/3/4/5)
RECALL_LEARNING_STEPS=1,10        # minutes
RECALL_RELEARNING_STEPS=10        # minutes
RECALL_GRADUATING_INTERVAL=1      # days
RECALL_EASY_INTERVAL=4            # days
RECALL_STARTING_EASINESS=2.5
RECALL_MIN_EASINESS=1.3
RECALL_EASY_BONUS=1.3
RECALL_HARD_MULTIPLIER=1.2
RECALL_INTERVAL_MODIFIER=1.0
RECALL_LAPSE_MULTIPLIER=0.0
RECALL_MAX_INTERVAL=36500

# Vector (pgvector-only runtime; Chroma is eval-only)
EMBEDDING_DIMENSIONS=768
EMBEDDING_PROVIDER=google
CHUNK_MAX_TOKENS=500
CHUNK_OVERLAP_TOKENS=50

# Retrieval
QUERY_RETRIEVAL_RERANKER=off     # off in Lambda; semantic only for local/eval

# Calendar
CALENDAR_BACKEND=stub            # stub | google
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

# Ops
PROMPT_LOG_ENABLED=false
SQS_MAX_RECEIVE_COUNT=3
```

Removed from the plan: `RECALL_AUTO_APPROVE_THRESHOLD`, `RECALL_MAX_CARDS_PER_NOTE`, `RECALL_MAX_NEW_CARDS_PER_WEEK`, `RECALL_SCHEDULER`, `RECALL_REVIEW_GRADES` (grades are fixed to 1/3/4/5 in code; caps and auto-approve were not implemented).

---

## 7. Retrieval architecture changes

### 7.1 pgvector migration

The `VectorStore` port isolates the store. Implemented:

- `backend/app/infrastructure/vector/pg_vector_store.py` implementing `VectorStore`.
- `get_vector_store()` always returns `PgVectorStore`; the Chroma runtime path and
  dual-write were removed (Chroma remains only in offline `evals/`).
- SQL functions:

```sql
-- note-level candidates aggregated from chunks
create or replace function match_note_chunks(
  p_user_id text,
  p_query_embedding vector(768),
  p_match_count int
) returns table (
  chunk_id uuid,
  note_id text,
  content text,
  similarity double precision
) language sql stable as $$
  select c.chunk_id, c.note_id, c.content,
         1 - (c.embedding <=> p_query_embedding) as similarity
  from note_chunks c
  where c.user_id = p_user_id
  order by c.embedding <=> p_query_embedding
  limit p_match_count;
$$;
```

- `notes`/`note_chunks` embeddings with HNSW indexes.
- The application path is **pgvector-only**. Do not add a runtime Chroma fallback.
- Migration order: add pgvector tables/functions → backfill existing notes → switch reads and writes → remove Chroma calls from `note_processor.py` and retrieval adapters.
- Keep `evals/.chroma` isolated **temporarily** for the existing retrieval harness; migrate eval fixtures to pgvector-compatible fakes next. Evals must never point at production tables.

### 7.2 Chunking

- Split notes by paragraph/semantic boundary, target ~500 tokens, 50-token overlap.
- Store `start_offset`/`end_offset` for citations.
- Embed chunks, not only whole notes.
- For note-level context (chat/recall), aggregate chunk results per note: keep best chunk score, retain all contributing chunk IDs.
- For card generation, pass the best 1–2 chunks from each related note, not the whole note.

### 7.3 Sparse retrieval

- Keep the current in-memory BM25 for MVP and eval parity.
- Cache per-user index with content-hash invalidation (already partially implemented).
- Add a `PostgresSparseRetriever` later using `tsvector` + `websearch_to_tsquery` if multi-instance memory becomes a problem.
- BM25 should index chunk content, not only full notes, once chunking lands.

### 7.4 Fusion and reranking

- Keep RRF as the default (no score calibration needed).
- Keep the guarded rewrite flow for chat only; do not use it for recall card generation.
- Default reranker to `off` in production/Lambda. Cross-encoder models are too large/slow for the current deployment; keep them for local/eval.
- Add per-stage timing and candidate-source diagnostics to metrics, not just file logs.

### 7.5 Caching

- Embedding cache keyed by `(provider, model, sha256(text))`.
- Query-result cache with short TTL and per-user invalidation on note write.
- Avoid caching personalized/private results across users.

---

## 8. Frontend changes

### 8.1 Route and navigation restructure

Current `App.tsx` routes: `login`, `register`, `dashboard`, `add-note`, `chat`; fallback is `chat` (`frontend/src/app/App.tsx:37-54`). Change to:

```text
#/today        (default after login)
#/review       (due cards session)
#/notes        (notes + knowledge units)
#/notes/new    (capture)
#/ask          (chat, secondary)
#/login
#/register
```

Navigation should be a persistent shell:

```text
[Today] [Review] [Notes] [Ask]                  [Logout]
```

### 8.2 New pages/components

| Component | Responsibility |
| --- | --- |
| `features/today/TodayPage.tsx` | Due count/progress ring, commitments, highlights, quick capture, summary status |
| `features/review/ReviewPage.tsx` | Due queue loader and session shell |
| `features/review/ReviewSession.tsx` | Question → Reveal → grade → next; keyboard shortcuts |
| `features/review/SuggestedCards.tsx` | Question-only suggestions; accept (generate answer) or skip |
| `features/notes/NotesPage.tsx` | Note list + processing/recall status |
| `features/notes/NoteDetail.tsx` | Summary, knowledge units, typed items, provenance, generated cards |
| `features/notes/QuickCapture.tsx` | Fast capture from Today |
| `features/ask/AskPage.tsx` | Existing `ChatPage`, relabeled |
| `features/calendar/Commitments.tsx` | Due dates + “Add to calendar” confirmation |
| `features/dashboard/...` | Reuse existing sections inside Today/Notes |

### 8.3 Review UX

```text
Loading due queue
  → Card 1: Question only
      [Reveal answer]
  → Answer + source link
      [Again] [Hard] [Good] [Easy]
  → POST review
  → Next card
  → Session complete: reviewed count, success rate, next due
```

Requirements:

- Never show the answer before “Reveal”.
- Grade buttons map to 1/3/4/5.
- Show progress (“7 of 12”) and overdue count.
- Source note links open the note detail.
- Empty state: “Nothing due today.”
- Keyboard: space to reveal, 1–4 to grade.
- Mobile-first layout.

### 8.4 Today UX

- Header: “X cards due” + progress ring.
- “Commitments” section: due dates and calendar status.
- “What you learned” section: recent knowledge units/concepts.
- “Open loops”: open tasks/risks/decisions.
- “Summary” section: daily/weekly status and generate action.
- Quick capture input at the top.

### 8.5 API client restructure

Split `frontend/src/shared/api/httpClient.ts` into modules or add clearly separated sections:

- `auth.ts`, `notes.ts`, `memory.ts`, `recall.ts`, `calendar.ts`, `summaries.ts`, `chat.ts`, `dashboard.ts`.

Add types mirroring backend response models. Keep token refresh behavior centralized. Do not log note content to the console in production (`console.debug` in `createNote` should be removed/gated).

### 8.6 Chat de-emphasis

- Remove chat as the default route.
- Label it “Ask Northstar” in navigation and copy.
- Keep it fully functional; it is the RAG showcase, not the product identity.
- Add source citations/links in answers (grounding already provides source refs).
- Optionally add “Turn into card” on a chat answer later; not MVP.

---

## 9. Async, operations, security, and cost

### 9.1 Reliability

- Add SQS DLQ + redrive policy; set `maxReceiveCount=3`.
- Add idempotency keys and unique constraints.
- Use stage status markers instead of one all-or-nothing note status.
- Add retry/backoff for Gemini rate limits and timeouts.
- Validate LLM JSON with Pydantic; store raw response only behind the logging flag.
- Add a failed-note UI state and reprocess endpoint.

### 9.2 Observability

Metrics:

- Queue: depth, age, retries, DLQ count.
- Extraction: latency p50/p95, items per type, failure rate.
- Recall: candidates created, cards generated, validation failure rate, card acceptance/rejection rate.
- Review: due count, completed sessions, grade distribution, lapse rate, review latency.
- Retrieval: recall@5, MRR@5, isolation failures, no-context rate, rewrite/rerank usage.
- Cost: tokens per note/chat/card, estimated cost per 100 notes.

Logs:

- Structured JSON with `request_id`, hashed `user_id`, `note_id`, `job_type`, `stage`, `outcome`, `elapsed_ms`.
- Remove raw note text from production logs.
- Add queue-age and error-rate alerts.

### 9.3 Security

- Replace `allow_origins=["*"]` with an environment-specific allowlist.
- Keep bearer auth on every protected route; add a test that unauthenticated requests return 401.
- Store calendar OAuth refresh tokens encrypted at rest; never log them.
- Treat notes as untrusted prompt input; delimit and validate LLM output.
- Rate-limit note creation, review submissions, and chat messages per user.
- Consider moving SPA tokens out of `localStorage` (httpOnly cookies) as a later hardening item.
- Add Supabase RLS or repository-enforced `user_id` scoping as defense in depth.

### 9.4 Cost

- Use one extraction LLM call per note when possible (summary + items + units + commitments).
- Generate cards only for eligible candidates, not every extracted unit.
- Cap card generation retries.
- Cache embeddings and query results.
- Use a cheap embedding model and a small chat/extraction model.
- Track tokens/cost per stage; set per-user daily budgets.

---

## 10. Testing and evaluation plan

### 10.1 Test pyramid

There are currently no Python tests in the repository. Add `backend/tests/`:

**Unit**

- Candidate scoring normalization and the eligibility threshold (incl. cold-start first notes).
- Dedupe keys and duplicate detection.
- Anki-style scheduling (learning/relearning steps, all grades, lapses, ease floor, intervals).
- Prompt rendering (no unresolved placeholders, injection resistance).
- Extraction schema validation (missing fields, invalid dates).
- Card validation (grounding, generic questions, empty output).
- Calendar date parsing/timezone behavior.
- Entity-name normalization and consolidation.

**Integration**

- Note creation → extraction (fake LLM) → typed rows → candidates → cards.
- Idempotent retry: same note/message twice produces no duplicates.
- Due queue → review → history → next due.
- Candidate accept/reject lifecycle.
- Calendar preview → confirm → event row, including duplicate confirmation.
- Auth/ownership: user A cannot read user B’s cards/notes.

**Contract**

- API response models match frontend types.
- Error mapping: 400/401/404/409/422/500.

**End-to-end**

- Manual happy path: capture → processing → review → calendar.
- Automated browser smoke test optional (Playwright) after MVP.

### 10.2 Evaluation extensions

Keep the existing retrieval suite and add recall-focused evals:

- `evals/datasets/recall_v1.jsonl`: synthetic notes with labeled eligible/ineligible knowledge units.
- `evals/datasets/recall_cards_v1.jsonl`: expected card qualities/source constraints.
- `evals/recall_metrics.py`:
  - eligibility precision/recall@k,
  - card groundedness (answer tokens supported by sources),
  - duplicate rate,
  - generic-question rate,
  - source/provenance completeness.
- `evals/scripts/run_recall_eval.py`.
- `evals/scripts/run_scheduler_simulation.py`:
  - simulate 90 days of reviews,
  - workload (new/due cards per day),
  - retention proxy (success rate over time),
  - lapse rate,
  - interval distribution.
- Extend CI (`.github/workflows/rag-eval.yml` or a new `recall-eval.yml`) with pytest and deterministic recall evals. LLM-backed card-quality evals run manually or on main with a secret.

### 10.3 Acceptance thresholds (initial)

- Retrieval recall@5 does not regress vs the saved v1 baseline by more than 2 percentage points.
- ≥80% of generated cards pass groundedness and duplicate checks on the synthetic set.
- 0 duplicate cards per source note in integration tests.
- Due queue returns only `active` cards with `next_due <= now`.
- Anki scheduler unit tests cover all grade/interval branches.
- Every card has at least one `source_notes` entry.
- Note processing is idempotent across 3 retries.
- Review submission p95 < 300 ms; due-queue p95 < 200 ms (excluding cold starts).
- Dashboard does not make LLM calls.

---

## 11. Phased delivery plan

Effort assumes one full-time developer; adjust for part-time work.

### Phase 0 — Foundation and defect fixes (3–4 days)

- Fix extraction prompt placeholders; add prompt rendering test.
- Add pytest scaffold and CI job.
- Add `PROMPT_LOG_ENABLED` and production-safe logging behavior.
- Add CORS allowlist.
- Add note status/recall status fields and `content_hash`.
- Add idempotency keys and unique constraints.
- Decide/configure reranker default (`off`).

**Exit:** tests run in CI; extraction prompt renders correctly; retry-safe schema in place.

### Phase 1 — Data and vector foundation (5–7 days)

- Add `phase4_recall.sql` and `phase4_pgvector.sql`.
- Add `note_chunks`, `note_entities`, entity scoring columns, `recall_candidates`, `recall_cards`, `review_history`, `calendar_events`.
- Add `PgVectorStore` and replace the runtime Chroma vector store.
- Add chunking during note processing and write chunks/embeddings to Postgres.
- Add repositories and port methods.
- Backfill existing notes/entities.
- Fix `query_memory_items_by_entity_names` with a single SQL/RPC query.

**Exit:** new notes write chunks/notes/entities to Postgres; pgvector search returns correct user-scoped results; no application code path depends on local Chroma.

### Phase 2 — Understand stage (5–7 days)

- Extend extraction schema/prompt: importance, durability, knowledge units, due dates, commitments.
- Persist `notes.metadata` projection.
- Add entity consolidation/mention counting.
- Add candidate scoring and candidate lifecycle.
- Add idempotent `extract_note` worker stage.
- Unit tests for scoring/dedupe.

**Exit:** saving a note produces scored candidates and note-entity links; retries do not duplicate.

### Phase 3 — Remember stage: cards and scheduling (done)

- Add question-first generation prompts/services with cross-note context.
- Add validation and dedupe.
- Add candidate → question → card state transitions (answer generated on accept).
- Add Anki-style learning-step scheduler + review history.
- Add `generate_recall` worker stage and DLQ handling.
- Add recall repository tests.

**Exit:** eligible candidates produce grounded questions; accepted suggestions become cards; due queue and scheduling work in integration tests.

### Phase 4 — Review API and UI (API done; UI pending)

- ~~Add `/recall/due`, `/recall/cards/{id}/review`, candidate accept/reject~~ (done); stats + list endpoints pending.
- Add `ReviewPage`/`ReviewSession` with reveal/grade flow.
- Add `SuggestedCards` (question-only; accept reveals the generated answer).
- Add source links.
- Add mobile styles and empty/loading/error states.

**Exit:** a user can complete a review session end-to-end; grades update `next_due` and history.

### Phase 5 — Today dashboard and product re-centering (4–6 days)

- Add `/dashboard/today` aggregate.
- Build Today page with due count, commitments, highlights, summary, quick capture.
- Change default route to Today; move chat to Ask.
- Extend daily/weekly summaries with recall workload and “what to remember”.
- Update navigation and copy.
- Remove chat-first redirects.

**Exit:** login lands on Today; review and commitments are visible before chat; summaries reflect recall.

### Phase 6 — Act stage: calendar (4–5 days)

- Add commitment extraction/due-date resolution.
- Add `CalendarProvider` with stub and Google implementations.
- Add preview/confirm endpoints and pending-action UX.
- Add idempotent `calendar_events` persistence.
- Add tests for duplicate confirmations and timezone handling.

**Exit:** a detected commitment can be previewed, confirmed, and recorded exactly once using the stub; Google adapter works behind config.

### Phase 7 — Evaluation, hardening, deployment (5–7 days)

- Add recall eval fixtures/scripts and scheduler simulation.
- Add metrics/logging/alerts and cost tracking.
- Add rate limits, DLQ config, reproducibility docs.
- Load-test note processing and due queue.
- Update architecture docs and README.
- Final regression: retrieval eval thresholds, recall quality, calendar stub E2E.

**Exit:** all acceptance criteria met; production config documented; no known P0 defects.

### Milestone mapping to `final.md`

| `final.md` milestone | Plan phase | Notes |
| --- | --- | --- |
| 1. Core backend | Phase 0–1 | Existing backend reduces effort |
| 2. LLM extraction | Phase 2 | Extend existing extraction |
| 3. Embedding/index | Phase 1 | pgvector + chunks |
| 4. Recall Engine V1 | Phase 2–3 | New build |
| 5. Chat interface | Existing | Keep, reposition |
| 6. Recall UI | Phase 4 | New build |
| 7. Summaries | Phase 5 | Existing, extend |
| 8. Calendar integration | Phase 6 | New build |
| 9. Hybrid retrieval | Existing + Phase 1 | Reuse; add pgvector/chunks |
| 10. Polishing/testing | Phase 7 | New tests/evals |

---

## 12. File-level change map

| File / area | Change |
| --- | --- |
| `backend/sql/phase4_recall.sql` | New recall/candidate/card/review/calendar tables, entity/note_entities, task due dates, indexes |
| `backend/sql/phase4_pgvector.sql` | `vector` extension, chunk table, embedding columns, HNSW indexes, match functions |
| `backend/app/schemas/models.py` | New recall/calendar/dashboard models; extend extraction models |
| `backend/app/domain/ports.py` | Recall/calendar/scheduler/generator/clock/queue ports |
| `backend/app/domain/recall/` | New candidate scoring, question/answer generation, Anki scheduler, services |
| `backend/app/domain/calendar/` | New commitment/calendar services |
| `backend/app/domain/dashboard/` | New read-only Today aggregator |
| `backend/app/domain/memory/services.py` | Extend persistence wrappers; keep existing API |
| `backend/app/infrastructure/db/recall_repository.py` | New Supabase implementation |
| `backend/app/infrastructure/db/calendar_repository.py` | New Supabase implementation |
| `backend/app/infrastructure/db/memory_repository.py` | Add note_entities/entity score methods; fix entity queries |
| `backend/app/infrastructure/db/note_chunk_repository.py` | New chunk persistence/query helpers |
| `backend/app/infrastructure/vector/vectorstore.py` | Switch runtime to pgvector; remove Chroma from the app path |
| `backend/app/infrastructure/vector/pgvector_store.py` | New `VectorStore` implementation |
| `backend/app/infrastructure/llm/gemini_client.py` | Extraction fields, card generation, commitment support; split functions as needed |
| `backend/app/prompts/recall-v1/*` | Updated extraction, card, commitment prompts |
| `backend/app/workers/note_processor.py` | Stage machine, idempotency, enqueue recall |
| `backend/app/workers/recall_processor.py` | New candidate/card worker |
| `backend/app/api/routes/recall.py` | New recall endpoints |
| `backend/app/api/routes/calendar.py` | New commitment/calendar endpoints |
| `backend/app/api/routes/dashboard.py` | New Today aggregate |
| `backend/app/api/routes/notes.py` | Extend memory snapshot; reprocess |
| `backend/app/main.py` | Register new routers; CORS allowlist |
| `frontend/src/app/App.tsx` | Replace monolithic routing with Today/Review/Notes/Ask shell |
| `frontend/src/features/today/` | New Today page |
| `frontend/src/features/review/` | New review session and suggestions |
| `frontend/src/features/notes/` | Note list/detail/quick capture |
| `frontend/src/features/calendar/` | Commitments UI |
| `frontend/src/shared/api/` | Split client; add recall/calendar/dashboard calls and types |
| `evals/` | Add recall datasets, metrics, scripts, scheduler simulation |
| `backend/tests/` | New unit/integration/contract tests |
| `.github/workflows/` | Add pytest + recall eval jobs |
| `docs/Project_Architecture_Blueprint.md` | Update after pivot lands |
| `README.md` | Update quickstart, schema files, pivot positioning |

---

## 13. Definition of done

A note is “done” when:

1. It is saved and processed idempotently.
2. It has a summary, typed memory items, knowledge units, entities, embeddings/chunks, and commitments where applicable.
3. It produces zero or a small number of scored recall candidates.
4. Eligible candidates produce grounded Q/A cards with provenance.
5. The user can review due cards, reveal answers, grade them, and see the next due date.
6. Suggested questions can be accepted (answer generated) or skipped.
7. The Today dashboard shows due cards, commitments, highlights, and summary status.
8. A detected commitment can be confirmed into a calendar event exactly once.
9. Ask Northstar still works through the shared retrieval module but is visually secondary.
10. Tests, evals, logs, and metrics cover the new loop.

System-level done:

- Retrieval regression gates pass.
- Recall quality meets initial thresholds.
- Note processing retries are safe; DLQ is configured.
- No raw note text in production logs.
- CORS/auth/ownership checks are enforced.
- Schema migrations are idempotent and documented.
- Cost per 100 notes is measured and documented.

---

## 14. Decisions, trade-offs, and open questions

Locked decisions:

| Decision | Decision | Why |
| --- | --- | --- |
| Vector store | **pgvector-only at runtime**; no Chroma fallback | Removes Lambda-local disk dependency; unifies storage |
| ID type | Keep text IDs; use `text[]` for card sources | Avoids a risky UUID migration |
| Recall schema | Add `recall_candidates` in addition to `final.md` tables | The lifecycle in `final.md` requires persistent candidate state |
| Scheduling | Anki-style learning steps first; FSRS behind a port later | Matches the product decision; testable and familiar to users |
| Card approval | **Question-first suggestions; answer generated only on accept.** No auto-create tier | Keeps the user in control and avoids wasting answer-generation tokens |
| Calendar | MCP/Google Calendar **last**; stub first | Keeps MVP focused on the memory loop |
| Chat placement | “Ask” tab, not default | Preserves product identity |
| Summary trigger | Explicit/background, never on dashboard load | Latency and cost control |
| Logging | File prompt logs off by default in production | Privacy hygiene (notes are not sensitive yet, but logs should stay clean) |
| Existing typed tables | Keep and extend | They are richer than the minimum schema and already tested by usage |
| Platform | Responsive web only | No native mobile in MVP |
| Initial users | Developers | Technical card style and entity vocabulary |
| Timezone | UTC-only for MVP | Simplest correct default for a solo MVP |
| Multi-user sharing | Disabled | Out of MVP scope |

Resolved/remaining questions:

- ~~Target platform~~ → responsive web only for MVP.
- ~~Initial user~~ → developers.
- Calendar provider → stub in dev, Google Calendar/MCP last; OAuth credentials can be added later.
- ~~Data privacy~~ → notes are not sensitive for now; normal logging hygiene only.
- LLM budget → Gemini-only unless a concrete need appears.
- ~~Timezone~~ → UTC for MVP.
- Deadline → PR1–PR5 first, then the Anki-style recall feature.
- ~~Multi-user sharing~~ → disabled.

---

## 15. Immediate next PRs

Status: **PR1–PR8 are implemented and reviewed.** Local verification: `129 passed, 1 skipped`; route/schema tests that require `pydantic` run in CI on Python 3.11 (local Termux Python 3.14 cannot install a wheel). PR9+ are not started.

1. **PR 1 — Prompt + config guardrails (done):** fix extraction placeholders, add prompt tests, add `PROMPT_LOG_ENABLED`, CORS allowlist, reranker default.
2. **PR 2 — Initial recall migration (done):** `phase4_recall.sql` with candidates/cards/`review_history`/note_entities/entity fields/task due dates/indexes, plus `phase4_recall_scheduler.sql`.
3. **PR 3 — Recall ports and repositories (done):** Pydantic models, `RecallRepository`, `CalendarRepository`, entity/note-entity methods, tests with fakes.
4. **PR 4 — pgvector + chunks (done):** `PgVectorStore`, chunking, dual-write, match RPC, backfill script, retrieval parity test.
5. **PR 5 — Extraction v2 (done):** importance/durability, commitments/due dates, metadata projection, entity consolidation.
6. **PR 6 — Candidate engine (done):** scoring formula, dedupe, lifecycle, idempotent worker stage, tests.
7. **PR 7 — Question generator (done):** question-first prompts, validation, dedupe, persistence, per-note `recall_enabled` gate, tests.
8. **PR 8 — Anki scheduler + review API (done):** learning-step scheduler, review history, `/recall/due`, accept/reject, review API, migrations, tests.
9. **PR 9 — Review UI:** Review route/session, suggested cards (question-only → accept → answer), source links.
10. **PR 10 — Today + Ask re-centering:** dashboard aggregate, default route, nav, quick capture, summary extension.
11. **PR 11 — Calendar stub + Google adapter:** preview/confirm, idempotency, tests.
12. **PR 12 — Evaluation + hardening:** recall metrics, scheduler simulation, CI gates, observability, docs.

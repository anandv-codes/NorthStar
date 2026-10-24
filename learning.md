# Learning: NorthStar retrieval + chat workflow

## Big picture

NorthStar now combines retrieval, chat persistence, and agentic orchestration scaffolding.
The current system turns a user message into:

1. stored conversation state
2. context from memory and retrieval
3. an assistant response
4. updated thread history for the next turn

## Implemented retrieval flow

1. Validate and normalize the query.
2. Load a small slice of recent memory for rewrite context.
3. Score query quality.
4. If the query is good enough, ask Gemini for one rewrite.
5. Check rewrite risks:
   - missing numbers
   - negation loss
   - semantic drift
   - empty rewrite
6. Retrieve candidates from multiple sources.
7. Fuse candidates with RRF.
8. Optionally rerank the fused list.

## Retrieval sources

- Dense retrieval: existing Chroma-based semantic search.
- Sparse retrieval: BM25 over the current user’s notes.

## Why hybrid retrieval

- Dense search is good for meaning.
- BM25 is good for exact terms, IDs, task names, and rare words.
- RRF keeps both signals without overcomplicating scoring.

## RRF mental model

Each source gives a ranked list.
RRF adds a small score for each rank position.
If the same note appears in multiple lists, its score rises.
That makes strong cross-signal candidates bubble up naturally.

## Rewrite mental model

Rewrite is a helper, not the main retrieval strategy.
It is used only when the query looks reliable enough.
If the rewrite looks risky, the system falls back to the original query path.

## Reranker mental model

The reranker is a second-stage sorter.
It looks at the fused candidate list and reorders it using a stronger relevance signal.
The current implementation is lightweight and local, and it can be replaced later with:

- a cross-encoder
- an external API
- a Gemini rerank call

Enable the current reranker with `QUERY_RETRIEVAL_RERANKER=token_overlap` (or any truthy value like `true`).

## Implemented chat and memory flow

The chat stack is intentionally simple right now:

- a single-pane frontend chat shell
- persistent chat threads
- stored user and assistant messages
- a backend chat API surface
- thread history returned to the UI

### Chat turn lifecycle

1. User submits a message in the chat UI.
2. Backend creates or loads the thread.
3. The user message is stored.
4. Short-term conversation context is loaded.
5. Retrieval context is added from memory / notes.
6. The assistant response is generated.
7. The assistant message is stored.
8. The thread summary can be refreshed for long conversations.

### Memory layers

NorthStar is moving toward three memory layers:

- **Short-term memory**: recent messages from the active thread
- **Summary memory**: compact thread-level summary for long chats
- **Knowledge memory**: retrieved notes and memories from the existing retrieval pipeline

## Current feature set

- JWT auth
- query quality gate
- LLM rewrite with recent memory context
- rewrite risk detection
- dense retrieval
- BM25 sparse retrieval
- RRF fusion
- optional reranking hook
- chat UI shell
- persistent chat threads
- stored user/assistant messages
- chat API surface that returns thread history
- intent/planner scaffolding for the next agentic phase

## Design notes

- Keep the dense retriever unchanged.
- Keep the code modular and small.
- Prefer simple defaults.
- Postpone directory restructuring until the retrieval flow settles.
- Keep the learning doc updated as each phase lands, but do not mark the learning todo complete yet.

## Agentic workflow mental model

The planned flow is:

User message -> intent detection -> planner -> retrieval/tools -> merge results -> conversation memory -> LLM -> answer -> memory extractor

The key idea is that the planner chooses _what to do_ before the LLM answers:

- retrieval for knowledge lookup
- tool calls for side effects or external data
- direct response when no extra action is needed

This keeps the system easier to reason about than a single monolithic prompt.

## Deterministic upsert keys

Status: **decided, not yet implemented.** See `docs/code-review.md` (C1 + R7) for the defect
this fixes.

### The problem

`note_processor.process_sqs_message` is retried by SQS whenever it raises, and it raises on
any unhandled error so AWS will redeliver. On a retry the pipeline starts over: a new
`extraction_runs` row, and a new set of `tasks` / `facts` / `questions` / `decisions` /
`risks` / `concepts` rows, each with a freshly generated UUID.

The typed tables have no unique constraint beyond the random primary key, so nothing
conflicts. A note that succeeded halfway before a timeout ends up with every extracted item
stored twice. There is no good way to clean this up afterwards, because the duplicates are
indistinguishable.

The fix is not "check before insert" (racy, and still wrong under concurrent retries). The
fix is to give each row a **deterministic identity** and let the database enforce it with an
upsert.

### The pattern already used in this repo

`recall_candidates` is the working precedent:

```python
# backend/app/domain/recall/text_utils.py
def dedupe_key(item_type: str, text: str) -> str:
    digest = hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()
    return f"{item_type}:{digest}"
```

```python
# backend/app/infrastructure/db/recall_repository.py
_execute_upsert(RECALL_CANDIDATES_TABLE, row, on_conflict="user_id,dedupe_key")
```

```sql
-- backend/sql/phase4_recall.sql
create unique index if not exists idx_recall_candidates_user_dedupe
  on recall_candidates(user_id, dedupe_key);
```

`note_chunks` uses the same idea structurally: `unique (note_id, chunk_index)` plus
`replace_note_chunks` doing delete-then-insert.

### Key design for typed memory rows

Use a content hash scoped to the note that produced the row:

```
dedupe_key = sha1(normalize_text(item_text))
unique (user_id, source_note_id, dedupe_key)
```

Where `item_text` is the row's payload column: `description` for tasks, `content` for facts,
`question` for questions, `decision`, `risk`, `concept`. `normalize_text` is the existing
lowercase + collapse-whitespace + strip-punctuation helper in
`backend/app/domain/recall/text_utils.py` (move it to a neutral shared module rather than
importing `recall` from `memory`).

Reasoning for each part of the key:

- **`user_id`** — the table is multi-tenant; two users can have identical tasks.
- **`source_note_id`** — a task in note A and the same sentence in note B are two
  observations with separate lifecycles and separate provenance. Collapsing them globally
  would lose "which note said this" and make completion ambiguous. Idempotency is per note,
  not per user.
- **`dedupe_key`** — the content itself, normalized. Wording that differs only in case,
  spacing, or trailing punctuation is the same item.
- **`extraction_run_id` is deliberately *not* in the key.** A retry creates a new run; if the
  run id participated, retries would never collide. On conflict the row's
  `extraction_run_id`, `confidence`, and `updated_at` are refreshed to the newest run, while
  `task_id` (and therefore every link and candidate pointing at it) stays stable.

Why include the note at all instead of `(user_id, dedupe_key)`? Because the same
commitment can legitimately be mentioned on several days. Per-note keys keep those as
separate rows; deduplicating them is a *consolidation* concern (recall candidates already
do this globally with their own `dedupe_key`), not an ingestion concern.

### Implementation sketch

Migration (one per typed table; `dedupe_key` stays nullable so existing rows are unaffected —
Postgres treats NULLs as distinct, the same reasoning documented at
`backend/sql/phase4_recall.sql:141-142`):

```sql
alter table tasks add column if not exists dedupe_key text;

create unique index if not exists idx_tasks_user_note_dedupe
  on tasks(user_id, source_note_id, dedupe_key);
```

Repository:

```python
def insert_tasks(self, user_id, source_note_id, extraction_run_id, tasks):
    rows = [
        {
            "task_id": _new_id(),
            "user_id": user_id,
            "source_note_id": source_note_id,
            "extraction_run_id": extraction_run_id,
            "dedupe_key": content_key(task["description"]),
            "description": task["description"],
            ...
        }
        for task in tasks
    ]
    # Collapse duplicates inside a single LLM response first; Postgres refuses an
    # upsert that touches the same conflict target twice in one statement.
    rows = list({row["dedupe_key"]: row for row in rows}.values())
    return _execute_upsert(
        TASKS_TABLE, rows, on_conflict="user_id,source_note_id,dedupe_key"
    ) if rows else []
```

Two details that bite in practice:

1. **Dedupe in Python before the upsert.** `ON CONFLICT DO UPDATE` cannot affect the same
   row twice in one statement (`cardinality_violation`), and LLMs do occasionally emit the
   same item twice.
2. **`on_conflict` must name a full unique index.** PostgREST cannot target a partial index;
   this is why `idx_recall_candidates_user_dedupe` is not partial. Do not add a `where`
   clause to the typed-table indexes.

### What about edited notes?

The deterministic key is content-derived, so editing a note changes the keys of the items
whose text changed. Upsert alone leaves the old rows behind. Two acceptable policies:

- **Supersede (recommended).** Add `superseded_at timestamptz` to each typed table. After
  upserting the new set, mark rows for this `source_note_id` whose `dedupe_key` is not in the
  new set as superseded. Rows keep their ids, so `memory_item_entities`, `recall_candidates`,
  and any review history stay valid; queries filter `superseded_at is null`. This also
  preserves a task the user already completed instead of silently deleting it.
- **Replace.** Delete rows for the note that are not in the new set. Simpler, but destroys
  ids that other tables reference and loses user-modified status.

### Why not "delete by source_note_id, then insert"

This was the other candidate and it is worse here:

- New UUIDs on every run orphan `memory_item_entities` rows and `recall_candidates.item_id`
  references; those tables have no cascade for item ids.
- The delete and the insert are separate PostgREST calls with no transaction, so a crash
  between them loses data that previously existed.
- Reprocessing a note to fix one item wipes and re-creates all of them, resetting statuses
  the user changed.

It is only acceptable for derived, unreferenced data — which is exactly why
`replace_note_chunks` can use it for embeddings.

### Trade-offs to keep in mind

- **Wording changes create new rows.** That is intended (it is a different statement), but it
  means dedupe is not semantic. Semantic merging belongs in the recall/candidate layer,
  which already has `dedupe_key` + scoring for that.
- **The key is frozen to its normalization.** Changing `normalize_text` changes every future
  key while old rows keep their old keys. Either freeze the function or add a `key_version`
  column and bump it deliberately.
- **Per-note keys do not deduplicate across notes.** Two notes stating the same task produce
  two tasks. That is the correct provenance model; consolidating them is a separate feature.
- **Upsert requires the unique index to exist and to be deployed before the code.** Ship the
  migration first, then the repository change; add a startup/CI check that the index exists
  (the existing `test_sql_migrations.py` table list is a natural place).
- **SQS deduplication is not a substitute.** The queue's dedupe window is short and
  best-effort; deterministic row keys protect against redelivery at any distance.

### Verification checklist

1. Call `process_sqs_message` twice with the same body and assert typed row counts are
   unchanged and the `task_id`s are identical.
2. Retry after a simulated failure between two `insert_*` calls; assert no duplicates and no
   partial orphan set once the fix lands.
3. Assert a note with two byte-identical tasks stores one task.
4. Assert the same task text in two different notes stores two rows.
5. Assert `bump_entity_mentions` (still non-idempotent today) is driven by distinct note
   links, not by retry count.

# Code Review — Note Processing Pipeline & Recall Flow

**Date:** 2026-10-24
**Scope:** ingestion worker → context retrieval → LLM extraction → typed memory writes → recall candidates → cards/decks/review API
**Method:** static reading + targeted runtime probes (no fixes applied)
**Branch state:** working tree (uncommitted changes present); line numbers reflect the working copy

## Files reviewed

| Area | Files |
| --- | --- |
| Ingestion | `backend/app/workers/note_processor.py` |
| Extraction / memory | `backend/app/domain/memory/services.py`, `memory/extraction_v2.py`, `backend/app/infrastructure/db/memory_repository.py` |
| Retrieval | `backend/app/domain/query_retrieval/*` (`candidate_service`, `engine`, `scoring`, `entity_context_retriever`, `note_context_provider`, `hybrid_retriever`), `backend/app/infrastructure/vector/pg_vector_store.py` |
| LLM | `backend/app/infrastructure/llm/gemini_client.py`, `prompt_logger.py` |
| Recall domain | `backend/app/domain/recall/*` (`candidate_service`, `review_service`, `question_service`, `card_generation`, `deck_service`, `card_library`, `scheduler`) |
| API | `backend/app/api/routes/notes.py`, `backend/app/api/routes/recall.py` |
| Schema | `backend/sql/phase3_work_memory.sql`, `backend/sql/phase3_phase_a_entity_queries.sql`, `backend/sql/phase4_recall.sql`, `backend/sql/phase4_pgvector.sql` |
| Frontend | `frontend/src/features/recall/RecallVerifyPage.tsx`, `SuggestionCard.tsx`, `frontend/src/features/notes/NoteTakerPage.tsx` |
| Other | `backend/app/infrastructure/queue/sqs_consumer.py`, `backend/app/domain/ports.py` |

## Baseline

```
python -m pytest backend/tests -q
195 passed
```

Green tests, but none of the four Critical findings below are covered. No test references
`process_sqs_message`, `apply_deterministic_task_resolution`, `EntityContextRetriever`,
`parse_gemini_response`, `query_memory_items_by_entity_names`, or the accept-batch route.

## Severity summary

| ID | Severity | Finding |
| --- | --- | --- |
| C1 | Critical | Re-processing a note duplicates every typed memory row |
| C2 | Critical | LLM output is parsed but never validated; one bad item crashes the pipeline |
| C3 | Critical | Deterministic task resolution completes **all** tied tasks |
| C4 | Critical | Entity-linked retrieval is a silent no-op (three independent defects) |
| R1 | Required | Note is marked `completed` before resolution and indexing run |
| R2 | Required | Accept-candidate is not idempotent; retry becomes a 500 |
| R3 | Required | Accept-batch is N+1 and non-atomic; failures are reported as 200 |
| R4 | Required | Deck archive/restore updates cards one at a time, `limit=100000` |
| R5 | Required | Deck restore reactivates cards the user suspended manually |
| R6 | Required | `GET /recall/due` reports `total_due` as the page size |
| R7 | Required | Typed tables have no uniqueness constraint, so they cannot be upserted |
| R8 | Required | Entity importance is bumped on every retry, not every real mention |
| R9 | Required | Three different tokenizers/stopword sets decide what "matches" |
| R10 | Required | `apply_deterministic_task_resolution` returns `list | dict` |
| R11 | Required | Worker mutates global logging config and logs whole SQS events |
| R12 | Required | Untested code paths are exactly where the Critical defects live |

### Fix status (2026-10-24)

Applied in the small-fix pass: **C2, C3, R6, R10, R11**, plus the two unused
`recall.py` imports. **C4** was removed outright (see its resolution note).
Entity-linked retrieval is no longer part of ingestion.

Still open: **C1/R7** (deterministic upsert key — design documented in `learning.md`),
**R1, R4, R5, R8, R9, R12**. **R2** and **R3** are fixed; R2's accept transition is now a
single idempotent RPC.

Tests now: `python -m pytest backend/tests -q` → **230 passed**, including new coverage for
task-resolution ties, the single return shape, extraction-output validation, bulk candidate
reads, idempotent/racing accepts, the 207 batch contract, pair generation/fallback, conditional
worker writes, and the accept RPC contract.

---

## Critical findings

### C1 — Re-processing a note duplicates every typed memory row

**Where:** `backend/app/workers/note_processor.py:158-197`,
`backend/app/infrastructure/db/memory_repository.py:84-234`,
`backend/sql/phase3_work_memory.sql:39-51`

Every `insert_*` call allocates a fresh UUID and performs a plain `insert`:

```python
rows = [{"task_id": _new_id(), ...} for task in tasks]
return _execute_insert(TASKS_TABLE, rows)
```

The SQS handler re-raises on failure (`note_processor.py:372-374`) so AWS redelivers the
message. A retry after the point of partial success re-runs the whole pipeline: a second
`extraction_runs` row, a second set of tasks/facts/questions/decisions/risks/concepts, and a
second set of `memory_item_entities` links (those are upserted, so they collapse onto the
duplicate item ids instead of preventing them).

Because the typed tables have **no unique constraint** (only the primary key on the random
UUID), Postgres has nothing to conflict on. This is invisible in tests and in the single
happy-path run; it shows up as duplicated tasks and duplicated recall candidates after any
retry, timeout, or Lambda restart.

**Fix direction:** give each typed row a deterministic identity and upsert against it —
see the "Deterministic upsert key" section of `learning.md` and the decision log at the end
of this document.

---

### C2 — LLM output is parsed but never validated

**Where:** `backend/app/infrastructure/llm/gemini_client.py:208-215`,
consumed at `backend/app/workers/note_processor.py:140-152`

```python
parser = JsonOutputParser(pydantic_object=WorkMemoryExtraction)
parsed = parser.invoke(output_text)
return parsed
```

`JsonOutputParser` uses `pydantic_object` only to build the format-instructions prompt. It
does **not** run validation. Probe:

```python
JsonOutputParser(pydantic_object=WorkMemoryExtraction).invoke('{"tasks":[{"wrong":"x"}]}')
# -> {'tasks': [{'wrong': 'x'}]}      (no error, no validation)
```

The worker then indexes required keys directly:

```python
"action_items": [item["description"] for item in enrichment_res.get("tasks", [])],
"questions":    [item["question"]    for item in enrichment_res.get("questions", [])],
```

A model that returns `{"tasks": [{"task": "..."} ]}` — a very plausible near-miss — raises
`KeyError: 'description'` at line 148 and fails the whole note, losing the summary and all
other extracted items. The same unvalidated payload also flows into
`task_rows_with_scoring`, `insert_facts`, etc., which index their own required keys.

**Fix direction:** run real validation before use —
`WorkMemoryExtraction.model_validate(parsed)` (or `pydantic.TypeAdapter`) in
`parse_gemini_response`, and fail with a typed error the worker can distinguish. Then either
fail the note with a clear marker or degrade per-item instead of crashing the pipeline.
There is already a `ValidationError` path in `extraction_v2`; reuse that contract.

**Applied (2026-10-24):** `parse_gemini_response` now runs
`WorkMemoryExtraction.model_validate(parsed).model_dump(mode="json")`; covered by
`backend/tests/test_gemini_parse.py`. `due_date` keeps a pre-validator that extracts an ISO
date from prose (`"due 2026-06-13 by EOD"` → `"2026-06-13"`) and drops unparseable values,
so validation does not regress the existing `normalize_due_date` tolerance.

---

### C3 — Deterministic task resolution completes all tied tasks

**Where:** `backend/app/domain/memory/services.py:343-366`

```python
ranked.sort(key=lambda item: item[0], reverse=True)
top_score = ranked[0][0]
best = [task for score, task in ranked if score == top_score]

if top_score < 2 and len(best) != 1:
    diagnostics["selection_blocked_reason"] = "ambiguous_low_confidence_match"
    return _result([], diagnostics)

for task in best:
    repo.update_task_item(..., updates={"status": "completed"})
```

The ambiguity guard only fires when `top_score < 2`. A tie at a high score passes straight
through and the loop completes **every** tied task.

Probe (real function, fake repo):

```
open tasks: "deploy the staging cluster", "deploy the production cluster"
note text:  "Deploy cluster done"
# stopwords remove "done"/"the"
# both tasks score 2 (deploy, cluster)
selected: ['t1', 't2'] -> both completed
```

One completion sentence silently closes two unrelated tasks. There is no confirmation step
and no per-task audit beyond the appended resolution log, so the user only finds out by
looking at the task list.

**Fix direction:** ties are not a match. If `len(best) != 1`, block with
`ambiguous_multiple_matches` regardless of score (or require the note to name a
discriminator). Keep the existing diagnostics so the log explains why nothing was applied.

**Applied (2026-10-24):** the guard is now `if len(best) != 1`; covered by
`backend/tests/test_memory_resolution.py`.

---

### C4 — Entity-linked retrieval is a silent no-op

**Where:** `backend/app/domain/query_retrieval/entity_context_retriever.py:46`,
`backend/app/infrastructure/db/memory_repository.py:759-837, 904-930`,
`backend/sql/phase3_phase_a_entity_queries.sql`

The path is called on every note (`note_processor.py:86-111`), logs a tidy "N entity names
matched, M memory items" line, and contributes nothing. Three independent defects:

1. **Case mismatch.** `_find_matched_entity_names` returns lowercased names
   (`entity_context_retriever.py:46`); `_get_note_ids_by_entity_names` filters with
   `.in_("name", entity_names)` (`memory_repository.py:915`) against `entities.name`, which
   stores the original case (`phase3_work_memory.sql:104-111`). Postgres `text` comparison is
   case-sensitive, so `"project atlas"` never matches `"Project Atlas"`.

2. **Wrong column name.** `query_memory_items_by_entity_names` filters
   `memory_item_entities` on `f"{item_type}_id"` → `task_id`, `fact_id`, … but the table only
   has `item_id` (`phase3_work_memory.sql:113-118`). PostgREST returns an `APIError`, which is
   swallowed per item (`memory_repository.py:827-829`), so `memory_items` is **always `[]`**
   — including in the log line that says otherwise.

3. **Source table never written.** `note_entities` is created in `phase4_recall.sql:45-60`,
   and `upsert_note_entity_links` / `query_note_entities_by_source_note` exist
   (`memory_repository.py:283-318`), but no caller invokes either. The SQL that was supposed
   to back this path, `phase3_phase_a_entity_queries.sql`, contains **only commented-out
   statements** and was never applied.

Net effect: hybrid retrieval is the only live context source; the entity branch costs two
extra queries (one of which is an N+1 over every typed item for the user) and always returns
empty. See the decision log for the keep/fix/delete call.

**Resolution (2026-10-24):** the branch was **removed**, not fixed. Deleted
`entity_context_retriever.py`, `query_entity_names_for_user`,
`query_source_notes_by_entity_names`, `query_memory_items_by_entity_names`,
`upsert_note_entity_links`, `query_note_entities_by_source_note`, the
`phase3_phase_a_entity_queries.sql` reference file, and the prompt's
"linked entities and open items" section. Ingestion now uses hybrid retrieval only.
The `note_entities` table remains in `phase4_recall.sql` so a future entity linkage can be
built without a schema rewrite. A future design should replace the per-item N+1 with one
RPC and must fix the case-insensitive join and the `item_id` column.

---

## Required findings

### R1 — Note is marked `completed` before post-steps run

`note_processor.py:319-359` writes `status="completed"` and then runs task resolution and
vector indexing. Both post-steps catch and swallow their own exceptions, so a note can be
`completed` while its tasks were never reconciled and its chunks were never indexed. The UI
treats `completed` as "everything is ready", which is only true for the first half of the
pipeline.

*Direction:* finalize last, or model per-stage status (`enrichment_status`,
`recall_status`, `index_status`) instead of one boolean.

### R2 — Accept-candidate is not idempotent

`review_service.py:85-108` creates the card, then updates the candidate to `carded`. There is
no state check. A double-click, a client retry, or the batch endpoint retrying sends the
second call into `idx_recall_cards_user_candidate` (`phase4_recall.sql:177-179`), which
raises a DB error → 500. Two narrower faults sit nearby: the card insert and the candidate
update are not atomic, so a failure between them leaves an orphan card with the candidate
still `suggested`; and `contexts` is optional, so the same card can get a different question
on a retry.

*Direction:* return the existing card when `candidate.status == "carded"` and
`candidate.card_id` is set; make accept a single transaction/RPC.

**Applied (2026-10-24):** `accept_recall_candidate` (`sql/phase4_recall_accept.sql`) locks the
candidate row (`for update`), returns the existing card when one exists (including an orphan
from the old two-statement flow), and otherwise inserts the card and marks the candidate
`carded` in one transaction. The repository maps the RPC's `carded | not_found |
already_carded` result, and the in-memory fake mirrors the same semantics. Apply
`phase4_recall_accept.sql` to Supabase before deploying this code.

### R3 — Accept-batch is N+1 and non-atomic; failures return 200

`recall.py:143-158` fetches each candidate individually and builds each context separately
before calling `accept_candidates`, which loops again (`review_service.py:229-260`).
Per-candidate failures are collected into `results[]` and returned with HTTP 200; the client
must inspect `failed` to notice. There is no transaction across the batch, which is
acceptable for UX but means a mid-batch crash leaves a half-accepted set with no marker.

*Direction:* one `get_candidates_by_ids` query, one context builder per source note, and
return 207/400 when `failed > 0` (or document the partial-success contract explicitly).

**Applied (2026-10-24):** one bulk `get_candidates_by_ids` read, contexts cached per
`source_note_id`, the request capped at 100 ids, and **207** whenever `failed > 0`. Writes
remain per-item (best-effort is intentional for "accept all"), so the body is the contract.

### R4 — Deck archive/restore updates cards one at a time

`deck_service.py:241-268`:

```python
for card in repo.query_cards(user_id, status="active", deck_id=deck_id, limit=100000):
    repo.update_card(user_id, card["card_id"], {"status": "suspended"})
```

Two full scans plus one write per card. Both directions are unbounded (the `100000` is a
guard, not a bound) and both make a deck action O(n) round trips — the slowest user-facing
operation in the recall surface, and the one most likely to time out mid-loop.

*Direction:* one `update ... where user_id and deck_id and status = ...` via RPC, or a
`recall_cards` bulk update method.

### R5 — Deck restore reactivates cards the user suspended manually

Same code path. Archive suspends **all** active cards; restore reactivates **all** suspended
cards. A card the user suspended deliberately before archiving comes back active, and a card
suspended for a different reason is indistinguishable. The archive action is lossy.

*Direction:* record why a card was suspended (`suspended_reason = 'deck_archived'`) or
archive by deck state at read time rather than mutating every card.

### R6 — `GET /recall/due` reports `total_due` as the page size

`recall.py:446-466`:

```python
cards = list_cards(..., limit=limit)   # limit <= 200
return DueCardsResponse(cards=cards, total_due=len(cards))
```

`total_due` is at most 50 by default. Any client showing "N due" under-reports as soon as
the backlog exceeds the page size, and the endpoint fetches full card rows purely to count
them.

*Direction:* a `count` query for `total_due`; keep the page for `cards`.

**Applied (2026-10-24):** `total_due` comes from a `count="exact"` query
(`query_cards_page(..., limit=1)`) matching the same active/due filters.

### R7 — Typed tables have no uniqueness constraint

`phase3_work_memory.sql:39-51, 53-62, 64-75, …`. Every table is `id uuid primary key` plus
free-form columns. That is the schema-level cause of C1 and it also blocks the obvious fix
(`upsert(..., on_conflict=...)`).

For contrast, the tables that *do* need to be idempotent already have the right shapes:
`entities` has `unique(user_id, name)` (`:110`), `memory_item_entities` has a unique index on
`(user_id, item_type, item_id)` (`:119-121`), `recall_candidates` has
`(user_id, dedupe_key)` (`phase4_recall.sql:143-144`), and `note_chunks` has
`(note_id, chunk_index)` (`phase4_pgvector.sql:27`). The typed memory tables were simply
never given the same treatment.

### R8 — Entity importance is bumped on every retry

`note_processor.py:199-209` calls `bump_entity_mentions` after insertion. On a retry the
pipeline re-runs, so the same entity gains importance again even though the user only
mentioned it once. Importance is meant to reflect how often an entity appears across notes,
not how often the worker was redelivered.

*Direction:* bump from the entity link upsert inside the same deterministic key, or make the
bump a function of the number of distinct `source_note_id`s.

### R9 — Three different tokenizers decide what "matches"

| Location | Behaviour |
| --- | --- |
| `query_retrieval/utils.py:22-33` | lowercases, `[a-z0-9]+`, `RETRIEVAL_STOP_WORDS` |
| `memory/services.py:369-401` | lowercases, `[a-z0-9]+`, its own 30-word set incl. `pending/done/complete/completed` |
| `recall/text_utils.py:30-34` | lowercases, `[a-z0-9]+`, a larger set incl. question words |

The stopword lists disagree, so the same sentence can be "ambiguous" to task resolution and
"informative" to recall scoring. This is the kind of duplication that silently drifts: a
word added to one list never reaches the others.

*Direction:* one shared `tokenize(text, stopword_set=...)` helper; keep only the deliberate
differences (e.g. resolution dropping completion verbs).

### R10 — `apply_deterministic_task_resolution` returns `list | dict`

`memory/services.py:270-282` returns a bare list when `include_diagnostics=False` and a dict
otherwise. Every caller has to narrow the union before use; `note_processor.py:336` only ever
uses the dict branch. A single return shape with an always-present `updated_tasks` key would
remove the branch and the type errors that come with it.

**Applied (2026-10-24):** the function now always returns
`{"updated_tasks": [...], "diagnostics": {...}}`; `include_diagnostics` is gone.

### R11 — Worker mutates global logging and logs whole SQS events

`note_processor.py:40-41` calls `logging.basicConfig(...)` at import time; in Lambda that
mutates the runtime's root logger, and it silently does nothing if the platform configured
logging first. `logger.info(f"...")` is used throughout (no lazy `%s` args), and
`lambda_handler` logs `json.dumps(event)` (`:377-378`) — every record body on every attempt,
including on retries where the payload is unchanged. Full prompt/response logging is also
persisted by `log_gemini_interaction`; production logging volume and note content exposure
should be a deliberate choice, not a default.

*Direction:* configure logging in the entrypoint once, log `note_id`/`user_id`/`messageId`
rather than the event, and use parameterized logging.

**Applied (2026-10-24):** the worker uses `getLogger(__name__)`, and `lambda_handler` logs
only the record count and the failing `messageId`. Remaining f-string call sites were left
untouched (a separate, mechanical cleanup).

### R12 — Untested code paths are exactly where the Critical defects live

All 195 tests pass, and none of them touch `process_sqs_message`,
`apply_deterministic_task_resolution`, `EntityContextRetriever`, `parse_gemini_response`, or
the recall routes. C1-C4 are not subtle bugs; they are the normal behaviour of code with no
test asserting the contract. The highest-value additions:

1. `parse_gemini_response` rejects a payload with missing required keys (C2).
2. `apply_deterministic_task_resolution` applies nothing on a tie (C3).
3. `EntityContextRetriever` returns a linked note for a mixed-case entity name (C4).
4. `process_sqs_message` called twice leaves one set of typed rows (C1).

---

## Simplification opportunities (optional)

- **`query_memory_items_by_entity_names`** (`memory_repository.py:759-837`) is the most
  over-built function in the codebase: six sequential table scans, an N+1 entity lookup per
  item, a swallowed `APIError`, and a dynamic column name built by `rstrip("s")` (which is
  also wrong for `concepts` → `concept`, and for any future word ending in `s`). Either move
  it into the SQL from `phase3_phase_a_entity_queries.sql` (one RPC) or delete it with the
  entity path.
- **`insert_*` boilerplate** in `memory_repository.py:84-234` — six near-identical functions
  differing only in table, id column, and text column. A small spec table plus one generic
  insert would remove ~120 lines.
- **Duplicate dedupe logic** between `note_processor.py:130-138` (manual ordered set) and
  `recall/candidate_service.py` (`dict.fromkeys`-style dedupe), and between the resolution
  tokenizer and the query tokenizer (see R9).
- **Unused imports** in `recall.py:44,51` (`move_card_to_deck`, `list_suggestions` imported
  but not used in the route module) and the unused `due_cards` variable in
  `review_service.py`.
- **`list | dict` return** (R10) — one shape.
- **`_summarize_top_sources`** (`hybrid_retriever.py:121-153`) builds labels only for logging;
  fine as-is, but it is a second place that must learn about any new retrieval channel.
- **`deck_service._stats_by_deck`** can become one grouped `count(*) filter (...)` query
  instead of loading every card row to bucket in Python.

---

## What is good

- **The recall candidate pipeline is properly idempotent.** `dedupe_key` +
  `(user_id, dedupe_key)` upsert (`recall/text_utils.py:24-27`,
  `recall_repository.py:71`, `phase4_recall.sql:141-144`) is exactly the pattern the typed
  tables are missing. The comment at `phase4_recall.sql:141-142` even explains the
  PostgREST/NULL constraint correctly.
- **Hybrid retrieval is well factored.** Dense, sparse, exact, and rewrite channels are
  independent functions composed by `rrf_fuse`, with a deterministic tie-break order
  (`hybrid_retriever.py:101-117`) and an explicit "exact identifier wins" rule. The
  `exact` channel (`fetch_exact_results`, identifier regex in `query_retrieval/utils.py:12-16`)
  is a real, working counterpart to entity matching.
- **Recall scoring is separated from persistence.** `candidate_engine`/`candidate_service`
  produce candidates from an extraction; the repository only stores them. That boundary is
  what makes the recall flow testable.
- **SM-2 scheduling is isolated** in `recall/scheduler.py` with pure functions and no I/O.
- **Error containment is deliberate.** Post-steps catch and degrade rather than losing the
  note; the problem is only that they degrade silently (R1) and that the same pattern hides
  C4.
- **`replace_note_chunks` is delete-then-insert**, so vector indexing is naturally
  re-runnable per note (`pg_vector_store.py:114`).
- **Tests are fast and hermetic** (195 in a few seconds), so adding the four contract tests
  above is cheap.

---

## Decisions and next steps

Recorded from the review discussion. These are decisions, not yet implemented.

### 1. Use a deterministic upsert key (documented in `learning.md`)

Chosen over "delete by `source_note_id` then insert" because the deterministic key keeps
retries idempotent **and** preserves stable row ids across reprocessing (links, candidates,
and review history reference `task_id` et al.; deleting rows would orphan or cascade them).
See `learning.md` → "Deterministic upsert keys" for the key design, the required migration,
and the trade-offs.

### 2. Use a proper validator

`parse_gemini_response` must validate, not just parse (C2). The target behaviour:

- `WorkMemoryExtraction.model_validate(parsed)` before returning;
- a typed error (`ExtractionValidationError`) carrying the failing JSON path;
- the worker records a failure marker and does not write partial typed rows.

### 3. Chat deprecation caveat

The instruction was: if a finding is chat-only, ignore it because chat may be deprecated.
Applied as follows:

- **Entity-linked retrieval is not a chat path.** `EntityContextRetriever` is constructed only
  by `note_context_provider.fetch_note_context`, which is called only from
  `note_processor.py:88`. Chat retrieval (`query_retrieval/services.py` / chat orchestration)
  never calls it. So "if this is for chat, ignore" does not discharge C4.
- **Recall, ingestion, and the worker are not chat.** They remain in scope.
- Chat-specific code inside the reviewed surface is limited to the shared `get_chat_model`
  used for card question generation; the recall flow does not depend on the chat UI.

### 4. Is entity-linked retrieval worth it? (probe more, no changes)

**Current value: zero, at a nonzero cost.** It is ingestion-only, always returns
`memory_items=[]`, and its note lookup fails on case. It costs two extra queries per note,
one of which is an N+1 over every task/fact/question/decision/risk/concept the user owns.

**What it would add if fixed:** deterministic recall of notes that share a named entity with
the current note, independent of embedding similarity — useful for "everything about Project
Atlas" even when the notes are worded differently. The hybrid `exact` channel does **not**
cover this: it matches identifier-shaped tokens (`ITEM-4101`, `CVE-2026-1234`) via a regex,
not known entity names. So there is real, non-overlapping value in principle.

**What it costs to make real:** create the missing RPCs from
`phase3_phase_a_entity_queries.sql` (currently comments), populate `note_entities` at
ingestion, and fix the case handling (lowercase both sides or use `citext`). That is a
schema migration plus a worker change — not a one-line fix.

**Recommendation:** either commit to it (one RPC + `note_entities` write + case-insensitive
join, with a test asserting a linked note is returned) or delete it outright (remove
`EntityContextRetriever`, the two repository methods, and the dead SQL file; keep hybrid +
exact). Keeping it in its current state is the worst option: it inflates the prompt's
context budget with nothing and the log line actively misleads.

**Decision taken (2026-10-24): delete it.** Entity-linked retrieval is gone from ingestion;
`note_entities` and the future linkage idea are deferred. Hybrid + exact remain.

No code changes were made for this item.

### Suggested order of work

1. **C2** — validate LLM output (small, unblocks reliable testing of everything downstream).
2. **C1 + R7** — deterministic upsert key + migration; add the double-process test.
3. **C3** — block ties in task resolution; add the tie test.
4. ~~**C4 / entity verdict** — fix or delete, per the recommendation above.~~ **Done:** deleted
   (2026-10-24).
5. **R2, R3, R6** — recall API idempotency and correctness.
6. **R4, R5** — deck archive/restore as bulk operations with a suspension reason.
7. **R1, R8, R9, R10, R11** — pipeline hygiene and shared helpers.

---

## Appendix — probes run

All probes were run against the working copy with throwaway scripts outside the repo.

### A1 — `JsonOutputParser` does not validate

```python
from langchain_core.output_parsers import JsonOutputParser
from app.schemas.models import WorkMemoryExtraction

parser = JsonOutputParser(pydantic_object=WorkMemoryExtraction)
print(parser.invoke('{"tasks":[{"wrong":"x"}]}'))
# {'tasks': [{'wrong': 'x'}]}
```

### A2 — Tied high-score tasks are all completed

Fake repo recording `update_task_item` calls; two open tasks
("deploy the staging cluster", "deploy the production cluster"); note text
"Deploy cluster done".

```python
result = apply_deterministic_task_resolution(
    user_id="u1", raw_text="Deploy cluster done", source_note_id="n1",
    include_diagnostics=True, repo=fake_repo,
)
# diagnostics.selected_task_ids == ['t1', 't2']
# both tasks marked completed
```

### A3 — Entity path returns empty

- `_find_matched_entity_names` → `["project atlas"]`
- `entities.name` contains `"Project Atlas"`
- `.in_("name", ["project atlas"])` → no rows
- `memory_item_entities` has `item_id`, query uses `task_id` → `APIError`, swallowed
- `note_entities` count → 0 (table never written)

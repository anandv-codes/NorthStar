# NorthStar — Codebase Suggestions for Interview Readiness

**Scope:** this file is *not* a product roadmap. Every item here exists for one reason —
it removes an attack surface an interviewer will press on, or it creates an artifact you
can point at when asked "why".

Keep this separate from `docs/interview_questions.md`. That file is what to *know*.
This file is what to *change* so you have less to explain away.

**Rule of thumb:** an interviewer's follow-up questions cluster around the same six
weaknesses. Close four of them and the interview changes character — you stop defending
and start choosing.

---

## Tier 1 — Removes the biggest attack surfaces

These are the four things that turn "interesting follow-up" into "gotcha". Do these first.

### 1. Make ingestion atomic and idempotent

**Change:** add `ingest_note_memories(p_user_id, p_note_id, p_extraction_run_id,
p_payload jsonb, p_now timestamptz)` — one Postgres function that writes tasks, facts,
questions, decisions, concepts, entity links, and contributions in a single transaction.
Persist the raw extraction payload in `extraction_runs.payload` with `fanned_out boolean`
*before* the fan-out, so a retry replays stored data instead of re-calling the LLM.

**Files:** `backend/sql/` (new migration), `backend/app/workers/note_processor.py`,
`backend/app/infrastructure/db/memory_repository.py`.

**Why it helps the interview:** it converts three separate "you have a bug" moments
(Q4, Q5, Q6) into one "here's how I solved it" story. It also gives you the strongest
available answer to *"design something transactional in a PostgREST architecture"* —
because you did it, twice, and can talk about both.

**Effort:** M (1–2 days). Highest ROI item in this document.

**The line you get to say:** *"Ingestion used to be twelve non-transactional PostgREST
calls, so a redelivery duplicated every typed memory. Now the fan-out is one RPC over a
persisted payload — at-least-once delivery is safe because the attempt key is stable."*

**Done (2026-10-28) — commit `8216d5f`. Applied to the live database before the API/worker.**

**What changed:**
- `backend/sql/phase7_atomic_ingestion.sql`: `extraction_runs.payload jsonb` and
  `fanned_out boolean`; a unique index on `extraction_runs(note_id)` makes `note_id` the
  stable attempt key; `begin_extraction_run(...)` reuses-or-creates the run; and
  `ingest_note_memories(...)` locks the run `for update`, writes every typed row, entity,
  link, and goal contribution in one transaction, then returns the persisted rows. A retry
  sees `fanned_out = true` and returns those rows instead of inserting again.
- `note_processor.py`: the LLM call happens only when `extraction_runs.payload` is null;
  the payload is saved *before* the fan-out, and the twelve PostgREST calls collapse into
  one RPC. A duplicate delivery of an `indexed` note is acknowledged without re-running.
- `memory_repository.py`: `begin_extraction_run`, `save_extraction_payload`,
  `ingest_note_memories`. `create_extraction_run` was removed — it minted a new run id per
  call, which the unique index now forbids.

**What I learned:**
- **The attempt key is the design.** "Idempotent" means nothing until you name the key a
  redelivery repeats. `note_id` is stable in the SQS message, so one run per note is the
  invariant; a fresh UUID per attempt is the bug, not the fix.
- **Persist before the side effect.** Saving the payload before the fan-out is what makes a
  retry cheap: "payload present" means "the LLM already ran". Saving it after the fan-out
  leaves a crash window that pays for the extraction again.
- **`fanned_out` is a commit marker, not a cache flag.** It is set in the same transaction
  as the writes, so a retry sees either both the rows and the marker, or neither.
- **The marker is only trustworthy with a lock.** Without `select ... for update`, two
  concurrent deliveries both read `fanned_out = false` and both insert.
- **Natural-key `on conflict` needs a natural key.** Links de-duplicate on their primary key
  and contributions on `(commitment_id, note_id)`; the typed tables still have no natural
  key (item 5), so they rely on the attempt-level guard. That is the honest boundary.
- **PostgREST can still be transactional.** The transaction boundary is the RPC, not the
  HTTP request: one `supabase.rpc(...)` is one transaction, and an exception rolls back
  every write in it.
- **Legacy rows are the migration's real test.** Existing runs had already fanned out with
  `payload = null`; the migration marks them `fanned_out = true`, so a redelivery cannot
  duplicate them. Reprocessing one costs a redundant LLM call and then no-ops.
- **Idempotency has to reach the terminal state.** A redelivery of an `indexed` note used to
  fail the state machine (`indexed -> enriched`); it is now an acknowledged no-op.

**Verified on the live database (2026-10-28):** 16 runs backfilled to `fanned_out = true`,
still one run per note; `begin_extraction_run` returned the same run id twice; a throwaway
probe note fanned out to exactly one row in each typed table plus five links, and the second
`ingest_note_memories` call returned `duplicate: true` with the same rows and no new writes.
All probe rows were deleted (notes, run, entities, links: 0 left). 327 tests pass, including
a replay test that asserts zero LLM calls on the second attempt.

**Still open:** concurrent *first* deliveries can both call the LLM before either saves the
payload (the fan-out is still exactly-once). Item 5's unique constraints remain
defense-in-depth, not a prerequisite.

---

### 2. Fix the status vocabulary and the `completed` lie

**Change:** one `Literal`/enum for note status (`processing | enriched | indexed | failed`),
plus `indexed_at`. Move `completed` to *after* `index_note`, and stop swallowing indexing
failures — set `failed` (or `indexed=false` with a reason) so the UI can show it.

**Files:** `backend/app/schemas/models.py`, `backend/app/workers/note_processor.py:317-350`,
`backend/sql/phase3_work_memory.sql` (add a `CHECK` or enum).

**Why it helps the interview:** Q3 is currently a trap you walk into. After this it's a
question where you describe a fix you made. It also removes the "five names for one
status" finding (Q10) and the `_create_synthetic_anchor_note` oddity (Q22) collapses into
"anchors are `kind=anchor`, they're deliberately not indexed".

**Effort:** S–M.

**The line you get to say:** *"`completed` used to mean 'the LLM returned'. That was a
lie — a note could be completed and invisible to retrieval. Now status is a real state
machine and indexing failure is visible."*

**Done (2026-10-28) — commit `5eb5093`.**

**Applied and verified on the live database (2026-10-28):** 16 rows migrated to
`indexed` with `indexed_at` backfilled, 0 `completed` remaining, 0 rows outside the
vocabulary, 0 indexed rows missing a timestamp, 0 non-indexed rows carrying one. The
`CHECK` constraint itself is confirmed by the migration's success plus a `pg_constraint`
query, since PostgREST does not expose catalogs.

**What changed:** `NoteStatus = processing | enriched | indexed | failed`; new
`indexed_at` and `index_error` columns; `phase6_note_status.sql` backfills legacy
`completed` rows and adds a `CHECK`; `domain/memory/note_status.py` holds the transition
table; the processor writes `enriched` after extraction and only writes `indexed` after
`index_note` succeeds; an indexing error now sets `failed` + `index_error`; the UI
"ready" filter maps to `indexed` only.

**Learnings:**
- The lie was **two** defects: writing the terminal status *before* the step that made
  the note retrievable, and an `except` that logged and continued. Fixing only the
  ordering would still have hidden failures.
- `enriched` had to become a real state, not a synonym. The frontend treated it as
  terminal (`TERMINAL_NOTE_STATUSES`), so polling stopped on a note that was not yet
  searchable. Terminal is now `{indexed, failed}`.
- A strict `Literal` turns a vocabulary change into a **deploy-order constraint**: run the
  migration before the API, or legacy `completed` rows fail response validation. Recorded
  in the commit message rather than discovered in production.
- Legacy `completed` rows cannot be distinguished from successfully indexed ones — the old
  code discarded the error. They are backfilled to `indexed` with
  `indexed_at = processed_at`; a note whose indexing failed is repairable by reprocessing.
  That assumption is stated in the migration, not buried.
- The regression test drives the whole pipeline with fakes and asserts the exact status
  sequence `["enriched", "indexed"]`, then asserts `failed` + `index_error` when
  `index_note` raises. Asserting the *sequence*, not just the final value, is what stops
  the terminal write drifting back above indexing.

---

### 3. Remove or gate `POST /notes/poll/process-jobs`

**Change:** delete the route, or put it behind an admin claim **and** a feature flag, and
scope it to the caller's own messages. The `sqs_consumer` already replaced it.

**Files:** `backend/app/api/routes/notes.py:265`.

**Why it helps the interview:** this is a genuine cross-tenant + cost-amplification hole
(Q28). Deleted, it's a one-sentence answer: *"that was a debug endpoint, it's gone — the
consumer process owns the queue."* Present, it's a five-minute grilling.

**Effort:** XS (delete) / S (gate). Best effort-to-benefit ratio in the repo.

**The line you get to say:** *"No HTTP path drains the queue. Work is pulled by the
worker, not triggered by a user."*

**Done (2026-10-28) — commit `12a0589`.**

**What changed:** route deleted (not gated), the now-unused `poll_sqs_messages` /
`delete_sqs_message` imports removed, the deployment note corrected, and a route-surface
test added in `backend/tests/test_notes_routes.py`.

**Learnings:**
- Deletion beat gating: the consumer already owned queue consumption, so an admin claim
  plus feature flag would have preserved the hole behind a second permission check. A
  route with no caller is not a feature.
- The hole was two-dimensional — **cross-tenant** (any authenticated user's request could
  process other users' queued notes) and **cost amplification** (one request could trigger
  ten LLM pipelines). Say both out loud; the second is the one interviewers press on.
- Patching the import *source* would not have fixed it: `notes.py` imported the poller
  functions directly. Deleting the route is what made the unused import visible.
- The guard asserts the route is absent from `app.routes`, including under any future
  prefix, so a re-introduction fails CI instead of reappearing silently.

---

### 4. Add RLS — and change the credential

**Change:** `alter table … enable row level security` plus
`using (user_id = auth.uid())` on every user-scoped table. **Then stop connecting with
the service-role key** for user-scoped requests — forward the user's JWT to PostgREST so
`auth.uid()` resolves. Keep the service role only for migrations and background jobs that
legitimately cross tenants.

**Files:** `backend/sql/` (new migration), `backend/app/infrastructure/db/supabase_client.py`,
`backend/.env.example`.

**Why it helps the interview:** Q27 is the highest-stakes question in the set. Today the
correct answer is "there's no enforcement, it's a convention". After this, the answer is
"there are policies, and the credential that can bypass them isn't used for user paths" —
which is the answer a Senior gives.

**Effort:** L. Also the riskiest change here, because a wrong policy is an outage. If you
can't do it before the interview, do the cheap half: one `_scoped(user_id)` query helper,
plus a test that fails when a repository query omits `user_id`. Then your answer becomes
*"defence in depth: RLS is the target, and here's the interim guard that's already in CI."*

**The line you get to say:** *"Tenancy is enforced by the database, not by remembering to
write `.eq('user_id')`."*

---

## Tier 2 — Turns "we know, but haven't" into "done"

Each of these closes a specific question's gap. Pick by which questions you're weakest on.

### 5. Unique constraints on typed memories

**Change:** `unique(source_note_id, extraction_run_id, content_hash)` on tasks/facts/
questions/decisions/concepts; a partial unique index for the active extraction run per
note.

**Why:** Q4 becomes "here's the natural key" instead of "we'd duplicate". Note this is
only fully correct *together with* item 1 — constraints without a stable attempt key give
you dedupe without consistency.

**Effort:** S.

**Done (2026-10-28) — commit `c412439`. Applied to the live database before the API/worker.**

**What changed:**
- `backend/sql/phase8_typed_memory_keys.sql`: `content_hash` on tasks/facts/questions/
  decisions/concepts, backfilled with `md5(lower(btrim(<content>)))`, and a unique index on
  `(source_note_id, extraction_run_id, content_hash)` for each.
- `ingest_note_memories` now inserts with `on conflict (...) do update ... returning`, so a
  duplicate item inside one payload reuses the existing row id. Without that, the first
  duplicate would abort the whole note and every retry would replay the same poison payload.
- The "partial unique index for the active run per note" half of this item is already
  covered by phase 7's full unique index on `extraction_runs(note_id)` — the stronger
  invariant.

**What I learned:**
- **A unique index is only as strong as its hash.** `lower(btrim(...))` makes `"Same  task"`
  and `"same task"` the same memory; without normalization the constraint is defeated by
  whitespace. The backfill and the RPC must use the exact same expression, or the index and
  the writer disagree about what a duplicate is.
- **Adding a constraint to existing data is a migration, not a DDL line.** I checked the live
  corpus for exact duplicates *before* writing the index; a single pair would have made the
  migration fail. The migration deliberately fails loudly rather than deleting a
  user-visible row.
- **`on conflict do update ... returning` is the clean way to resolve a duplicate and still
  get the row id.** `do nothing` returns no row, which breaks the entity links that need the
  id; a no-op update (`set description = tasks.description`) returns the existing row.
- **Constraints change the failure mode, not just the data.** Before this, a duplicate inside
  one LLM payload was silently inserted twice; with a bare unique index it would become a
  poison message. The RPC had to learn to absorb the conflict.
- **NULL is not a value in a unique index.** Chat-created rows have no extraction run and a
  NULL key, so they sit outside the constraint by design — they are one-per-anchor-note
  anyway.
- **Two migrations, one invariant.** Phase 7's attempt key prevents *retry* duplication;
  phase 8's content key prevents *payload* duplication. The interview answer is the pair,
  not either one alone.

**Verified on the live database (2026-10-28):** all 61 existing typed rows have a hash and
zero duplicate keys; a probe payload with two case/whitespace-variant tasks and two identical
facts persisted exactly one row each (5 links, 1 entity), and the replay still returned
`duplicate: true`. Probe rows deleted (0 left). 352 tests pass.

---

### 6. Route-level tests for the untested main path

**Change:** add `TestClient` tests for `POST /notes` (create → 202 → status), `/auth/login`
(bad password, inactive user), `/auth/refresh` (410), and one `/chat/message` happy path.
You don't need full coverage — you need the *walked path* covered.

**Why:** Q30 currently ends with you admitting the main user journey has no tests. Four
tests change the ending. Also catches dependency-wiring bugs that pure-function tests
structurally cannot.

**Effort:** S (≈100 lines). Highest testing ROI.

**Done (2026-10-28) — commit `049a184`.**

**What changed:** 7 `TestClient` tests in `backend/tests/test_main_path_api.py` —
`POST /notes` → 202 → pollable status, anonymous rejection, `/auth/login` bad password /
inactive user / token issuance, `/auth/refresh` 410, and one `/chat/message` happy path.
`httpx` is now declared in `requirements-dev.txt`.

**Learnings:**
- There were **no** `TestClient` tests before this; the suite was entirely pure-function
  and contract tests. That is exactly why the wiring bugs this item targets were invisible.
- Auth is exercised by overriding the `get_current_user_id` dependency. One test
  deliberately does *not* override it, so the real bearer check still has to reject
  anonymous calls.
- Route modules import collaborators by value (`from ... import put_note_item`), so
  `monkeypatch.setattr(notes_routes, "put_note_item", ...)` is required. Patching
  `supabase_client.put_note_item` would silently do nothing.
- `TestClient(app)` as a context manager runs the lifespan, which warms up Gemini and
  embeddings. `WARMUP_ON_STARTUP=false` keeps the suite offline and fast.
- `pytest.ini` already sets `-q`; passing `-q` again produces `-qq`, which suppresses the
  pass count. Small trap when reading CI output.
- Response models are part of the contract: these tests fail if a repository row shape and
  its `response_model` drift apart, which pure-function tests cannot see.

---

### 7. Fail the build on eval regression

**Change:** pin a baseline per dataset in `rag-eval.yml` and fail on a Recall@5 drop beyond
noise. Require a written note to move the baseline.

**Why:** Q34 becomes "we gate on it" instead of "it's report-only". It also retroactively
justifies the reranker decision (Q14) as a *process*, not a lucky observation.

**Effort:** S. The datasets and metrics already exist — this is CI YAML plus a JSON baseline.

---

### 8. Make BM25 search non-mutating

**Change:** pass `k1`/`b` into `search()` or construct per call; never assign
`self.model.k1`. Then the cached index is genuinely read-only.

**Why:** Q16 is a "is your code thread-safe" question with an uncomfortable answer. The
fix is a handful of lines and converts it into a positive story about shared-state hygiene.

**Effort:** XS.

---

### 9. Replace the content fingerprint with a cheap version signal

**Change:** `max(updated_at)` + `count(*)` per user, or a `notes_version` column bumped by
a trigger, instead of loading all notes and hashing them on every retrieval.

**Why:** Q15 is the "find the scaling wall in your hot path" question. Today the answer is
"we read the whole corpus per query". After, it's "one indexed aggregate".

**Effort:** S. Measures well in `loadtest/k6-read.js` afterwards — take the before/after p95
and quote it. Numbers make this answer land.

---

### 10. Hoist the per-request thread pool

**Change:** module-level `ThreadPoolExecutor` (or a small pool sized to DB connection
limits) instead of `ThreadPoolExecutor(max_workers=3)` inside `retrieve()`.

**Why:** small, but it's the kind of detail that separates "I wrote this" from "I read this".
Also a legitimate p95 win under concurrency.

**Effort:** XS. Do it in the same PR as item 9 and measure once.

---

## Tier 3 — Cheap artifacts that make you look like an owner

### 11. Write five ADRs

**Change:** `docs/adr/` with one page each for: (a) PostgREST over an ORM, (b) pgvector over
Chroma, (c) rule-based chat routing over an LLM classifier, (d) JWT with no refresh
(7-day token), (e) RPC for atomicity.

**Why:** every "why did you do it this way" question has a citable artifact. This is the
single cheapest way to look like the person who owns the architecture rather than the
person who inherited it. Format is four headings: Context / Decision / Consequences /
Alternatives rejected.

**Effort:** S (an hour each, and you already know the content — it's in the questions doc).

---

### 12. Fix the stale docs

**Change:** `docs/blueprint.md` and `docs/Project_Architecture_Blueprint.md` still describe
Chroma, `vectorstore.py`, `token_overlap` reranking, and "direct client adapters rather than
a repository abstraction". All four are wrong.

**Why:** an interviewer reads the README and the blueprint first. Finding a doc that
contradicts the code costs you credibility before you've said a word. Delete, or add a
one-line banner: *"Historical — describes the pre-pgvector design. See architecture map in
docs/interview_questions.md §3."*

**Effort:** XS. Do this one tonight.

---

### 13. Delete the dead weight

**Change:** `backend/app/handlers/` (`memory.py` is unreferenced), `backend/package.json`
(declares only `requests@^0.3.0` in a Python service), `backend/chroma_data/`,
`chroma_data/` at root, `backend/node_modules/` if present.

**Why:** `test_package_imports` and `compileall` already prove nothing imports them. Dead
top-level directories invite "what's this?" questions with no good answer — and every one
of those is a minute you're not spending on a question you prepared for.

**Effort:** XS.

**Done (2026-10-28) — commit `d9cd70a`** (the legacy `handlers/notes.py` was removed
earlier in `1dd894f`; this finished the directory).

**What changed:** deleted `backend/app/handlers/`, `backend/package.json` +
`package-lock.json`, both `chroma_data/` directories, and `backend/node_modules/`. Added
`backend/tests/test_repo_hygiene.py` so the paths cannot silently return.

**Learnings:**
- `vectorstore.py` is now a pgvector shim, so the Chroma path was genuinely orphaned.
  Worth checking before deleting a data directory: a live store would recreate it on the
  next run and hide the mistake.
- `chroma_data/` and `node_modules/` are `.gitignore`d, so they never appeared in
  `git status`. Dead weight hides precisely where you are not looking; the guard test
  checks the working tree, not git.
- `backend/package.json` declaring `requests@^0.3.0` is a Python/JS category error. The fix
  is deletion, not migration — there is no Node code in the backend that could depend on it.
- Guarding the *absence* is what makes this stick: a deletion commit alone can be undone by
  any stray `npm install`, and the guard then fails loudly instead of the directory quietly
  returning.

---

### 14. Introduce a `Settings` object

**Change:** `pydantic-settings` class replacing scattered `os.getenv` at import time; pass
the instance explicitly instead of freezing it at module import.

**Why:** closes Q35's runner-up ("rotating a key needs a restart") and makes half the test
suite easier to write, because config becomes injectable rather than ambient. Also fixes
the `lru_cache`-keyed-by-API-key rotation problem.

**Effort:** M. Do it *after* the interview if time is short — it's a nice-to-have answer,
not a gotcha.

---

### 15. Add a Dockerfile + compose for local dev

**Change:** one `Dockerfile` (python:3.11-slim) and a `compose.yaml` with a Postgres image
plus `pgvector`, so the nine migrations apply against a real database in one command.

**Why:** "can you run it locally?" is asked in almost every real loop, and the honest
current answer involves a Supabase project, a service-role key, and manual SQL. Compose
turns that into `docker compose up` — and it's also how you'd test item 4 safely.

**Effort:** M.

---

### 16. Put the architecture map in the README

**Change:** copy §3 of `docs/interview_questions.md` into `README.md` (trimmed), with the
ingestion and chat sequence diagrams as ASCII blocks.

**Why:** it sets the frame before you speak. If the first thing an interviewer reads is an
accurate, honest pipeline diagram, they ask better questions — and you answer them well.
This is subtly one of the highest-ROI items on the list.

**Effort:** XS.

---

## What NOT to change (just know the answer)

Interview-readiness is also about knowing where to stop. These are all defensible as-is;
changing them costs days and buys you little in an interview.

| Thing | Why leave it | What to say instead |
|---|---|---|
| **7-day JWT, no refresh** | Real work: rotation, denylist, `is_active` check, client changes | "Deliberate: no refresh, `/auth/refresh` returns 410 so stale bundles fail loudly. Cost is a long-lived bearer token with no revocation — here's the fix I'd sequence." |
| **Token in `localStorage`** | Moving to cookies = CSRF + CORS + SameSite work across the client | "Risk concentration, mitigated by centralising auth in `httpClient.ts` so the swap is one file." |
| **No ORM** | It's a coherent architecture, and RPC-heavy SQL is the actual answer | "PostgREST means atomicity lives in Postgres functions — which is where it belongs." |
| **Rule-based chat router** | Rules are the right call at this scale | "Regulate deterministically, generate probabilistically — and never pay for generation you can't ground." |
| **1.5s polling** | SSE/WebSockets is new infra for a 30-second job | "Polling self-heals on the next tick; SSE doesn't. At this job duration, polling is the cheaper correctness story." |
| **Reranker off by default** | Already correct — it measured worse | "An optimisation you can't measure is a liability. The flag is the receipt." |
| **No Alembic** | Migrating a live database to get a migration tool is a bigger risk than the tool removes | "Idempotent DDL, enforced by a test. The gap is ordering and rollback, not re-runs." |

---

## Suggested order of work

| When | What | Why then |
|---|---|---|
| **Tonight (30 min)** | Items 12, 13, 3 | Delete contradictions and the cross-tenant endpoint. Pure upside, no risk. |
| **Day 1** | Item 2 (status fix), item 8 (BM25), item 10 (pool) | Small, self-contained, immediately answerable. |
| **Day 2** | Item 1 (atomic ingestion RPC) | The big one. Do it alone, with a test that redelivers a message twice and asserts no duplicates. |
| **Day 3** | Item 6 (route tests), item 7 (eval gate), item 11 (ADRs) | Now you have a story and evidence. |
| **If time remains** | Item 4 (RLS), item 15 (compose) | Highest value, highest risk. |
| **After the interview** | Items 9, 14 | Genuine improvements, not interview leverage. |

---

## How this maps to the question set

| Fix | Questions it neutralises |
|---|---|
| 1. Atomic ingestion | Q4, Q5, Q6 (partly), Q35 |
| 2. Status vocabulary | Q3, Q10, Q22, Q35 |
| 3. Poll endpoint | Q28, Q27 |
| 4. RLS + credential | Q27, Q26 (partly), Q28 |
| 5. Unique constraints | Q4, Q10 |
| 6. Route tests | Q30 |
| 7. Eval gate | Q34, Q14 |
| 8. BM25 immutability | Q16 |
| 9. Version signal | Q15 |
| 10. Shared pool | Q15 |
| 11. ADRs | Q7, Q11, Q19, Q25, Q5 |
| 12–13. Docs + dead code | Q11, and the first impression |
| 14. Settings | Q35 (runner-up) |
| 16. README map | Every question — it sets the frame |

**Read that table by column, not by row.** The four fixes that clear the most questions are
1, 2, 3, and 4 — which is exactly Tier 1.

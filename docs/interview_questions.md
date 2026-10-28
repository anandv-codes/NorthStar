# NorthStar — Technical Interview Dossier

**Purpose:** a complete, self-contained study guide for interviewing on *this* codebase.
Every answer here is grounded in the actual code, not generic textbook material.

**Calibration:** Mid-level candidate, demanding market. Bar sits slightly above a
comfortable Mid loop — you will be pushed into failure modes and trade-offs normally
reserved for Senior. Questions are marked **Core** (Mid bar) or **Stretch** (Senior bar).

**Status when this doc was written:** Q1–Q3 were already asked and answered live.
See §6 for what happened and where the session stopped (mid-Q4).

---

## Table of contents

1. [How to use this document](#1-how-to-use-this-document)
2. [The 60-second pitch](#2-the-60-second-pitch)
3. [Architecture map (as-built)](#3-architecture-map-as-built)
4. [The 35 questions](#4-the-35-questions)
   - A. Ingestion & async (Q1–Q6)
   - B. Data & persistence (Q7–Q11)
   - C. Retrieval (Q12–Q18)
   - D. Chat & derived data (Q19–Q24)
   - E. Security (Q25–Q29)
   - F. Quality, ops & production (Q30–Q35)
5. [How you will be scored](#5-how-you-will-be-scored)
6. [Session history](#6-session-history)
7. [Cheat sheet](#7-cheat-sheet)

---

## 1. How to use this document

Read it in three passes:

1. **§3 Architecture map** — read until you can draw the ingestion and chat sequences
   from memory on a whiteboard. If you can't draw it, you can't defend it.
2. **§4 questions** — do not memorise the wording. Memorise the *structure* of each
   answer: what it is → why it's built that way → what breaks. Interviewers can tell
   memorisation from understanding within one follow-up.
3. **§7 cheat sheet** — the numbers. Being able to say "800 chars, 100 overlap, RRF k=60,
   7-day token" without hesitating reads as ownership. Not knowing them reads as
   "I inherited this repo".

**The single most important habit:** every answer should end with a trade-off or a
failure mode. An answer that only describes what the code does is a description. An
answer that says "and here's what it costs us" is an engineer.

---

## 2. The 60-second pitch

> NorthStar is a personal work-memory system. You dump raw notes in — meeting scraps,
> decisions, half-thoughts — and the backend turns them into structured memory:
> tasks, facts, decisions, concepts, questions, and entities. That memory then does two
> things. First, it feeds retrieval so a chat assistant can answer questions about your
> own history with citations. Second, it feeds a spaced-repetition system that resurfaces
> what you're at risk of forgetting. It's FastAPI + Supabase Postgres on the backend,
> React + Vite on the frontend, with ingestion pushed through SQS to a separate worker
> process, and retrieval using hybrid BM25 + pgvector fused with reciprocal rank fusion.

Say that in under 60 seconds. It signals: product, pipeline, two consumers of the memory,
and the two hard technical choices (async ingestion, hybrid retrieval).

---

## 3. Architecture map (as-built)

### 3.1 Layers

| Layer | Location | Responsibility |
|---|---|---|
| API routes | `backend/app/api/routes/` | HTTP, request validation, auth dependency, status codes |
| Domain services | `backend/app/domain/` | Business logic, orchestration, scoring, scheduling |
| Ports | `backend/app/domain/ports.py` | `Protocol` interfaces for every repository/adaptor |
| Infrastructure | `backend/app/infrastructure/` | Supabase, SQS, Gemini, pgvector, JWT, embeddings |
| Workers | `backend/app/workers/` | SQS consumer and the ingestion pipeline |
| Schemas | `backend/app/schemas/models.py` | Pydantic DTOs (~750 lines) |

There is **no ORM**. Supabase PostgREST is the data access layer, called through
`supabase-py`. There is no Alembic — schema lives in nine hand-run `.sql` files.

### 3.2 Note ingestion — the real sequence

```
POST /notes                          (202 Accepted, returns immediately)
  └─ uuid4() note_id, insert row: status="processing"
  └─ if PROCESS_NOTES_INLINE: BackgroundTasks.add_task(_process_note_job)   [debug path]
     else:                    send_note_job(...) → SQS                        [prod path]

SQS consumer (app/workers/sqs_consumer.py, systemd service)
  └─ poll 5 messages, 20s long-poll, graceful SIGTERM
  └─ per message: process_sqs_message(body)
       1. get_note_item(user_id, note_id)
       2. fetch_note_context(...)          ← hybrid retrieval over EXISTING corpus
       3. commit.regenerate(); call_gemini_api(...)   ← the only LLM call
       4. create_extraction_run(status="completed")   ← note: status completed AT CREATION
       5. update_note_item(..., summary=...)
       6. insert_tasks / insert_facts / insert_questions / insert_decisions / insert_concepts
       7. upsert_entities + bump_entity_mentions
       8. persist_note_contributions, link entities to memory items
       9. generate_candidates (recall), generate_questions (recall)
      10. update_note_item(status="completed", recall_status=...)   ← line 317
      11. apply_deterministic_task_resolution(...)                  ← line 323
      12. index_note(...)  → chunk + embed + upsert note_chunks     ← line 343
  └─ delete_sqs_message on success only
  └─ on exception: do NOT delete → SQS redelivers → DLQ after maxReceiveCount
```

Three things to internalise, because they are the interview:

- **The note being ingested is not in the vector index yet.** Retrieval at step 2 sees
  *prior* notes plus entity links, never the note in flight. Indexing happens last.
- **`status="completed"` is written at step 10, before resolution (11) and indexing (12).**
  So `completed` means "the LLM returned", not "fully processed".
- **Steps 6–9 are separate PostgREST calls.** There is no transaction spanning them.

### 3.3 Retrieval — the real sequence

```
query
  ├─ channel 1: dense embeddings, original query        ┐
  ├─ channel 2: BM25 sparse                             ├─ ThreadPoolExecutor(3), parallel
  ├─ channel 3: dense embeddings, rewritten query       ┘   (only if alternate_query set)
  └─ channel 4: exact identifier matches              (sequential, deterministic)

fuse_candidates(...)  →  score = Σ weight / (RRF_K + rank),  RRF_K = 60
                          exact-identifier channel weight = 3
  └─ optional rerank: cross-encoder, only if QUERY_RETRIEVAL_RERANKER != "off"
  └─ clamp limit to [1, 20]
```

Defaults: `QUERY_RETRIEVAL_RRF_K=60`, `QUERY_RETRIEVAL_CANDIDATE_MULTIPLIER=3`,
`QUERY_RETRIEVAL_EXACT_ID_WEIGHT=3`, `QUERY_RETRIEVAL_RERANKER=off`.

### 3.4 Chat — the real sequence

```
POST /chat/message
  └─ handle_chat_message
      ├─ _try_resolve_pending_action(...)     # did the user confirm a proposed tool call?
      ├─ RoutingOrchestrator.route(...)       # rule-based classifier (not an LLM)
      ├─ optional retrieve_query_context(...) # hybrid retrieval
      ├─ assess_grounding(...)                # strong / weak / conflict / no_context
      │    └─ if not allow_answer → fallback_message, no LLM call
      ├─ GeminiChatModel.generate(...)        # answer with citations
      └─ _try_propose_tool_call(...)          # mutating actions become pending actions
```

Grounding thresholds (`backend/app/domain/chat/guardrails.py`):
`top_score < 1.4` → `weak`; dissenting weight `>= 0.9` and runner-up
`>= 0.7 × top` → `conflict`; `top_score < 2.2` with fewer than 2 supporters → `weak`.

### 3.5 Data model spine

| Table | Key | Notes |
|---|---|---|
| `notes` | `note_id` (uuid) | `status`, `raw_text`, `summary`, `recall_*` |
| `extraction_runs` | `extraction_run_id` | One row per attempt. **No unique on `note_id`** |
| `tasks` / `facts` / `questions` / `decisions` / `concepts` | fresh uuid | **No unique constraints** |
| `entities` | `unique(user_id, name)` | Upserted — genuinely idempotent |
| `memory_item_entities` | `unique(user_id, entity_id, item_type, item_id)` | Upserted |
| `note_chunks` | `unique(note_id, chunk_index)` | `vector(768)` |
| `recall_candidates` | `unique(user_id, dedupe_key)` | Upserted |
| `recall_cards` | `unique(user_id, candidate_id)` | SM-2 state |
| `commitments` | `commitment_id`, `max_active = 3` | Unique index protects auto-write |

### 3.6 Auth

HS256 JWT, `iss=northstar-backend`, `aud=northstar-client`, `type=access`,
**7-day expiry** (`ACCESS_TOKEN_EXPIRE_MINUTES=10080`). Argon2 password hashing.
`/auth/refresh` deliberately returns **410 Gone** — refresh was removed, forcing
re-login. Token lives in `localStorage`. `get_current_user_id` verifies signature,
alg, aud, iss, type, and that `sub` exists — **nothing else**.

---

## 4. The 35 questions

---

## A. Ingestion & async

### Q1 — Walk me through a note from `POST /notes` to fully processed *(Core)*

**What I'm testing:** do you understand your own request path, or just the happy-path
narrative?

**Answer**

`POST /notes` returns **202 Accepted** immediately. It mints a `uuid4` `note_id`,
inserts the row with `status="processing"`, then branches:

- **Production:** `send_note_job(...)` publishes `{user_id, note_id, created_at, raw_text}`
  to SQS. `app/workers/sqs_consumer.py` picks it up in a separate systemd process.
- **Debug:** if `PROCESS_NOTES_INLINE` is set, it goes to FastAPI `BackgroundTasks`.

The worker calls `process_sqs_message`, which retrieves context from the *existing*
corpus, makes one Gemini call, records an `extraction_run`, writes the typed memories,
upserts entities and contributions, generates recall candidates and questions, marks
the note `completed`, applies deterministic task resolution, and finally chunks +
embeds + indexes into pgvector. Success deletes the SQS message; failure leaves it for
redelivery and eventual DLQ.

**Go deeper**
- Retrieval during ingestion sees prior notes only — indexing is step twelve, not three.
- Order matters: status flips to `completed` before resolution and indexing.
- The whole fan-out is non-transactional.

**Trap:** describing it as "store chunks, then retrieve, then call the LLM". That
inverts the pipeline and shows you've never traced the code.

---

### Q2 — Why SQS plus a separate worker instead of just `BackgroundTasks`? *(Core)*

**What I'm testing:** whether you can justify infrastructure rather than accept it.

**Answer**

`BackgroundTasks` runs *in the API process*, after the response. That means:

- CPU-heavy work (embedding 800-char chunks with a sentence-transformer) competes with
  request handling on the same event loop worker.
- No durability. Process restart or deploy = the job is gone. The note sits at
  `processing` forever.
- No retry, no backoff, no dead-letter. Failures vanish into a log line.
- No backpressure. A burst of writes becomes a burst of in-process work.

SQS gives durability, at-least-once delivery, a visibility timeout for long jobs, a
redrive policy to a DLQ, and independent scaling — you can run three worker processes
without touching the API tier.

The inline path still exists deliberately: it's a local debugging affordance so
breakpoints in `note_processor` fire inside the request. It is **not** production-safe.

**Go deeper**
- The trade-off you accept: **at-least-once**, not exactly-once. Which means ingestion
  must be idempotent — and here it partially isn't (Q4).
- Also: 2 services to deploy, 2 to monitor, and local dev needs either a real queue or
  the inline flag.

**Trap:** "SQS is more scalable" with no dimension named. Scalable in throughput,
durability, or isolation? Name it.

---

### Q3 — What does `status="completed"` actually mean here? *(Core)*

**What I'm testing:** whether you read your own status machine critically.

**Answer**

It means "the LLM call returned and the derived rows were written". It does **not** mean
fully processed.

`note_processor.py` sets it at line 317 — **before** `apply_deterministic_task_resolution`
(line 323) and **before** `index_note` (line 343). Worse, `index_note` is wrapped in a
`try/except` that only logs:

```python
except Exception as exc:
    logger.warning(f"Vector indexing failed; note stored without embeddings: {exc}")
```

So a note can be `completed`, visible with a summary, and **permanently invisible to
retrieval** — no chunks, no embedding, no error surfaced to the user. Silent partial
failure.

**Go deeper**
- Why is it set there? The code comment says it's deliberate: setting status only after
  question generation means a concurrent recall *toggle* can rely on status. So the
  placement is a decision with a cost, not pure sloppiness — say that.
- The fix is not just "move the line". You need a status vocabulary that can express
  intermediate reality: `processing → enriched → indexed` (+ `failed`), with `indexed_at`.
- Related smell: the vocabulary is inconsistent across the codebase —
  `processing | completed | enriched | processed | failed` all appear.

**Trap:** "completed means processing finished." It's the exact thing this question
is designed to catch.

---

### Q4 — Where is ingestion idempotent and where does it break? *(Stretch)*

**What I'm testing:** idempotency as a *per-table audit*, not a vibe.

**Answer**

**Idempotent (upsert with a real unique constraint):**
`entities` `(user_id, name)`, `memory_item_entities`
`(user_id, entity_id, item_type, item_id)`, `note_chunks` `(note_id, chunk_index)`,
`recall_candidates` `(user_id, dedupe_key)`, `commitments`, `period_summaries`.

**Not idempotent:**
- `extraction_runs` — primary key is a freshly minted uuid, and there's **no unique
  constraint on `note_id`**. Every delivery adds a run row.
- `tasks`, `facts`, `questions`, `decisions`, `concepts` — each row gets `_new_id()`
  (`memory_repository.py:92`) and the tables have **no unique constraints**.

So an SQS redelivery duplicates every typed memory. This is a real, unpatched defect —
it's written down as still-open in `docs/code-review.md`.

**Go deeper**
- The natural key can't be `hash(task_id + note_id)` — `task_id` is minted at insert
  time, so the hash is different every attempt. Circular.
- It can't be a pure content hash either, because the retry re-calls a nondeterministic
  LLM and gets different wording.
- The workable shape: mint `extraction_run_id` **before** the LLM call, persist it on
  the note (or use `note_id` as the attempt key), and key typed rows on
  `(source_note_id, extraction_run_id, content_hash)`. Then a retry replays the same
  attempt id and conflicts instead of duplicating.
- Even better: persist the extraction payload once, then fan out from stored JSON —
  retries replay data instead of re-calling the model (see Q5).

**Trap:** "the note row is idempotent because `note_id` is stable, so the pipeline is
idempotent." The note row is; its children are not.

---

### Q5 — The fan-out is non-transactional. Fix it. *(Stretch)*

**What I'm testing:** can you design a real correctness boundary, not say "add a
transaction" into a PostgREST-shaped void.

**Answer**

The problem: `insert_tasks` … `insert_concepts` … entity links are separate HTTP calls,
each its own transaction. A crash after `insert_tasks` leaves a partial memory set, and
the message is redelivered, so the retry either duplicates (no constraints) or, once you
add constraints, leaves a note with tasks from attempt 1 and facts from attempt 2 —
mixed provenance plus an abandoned `extraction_run`.

**"Wrap it in a transaction" is not available.** PostgREST gives you one statement per
call. You cannot hold a Python-side transaction across them.

**The fix already exists in this repo, once.** `backend/sql/phase4_recall_accept.sql`
solves the identical shape for candidate→card:

> *"Why an RPC: the previous flow inserted the card, then updated the candidate in two
> PostgREST calls. A retry could hit the (user_id, candidate_id) unique index, and a
> crash between the two writes left an orphan card."*

So: one `create or replace function ingest_note_memories(p_user_id, p_note_id,
p_extraction_run_id, p_payload jsonb, p_now timestamptz) returns jsonb`, doing every
insert in a single server-side transaction, idempotent on the attempt key.

**The awkward part — the LLM call can't be rolled back.** Options:

1. **Persist-then-fan-out (outbox).** Step 1: store the raw extraction payload in
   `extraction_runs.payload jsonb` with `fanned_out=false`. Step 2: RPC reads the stored
   payload and fans out atomically, setting `fanned_out=true`. A retry reuses the stored
   payload — no second LLM call, no nondeterminism, and you stop paying twice for the
   same note.
2. **Resume, don't restart.** Per-table `INSERT … ON CONFLICT DO NOTHING` plus an
   `extraction_runs.completed_at` marker; a retry skips completed sub-steps.

Option 1 is the stronger answer because it also fixes the double-billing and the
divergent-wording problem at the same time.

**Go deeper**
- Cost: one more column, one more RPC, and a migration. Cheaper than a duplicate-memory
  incident.
- Honest failure still matters: if the RPC fails, mark the note `failed` — better than
  a half-written memory set.

**Trap:** "just wrap it in a transaction" (not possible), or "just add unique
constraints" (gives you dedupe without consistency, and content hashes won't match
across nondeterministic retries).

---

### Q6 — Worker lifecycle, DLQ, and poison messages *(Core)*

**What I'm testing:** operational thinking about the consumer, not just the function.

**Answer**

`sqs_consumer.run_forever()`:

- Polls 5 messages with a 20-second long-poll, loops immediately.
- Registers `SIGTERM`/`SIGINT` handlers that set a `_stopping` flag — it finishes the
  in-flight message, then exits. That's what makes a systemd restart not corrupt a note.
- Deletes the message **only on success**. On exception it logs and leaves it — SQS
  redelivers after the visibility timeout (600s in the runbook).
- Redrive policy: `maxReceiveCount=3`, then DLQ for manual inspection.

**Go deeper**
- **The failure mode nobody plans for:** a message that always fails costs
  `3 × 600s = 30 minutes` before it reaches the DLQ, and each attempt re-runs the LLM
  and re-writes partial memories. Poison-message handling and idempotency are the same
  problem wearing different hats.
- There is **no exponential backoff** — SQS standard queues don't do that. If you want
  it you need delay queues or explicit re-publish with `DelaySeconds` and an attempt
  counter in the message.
- A 600s visibility timeout is longer than most LLM calls but shorter than a slow
  embedding run plus retries on a loaded box — know your p99 before you pick it.
- Wrong-but-common claim: "the DLQ retries automatically". It doesn't. Nothing drains a
  DLQ unless you build it.

**Trap:** saying retries use exponential backoff because SQS has a redrive policy.

---

## B. Data & persistence

### Q7 — No ORM, no migrations tool. Defend it, then attack it. *(Core)*

**What I'm testing:** can you hold two positions at once — justify a choice and name
its cost.

**Answer**

**Defence:** `supabase-py` + PostgREST means the database *is* the API. No mapping
layer, no N+1 surprises from lazy loading, no ORM session lifecycle to manage, no
identity map to reason about. For a single-user-scoped CRUD app with heavy vector SQL,
that's mostly upside — the vector work goes through `match_note_chunks` RPC anyway, so
an ORM would just be a thin wrapper you fight.

**Attack:** you lose things you don't notice until you need them.

- `_execute_with_retry` only retries `httpx.RemoteProtocolError` on a freshly built
  query. It is a *transport* retry, not a transaction retry.
- No unit-of-work, so multi-table invariants (Q5) are unenforceable client-side.
- Schema drift is unmanaged — no Alembic, nine hand-run `.sql` files, applied manually
  in README order.
- Aggregations and joins become multiple round-trips or RPCs.

**Go deeper**
- The honest framing: PostgREST pushes you toward **server-side functions for anything
  atomic**, which is a fine architecture — but it only works if you actually write them.
  This repo wrote one (`accept_recall_candidate`) and stopped.
- `test_sql_migrations.py` statically asserts `if not exists` in every migration — a
  cheap guard against a genuinely annoying failure (partial re-run).

**Trap:** "ORMs are slow" as the whole answer, or "we should add SQLAlchemy" without
noticing that atomicity, not mapping, is the actual gap.

---

### Q8 — `repo: X | None = None` defaulting to a module singleton. What does that buy, what does it cost? *(Core)*

**What I'm testing:** whether you understand your own hand-rolled DI.

**Answer**

Ports are `Protocol`s in `domain/ports.py`. Services take an optional repository and
fall back to a module-level factory (`get_memory_repository()`, `get_recall_repository()`).

**Buys:** testability without a framework. Pass a fake, get a pure unit test. The full
suite runs with almost no dependencies installed (Q30). You also avoid import-time
coupling to Supabase in pure-logic modules.

**Costs:**

- The default path is a **process-wide mutable singleton** — configuration and
  connection state are captured at first use, so tests leak state between cases unless
  they `monkeypatch` the factory.
- Two ways to construct the same object means "which one am I getting?" is a real
  question. Reading a service body doesn't tell you.
- Nothing prevents a service from reaching past its port. The abstraction is by
  convention, not enforcement.

**Go deeper**
- The stronger pattern for this size: explicit constructor injection at the edge
  (FastAPI `Depends`), singletons only in `main.py` wiring. One place decides lifetimes.
- Watch for services constructed at **import time** — `ChatRoutingOrchestrator` is
  instantiated at module import in `domain/chat/services.py`, which means env vars read
  then are frozen (Q35).

**Trap:** "it's dependency injection because of Protocols." Protocols are typing;
injection is who constructs what, and when.

---

### Q9 — Nine hand-run SQL files, no Alembic. How do you not break prod? *(Core)*

**What I'm testing:** migration discipline when the tooling is absent.

**Answer**

The current discipline is real but manual:

- Every migration is **idempotent**: `create table if not exists`,
  `create index if not exists`, `create or replace function`.
- `backend/tests/test_sql_migrations.py` statically enforces that (`if not exists`
  present, expected functions defined). It's a lint, not a migration engine, but it
  catches the most common re-run failure.
- README fixes the apply order.

**What's missing:** no version table, no checksums, no rollback, no CI application, no
drift detection. Applying a migration out of order on a live database is unrecoverable
without a restore.

**Go deeper**
- The minimum viable upgrade is a `schema_migrations(version, applied_at, checksum)`
  table plus a tiny runner — 60 lines, and it converts "hope the README order is right"
  into an auditable fact.
- Alternatively, a real tool (Alembic, Atlas, Sqitch) — but note that the RPC-heavy
  style means most "migrations" here are `create or replace function`, which are
  naturally idempotent and easy to keep declarative.
- Interviewer-grade nuance: idempotent DDL makes *re-running* safe but does nothing for
  *ordering* or *rollback*. Those are different problems.

**Trap:** "we use `if not exists` so migrations are safe." Safe to re-run ≠ safe to
sequence.

---

### Q10 — Schema review: what would you change about the memory tables? *(Stretch)*

**What I'm testing:** whether you can look at a schema and see invariants that aren't
written down.

**Answer**

Three things.

1. **Missing uniqueness on typed memories.** `tasks`, `facts`, `questions`, `decisions`,
   `concepts` have uuid PKs and no natural key. Nothing prevents duplicates at the
   database layer — the invariant "one task per source note per extraction attempt"
   exists only in the worker's head (Q4).
2. **`extraction_runs` has no unique on `note_id`.** So "the run for this note" isn't a
   queryable concept; you get a pile of attempts and have to guess which one counts.
   Add `completed_at` and `superseded_by`, or a partial unique index on the active run.
3. **Status vocabulary is inconsistent.** Across code you'll find `processing`,
   `completed`, `enriched`, `processed`, `failed`. That's four names for what should be
   a single `Literal` / Postgres enum. Every misspelling is a silent branch that never
   fires.

Plus: `notes.embedding` and `note_chunks.embedding` both exist — decide which is
authoritative for retrieval (currently chunks) and whether the note-level vector is
dead weight.

**Go deeper**
- Add `CHECK` constraints for status values, or a real enum — the DB then rejects the
  typo you'd otherwise ship.
- `memory_item_entities(user_id, entity_id, item_type, item_id)` is the right shape: a
  polymorphic join with a natural key. Point at it as the model the typed tables should
  follow.
- `source_note_id` on every memory table means provenance is recoverable — good. Use it
  in the unique key.

**Trap:** "add an `id` column" — they already have one. The issue is the *natural* key.

---

### Q11 — Chroma → pgvector. Why, and what did it cost? *(Core)*

**What I'm testing:** migration reasoning, not tool fandom.

**Answer**

**Why it was right:** a second datastore is a second backup story, a second auth model,
a second thing to run on one EC2 box, and a consistency problem the moment a note is
deleted. Moving vectors into Postgres makes `note_chunks` transactionally adjacent to
`notes` and lets `match_note_chunks` filter by `user_id` in the same query that ranks by
distance — which is exactly what multi-tenancy needs.

**Cost:**

- You now depend on a Postgres extension and an RPC function. `create extension vector`
  and `match_note_chunks` must exist before indexing works.
- Dimension is a hard contract: `note_chunks` is `vector(768)`, and `PgVectorStore`
  validates dimensionality before insert/delete. Swap the embedding model and you need
  a migration plus a full re-index.
- You must hand-manage index type and query parameters (`ivfflat` lists / `hnsw` `ef_search`)
  — Chroma tuned some of that for you.
- `replace_note_chunks` has to delete-then-insert; a well-tuned pgvector index pays for
  that on every re-index.

**Go deeper**
- `docs/blueprint.md` still describes the Chroma design. That's a documentation failure,
  not a code failure — but it's the kind of thing an interviewer finds in 30 seconds and
  it makes you look like you don't read your own docs. (See suggestions doc.)
- The real interview point: **you can't answer "why pgvector" without saying "user
  scoping in the same query".** That's the load-bearing reason.

**Trap:** reciting Chroma's downsides without saying what you gave up.

---

## C. Retrieval

### Q12 — Why three retrieval channels instead of one good embedding search? *(Core)*

**What I'm testing:** do you know what each channel is *for*, or did you just add them?

**Answer**

They fail in different directions, and the domain has both failure modes.

1. **Dense (semantic)** — handles paraphrase. "How did the deploy go wrong" matches a
   note about "the rollout broke on the canary". Fails at rare tokens: `POSTGRES_URL`,
   `JIRA-4412`, `northstar-api` — embeddings smear identifiers into noise.
2. **Sparse (BM25)** — exact terms, rare identifiers, acronyms. Fails at paraphrase.
3. **Dense on a rewritten query** — recovers recall when the user's phrasing is far from
   the note's vocabulary.
4. **Exact identifier channel** — not a similarity guess at all. `extract_identifiers`
   pulls things that look like IDs/paths/symbols and matches them deterministically,
   with weight 3 so an exact hit outranks a fuzzy neighbourhood.

A personal memory system is exactly the case where identifiers matter (repo names,
ticket numbers, function names) *and* paraphrase matters (you won't remember your own
wording). One channel can't do both.

**Go deeper**
- The identifier channel is the interesting design: it's a *precision* channel with a
  fixed weight, not a ranked similarity channel. Different epistemics.
- Cost: 3–4× the queries per retrieval, and fusion becomes a ranking problem (Q13).
- `exclude_note_id` exists because during ingestion you must not retrieve the note you're
  currently processing.

**Trap:** "hybrid is more accurate" without naming the specific failure each channel
covers.

---

### Q13 — Explain RRF, and why not normalise and sum the scores. *(Core)*

**What I'm testing:** real understanding of the fusion formula you shipped.

**Answer**

```python
scores[note_id] += weight / (rrf_k + rank)      # rrf_k = 60, ranks start at 1
```

RRF ignores *scores* and uses *ranks*. The best document in a channel contributes
`weight / 61`; the tenth contributes `weight / 70`. Contribution decays slowly and
compresses far outliers.

**Why not normalise-and-sum:** BM25 scores are unbounded and corpus-dependent (they
change as notes are added). Cosine distance lives in a narrow band. Summing them means
the BM25 channel secretly dominates whenever the corpus grows. Per-query min-max
normalisation is better but unstable — one outlier compresses everything else, and a
channel with a single result maps to 1.0 and wins falsely. RRF is scale-free, needs no
tuning, and degrades gracefully when a channel returns garbage.

**Go deeper**
- `k` controls how much weight the tail gets. Small `k` → top ranks dominate hard; large
  `k` → flatter. 60 is the standard from the original RRF paper, and it's env-tunable
  (`QUERY_RETRIEVAL_RRF_K`) — meaning it's a knob someone could turn without telling you.
- Weights are per-channel (`EXACT_IDENTIFIER_WEIGHT=3`). That's where domain knowledge
  lives — the fusion isn't neutral.
- Weakness: RRF discards confidence. A channel that returned 10 strong matches and one
  that returned 10 weak ones contribute identically. That's the cost of scale-freedom.

**Trap:** describing RRF as "average the scores". It never touches the scores.

---

### Q14 — You have a cross-encoder reranker that's off by default. Why? *(Stretch)*

**What I'm testing:** whether you can defend a *disabled optimisation* with evidence,
which is the most senior thing in this whole codebase.

**Answer**

`QUERY_RETRIEVAL_RERANKER=off` ships the retriever without reranking; any of
`semantic|sentence|cross|local|true|1|yes|on` instantiates
`SentenceTransformerReranker(CrossEncoder)`.

It's off because **it measured worse**. The eval harness showed recall@5 dropping with
reranking enabled. That's not a bug in the reranker — it's a mismatch between what a
cross-encoder optimises (query-document relevance) and what this task needs (does this
note contain the *fact* I'm asking about). A cross-encoder will happily promote a note
that is topically about the query and demote the note that actually contains the answer.

**A cross-encoder is also the wrong cost profile here:** it scores every
`(query, candidate)` pair serially, on a CPU-only box, inside the request. That's the
single most expensive thing you can add to a p95.

**Go deeper**
- The correct disposition isn't "delete it" — it's "keep it behind a flag, with the eval
  numbers in the commit message". That's exactly what was done. Say that.
- What would make reranking win: rerank only the identifier-missed candidates, or
  fine-tune on this domain, or move it off the hot path (precompute at ingest).
- The meta-point an interviewer wants to hear: **an optimisation you can't measure is a
  liability**. The flag is the receipt.

**Trap:** "cross-encoders are better than bi-encoders" as an absolute. They're better at
*some* objectives, and worse at your p95.

---

### Q15 — Every retrieval fetches all of a user's notes to compute a cache key. Talk me through that. *(Stretch)*

**What I'm testing:** whether you can find the scaling wall in your own hot path.

**Answer**

`SparseBM25Retriever` keeps a process-wide `OrderedDict` cache keyed by `user_id`,
holding `(fingerprint, BM25Index)`. To decide whether the cache is stale, it calls
`_get_index_for_user`, which **loads all of the user's notes** and runs
`fingerprint_notes(notes)` over them — every retrieval, even on a cache hit.

Consequences:

- Retrieval cost is **O(corpus size) per query** even when nothing changed. The cache
  saves the BM25 *build*, not the *read*.
- It's a full table scan over `notes.raw_text` on a Supabase round-trip. At 10k notes
  that's megabytes per query.
- The cache is per-process, so three worker processes hold three copies and warm them
  independently.
- Bounded at 128 users (`BM25_INDEX_CACHE_MAX_USERS`), LRU eviction — reasonable, but it
  means a cold user pays the build every time.

**Better shapes:** a cheap monotonic signal instead of a content fingerprint —
`max(updated_at)` plus `count(*)` (one indexed aggregate), or a per-user `notes_version`
column bumped by a trigger. Or push BM25 into Postgres (`ts_rank` / `tsvector` GIN
index) and delete the cache entirely — you lose nothing but the Python dependency.

**Go deeper**
- The `ThreadPoolExecutor(max_workers=3)` is created **per request**. That's a new pool,
  three new threads, on every retrieval. Reuse a module-level pool, or make the fan-out
  `asyncio.gather` if the DB client supports async (it doesn't today — `supabase-py` is
  sync, which is why the threads exist).
- Sync client inside a thread pool inside an async framework is the real architectural
  tension here. Say it out loud — it's a better answer than optimising the fingerprint.

**Trap:** "it's cached so it's fast". The cache hit still pays the full read.

---

### Q16 — Is the BM25 index thread-safe? *(Stretch)*

**What I'm testing:** concurrency reading of code you wrote.

**Answer**

**No, and the reason is subtle.**

The index is cached and shared across requests. `BM25Index.search(...)` does:

```python
self.model.k1 = k1
self.model.b = b
```

It **mutates the shared model** before scoring. `rank_bm25`'s `get_scores` reads `k1`
and `b` during the loop. Two threads with different `k1`/`b` racing through `search()`
can interleave so one query is scored with the other's parameters. Today `k1`/`b` are
constant per instance, so the practical blast radius is ~zero — but the code is wrong,
and the moment anyone adds per-request tuning it becomes a real, silent, unreproducible
ranking bug.

Compounding it: `_INDEX_CACHE` is guarded by `_INDEX_CACHE_LOCK` for *lookup and insert*,
but the returned `BM25Index` is then used outside the lock. So the guard protects the
dict, not the object in it.

**Fix:** make `search` take `k1`/`b` as parameters (or pass them into a new
`BM25Okapi` per call), never mutate shared state. Then the index is genuinely read-only,
which is also what makes it safe to share.

**Go deeper**
- The general principle: **shared mutable objects in a thread pool are a bug waiting for
  a second caller.** The lock you need is around mutation, not around the container.
- Good interview move: note that this is a *latent* bug, and say what would make it real.
  Interviewers respect "this is wrong but currently harmless because X" far more than
  either ignoring it or overclaiming an outage.

**Trap:** "it's protected by a lock" — the lock covers the cache dict, not the model.

---

### Q17 — 800 characters, 100 overlap, sentence-packed. Defend those numbers. *(Core)*

**What I'm testing:** whether your chunking constants are choices or defaults.

**Answer**

`DEFAULT_MAX_CHARS = 800`, `DEFAULT_OVERLAP_CHARS = 100`
(`infrastructure/vector/chunking.py`). Splitting is paragraph-aware, then sentence-aware,
with a hard split for a sentence longer than the cap. `chunk_text` raises if
`overlap_chars >= max_chars`.

**Why this shape:**

- **Sentence-boundary packing** avoids cutting mid-fact. A chunk that starts mid-sentence
  embeds badly and reads badly in a citation.
- **100/800 = 12.5% overlap** so a fact spanning a boundary is wholly present in at least
  one chunk. Without overlap you get retrieval holes exactly at boundaries.
- **800 chars** is roughly 150–200 tokens — comfortably inside the embedding model's
  window (`all-MiniLM-L6-v2`, 256 tokens) while keeping each chunk fact-dense.

**Where the numbers bend:**

- The docstring is honest that 800 is a *soft* cap: overlap can push a chunk over, and a
  hard-split sentence can too.
- Chunk size is tuned to the **embedder's** window, not the **LLM's** context. Fine here
  because chunks are for retrieval, not generation.
- No semantic chunking (topic shift detection). Cheap and predictable beats clever and
  variable for a memory app — but it means a rambling note produces mediocre chunks.

**Go deeper**
- Overlap is duplicated storage and duplicated embedding cost. 12.5% is a defensible
  middle; at 50% you'd pay double for marginal recall.
- A real improvement: store chunk offsets back into `raw_text` so citations can quote the
  surrounding paragraph, not just the chunk.

**Trap:** "800 characters is the optimal chunk size." There is no universal optimum —
name what it's optimised against.

---

### Q18 — The rewritten query concatenates the original, the rewrite, and a `likely_answer`. Problem? *(Stretch)*

**What I'm testing:** whether you can spot an evaluation leak inside your own design.

**Answer**

**Yes — it's an answer leak into the retrieval stage.**

`alternate_query_text` is built from the original query **plus** the rewrite **plus**
`likely_answer`. That third part is the killer: you're embedding a *guess at the answer*
and using it to search. Effects:

- **Circular retrieval.** The system finds notes similar to what it already believes,
  which inflates apparent grounding confidence. That's confirmation bias implemented in
  the retrieval layer.
- **Eval contamination.** If any eval path uses the rewritten query, recall metrics look
  better than a user would experience. Numbers stop meaning what you think.
- **Identifier dilution.** Averaging answer-ish prose into the query vector softens the
  exact terms that made the original query precise — the opposite of what the identifier
  channel is for.

**Better:** retrieve on `original` and `rewrite` as *separate* channels with their own
weights (the machinery already supports per-channel weights — you're using it for exact
IDs). Keep `likely_answer` for reranking or for the answer prompt, never for recall.

**Go deeper**
- This is the single best "I read my own system sceptically" answer available in this
  repo. If you get asked an open-ended "what would you change", lead with this.
- It's also a nice example of a metric that can only go up: you're optimising retrieval
  against a hypothesis.

**Trap:** "it improves recall" — of course it does; it's searching with the answer.

---

## D. Chat & derived data

### Q19 — The chat router is a rule-based classifier, not an LLM. Defend that. *(Core)*

**What I'm testing:** judgement about when *not* to use a model.

**Answer**

`RoutingOrchestrator.route(...)` runs a deterministic rule classifier, produces a plan,
optionally calls hybrid retrieval, then assesses grounding, then generates — or returns
a fallback without calling the model at all.

**Why rules are right here:**

- **Latency.** A classifier call is another 500ms–2s before you've retrieved anything.
  Routing is on the critical path of every message.
- **Cost.** Every chat message would pay twice for an LLM.
- **Predictability.** Rules are testable without a model (the suite runs with no Gemini
  installed). An LLM classifier needs eval coverage just to prove it isn't drifting.
- **The decision space is small.** A handful of intents over a personal corpus doesn't
  need semantic understanding.

**Where rules hurt:** they're brittle to phrasing. "what did I say about the migration"
vs "did I ever write down anything about migrating" hits different branches. And rule
maintenance is invisible work — every new intent is a new branch nobody wrote a test for.

**Go deeper**
- The right answer names the boundary: **regulate the router, generate the answer.** Cheap
  deterministic decision, expensive probabilistic output — and crucially, a *gate* between
  them so you don't pay for generation you can't ground (Q20).
- The orchestrator is constructed at **import time** (`CHAT_ROUTING_ORCHESTRATOR`), so it
  captures config once per process (Q35).

**Trap:** "LLM classifiers are more flexible" without acknowledging the doubling of
latency, cost, and eval surface.

---

### Q20 — Explain the grounding gate and its failure modes. *(Stretch)*

**What I'm testing:** whether you understand that a heuristic gate trading precision for
recall is a product decision.

**Answer**

`assess_grounding` collects evidence from notes, summary memory, and recent messages,
scores **claims** (not documents), and returns one of `strong | weak | conflict |
no_context` with `allow_answer`.

Thresholds:

- no claim-bearing evidence → `no_context`
- `top_score < 1.4` → `weak`
- a dissenter with weight ≥ 0.9 and runner-up ≥ 0.7 × top → `conflict`
- `top_score < 2.2` **and** fewer than 2 supporters → `weak`

When `allow_answer` is false, you get a templated `fallback_message` and **no LLM call**.

**Why claim-scoring instead of document-scoring:** for a memory app the question is
almost always a status question ("did I finish X", "when did Y happen"). Scoring claims
lets you detect *disagreement* between sources, which document-level similarity can't.
`conflict` is the interesting state — two notes from different dates saying different
things.

**Failure modes, and they're both real:**

- **False `weak`/`no_context`** — the classic precision/recall trade. Paraphrased notes,
  terse notes ("shipped it"), or a query that doesn't tokenize into claim markers all
  produce a refusal even though the answer is sitting right there. From the user's side
  the assistant looks stupid, and they can't tell why.
- **Unbounded tuning** — the constants (1.4, 2.2, 0.7, 0.9) are magic numbers with no
  calibration dataset. They're guesses that were never re-derived.

**Go deeper**
- Best answer: log every grounding decision with its inputs and turn refusals into a
  labelled dataset. Then the thresholds are *tuned*, not *believed*.
- Softer UX: on `weak`, offer the evidence with a "not confident" frame instead of a
  refusal. You already have `source_refs` — the information exists, you're throwing it away.

**Trap:** "the gate prevents hallucinations". It prevents *some* hallucinations at the
cost of *some* true answers, and you should name both sides.

---

### Q21 — Mutating chat tools need confirmation. Walk me through the safety design. *(Core)*

**What I'm testing:** human-in-the-loop thinking and expiry/idempotency in a stateful flow.

**Answer**

Mutating tools aren't executed inline. `_try_propose_tool_call` writes a
`pending_chat_actions` row, the user sees a proposal, and a later message resolves it via
`_try_resolve_pending_action`. `PENDING_ACTION_EXPIRY_MINUTES = 15`.

**Good properties:**

- **Separation of proposal and execution** — the model can suggest, only the user commits.
- **Expiry** — a proposal from 3 hours ago can't be silently confirmed by an unrelated
  message.
- **Single pending action per thread** (`get_latest_pending_action`) — no queue of
  half-confirmed mutations.
- **Explicit resolution status** — `resolve_pending_action(status=...)` records the
  outcome, so it's auditable.

**Gaps worth naming:**

- **Resolution is not obviously idempotent.** Two rapid confirmations need the resolve
  step to be conditional (`where status='pending'`) or you can execute twice. That's the
  same guard pattern as Q4, and it should live in an RPC.
- 15 minutes is a UX guess; some flows (a long analysis, then "yes create the task")
  take longer, and some should be shorter.
- Only `create_task` / `complete_task` are wired. The safety machinery exists but the
  blast radius is deliberately tiny — which is the right place to be while it's immature.

**Go deeper**
- The general design is "propose → confirm → execute → record", which is the correct
  shape for agentic writes. Naming that pattern explicitly is worth points.
- Next step would be a `executed_at` + `result` column, and an idempotency key per action.

**Trap:** treating confirmation as sufficient. Confirmation without a conditional state
transition just means "the user clicked twice".

---

### Q22 — `_create_synthetic_anchor_note` writes `status="processed"`. What's wrong? *(Stretch)*

**What I'm testing:** attention to a status vocabulary that has quietly drifted.

**Answer**

It creates a note that is **never processed and never indexed**. It exists to give chat
actions an anchor note to hang provenance on. But:

- `status="processed"` is a **fifth** name in a vocabulary that also has `processing`,
  `completed`, `enriched`, `failed`. Anything that filters on `status == "completed"`
  will never see it; anything that filters `!= "completed"` will treat it as in-flight
  forever.
- It is **not in pgvector**, so it can never be retrieved. It's a note-shaped object that
  cannot participate in the only feature notes exist for.
- Any list view that shows "processing" notes will accumulate these silently.

**What it should be:** an explicit `kind="anchor"` (or `synthetic=true`) flag plus a
terminal status like `indexed=false, kind=anchor`, so downstream code can *decide*
rather than accidentally fall into a branch.

**Go deeper**
- This is a symptom of Q10: no enum, no `CHECK`, no single `Literal`. Free-text status
  means every new writer invents a word.
- Great "small find" to have ready — it shows you read past the happy path, and it's
  concrete enough that you can describe the fix in one sentence.

**Trap:** missing it entirely, or "processed is fine, it means done".

---

### Q23 — Commitments: why `max_active = 3`, and how is auto-write safe? *(Core)*

**What I'm testing:** product judgement encoded as a constraint, plus idempotency done right.

**Answer**

`Commitment` models a long-term goal the user is working toward, with
`max_active: 3` enforced in the domain. The DB has unique indexes that make auto-write
idempotent — `commitment_contributions(commitment_id, note_id)` plus the commitments
natural key.

**Why 3:** it's a focus constraint, not a technical one. An unbounded goal list becomes a
graveyard; three forces the user to choose. It also bounds the cost of every downstream
consumer — commitments are loaded into ingestion (Q1, step 2) and into chat context, so
"3" is simultaneously a UX decision and a token-budget decision. That dual justification
is the answer.

**Why auto-write is safe:** the contribution row is keyed on
`(commitment_id, note_id)` — one note can contribute to a commitment exactly once, so a
redelivery conflicts instead of double-counting. This is the pattern the *typed memories*
should have copied (Q4).

**Go deeper**
- Note the asymmetry: the newest subsystem (commitments) got idempotency right, while the
  oldest (typed memories) didn't. That's a good story — "the codebase learned, and the
  fix just never got backported."
- `max_active=3` enforced in domain rather than DB is a gap: a concurrent second create
  could exceed it. A partial unique index or a DB-level check would close it.

**Trap:** "3 is arbitrary". It's a product constraint with a cost rationale — say both.

---

### Q24 — Period summaries with `insufficient_data`. Why does this exist? *(Core)*

**What I'm testing:** derived-data design, and whether you think about *cold start*.

**Answer**

`summary/services.py` generates daily/period summaries with statuses
`ready | insufficient_data | not_generated`, gated by
`MIN_NOTES_FOR_DAILY_SUMMARY`.

**Why the third state matters:** with two notes in a fresh account, a "daily summary" is
either empty or nonsense — and a confidently wrong summary poisons every downstream
consumer, because summary memory is fed into chat grounding (Q20). Refusing to generate is
better than generating garbage. `insufficient_data` is an honest, non-error state, and
`upsert_period_summary` keyed on `(user_id, period_type, period_start)` means regenerating
a period *overwrites* rather than accumulating.

**Go deeper**
- This is the same discipline as grounding (refuse rather than hallucinate) applied to
  batch jobs — worth pointing out as a consistent design value rather than a one-off.
- Gap: summaries are computed on demand/upsert, with no scheduler in the repo. So "daily"
  is a label, not a guarantee. If nothing triggers it, the period simply has no summary.
- `MIN_NOTES_FOR_DAILY_SUMMARY` is another uncalibrated constant.

**Trap:** "insufficient_data is just an empty state". It's a deliberate refusal, and the
reason is downstream trust.

---

## E. Security

### Q25 — Walk the auth flow. Then tell me what's missing. *(Core)*

**What I'm testing:** whether you know your token lifecycle end to end, including the
deliberate holes.

**Answer**

**Flow:** `POST /auth/register|login` → Argon2 verify → `create_access_token` → HS256 JWT
with `sub`, `type="access"`, `exp`, `iss=northstar-backend`, `aud=northstar-client`.
`ACCESS_TOKEN_EXPIRE_MINUTES=10080` — **7 days**. Client stores it in `localStorage` and
sends `Authorization: Bearer`. `get_current_user_id` decodes, verifying signature,
algorithm, audience, issuer, `type`, and that `sub` is non-empty.

**Missing:**

- **No refresh.** `/auth/refresh` returns **410 Gone** deliberately — the comment says
  it's for stale bundles to fail clearly. So the user re-logs in weekly. That's a UX
  decision, honestly made, but it's why the token is 7 days — a long-lived bearer token
  with no rotation is the security cost of that simplicity.
- **No revocation.** No `jti` denylist checked at request time. Logout is a no-op
  server-side. A stolen token is valid for up to 7 days.
- **No `is_active` re-check** at request time. Deactivating a user doesn't invalidate
  their live token; only login check enforces it.
- **No rate limiting or lockout** on login. Credential stuffing is unthrottled.

**Go deeper**
- 7-day bearer + `localStorage` = XSS equals full account takeover with no revoke path.
  `httpOnly` cookies + CSRF would change that equation; the trade is SPA complexity.
- The correct minimum: short access token (15 min) + refresh with rotation, `jti` checked
  against a denylist, and `is_active` in the auth dependency (one extra indexed read, or a
  cached claim with a short TTL).

**Trap:** "we use JWT so it's stateless and secure". Stateless is exactly why you can't
revoke it — that's the trade, say it out loud.

---

### Q26 — The frontend keeps the token in `localStorage`. Consequence? *(Core)*

**What I'm testing:** full-stack security reasoning, not just backend.

**Answer**

`localStorage` is readable by any JavaScript on the origin. One XSS — a compromised npm
dependency, an unsanitised `dangerouslySetInnerHTML`, a malicious browser extension with
page injection — and the attacker exfiltrates a 7-day token that **cannot be revoked**.

`httpOnly` + `secure` + `sameSite` cookies are unreadable by JS, so XSS can *act as* the
user but can't *steal* the credential. The costs are real: CSRF protection becomes your
problem, and cross-origin API calls need credentials mode plus a strict CORS policy.

**Go deeper**
- The honest framing: `localStorage` is a *risk concentration* problem, not a bug. Given
  the app is a personal memory store, that's a meaningful concentration.
- `httpClient.ts` centralises the header injection, so switching to cookie auth is a
  smaller change than it looks — one file, not fifty. Good answer to "how would you fix it".
- Note the interaction with Q25: the reason the token is 7 days is the missing refresh.
  Fix refresh first, then the `localStorage` blast radius shrinks to 15 minutes.

**Trap:** "localStorage is fine if you sanitise". Sanitisation is defence in depth, not
a substitute for making the credential unreadable.

---

### Q27 — There's no RLS. Isolation is `eq("user_id", …)` in Python. Blast radius? *(Stretch)*

**What I'm testing:** the flagship security question. Whether you understand that
tenancy is an invariant, not a filter.

**Answer**

**Blast radius: one forgotten filter equals full cross-tenant read/write.**

Every repository method body is a PostgREST query. Isolation exists only where someone
wrote `.eq("user_id", user_id)`. Nothing at the database layer enforces it, and — this is
the part that turns a bug into an incident — the app connects with a **service-role key**
(`.env.example` requires it), which **bypasses RLS entirely**. So even if you added
policies tomorrow, the current credentials would sail straight through them.

Failure modes:

- A new endpoint that queries `notes` by `note_id` only. `note_id` is a uuid so it's not
  enumerable — but `recall_candidates`, `period_summaries`, and list endpoints are.
- A joined read where the `user_id` filter lands on the wrong table.
- Any admin/debug path (Q28) that bypasses the scoped repository.

**The fix is two-part, and this is where candidates lose points:**

1. **Make the database enforce it** — `alter table ... enable row level security` plus
   `using (user_id = auth.uid())` on every user-scoped table.
2. **Change the credential** — the app must connect as the *user's* role (JWT forwarded to
   PostgREST) so `auth.uid()` resolves. Keeping the service-role key and adding RLS is
   security theatre; the key ignores the policies.

**Go deeper**
- Interim mitigation that's genuinely useful: a single `_scoped(user_id)` query builder
  plus a test that greps repository code for `table(` calls without `.eq("user_id"`.
  Crude, but it converts a silent class of bug into a failing test.
- Defence in depth is the phrase to use: RLS for the database, scoped repositories for the
  application, tests for the regression.

**Trap:** "we always filter by user_id so it's fine". That's a convention, and conventions
don't survive deadline pressure. Also: deploying RLS without changing the key does
nothing — being able to say that is the difference between reading a blog post and
understanding the system.

---

### Q28 — Any authenticated user can call `POST /notes/poll/process-jobs`. Why is that bad? *(Stretch)*

**What I'm testing:** whether you can find a cross-tenant hole in your own debug endpoint.

**Answer**

The handler takes `_: str = Depends(get_current_user_id)` — it authenticates the caller
and then **ignores who they are**. It then calls `poll_sqs_messages(max_messages=10)` on
the **global** queue and runs `process_sqs_message` for every message it finds.

Three distinct problems:

1. **Cross-tenant work theft.** User A's endpoint call processes user B's notes. The work
   still completes (the message body carries its own `user_id`), so it's not a data leak —
   but it means tenancy boundaries are enforced nowhere in the queue path.
2. **Unauthenticated-cost DoS.** Any logged-in user can trigger up to 10 LLM calls per
   request, synchronously, at the app's expense. Loop it and you're burning someone's
   Gemini budget from a free account.
3. **It's synchronous inside a request.** Ten notes × LLM + embedding easily exceeds any
   sane gateway timeout, so the caller sees a timeout while the work continues — and the
   message may be redelivered mid-flight if the process dies (which is Q4 all over again).

The `sqs_consumer` docstring calls itself "the EC2-native replacement for the manual
`POST /notes/poll/process-jobs` debug endpoint" — but the debug endpoint is still routed
and still reachable.

**Fix:** delete it from production routing, or gate it behind an admin claim *and* a
feature flag, and never let it drain more than the caller's own work.

**Go deeper**
- This is the best example in the repo of "debug affordance that graduated to a
  vulnerability". Interviewers love it because it's realistic — everyone ships one.
- It also demonstrates why Q27 matters: there is no layer that would have stopped it.

**Trap:** "it requires auth so it's safe". Authentication is not authorisation, and it
certainly isn't tenant scoping.

---

### Q29 — Prompt logging writes full note text to disk. Talk it through. *(Core)*

**What I'm testing:** whether you treat user content as sensitive by default.

**Answer**

`PROMPT_LOG_ENABLED` (off by default) makes `log_gemini_interaction` persist prompt and
response to a file — writing **full note text** into `backend/logs` by default, i.e. into
the repo working tree. It also *overwrites* a single file rather than appending.

Why it's dangerous:

- Personal memory notes are about as sensitive as user data gets — health, work
  performance, half-formed opinions.
- Writing to the working tree means it's one careless `git add .` from being committed,
  and one `git push` from being permanent. `.gitignore` protects you only if nobody
  renames the folder.
- On a shared EC2 box the file lands in the deploy directory, readable by anything with
  filesystem access.
- The overwrite behaviour means you lose the *previous* bad state — it's not even a
  reliable audit trail.

**Better:** default off (already true), write to a configured directory outside the repo,
redact or hash note bodies and keep only ids + token counts, rotate with a size cap, and
gate it on an explicit debug env that can't be enabled in prod.

**Go deeper**
- The right mental model: **prompt logs are a data-processing surface**, not a debug
  convenience. They need the same handling as a database dump.
- Good contrast to raise: the codebase is careful about *auth* but casual about *content*.
  That's a common and interview-worthy blind spot.

**Trap:** "it's off by default so it's fine". Defaults protect you until someone debugging
at 2am flips it in prod — which is precisely when it happens.

---

## F. Quality, ops & production

### Q30 — How does the test suite run without Supabase, Gemini, or Postgres installed? *(Core)*

**What I'm testing:** whether your testing strategy is a design or an accident.

**Answer**

Deliberately minimal `requirements-dev.txt` — pytest, dotenv, pydantic, and nothing else.
If a module needs Supabase, the suite would fail to import it, so the suite *forces* the
pure-logic boundary to stay clean.

Three mechanisms:

1. **Fakes at the port.** `tests/fakes.py` has `InMemoryRecallRepository` and
   `InMemoryCommitmentRepository`. Services accept injected repos, so tests never touch a
   database.
2. **`monkeypatch` on module factories** — `monkeypatch.setattr(module, "get_repository", …)`
   for code that takes the singleton path.
3. **Direct function calls instead of HTTP.** `test_recall_batch_api.py` calls route
   functions with plain arguments. No `TestClient`, no httpx, no ASGI lifetime.

Strong coverage: scheduler, review service, candidate scoring, hybrid fusion, prompt
rendering, SQL idempotency (`test_sql_migrations`), lazy-import boundaries
(`test_package_imports`), and p95 latency parsed from logs (`test_p95_latency`). 242 tests
across 32 files.

**Gaps, and you should lead with these:** `POST /notes` create/list/toggle, all of
`auth.py`, summary generation, and the full chat service have no tests. So the untested
surface is exactly the traversal path a user actually walks — which is the worst possible
gap distribution.

**Go deeper**
- `test_package_imports` is the unsung hero: it asserts that pure modules don't import
  infrastructure, which is what makes the minimal-deps trick possible *and* stable. That's
  an architectural test, not a unit test, and almost nobody writes them.
- Direct route calls are fast but blind to the things that actually break: dependency
  wiring, status codes, request/response validation, and auth. Adding `TestClient` for
  three or four route tests would cover the highest-value untested area for ~100 lines.

**Trap:** "we have 242 tests". Count isn't coverage, and the gap is on the main path.

---

### Q31 — The frontend polls every 1.5s. Why, and what's wrong with it? *(Core)*

**What I'm testing:** whether you can critique your own client architecture.

**Answer**

`NoteTakerPage` polls every 1.5s with a 60s timeout while a note is `processing`;
`RecallVerifyPage` and `StudyPage` poll similarly. Networking is centralised in
`shared/api/httpClient.ts` (~1,250 lines of typed functions) with a Bearer header injected
once and a 401 handler that calls `expireSession()` and fires a `northstar:auth-expired`
window event.

**Why polling is defensible here:** the work genuinely takes tens of seconds, the
alternative is WebSockets/SSE (new infrastructure, new failure modes, sticky sessions
behind Nginx), and 1.5s for a single note is cheap. Optimising for simplicity at this
scale is correct.

**What's wrong:**

- **No `AbortController`/timeout on `fetch`.** A hung request hangs the UI state machine
  until the browser gives up. The 60s "timeout" is a counter, not a cancellation.
- **No retry or backoff.** One transient 502 and the note appears stuck.
- **Polling doesn't stop on unmount properly** — the classic stale-closure family of bugs.
- **No cache layer.** No React Query/SWR means each page re-fetches what the last one had,
  and there's no single source of truth for "the note's status".
- **1,250-line single module** is a maintenance cliff: it's the file everyone edits, so it's
  where "why does auth break on one screen" bugs live.

**Go deeper**
- The 401 → window-event → `expireSession` chain is a decent pattern (one place decides the
  session is dead) but the event payload carries no reason, so the UI can't distinguish
  "expired" from "revoked".
- The honest upgrade: SSE for note status (one connection, server push) plus React Query
  for the rest. Bigger change, strictly better UX.
- Interview-grade nuance: polling and SSE have the same failure mode (missed update);
  polling self-heals on the next tick, SSE doesn't. That's why polling survives longer than
  people expect.

**Trap:** "polling is bad, use WebSockets" without the operational cost of sockets behind a
proxy.

---

### Q32 — SM-2 with `lapse_multiplier = 0.0`. Explain what "Again" does. *(Stretch)*

**What I'm testing:** domain correctness — whether you know your scheduling maths.

**Answer**

`RECALL_LAPSE_MULTIPLIER` defaults to `0.0`. In `_schedule_review`:

```python
interval = max(1, int(round(interval * config.lapse_multiplier))) if config.lapse_multiplier else 0
due = now + timedelta(minutes=config.relearning_steps[0])
```

So on `AGAIN`: easiness drops by `ease_penalty_again` (floored at `min_easiness`),
**interval becomes 0**, state becomes `RELEARNING`, lapse count increments, and the card
comes back after `relearning_steps[0]` minutes.

**Why 0 is coherent:** the interval is meaningless once you're in relearning — the *next*
due time comes from the relearning steps, not from the interval. Setting it to 0 makes the
card unambiguously "not scheduled by interval" and forces a real graduation before it re-enters
the review queue. `max(1, …)` would create a fake 1-day interval that the relearning path
never uses, which is worse: a value that looks meaningful and isn't.

**Where it bites:** anything that reads `interval` for display ("next in 0 days"), or
analytics that average intervals, will read a sentinel as data. And the easiness floor
means a card you keep failing converges to `min_easiness` and then schedules at a constant
cadence forever — the system gives up on adapting.

**Go deeper**
- SM-2's known weakness: it assumes a stable difficulty per card. Real cards get easier
  with context and harder with interference. FSRS models that; SM-2 doesn't.
- `SystemClock` is the right abstraction — the scheduler is pure and testable, which is why
  it's one of the best-tested modules.
- `max_interval` caps runaway growth; without it, `interval * easiness * easy_bonus` compounds.

**Trap:** "interval 0 means it's due immediately" — it means the relearning steps govern,
which is different.

---

### Q33 — How would you know this system got worse? *(Stretch)*

**What I'm testing:** observability as a design property, not a dashboard.

**Answer**

Today: `RequestTimingMiddleware`, a `timer` object per ingestion stage
(`extraction`, `questions`, `finalize`, `resolution`, `indexing`), and
`log_timing_event(...)` emitting structured p50/p95 for `note_processing` and failures
with `error_type`. `test_p95_latency` parses those logs to assert a budget — a genuinely
nice trick, because it makes latency a test rather than a wish.

**What's missing is quality signal.** Latency tells you it's fast; nothing tells you it's
*right*:

- No retrieval-quality metric in production. A retrieval regression (reranker on, bad
  chunking, a wedged index) is invisible until a user complains.
- No grounding-refusal rate. A spike in `weak`/`no_context` is the earliest symptom of a
  retrieval failure and it's already computed — it just isn't counted.
- No ingestion success ratio. `completed` doesn't imply indexed (Q3), so "notes processed"
  is a lie you're telling yourself.
- No DLQ depth alarm. Messages reach the DLQ silently.

**The three metrics I'd add tomorrow:** grounding decision distribution by status,
ingestion `indexed / attempted` ratio, and DLQ depth. All three are almost free — the
events are already logged.

**Go deeper**
- Structured logs + a `search_id`/`note_id` correlation id would let you reconstruct one
  bad answer end to end. `append_pipeline_log` already records per-stage retrieval detail;
  it just isn't joined to the answer.
- The eval harness (Q34) is the offline half of this. Production is the half that catches
  drift.

**Trap:** "we have logs". Logs aren't signal until something counts them.

---

### Q34 — The RAG eval harness runs but never fails the build. Why is that a problem? *(Stretch)*

**What I'm testing:** whether you understand evals as a gate versus a report.

**Answer**

`rag-eval.yml` runs sparse eval on every push, and dense/rerank/rewrite only on manual
dispatch. It computes Precision@5, Recall@5, MRR@5 over v0–v4 datasets (v4: 50 questions /
63 notes; v1: 100 / 350). It is **report-only — no thresholds**.

That means:

- A regression is **detected and ignored**. Recall@5 can drop 15 points and CI stays green.
- Nobody reads a report that never fails. Within two weeks it's a green checkmark people
  scroll past.
- Manual-only dense/rerank paths mean the expensive configurations are the least tested —
  exactly the ones you'd be tempted to enable in prod.

**Fix:** pin a baseline per dataset, fail on a drop beyond noise (say 2–3 points on
Recall@5, calibrated from repeated runs), and require a written justification to move the
baseline. Keep the report for the numbers; add the gate for the behaviour.

**Go deeper**
- The reranker decision (Q14) is the proof this matters: the only reason the team *knew*
  reranking hurt was that someone ran the eval. A gate makes that knowledge automatic.
- Dataset design is the deeper problem: 50 questions over 63 notes is a small sample — a
  3-point swing could be one question. Say that; it's the kind of statistical honesty that
  reads as Senior.
- Precision/Recall/MRR at k=5 is the right triple for a memory assistant: MRR tells you
  whether the *first* result is usable, which is what a citation UI needs.

**Trap:** "we have an eval suite" — a suite that can't fail is a dashboard.

---

### Q35 — Top three changes before real production traffic. *(Core, the classic closer)*

**What I'm testing:** prioritisation. Everyone can list problems; can you rank them?

**Answer**

There are more than three. Ranking is the answer.

1. **Make ingestion atomic and idempotent (Q4, Q5).** This is #1 because it's the only
   issue that silently corrupts the product's core asset. Duplicate tasks and
   mixed-provenance facts are invisible until a user notices their task list is wrong —
   and by then the data is polluted with no clean recovery. One RPC, one outbox column.
2. **Close the tenancy hole (Q27, Q28).** RLS policies *plus* moving off the service-role
   key, and remove or gate `/notes/poll/process-jobs`. This is #2 because the blast radius
   is total (all user data) even though the probability is lower than #1.
3. **Fix the `completed` lie (Q3).** Split the status so `indexed_at` is explicit and an
   indexing failure surfaces to the user. This is #3 because it makes failures *visible* —
   and right now the system's worst failures are the ones it hides.

**Why not the others:** the reranker is already safely off; the config-at-import-time
issue is real but only bites on redeploy; the BM25 thread-safety bug is latent; the
frontend polling is a UX cost, not a correctness one.

**Go deeper**
- **Config at import time** is worth naming as a runner-up: ~70 env vars read via
  `os.getenv` at module import, plus `lru_cache` keyed by API key, means rotating a key or
  changing a threshold requires a process restart. It's not urgent, but it makes every
  other fix harder to roll out safely.
- The meta-answer: the theme across all three is **make failure visible rather than
  silent**. That's a coherent engineering position, not a bug list.

**Trap:** listing ten things in no order. Ranking, with a reason for the ranking, is the
answer.

---

## 5. How you will be scored

| Area | Weight | What earns full marks |
|---|---|---|
| Architecture understanding | 20% | Draws the real pipeline; knows what's sync vs async; names the ordering trap unprompted |
| Security | 15% | Tenancy as an invariant; service-role key vs RLS; auth gaps named without prompting |
| Code-level depth | 20% | Real symbols, real line-level behaviour, real constants |
| Failure mode instinct | 20% | Volunteers what breaks; distinguishes latent from live bugs |
| Testing awareness | 10% | Knows the strategy *and* the gap distribution |
| Production thinking | 15% | Ranks by blast radius × probability and says why |

**Rubric per answer:** full marks = correct and unprompted with trade-offs; 75% = correct
after one follow-up; 50% = partial, needed guidance; 25% = wrong but recovered when guided;
0% = wrong and stayed wrong.

The single biggest lever on your score is **volunteering failure modes before I ask**.
Every question above has one. Lead with it.

---

## 6. Session history

**Session 1 (this one) — Assignment review, Mid, demanding bar.**

| # | Question | Outcome |
|---|---|---|
| Q1 | End-to-end ingestion | Partial. Right shape, wrong ordering: described "store chunks → retrieve" when indexing is last. Also claimed exponential backoff (SQS doesn't do that) and that `completed` means fully processed. |
| Q2 | Idempotency audit | Partial → recovered. Initially claimed unique-key idempotency; correctly walked it back to "only extraction_runs, and we'd duplicate tasks". Proposed fix had a circular key (`hash(task_id + note_id)`) and an `UPDATE` that guards double-completion, not double-creation. |
| Q3 | Non-transactional fan-out | Directionally right ("make it atomic, fail honestly"). Missed that retries produce *different* LLM output, so it's not a clean split — and that PostgREST gives you no cross-call transaction. |
| Q4 | Design the RPC | **Left open when the session ended.** The interesting half — how to keep an RPC idempotent when the extraction payload differs between attempts — is unanswered. See Q5 in this doc for the model answer (persist-then-fan-out / outbox). |

**What that says about the profile:** strong product-level grasp of the pipeline, weak on
transactional and idempotency semantics, and a habit of asserting mechanisms
(SQS backoff, unique keys, "transaction") without checking them against the code. That is
exactly the gap between "built it" and "owns it", and it's the first thing to drill.

**Resume point next session:** Q4 above (→ Q5 in this doc), then run the full 35.

---

## 7. Cheat sheet

**Numbers**

| Thing | Value | Where |
|---|---|---|
| Chunk size / overlap | 800 / 100 chars | `chunking.py` |
| RRF k | 60 | `QUERY_RETRIEVAL_RRF_K` |
| Candidate multiplier | 3 | `QUERY_RETRIEVAL_CANDIDATE_MULTIPLIER` |
| Exact-identifier weight | 3 | `QUERY_RETRIEVAL_EXACT_ID_WEIGHT` |
| Retrieval limit clamp | 1–20 | `_clamp_limit` |
| Reranker default | `off` | `QUERY_RETRIEVAL_RERANKER` |
| BM25 k1 / b | 1.5 / 0.75 | `sparse.py` |
| BM25 cache | 128 users LRU | `BM25_INDEX_CACHE_MAX_USERS` |
| Retrieval thread pool | 3 (per request!) | `hybrid_retriever.py` |
| Embedding dim | 768 | `note_chunks.embedding vector(768)` |
| Embedding model | `all-MiniLM-L6-v2` | `embeddings.py` |
| JWT algorithm | HS256 | `jwt_service.py` |
| Token lifetime | 7 days (10080 min) | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Pending action expiry | 15 min | `PENDING_ACTION_EXPIRY_MINUTES` |
| Max active commitments | 3 | domain |
| SQS visibility timeout | 600s | `docs/ec2_deployment.md` |
| DLQ threshold | 3 receives | redrive policy |
| Worker poll | 5 msgs / 20s long-poll | `sqs_consumer.py` |
| Migrations | 9 hand-run `.sql` | `backend/sql/` |
| Tests | 242 across 32 files | `backend/tests/` |
| Grounding weak | `top < 1.4`; `top < 2.2` & <2 supporters | `guardrails.py` |
| Grounding conflict | dissenter ≥0.9 & runner-up ≥0.7×top | `guardrails.py` |

**Names to say correctly**

`process_sqs_message` · `fetch_note_context` · `create_extraction_run` ·
`apply_deterministic_task_resolution` · `index_note` · `replace_note_chunks` ·
`match_note_chunks` · `fuse_candidates` · `SparseBM25Retriever` ·
`SentenceTransformerReranker` · `assess_grounding` · `RoutingOrchestrator` ·
`accept_recall_candidate` (the one existing atomic RPC) · `HybridRetriever` ·
`get_current_user_id` · `expireSession`

**The five sentences that do the most work**

1. "Indexing is last, so the note being ingested isn't in the index yet."
2. "`completed` means the LLM returned — not that it's indexed."
3. "Typed memories aren't idempotent; only entities and commitments are, because only they
   have natural keys."
4. "PostgREST gives no cross-call transaction, so atomicity has to live in a Postgres
   function — like `accept_recall_candidate`."
5. "There's no RLS and the app uses a service-role key, so tenancy is a convention enforced
   one `.eq('user_id')` at a time."

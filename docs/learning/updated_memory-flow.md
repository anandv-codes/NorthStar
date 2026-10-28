# NorthStar — Note Processing + Retrieval Flow

> Interview-prep notes. NorthStar has **two separate pipelines**:
>
> 1. **Note processing (write path)** — save a note once, extract structured memory, score recall candidates, and index searchable chunks.
> 2. **Chat retrieval (read path)** — every chat message runs a fresh hybrid search and builds a short context block for the LLM.
>
> Chat messages are **never turned into notes**. They live in their own `chat_messages` table and are not embedded or extracted. The two pipelines meet only when chat reads the notes that note processing already indexed.

## How to read this document

Every step is labelled:

| Label | Meaning |
|---|---|
| `[NOTE]` | Runs only in note processing (`POST /notes` → SQS worker) |
| `[CHAT]` | Runs only in the chat pipeline (`POST /chat/message`) |
| `[SHARED]` | Same retrieval code or same index is used by both pipelines |
| `[LLM]` | Makes an LLM call |
| `[NO LLM]` | Deterministic code, no LLM |

The most important distinction for interviews:

> **Note processing writes the index. Chat retrieval reads it.**
> They share the retrieval engine, but they do different jobs.

---

# 0. The 30-second map

```text
NOTE PROCESSING (async, write path)                         [NOTE]
──────────────────────────────────────────────────────────────────
POST /notes
  -> create notes row: status = "processing"
  -> send SQS job {user_id, note_id, raw_text, created_at}
  -> worker:
       1. load note + recall flag
       2. retrieve related notes                  [SHARED]
       3. load active long-term goals
       4. Gemini extraction                       [LLM]
       5. create extraction_run + notes.metadata
       6. write typed tables + entities + links + goal contributions
       7. score recall candidates                 [NO LLM]
       8. generate recall Q+A if enabled          [LLM]
       9. deterministic task resolution           [NO LLM]
      10. chunk + embed + index note              [NO LLM, except embedding model]
      11. status = "indexed" or "failed"
  -> UI polls GET /notes/{id}


CHAT RETRIEVAL (sync, read path)                            [CHAT]
──────────────────────────────────────────────────────────────────
POST /chat/message
  -> store user turn + load recent turns/summary
  -> intent gate: does this message need memory?
  -> optional query rewrite                        [LLM]
  -> BM25 + dense + exact-ID search                [SHARED core]
  -> RRF fusion                                    [SHARED core]
  -> top 5 notes
  -> grounding guardrail                           [NO LLM]
  -> format "Knowledge memory" block
  -> final answer LLM                              [LLM]
  -> store assistant turn
```

---

# 1. The one-sentence version

**Note processing** turns a raw note into three things:

1. structured memory rows (tasks, facts, questions, decisions, concepts, entities),
2. scored recall candidates (and optionally recall flashcards),
3. searchable chunks in pgvector.

**Chat retrieval** turns a question into a short, ranked reading list for the LLM. It does **not** answer the question itself. It decides what the LLM is allowed to read.

---

# 2. Note processing — write path `[NOTE]`

## 2.1 API entry: save the note

**Endpoint:** `POST /notes`

**Input:**

```json
{
  "text": "Call with Priya. We're delaying the onboarding launch to Nov 15 because analytics isn't ready.",
  "metadata": {},
  "recall_enabled": false
}
```

**Output:**

```json
{
  "note_id": "uuid",
  "status": "processing"
}
```

The endpoint returns **202 Accepted** immediately. It does **not** wait for Gemini, embeddings, or recall generation.

What it writes before returning:

- a row in `notes` with `status = "processing"`,
- `recall_status = "pending"` if recall is enabled, otherwise `"off"`,
- an SQS job containing `{user_id, note_id, raw_text, created_at}`.

In local development, `PROCESS_NOTES_INLINE=true` replaces SQS with a FastAPI `BackgroundTasks` job. In production, the EC2 worker consumes SQS.

**Why async?**

Gemini extraction plus optional recall-question generation can take 10–40 seconds. If this ran inside the HTTP request, the browser would time out, and a crash would lose the work. SQS gives retries, a DLQ, and a separate worker process so API latency is unaffected.

---

## 2.2 SQS job and worker loop

**Current production shape:** a long-running EC2 worker, run as its own systemd service:

```bash
python -m app.workers.sqs_consumer
```

**Worker loop:**

1. Long-poll SQS (`max_messages=5`, `wait_time_seconds=20`).
2. For each message, parse the JSON body.
3. Call `process_sqs_message(body)`.
4. On success: delete the message.
5. On exception: **leave the message** so SQS redelivers it.
6. After `maxReceiveCount = 3` receives, SQS moves it to the DLQ.

**Deployment settings:**

- Visibility timeout: **600 seconds**
- Message retention: **4 days**
- DLQ redrive: **maxReceiveCount = 3**

The same `process_sqs_message` function also has a `lambda_handler` wrapper that returns `batchItemFailures` for partial-batch retries, but the current deployment path is the EC2 consumer.

**Why a DLQ?**

A poison message — bad prompt, malformed note, persistent model failure — should not retry forever. After three attempts it lands in the DLQ for inspection. The worker deliberately does **not** delete failed messages.

---

## 2.3 Worker step by step

### 2.3.1 Load the note and recall flag `[NOTE]`

**Input:** SQS body `{user_id, note_id, raw_text}`

**Output:**

- `recall_enabled` (defaults to `false`)
- `note_status` (defaults to `"processing"`)

If the note is currently `failed`, the worker validates the transition `failed → processing` and resets `index_error` so a redelivered job can re-enter the lifecycle.

**Why re-read the flag?**

The user may toggle recall ON while the note is processing. The worker re-reads the flag again just before question generation, so it does not use a stale value.

---

### 2.3.2 Retrieve related notes `[SHARED]`

**Function:** `fetch_note_context(user_id, raw_text, limit_hybrid=3, exclude_note_id=note_id)`

**Input:**

- the new note’s raw text,
- the current user,
- the current note ID (excluded from its own context).

**Output:**

- `related_notes`: up to 3 notes,
- `retrieval_sources`: counts such as `hybrid_count` and `merged_note_count`.

**What runs underneath:**

The **same hybrid retrieval engine used by chat**:

- BM25 keyword search,
- dense pgvector search over `note_chunks`,
- exact-identifier search,
- RRF fusion.

The difference is the policy:

- **Note processing:** no query rewrite, `limit = 3`, exclude the current note, then **deduplicate by note ID and re-sort by recency** before passing the notes to Gemini.
- **Chat:** optional query rewrite, `limit = 5`, keep RRF ranking, then ground and format for the final LLM.

That recency sort is a useful interview detail: the ingestion prompt wants the most recent related context, not necessarily the highest RRF score.

**Why retrieve related notes during ingestion?**

They are given to Gemini as context. Example: a note says “Priya approved the revised date”; retrieval can pull the earlier note that explains what “revised date” refers to. The extraction is therefore grounded in prior work memory, not just the current note.

**Failure behavior:** retrieval errors are caught and logged. Processing continues with no related notes. A retrieval outage should not block note ingestion.

---

### 2.3.3 Load active long-term goals `[NOTE]`

**Input:** `user_id`

**Output:** active rows from the `commitments` table (user-authored goals).

These are passed into the extraction prompt so Gemini can decide whether the note contains **progress toward an existing goal**.

Important distinction:

- The note pipeline does **not** create new long-term goals.
- It can add a **contribution** (a short progress comment) to an already-active goal.
- Contributions are deduplicated by `(commitment_id, note_id)`, so reprocessing a note does not duplicate the same progress comment.

A goal-query failure is caught and logged; extraction continues without goals.

---

### 2.3.4 Gemini extraction `[LLM]`

**Function:** `call_gemini_api(raw_text, related_notes=..., commitments=...)`

**Input:**

- raw note text,
- summaries of up to 3 related notes,
- active long-term goals.

**Output:** a validated `WorkMemoryExtraction` object:

```text
summary
tasks[]
facts[]
questions[]
decisions[]
concepts[]
entities[]
commitment_contributions[]
```

Each item carries its own fields:

| Item | Main text field | Extra fields |
|---|---|---|
| Task | `description` | `confidence`, `due_date`, `importance`, `durability`, `entities` |
| Fact | `content` | `confidence`, `importance`, `durability`, `entities` |
| Question | `question` | `confidence`, `entities` |
| Decision | `decision` | `rationale`, `confidence`, `entities` |
| Concept | `concept` | `confidence`, `importance`, `durability`, `entities` |
| Entity | `name` | `entity_type` |
| Goal contribution | `comment` | `commitment_id` |

**Current schema does not include `risks`.** Older docs may mention a risks table, but the current `WorkMemoryExtraction` has no `risks` field and the worker does not insert risks.

**Why one extraction call per note?**

The note is small enough to fit in one prompt, and one call keeps the pipeline simple. This is also the design limit to mention for long documents: a 50-page PDF should be chunked and extracted per section, not stuffed into one prompt.

**Failure behavior:** parsing or model failure raises. The outer worker catches it, logs it, and re-raises so SQS retries. No extraction run is written if extraction fails.

---

### 2.3.5 Record the extraction run and project note metadata `[NOTE]`

**Functions:**

- `create_extraction_run(...)`
- `build_note_metadata(enrichment_res)`
- `update_note_item(...)`

**Input:** validated extraction.

**Output:**

1. A row in `extraction_runs` with:
   - `user_id`, `note_id`,
   - model name,
   - prompt version,
   - status (`completed`),
   - timestamps.
2. The note row is updated:
   - `enriched_summary`,
   - `context_note_ids` (deduplicated),
   - `action_items` (task descriptions),
   - `questions` (extracted open questions),
   - `metadata` (the raw extraction projection, schema version 2),
   - `processed_at`,
   - `status = "enriched"`.

**Why store the raw extraction in `notes.metadata`?**

It is the audit/debug record of what the model returned. Only high-value items are normalized into typed tables; keeping the full projection makes it possible to inspect or reprocess without re-calling the LLM.

**Why `enriched` instead of `indexed`?**

Extraction is persisted, but the note is **not retrievable yet**. The vector index has not been written. `enriched` is an honest intermediate state. It used to be reported as `completed` before indexing, which allowed a note to look done while being invisible to retrieval.

**Don’t confuse these two question stores:**

- `notes.questions` / the `questions` table = open questions extracted from the note.
- `recall_candidates.prompt` / `.answer` = flashcard-style recall questions generated later from scored candidates.

They are different features with different lifecycles.

---

### 2.3.6 Write typed memory rows `[NOTE]`

**Input:** the extraction object.

**Output rows:**

| Table | What it stores |
|---|---|
| `tasks` | Description, status, confidence, due date, importance, durability |
| `facts` | Content, confidence |
| `questions` | Question, status, optional answer, confidence |
| `decisions` | Decision, rationale, confidence |
| `concepts` | Concept, importance, durability |
| `entities` | Unique entity names, mention counts, importance |
| `memory_item_entity_links` | Links between a typed item and its entities |
| `commitment_contributions` | Progress comments on active user-authored goals |

Also in this stage:

- `bump_entity_mentions(...)` increases entity importance when an entity recurs across notes.
- Entity links are built by matching each item’s `entities` list to the upserted entity IDs.

**Why typed tables at all?**

The vector index is good at “find a note that means this.” Typed tables are good at exact, structured questions: “show me all open tasks,” “what decisions did I make about this project,” “which questions are still unanswered.” They are the source of truth for the memory views and the recall loop.

**Failure behavior:** typed-table writes are not wrapped in a broad try/except. A database failure raises and triggers SQS retry. This is where the idempotency caveat matters — see section 2.6.

---

### 2.3.7 Score recall candidates `[NOTE] [NO LLM]`

**Function:** `generate_candidates(...)`

**Input:**

- the extraction object,
- the source note ID,
- related note IDs,
- entity rows,
- the typed rows just inserted.

**Output:** rows in `recall_candidates`.

Candidate types:

- task,
- fact,
- concept,
- question,
- decision.

**Scoring formula (defaults):**

```text
score = 0.30 * importance
      + 0.20 * normalized_mention_count
      + 0.20 * related_note_count_score
      + 0.15 * recency_score
      + 0.15 * user_interest_score
```

Eligibility requires:

- score ≥ `0.45`,
- confidence ≥ `0.6` (when confidence is present).

The dedupe key is content-based:

```text
dedupe_key = "<item_type>:<sha1(normalized_text)>"
```

The repository upserts on `(user_id, dedupe_key)`. Crucially, it does **not** overwrite a candidate that has already moved past `eligible` (for example `suggested`, `carded`, or `rejected`). That makes reprocessing safe for recall state.

**The key interview point:**

> Candidates are scored **even when recall is disabled**. Only the question-and-answer generation is the expensive LLM step. Scoring first means toggling recall ON later is instant; it does not require re-running extraction.

There is **no default per-note cap** (`max_items_per_note = 0`). The product decision was that the review queue limits load, not an ingestion cap. This is a likely scaling question.

---

### 2.3.8 Generate recall questions and answers `[NOTE] [LLM, conditional]`

Only runs when `recall_enabled = true`.

**Input:**

- eligible candidates for this note,
- raw note text,
- up to 2 related note snippets,
- entity names.

**Output:** for each candidate, one LLM call that produces:

- `prompt` (the recall question),
- `answer`,
- `status = "suggested"` or `"rejected"`.

If the question is valid but the answer is not, the question is kept with `answer = null`; the answer can be generated later on reveal/accept.

The write is conditional on the candidate still being `eligible`, so a duplicate worker delivery cannot overwrite a question another writer already produced.

**Recall status:**

- `off` — user did not enable recall,
- `pending` — processing or waiting,
- `ready` — questions generated,
- `failed` — generation failed.

**If recall is disabled at ingestion**, `recall_status = "off"` and no question generation happens. If the user enables recall later, `PATCH /notes/{note_id}/recall` generates questions **synchronously** for the already-scored candidates. If the note is still processing, the status stays `pending` so the worker can finish instead of the UI claiming `ready` with zero suggestions.

**Why one LLM call per candidate?**

Each candidate needs a grounded question and answer. Batching them into one prompt would make validation and partial failure harder. The trade-off is cost and latency, which is exactly why this step is opt-in.

---

### 2.3.9 Deterministic task resolution `[NOTE] [NO LLM]`

**Function:** `apply_deterministic_task_resolution(...)`

**Input:** raw note text + user ID.

**Output:** zero or more existing open tasks marked `completed`.

It only runs when the note contains a completion marker:

```text
done | completed | finished | resolved | closed | fixed
```

Then:

1. Load all open tasks for the user.
2. Tokenize the note and each task description.
3. Require that any numbers in the note also appear in the task.
4. Rank by token overlap.
5. If there is exactly **one** best match, mark it `completed`.
6. If the top score is tied, do nothing.

**Why no LLM?**

Task completion is a high-impact, low-ambiguity action. A deterministic rule is auditable and conservative. A tie is treated as “not sure,” not as “complete both.”

**Failure behavior:** this call is not wrapped in a broad try/except. A failure raises and triggers SQS retry.

---

### 2.3.10 Chunk, embed, and index the note `[NOTE]`

**Function:** `index_note(user_id, note_id, text=raw_text)`

**Input:** the raw note text. The summary is **not** embedded here; only the raw text is chunked.

**Output:** rows in `note_chunks`, one per chunk:

```json
{
  "user_id": "...",
  "note_id": "...",
  "chunk_index": 0,
  "content": "...",
  "embedding": [0.012, -0.034, "... 768 floats ..."]
}
```

Under the hood:

1. `chunk_text()` splits the note into roughly 800-character chunks with 100-character overlap.
2. The embedding provider turns each chunk into a 768-dimensional vector.
3. `replace_note_chunks()` deletes the note’s old chunks and inserts the new ones.
4. pgvector’s HNSW index makes nearest-neighbor search fast.

**Why is indexing last?**

Failed extraction should not pollute the retrieval index. Indexing is the step that makes the note retrievable, so it also decides the terminal status:

- success → `status = "indexed"`,
- failure → `status = "failed"` and `index_error` is stored.

A note is **not retrievable until `index_note` succeeds**. This is why `enriched` is not a success state.

**Failure behavior in the EC2 worker:** the indexing exception is caught inside `process_sqs_message`, the note is marked `failed`, and the function returns normally. The consumer then deletes the SQS message. In other words, an indexing failure is **terminal**, not retried automatically. A manual reprocess can move `failed → processing` and try again.

---

### 2.3.11 Finalize the note `[NOTE]`

**Function:** `_finalize_note(...)`

**Input:** terminal status, recall status, optional `indexed_at` or `index_error`.

**Output:** the note row is updated with the terminal state.

This status write is **best effort**: if it fails, the error is logged but the job is not re-raised. The reason is important:

> The typed memories and vectors are already persisted. Re-raising would trigger a full SQS redelivery and re-run the LLM, which is worse than a stale status. A status repair can be done separately.

---

## 2.4 Note status lifecycle

```text
processing ──> enriched ──> indexed
     │             │
     └─────────────┴──────> failed ──> processing (retry)
```

| Status | Meaning | Retrievable? |
|---|---|---|
| `processing` | Worker is running; nothing user-visible is complete yet | No |
| `enriched` | Extraction and typed memories are persisted; vectors are not | **No** |
| `indexed` | Typed memories **and** vectors are in place | **Yes** |
| `failed` | Terminal failure; `index_error` explains why | No |

`indexed` is the **only** success terminal state. `enriched` deliberately sits between extraction and indexing.

The state machine is enforced in `note_status.py`. Idempotent writes (`current == next`) are allowed so a retry does not fail on a state it already reached.

---

## 2.5 Failure behavior at a glance

| Failure | What happens | SQS retry? |
|---|---|---|
| Bad/missing SQS body fields | Raises immediately | Yes, then DLQ |
| Related-note retrieval fails | Caught; continues with no related notes | No |
| Active-goal query fails | Caught; continues without goals | No |
| Gemini extraction/parsing fails | Raises | Yes, then DLQ |
| Typed-table insert fails | Raises | Yes, then DLQ |
| Recall candidate generation fails | Caught; `recall_status = "failed"` | No |
| Recall Q+A generation fails | Caught; `recall_status = "failed"` | No |
| Deterministic task resolution fails | Raises | Yes, then DLQ |
| Vector indexing fails | Caught; note marked `failed` | **No** in the EC2 consumer |
| Terminal status write fails | Logged; job still returns success | No |

**Interview nuance:** “SQS retries on failure” is only half true. The code deliberately distinguishes between failures that should re-run the whole note (extraction, typed writes) and failures that are already terminal or best-effort (indexing, status write, recall generation). That distinction protects against duplicate LLM spend and infinite retries.

---

## 2.6 Idempotency: what is safe and what is not

This is one of the best interview topics because it shows you understand at-least-once delivery.

**Safe / idempotent:**

- `note_chunks` — `replace_note_chunks` does delete-then-insert per note.
- `recall_candidates` — upsert on `(user_id, dedupe_key)`; does not clobber candidates past `eligible`.
- `commitment_contributions` — dedupe on `(commitment_id, note_id)`.
- Note status transitions — same-state writes are allowed.

**Not fully idempotent today:**

- `extraction_runs` — a retry creates a new run row.
- `tasks`, `facts`, `questions`, `decisions`, `concepts` — each retry generates new UUIDs, so a note that fails halfway can end up with duplicate typed rows.
- `bump_entity_mentions` — a retry can double-count mentions.

The planned fix (documented in `learning.md`) is deterministic upsert keys:

```text
sha1(normalize_text(item_text))
unique (user_id, source_note_id, dedupe_key)
```

That keeps task IDs stable across retries while preserving provenance per note.

**Say this in an interview:**

> “Recall candidates and note chunks are idempotent, but the typed memory rows are not yet. SQS gives at-least-once delivery, so a mid-pipeline retry can duplicate extraction rows. The designed fix is a deterministic content hash plus a unique index and `ON CONFLICT DO UPDATE`, scoped per user and source note.”

Do **not** say “the pipeline is fully idempotent.”

---

## 2.7 What is stored where

| Store | What it holds | Written by | Read by |
|---|---|---|---|
| `notes` | Raw text, status, summary, context note IDs, metadata | Note API + worker | Chat BM25, UI, worker |
| `extraction_runs` | One row per extraction attempt | Worker | Audit/debug |
| `tasks`, `facts`, `questions`, `decisions`, `concepts` | Typed structured memory | Worker | Memory views, recall scoring |
| `entities` | Unique people/projects/terms + importance | Worker | Entity links, recall scoring |
| `memory_item_entity_links` | Typed item ↔ entity links | Worker | Memory views |
| `commitments` + `commitment_contributions` | User-authored goals + progress comments | Goals API + worker | Goals UI |
| `recall_candidates` | Scored candidate memory units + optional Q/A | Worker | Recall UI |
| `note_chunks` | Chunk text + 768-d embeddings | Worker | Dense retrieval |
| `chat_messages` | Chat turns | Chat pipeline | Chat memory |

---

# 3. Chat retrieval — read path `[CHAT]`

## 3.1 Entry and intent gate `[CHAT]`

**Input:** a chat message.

**What happens first:**

1. Find or create the chat thread.
2. Store the user message in `chat_messages`.
3. Load the last 8 messages (`SHORT_TERM_WINDOW = 8`) and the thread summary.
4. Run the intent classifier.
5. If `needs_retrieval = false` (for example “thanks!”), skip retrieval entirely.
6. If `needs_retrieval = true`, call `retrieve_query_context(...)`.

**Output:** either a direct/tool response path, or a retrieval request.

**Why gate retrieval?**

Not every message needs memory. Greetings and small talk should not pay for BM25, embeddings, and a database round trip.

---

## 3.2 Optional query rewrite `[CHAT] [LLM]`

**Input:**

- the user query,
- recent memory (tasks/facts/etc. for the rewriter’s background),
- the last few chat turns.

**Output:**

```json
{
  "rewritten_query": "...",
  "likely_answer": "...",
  "confidence": 0.0,
  "risk_flags": []
}
```

The rewrite is used only if:

- the query looks substantial enough,
- confidence is high enough,
- no risk flags were detected,
- and the query has no explicit identifier like `ITEM-4101`.

Risk checks include:

- missing numbers,
- lost negation,
- semantic drift,
- empty rewrite.

If accepted, the alternate query combines the original, the rewrite, and the likely answer, and a third dense search runs against that alternate query.

**Why guard the rewrite?**

A rewrite can accidentally inject the supposed answer into the search query, which biases retrieval. The risk checks keep the rewrite as a helper, not the main retrieval strategy.

**Note:** this is an LLM call **before** retrieval. If you are explaining “the pipeline until the final LLM,” this is an earlier, optional LLM touchpoint.

---

## 3.3 Hybrid retrieval core `[SHARED]`

This is the same core used by note processing for related-note context.

### BM25 — exact-word search

**Input:** query text + the user’s notes.

**Output:** a ranked list of notes with BM25 scores.

How it works:

1. Lowercase and tokenize the query.
2. Remove stop words.
3. Score each note by keyword overlap, term rarity, and note length.
4. Keep results with score > 0.
5. Return the top candidates.

BM25 indexes a **combined note text**:

```text
raw_text
enriched_summary
text
summary
title
content
```

It is built **lazily, per user**, from the `notes` table, then cached in memory. The cache key is a fingerprint of `note_id + updated_at`. It is not stored in Postgres.

Best at: names, jargon, exact phrases, numbers, IDs.  
Bad at: synonyms and paraphrases. “Slip” will not match “delay.”

> Gotcha: the code stores the BM25 score in a field called `distance`, but higher is better. Dense retrieval’s `distance` is the opposite: lower is better. RRF exists partly to hide that mismatch.

### Dense — meaning search

**Input:** the query.

**Output:** the query’s 768-number embedding → nearest `note_chunks` → best chunk per note → ranked notes.

Flow:

1. Embed the query with the same embedding model used for notes.
2. Call `match_note_chunks(query_embedding, user_id, count)`.
3. Get chunk rows with cosine distances.
4. Group chunks by `note_id`.
5. Keep only the best-scoring chunk per note.
6. Return the top notes.

Best at: paraphrases, concepts, “why did X happen?” questions.  
Bad at: exact IDs and rare tokens.

### Exact-identifier search

**Input:** query.

**Output:** notes containing an exact identifier such as `ITEM-4101` or `CVE-2026-1234`.

This is deterministic, not similarity-based. Exact hits get a **3× weight** in fusion, because if the user typed a specific ID, they probably mean it.

### Parallelism

Dense-original, BM25, and dense-rewritten searches are independent and run concurrently in a `ThreadPoolExecutor`. Exact-ID search runs after, since it is cheap and deterministic.

---

## 3.4 RRF fusion `[SHARED]`

**Input:** several ranked lists:

- exact matches,
- BM25 results,
- dense results,
- optional rewritten-query dense results.

**Output:** one merged ranked list.

The formula for each note:

```text
rrf_score = Σ 1 / (60 + rank)
```

Example:

- Note A is #2 in BM25 and #4 in dense: `1/62 + 1/64 ≈ 0.0318`
- Note B is #1 in BM25 only: `1/61 ≈ 0.0164`

Note A wins because it was supported by two independent retrievers.

**Why RRF instead of adding raw scores?**

- BM25 scores and cosine distances are not on the same scale.
- Calibrating them is query-dependent and fragile.
- Ranks are comparable. RRF is simple and robust.

**Candidate depth:** with `limit = 5`, each source fetches `5 × 3 = 15` candidates. Fusion produces up to 15; the final cut keeps 5. For note ingestion, `limit = 3`, so it fetches 9 and keeps 3.

---

## 3.5 Optional reranking — currently off `[CHAT]`

The code supports a cross-encoder reranker, but it is **off by default**:

```text
QUERY_RETRIEVAL_RERANKER=off
```

Your evaluation showed it hurt:

- Recall@5: `0.953 → 0.884`
- MRR@5: `0.818 → 0.809`

So production keeps the RRF order and cuts to the top 5. If enabled, the reranker would reorder the fused candidates before the cut.

**Interview point:** this is a good example of measuring a plausible optimization and rejecting it on evidence rather than shipping it because it sounds advanced.

---

## 3.6 Grounding guardrail `[CHAT] [NO LLM]`

**Input:** the top candidates + the user’s message + thread summary + recent messages.

**Output:**

```json
{
  "status": "strong | weak | conflict | no_context",
  "confidence": 0.0,
  "allow_answer": true,
  "source_refs": [],
  "fallback_message": null
}
```

How it works:

- Each piece of evidence gets an authority weight:
  - retrieved notes: **3.0**,
  - thread summary: **1.8**,
  - recent chat messages: **1.2**.
- It scans for claim markers such as “done/complete,” “waiting/pending,” “blocked.”
- It combines `authority × recency × retrieval_score × overlap`.
- If one claim clearly wins, the answer is allowed.
- If evidence is missing, weak, or conflicting, the answer is blocked or hedged.

This is the last safety gate before generation. If `allow_answer = false`, the final LLM is not called at all; the user gets a fallback message.

**Why it matters:** retrieval quality is not just “did we find something?” It is also “is the evidence strong enough to assert an answer?” The guardrail prevents confident answers from thin or contradictory context.

---

## 3.7 Format the context `[CHAT]`

**Input:** the top 5 candidates.

**Output:** a prompt-ready block:

```text
Knowledge memory:
- [note-123] Launch moved to Nov 15; analytics not ready.
- [note-456] Priya prefers weekly demos.
```

In chat, it prefers the **summary** over the raw text and truncates each excerpt to 240 characters.

The LLM does **not** see your whole database — only this short list.

---

## 3.8 Final answer LLM and save `[CHAT] [LLM]`

The prompt contains:

- intent,
- plan,
- conversation summary memory,
- short-term conversation memory (last 8 messages),
- formatted knowledge memory,
- grounding guardrail,
- tool results,
- the user’s message.

Then `chat_model.generate(prompt)` runs. That is the first **answer-generating** LLM call.

After generation, the assistant message is stored in `chat_messages`. Periodically, older turns are compacted into the thread summary so the short-term window does not grow forever.

---

# 4. Note-only vs chat-only vs shared

| Capability | Note processing | Chat |
|---|---|---|
| Trigger | `POST /notes` | `POST /chat/message` |
| Execution | Async SQS worker | Synchronous HTTP request |
| Gemini extraction | **Yes** | No |
| Typed memory writes | **Yes** | No (chat does not create notes) |
| Recall candidate scoring | **Yes** | No |
| Recall Q+A generation | **Yes, if enabled** | No |
| Deterministic task resolution | **Yes** | No |
| Chunk + embed + index | **Writes** | **Reads** |
| BM25 + dense + RRF | **Reads for related context** | **Reads for answer context** |
| Query rewrite | No | **Optional** |
| Grounding guardrail | No | **Yes** |
| Final answer LLM | No | **Yes** |
| Thread/message persistence | No | **Yes** |

**Shared things:**

- the `notes` table,
- `note_chunks` and pgvector,
- `HybridRetriever` (BM25 + dense + exact + RRF),
- user scoping,
- the embedding model.

**Not shared:**

- note processing writes typed memory and recall candidates; chat does not.
- chat writes chat messages and thread summaries; note processing does not.
- chat adds query rewrite, grounding, and final answer generation; note processing does not.

---

# 5. Inputs and outputs at a glance

| Stage | Input | Output | Pipeline | LLM? |
|---|---|---|---|---|
| Save note | text, recall flag | `notes` row + SQS job | `[NOTE]` | No |
| Load note/flag | SQS body | recall flag, status | `[NOTE]` | No |
| Related notes | raw text, user, note ID | up to 3 related notes | `[SHARED]` | No |
| Load goals | user ID | active commitments | `[NOTE]` | No |
| Extract | raw text + related notes + goals | summary/tasks/facts/questions/decisions/concepts/entities/contributions | `[NOTE]` | **Yes** |
| Extraction run | extraction result | `extraction_runs` row | `[NOTE]` | No |
| Note metadata | extraction result | `notes.metadata` + summary + context IDs | `[NOTE]` | No |
| Typed rows | extraction result | tasks/facts/questions/decisions/concepts/entities/links/contributions | `[NOTE]` | No |
| Recall candidates | extraction + typed rows | scored `recall_candidates` | `[NOTE]` | No |
| Recall Q+A | eligible candidates + context | question/answer pairs | `[NOTE]` | **Yes, if enabled** |
| Task resolution | raw text | completed tasks (maybe) | `[NOTE]` | No |
| Chunk | raw text | ~800-char overlapping chunks | `[NOTE]` | No |
| Embed | chunks | 768-d vectors | `[NOTE]` | Embedding model |
| Index | vectors | `note_chunks` rows | `[NOTE]` | No |
| Finalize | status | `indexed` or `failed` | `[NOTE]` | No |
| Chat intent | message | `needs_retrieval` | `[CHAT]` | No |
| Query rewrite | query + recent memory | alternate query / likely answer | `[CHAT]` | **Optional** |
| BM25 | query + notes | ranked notes | `[SHARED]` | No |
| Dense | query embedding | ranked notes | `[SHARED]` | No |
| Exact IDs | query | notes with exact IDs | `[SHARED]` | No |
| RRF | ranked lists | fused ranked list | `[SHARED]` | No |
| Cut | fused list | top 5 candidates | `[CHAT]` | No |
| Grounding | candidates + message | allow/block + source refs | `[CHAT]` | No (rules) |
| Format context | top 5 | `Knowledge memory` block | `[CHAT]` | No |
| Final answer | prompt | assistant text | `[CHAT]` | **Yes** |
| Save reply | assistant text | `chat_messages` row | `[CHAT]` | No |

---

# 6. Interview Q&A

## 6.1 “Walk me through what happens when I save a note.”

> “The API writes the note with `status=processing` and returns 202. It enqueues an SQS job. The worker retrieves related notes with the same BM25 + dense + RRF engine chat uses, loads active goals, and sends the note plus that context to Gemini. Gemini returns a summary, tasks, facts, questions, decisions, concepts, entities, and goal contributions. The worker writes those to typed tables, creates an extraction run, and stores the raw extraction on the note. It then scores recall candidates from the typed items. If recall is enabled, it generates question/answer pairs. Next it runs deterministic task completion, then chunks and embeds the raw note into pgvector. Only after indexing succeeds does the note become `indexed` and retrievable.”

## 6.2 “Why is note processing asynchronous?”

> “Gemini extraction and optional recall-question generation take tens of seconds. The API should return immediately, and the work should survive a process crash. SQS gives at-least-once delivery, retries, and a DLQ. Running the worker as a separate systemd service also keeps CPU-heavy processing away from API request handling.”

## 6.3 “Why does the note go through `enriched` before `indexed`?”

> “`enriched` means the LLM extraction and typed rows are persisted, but the vector index is not written yet. The note is still invisible to retrieval. `indexed` is the only success state because it guarantees both structured memory and vectors exist. Before this state machine, a note could be marked `completed` before indexing and be impossible to retrieve.”

## 6.4 “Why generate recall candidates when recall is off?”

> “Candidate scoring is deterministic and cheap. Only question/answer generation costs an LLM call. Scoring first means if the user toggles recall on later, the system can generate questions immediately from existing candidates instead of re-running extraction.”

## 6.5 “Why hybrid retrieval instead of just vector search?”

> “Dense search is good at meaning but bad at exact identifiers and numbers — embeddings can treat `ITEM-4111` and `ITEM-4110` as nearly identical. BM25 is good at exact terms but blind to paraphrases. Running both and fusing them gets the best of each. The exact-identifier channel handles IDs deterministically.”

## 6.6 “Why RRF instead of averaging scores?”

> “BM25 scores and cosine distances are not on the same scale, and the right calibration is query-dependent. RRF only uses each result’s rank in each list, which is scale-independent. A note that appears near the top of both lists gets a higher fused score than a note that appears in only one.”

## 6.7 “Why is the reranker off?”

> “I evaluated a cross-encoder over a 15-candidate pool and it reduced Recall@5 from 0.953 to 0.884 and MRR@5 from 0.818 to 0.809. The regressions were concentrated in short factual notes. Keeping RRF alone was the evidence-based choice. The reranker is still wired behind an env flag.”

## 6.8 “What happens on retry? Is the pipeline idempotent?”

> “SQS gives at-least-once delivery, so retries are expected. `note_chunks` are delete-then-insert and idempotent. `recall_candidates` upsert on `(user_id, dedupe_key)` and never overwrite a candidate past `eligible`. Goal contributions dedupe on `(commitment_id, note_id)`. But the typed memory tables currently create new UUIDs on each retry, so a mid-pipeline failure can duplicate tasks or facts. The designed fix is a deterministic content hash plus a unique index and `ON CONFLICT DO UPDATE`, scoped per user and source note. So: partially idempotent today, not fully.”

## 6.9 “Why deterministic task resolution instead of asking the LLM?”

> “Marking a task complete is a high-impact action. The deterministic rule only runs when the note contains a completion marker, requires the note’s numbers to appear in the task, and requires exactly one best token-overlap match. A tie does nothing. That is auditable and conservative; an LLM could confidently close the wrong task.”

## 6.10 “What does the final LLM actually see?”

> “Only a short context block: the top 5 notes, each represented by its summary or best chunk, truncated to 240 characters, plus conversation summary, the last 8 messages, the grounding verdict, the user message, and any tool results. It never sees raw database rows or the whole vector index.”

## 6.11 “What would you change for long documents?”

> “I would not put a 50-page PDF into one extraction prompt. I would add document ingestion that extracts text, chunks by page or section, runs extraction per chunk or section, and merges the results with caps and dedupe. The existing `note_chunks` and pgvector path can be reused, but the recall-candidate path needs per-chunk scoring and a source-page citation schema. OCR and figures are a separate, harder tier.”

---

# 7. Common traps / things not to say

| Don’t say | Say instead |
|---|---|
| “The LLM extracts and answers in one call.” | Note extraction and chat answer generation are separate pipelines and separate calls. |
| “Chat messages become notes.” | Chat messages are stored in `chat_messages`; they are not embedded or extracted. |
| “A note is done when extraction finishes.” | It is `enriched`; it becomes `indexed` and retrievable only after vector indexing. |
| “BM25 is stored in Postgres.” | BM25 is an in-memory, per-user index rebuilt lazily from the `notes` table. |
| “We use Chroma at runtime.” | Runtime retrieval uses pgvector (`note_chunks`); Chroma remains in eval/history tooling. |
| “The pipeline is fully idempotent.” | Candidates/chunks are idempotent; typed rows currently are not. |
| “The reranker is active.” | It is off by default; the eval rejected it. |
| “The LLM sees all my notes.” | It sees the top 5 formatted excerpts, not the database. |
| “Chat searches the typed tasks/facts tables directly.” | Final chat candidates are notes/chunks; typed tables power memory views, recall, and rewrite context. |
| “Recall questions are generated for every note.” | Candidates are scored for every note; Q+A generation is opt-in via `recall_enabled`. |
| “Risks are extracted.” | The current `WorkMemoryExtraction` has no `risks` field. |
| “Related notes are passed to Gemini in RRF order.” | Note processing dedupes them and re-sorts by recency before building the extraction prompt. |
| “`notes.questions` are the recall cards.” | They are extracted open questions; recall cards live in `recall_candidates.prompt/answer`. |

---

# 8. One-paragraph answers to memorize

### Note processing

> “A note is saved as `processing` and queued to SQS. The worker retrieves related notes with hybrid retrieval, loads active goals, and calls Gemini once to extract a summary, tasks, facts, questions, decisions, concepts, entities, and goal contributions. It writes typed rows and an extraction run, marks the note `enriched`, scores recall candidates, optionally generates recall Q+A, runs deterministic task completion, then chunks and embeds the raw note into pgvector. Only after indexing succeeds does it become `indexed` and retrievable. Failures either retry via SQS/DLQ or become terminal `failed`, depending on the stage.”

### Chat retrieval

> “A chat message is stored, the intent gate decides whether memory is needed, and an optional rewrite expands the query. BM25, dense pgvector search, and exact-ID search run over the user’s notes, then RRF fuses their ranked lists. The top five notes go through a rule-based grounding guardrail, are formatted into a short knowledge block, and only then reach Gemini. Reranking is disabled because the evaluation showed it reduced Recall@5.”

### The whole system in one sentence

> “Note processing writes structured memory and a hybrid-search index once; chat retrieval reads that index on every turn and compresses it into a small, grounded context block for the answer LLM.”

---

# 9. Code map

| Concern | File / function |
|---|---|
| Create note + queue job | `backend/app/api/routes/notes.py` → `create_note` |
| SQS send | `backend/app/infrastructure/queue/sqs_client.py` → `send_note_job` |
| SQS poll/delete | `backend/app/infrastructure/queue/sqs_poller.py` |
| EC2 worker loop | `backend/app/workers/sqs_consumer.py` → `run_forever` |
| Note pipeline | `backend/app/workers/note_processor.py` → `process_sqs_message` |
| Note status machine | `backend/app/domain/memory/note_status.py` |
| Gemini extraction | `backend/app/infrastructure/llm/gemini_client.py` → `call_gemini_api` |
| Extraction schema | `backend/app/schemas/models.py` → `WorkMemoryExtraction` |
| Metadata projection | `backend/app/domain/memory/extraction_v2.py` → `build_note_metadata` |
| Typed inserts | `backend/app/domain/memory/services.py` + `backend/app/infrastructure/db/memory_repository.py` |
| Goal contributions | `backend/app/domain/commitments/services.py` → `persist_note_contributions` |
| Recall candidates | `backend/app/domain/recall/candidate_service.py` + `candidate_engine.py` |
| Recall scoring | `backend/app/domain/recall/candidate_scoring.py` |
| Recall Q+A | `backend/app/domain/recall/question_service.py` |
| Task resolution | `backend/app/domain/memory/services.py` → `apply_deterministic_task_resolution` |
| Chunking | `backend/app/infrastructure/vector/chunking.py` → `chunk_text` |
| Indexing | `backend/app/infrastructure/vector/vectorstore.py` → `index_note` |
| pgvector writes/reads | `backend/app/infrastructure/vector/pg_vector_store.py` |
| Hybrid retriever | `backend/app/domain/query_retrieval/hybrid_retriever.py` |
| BM25 | `backend/app/domain/query_retrieval/strategies/sparse.py` |
| Note-ingestion retrieval policy | `backend/app/domain/query_retrieval/note_context_provider.py` |
| Chat retrieval orchestration | `backend/app/domain/query_retrieval/services.py` → `retrieve_query_context` |
| Chat routing | `backend/app/domain/chat/orchestrator.py` + `backend/app/domain/routing/orchestrator.py` |
| Grounding | `backend/app/domain/chat/guardrails.py` → `assess_grounding` |
| Status SQL | `backend/sql/phase6_note_status.sql` |
| Chunk SQL | `backend/sql/phase4_pgvector.sql` |

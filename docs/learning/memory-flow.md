# NorthStar Memory Flow — Revision Notes

Plain-language recap of how NorthStar builds "memory" for the LLM, for quick
revision before interviews. Read top to bottom; each section stands alone.

---

## 1. The one-line answer

NorthStar has **two independent pipelines**:

1. **Notes pipeline** — write-time. When you save a note, it gets enriched
   once and stored in two places: structured facts in a relational database,
   and a meaning-vector in a vector database.
2. **Chat pipeline** — read-time. Every chat message triggers a fresh search
   across both databases, merges what it finds, and asks the LLM to answer
   using only that merged context.

**Chat messages are never turned into notes.** They live in their own
`chat_messages` table and are never embedded or extracted. The two pipelines
only meet when chat retrieval reads from the notes that already exist.

---

## 2. The two stores, and why both exist

| Store | Type | What it holds | Good at |
|---|---|---|---|
| Relational (Postgres/Supabase) | structured rows | notes, tasks, facts, questions, decisions, risks, concepts, chat threads, chat messages | exact filters ("all open tasks"), source of truth, cheap reads |
| Vector (Chroma) | embeddings | one vector per note, tagged with `user_id` | "meaning" search — finds a note even if the wording is totally different |
| BM25 (in-memory index) | keyword index | tokenized note text, rebuilt from the relational notes | exact keyword/ID matches ("Datafix 42") |

Why not just one? Vector search is great at "this note means the same
thing" but bad at exact IDs (embeddings can confuse `ITEM-4111` with
`ITEM-4110`). Keyword search (BM25) is great at exact IDs but blind to
rephrasing. NorthStar runs both and **fuses** the results — that's the
"hybrid" in hybrid retrieval.

---

## 3. Notes pipeline (write-time) — step by step

Say you save 3 notes about "Datafix 42" over a few days: a progress update,
a note that the lead confirmed it, and a note that the client asked for a
clarification.

Each `POST /notes` call does this ([notes.py](../../backend/app/api/routes/notes.py) → [note_processor.py](../../backend/app/workers/note_processor.py)):

1. Save the raw note to the relational `notes` table with `status=processing`.
2. Queue a background job (SQS) to process it (or run inline in dev).
3. **Worker runs once**, calling Gemini to extract structured pieces out of
   the raw text: a summary, tasks, facts, questions, decisions, risks.
4. Those structured pieces become **new rows** in relational tables:
   `tasks`, `facts`, `decisions`, etc. Example: a `tasks` row like
   *"Get lead confirmation on Datafix 42"*, later flipped to `completed`.
5. The **whole raw note text** gets embedded (turned into a vector) and
   upserted into Chroma, scoped by `user_id`.
6. Note status flips to `completed`.

**Key idea:** enrichment happens exactly once, when the note is created.
Reading a note later (`GET /notes/{id}/memory`) is a plain relational read —
no LLM call, no vector search, nothing "live" about it.

---

## 4. Chat pipeline (read-time) — step by step

Now you type **"Datafix 42 done"** in chat. Here's everything that happens,
in order.

### Step 1 — Store the turn (relational only)
[chat/services.py](../../backend/app/domain/chat/services.py) `handle_chat_message`:
- Find or create the chat thread (relational).
- Insert your message into `chat_messages` (relational).
- Load the last 8 messages of this thread (`SHORT_TERM_WINDOW = 8`) — relational read.
- Load the thread's rolling `summary` field (relational) — a compacted digest of older turns.

Nothing vector-related has happened yet.

### Step 2 — Decide if we even need to search
An intent classifier looks at "Datafix 42 done" and decides this is a
factual/status question, so `needs_retrieval = True`. (If you'd said "thanks!"
it would skip retrieval entirely.)

### Step 3 — Hybrid retrieval
[query_retrieval/services.py](../../backend/app/domain/query_retrieval/services.py) `retrieve_query_context` runs:

1. **Relational snapshot**: grab your recent tasks/decisions/etc. This isn't
   shown to you directly — it's handed to the query rewriter as background
   context so it can rewrite your question more precisely.
2. **Dense (vector) search**: embed "Datafix 42 done", search Chroma for your
   `user_id`. This can find the client-clarification note even if it never
   uses the word "done", because vectors capture meaning.
3. **Sparse (BM25) search**: keyword search over the same notes. This
   strongly favors the progress-update and lead-confirmation notes because
   they literally contain "Datafix" and "42".
4. **Guarded query rewrite (optional)**: if your query looks "rich enough"
   (has a number, isn't too short/generic), Gemini proposes a rewritten,
   expanded version of the query. If the rewrite is confident and doesn't
   silently drop a number or a "not"/negation, a **third** dense search runs
   using the rewritten query.
5. **Fusion (RRF — Reciprocal Rank Fusion)**: merge the 3 result lists
   (sparse, dense-original, dense-rewritten) into one ranked list. Notes that
   show up near the top of multiple lists rank highest overall.
6. **Rerank (optional)**: a cross-encoder model re-scores the fused list for
   a final, more precise order.

End result: a ranked list of ~5 candidate notes (your 3 Datafix notes should
be near the top), each just raw evidence — no verdict yet on whether it's
"done".

### Step 4 — Grounding: turn evidence into a verdict
[chat/guardrails.py](../../backend/app/domain/chat/guardrails.py) `assess_grounding` is the "merge relational + vector into one answer"
step. It gathers three kinds of evidence and gives each a different trust
weight (authority):

| Evidence source | Authority weight | Example |
|---|---:|---|
| Retrieved notes (vector+BM25) | 3.0 (highest) | the lead-confirmation note |
| Thread summary | 1.8 | "earlier discussed Datafix rollout" |
| Recent chat messages | 1.2 (lowest) | your last few chat turns |

For each piece of evidence, it scans for keywords like "done"/"completed"
(→ `completed`), "waiting"/"pending" (→ `pending`), "blocked" (→ `blocked`).
Each piece of evidence gets a weight = `authority × recency × how well it
matches your query`. All the "completed"-flavored evidence gets summed up,
same for "pending", same for "blocked" — whichever claim has the highest
total weight wins, **as long as** it's clearly ahead of the runner-up.

Four possible outcomes:
- **strong** — one claim clearly wins → answer normally.
- **weak** — evidence exists but isn't confident enough → hedge the answer.
- **conflict** — two claims are close in weight (e.g. progress note says
  "in progress", confirmation note says "completed") → tell the user about
  the disagreement instead of picking one.
- **no_context** — nothing relevant found at all → say so, ask for more info.

### Step 5 — Build the prompt and call the LLM
[chat/orchestrator.py](../../backend/app/domain/chat/orchestrator.py) assembles one text prompt with clearly labeled sections:
```
Conversation summary memory     <- relational thread.summary
Short-term conversation memory  <- relational, last 8 chat_messages
Knowledge memory                <- the fused/reranked notes from Step 3
Grounding guardrail             <- the verdict from Step 4
```
This whole block, plus your raw message, goes to Gemini **once**. The model
never sees raw database rows or raw vectors — only these pre-digested text
blocks.

### Step 6 — Save the reply
The assistant's answer is stored back into `chat_messages` (relational).
Periodically, once a thread gets long enough, older turns get compacted into
`thread.summary` (relational) so the short-term window doesn't grow forever.

---

## 5. Notes flow vs. Chat flow — side by side

| | Notes flow (`POST /notes`) | Chat flow (`POST /chat/message`) |
|---|---|---|
| When does LLM/retrieval run? | Once, at save time | Every single message |
| Vector DB | **Written to** (one embedding stored) | **Read from** (semantic search) |
| Relational DB | **Written to** (tasks/facts/decisions extracted) | **Read from** (recent chat, summary, recent-memory snapshot) |
| BM25 keyword search | Not used | Used, fused with vector results |
| Grounding/guardrails | Not applied | Applied every turn |
| Output | Structured rows you can query later, instantly, with no LLM call | A generated natural-language answer (not saved as structured memory) |

**One-sentence mental model:** notes are the source of truth, written once
and indexed twice (a row + a vector); chat is a live consumer that re-fuses
whatever exists at query time and never changes the underlying notes.

---

## 6. Likely interview follow-ups

**Q: Why hybrid retrieval instead of just vector search?**
A: Vector search alone is bad at exact identifiers/numbers (embeddings treat
`ITEM-4111` and `ITEM-4110` as nearly identical). Keyword search (BM25) is
bad at paraphrases. Fusing both gets the best of each.

**Q: Why fuse with RRF instead of just averaging scores?**
A: Dense and sparse scores aren't on the same scale (cosine distance vs.
BM25 score), so you can't average them directly. RRF only cares about each
result's *rank* in each list, which is scale-independent and simple to
combine fairly.

**Q: What stops the model from confidently answering with no real evidence?**
A: The grounding step. If no evidence is found, or evidence is weak, or two
sources disagree, the system routes to a hedge/clarify/abstain answer
instead of asserting a fact.

**Q: Why not just dump the whole database into the prompt?**
A: Cost, latency, and noise. Retrieval limits it to a handful of the most
relevant notes (top-5 by default) instead of everything, and grounding
compresses "evidence" into a short verdict instead of raw rows.

**Q: What's the difference between short-term memory and summary memory?**
A: Short-term memory is the literal last 8 messages (relational rows, verbatim).
Summary memory is a compacted digest of everything *older* than that window,
refreshed periodically so the prompt doesn't grow unbounded as a conversation
gets long.

# Executive Summary  
Northstar will pivot from a generic AI-notes app into a **personal memory system** and RAG-based Q&A tool. The core loop becomes **Capture → Understand → Remember → Act**. New notes flow into Northstar, which extracts key knowledge (facts, concepts, tasks, etc.) and embeds them. The system then *actively* reinforces important knowledge via spaced‐repetition flashcards (questions) and turns commitments into calendar events. For example, Northstar might ask you “*What is SQS visibility timeout?*” on a review day instead of passively showing you another summary. This recall-centric focus leverages proven cognitive science: actively retrieving knowledge boosts retention. Meanwhile, the LLM chat agent and daily/weekly summaries are still provided via Retrieval-Augmented Generation (RAG), but **support** (not lead) the product. The result is a product that turns **what you learn into what you remember and do**, rather than merely another note-taking app.  

# Product Pivot & User Value  
- **From Notes to Memory:** Instead of just archiving notes, Northstar helps users retain *important* knowledge over time via automated Q&A cards (flashcards) and review sessions. This taps the *spacing effect* in memory, which shows that “rehearsal spaced over time” greatly improves retention.  
- **Evidence-Based RAG:** Northstar will use a **Retrieval-Augmented Generation** architecture to answer user queries. As IBM explains, RAG “connects [an LLM] with external knowledge bases” so the model’s output is more relevant and accurate. In practice, this means every query first retrieves semantically similar notes (via vector search/BM25) and then the LLM synthesizes answers using that context. Users get up-to-date, domain-specific answers without hallucination.  
- **Memory + Action:** Northstar doesn’t just generate summaries; it **turns notes into outcomes**. Important tasks or decisions extracted from notes can be confirmed as commitments (e.g. “Finish frontend by Friday”) and added to the user’s Google Calendar. This closes the loop to *action*.  
- **User Value:** The end-user (knowledge worker, developer, learner) will see three things on any given day: **(1)** *What matters today* – a dashboard of today’s commitments and key insights, **(2)** *What to remember* – scheduled flashcards due for review, and **(3)** *What to do* – next tasks/deadlines (Calendar view). By contrast to an “AI notes app”, the user gets an **active system** that builds memory and nudges actions.  

# MVP Scope  

- **Built-In:**  
  - **Fast Note Capture:** Text editor (web app) for user to add/edit notes.  
  - **Backend Processing (async):** Upon note save, queue a job that:  
    - Summarizes the note (optional short version).  
    - Extracts structured items (facts, concepts, tasks, decisions, risks, questions, entities) via LLM/ML.  
    - Computes and stores embeddings for retrieval.  
  - **Vector+BM25 Retrieval:** Store note chunks in a database index. Implement hybrid search: lexical (BM25) + vector (embedding) for queries. (Use pgvector or a vector DB.)  
  - **Recall Engine:** Identify *high-value* knowledge units across notes and generate Q&A flashcards:  
    - **Candidate Extraction:** From extracted facts/concepts.  
    - **Eligibility Scoring:** Deterministic formula (see below) to rank importance.  
    - **Card Creation:** For top candidates, auto-generate a question and answer (combining the source note and related notes for context).  
    - **Review Session:** Daily/weekly review UI where user sees each question, thinks of answer, then taps “Reveal” and rates difficulty (“Easy/Good/Hard”).  
    - **Spaced Repetition:** Schedule next review (e.g. SM-2 style or FSRS) based on difficulty rating and last interval.  
    - **Provenance:** Each card links to its source note IDs (so user can review original context).  
  - **“Ask Northstar” Chat:** Simple Q&A interface powered by RAG (uses the same retrieval index to provide context). (This feature is implemented but deemphasized in UI; shown under an “Ask” tab rather than front-and-center.)  
  - **Daily/Weekly Summaries:** Auto-generated recaps (via LLM) of recent notes/knowledge units, highlighting learning, open items, and commitments.  
  - **Calendar Integration (MCP):** Extract **commitments** from notes (detected via intent). Provide a prompt (“Add [Task] to calendar on [date]?”) that creates Google Calendar events via the API or a GPT tool (with user confirmation).  

- **Explicitly Excluded (MVP):**  
  - **Social/Collaboration** (multi-user sharing).  
  - **Complex Graphs/Knowledge Graph:** No full knowledge-graph system yet.  
  - **Voice or Attachments** (no image/OCR/nlp beyond text).  
  - **Full ML Training:** Only use LLM via API; no custom AI model training.  
  - **Advanced Mobile App:** Focus on responsive web; native app later.  
  - **Automated Fine-tuning/Agent-based workflows.**  

# Data Model  

We aim for minimal, robust tables, using JSONB only for raw extractions. The core DB entities are:

- **notes:** (the single source of truth for each note)  
  | Column     | Type               | Description                     |  
  |---         |---                 |---                              |  
  | `id`       | UUID (PK)          | Unique note ID                  |  
  | `user_id`  | UUID (FK)          | Owner of the note               |  
  | `content`  | TEXT               | Full note text                  |  
  | `summary`  | TEXT (nullable)    | AI-generated summary (if any)   |  
  | `embedding`| VECTOR             | Embedding of `content`          |  
  | `metadata` | JSONB              | Extracted items: e.g.  
  |            |                    | `{ "facts": [...], "concepts": [...], "questions": [...],  
  |            |                    |    "decisions": [...], "risks": [...], "entities": [...] }` |  
  | `created_at`| TIMESTAMPTZ       | Timestamp                      |  
  | `updated_at`| TIMESTAMPTZ       | Timestamp                      |  

- **entities:** (consolidated key terms across notes)  
  | Column     | Type               | Description                     |  
  |---         |---                 |---                              |  
  | `id`       | UUID (PK)          | Unique entity ID                |  
  | `user_id`  | UUID (FK)          | Owner (same user as notes)      |  
  | `name`     | TEXT               | The entity name (normalized)    |  
  | `importance`| FLOAT             | Evolving importance score       |  
  | `created_at`| TIMESTAMPTZ       | First seen                      |  
  | `updated_at`| TIMESTAMPTZ       | Last seen                       |  

- **note_entities:** (many-to-many join between notes and entities)  
  | Column       | Type     | Description                  |  
  |---           |---       |---                           |  
  | `note_id`    | UUID (FK)| References notes(id)         |  
  | `entity_id`  | UUID (FK)| References entities(id)      |  
  | `snippet`    | TEXT     | Short context snippet (optional) |  
  | `created_at` | TIMESTAMPTZ | Timestamp                 |  
  *Composite PK = (note_id, entity_id).*  
 
- **tasks:** (action items extracted from notes)  
  | Column       | Type     | Description                  |  
  |---           |---       |---                           |  
  | `id`         | UUID (PK)| Task ID                      |  
  | `user_id`    | UUID     | Owner                        |  
  | `note_id`    | UUID     | Originating note             |  
  | `text`       | TEXT     | Task description             |  
  | `status`     | TEXT     | e.g. `todo/doing/done`       |  
  | `due_date`   | DATE     | Optional deadline            |  
  | `created_at` | TIMESTAMPTZ | Timestamp                |  

- **decisions:** (important decisions recorded)  
  | Column       | Type     | Description                  |  
  |---           |---       |---                           |  
  | `id`         | UUID (PK)| Decision ID                 |  
  | `user_id`    | UUID     | Owner                       |  
  | `note_id`    | UUID     | Source note                 |  
  | `text`       | TEXT     | Description of the decision |  
  | `created_at` | TIMESTAMPTZ | Timestamp                |  

- **risks:** (risks/issues noted)  
  | Column       | Type     | Description                  |  
  |---           |---       |---                           |  
  | `id`         | UUID (PK)| Risk ID                     |  
  | `user_id`    | UUID     | Owner                       |  
  | `note_id`    | UUID     | Source note                 |  
  | `text`       | TEXT     | Description of the risk     |  
  | `created_at` | TIMESTAMPTZ | Timestamp                |  

*(Tasks/decisions/risks are normalized to allow querying and possible updates. Other extracted items like “facts” or “concepts” remain in the `notes.metadata` JSON until needed for recall.)*

- **recall_cards:** (flashcards for spaced repetition)  
  | Column          | Type     | Description                          |  
  |---              |---       |---                                   |  
  | `id`            | UUID (PK)| Card ID                              |  
  | `user_id`       | UUID     | Owner                                |  
  | `question`      | TEXT     | The generated question text          |  
  | `answer`        | TEXT     | The generated answer text            |  
  | `source_notes`  | UUID[]   | IDs of notes providing context       |  
  | `entity_ids`    | UUID[]   | Linked entities (optional)           |  
  | `created_at`    | TIMESTAMPTZ | When card was created            |  
  | `last_reviewed` | TIMESTAMPTZ | Last review timestamp           |  
  | `next_due`      | TIMESTAMPTZ | Next scheduled review time      |  
  | `interval`      | INT      | Current review interval (days)       |  
  | `easiness`     | FLOAT    | SM-2 easiness factor (for scheduling)|  

- **review_history:** (records of past reviews for analytics)  
  | Column        | Type      | Description                          |  
  |---            |---        |---                                   |  
  | `id`          | UUID (PK) | History record ID                    |  
  | `card_id`     | UUID      | References recall_cards(id)         |  
  | `reviewed_at` | TIMESTAMPTZ | When the review happened          |  
  | `grade`       | SMALLINT  | e.g. 1=hard, 3=good, 5=easy          |  

This schema minimizes JSONB usage (only for “metadata” of note) and keeps high-value items queryable. It’s designed so that **our retrieval and recall pipelines share data** (e.g. entities and note embeddings). The `entities` table (with pgvector) can even serve as a lightweight “knowledge graph” backbone (see Supabase’s approach of storing embeddings in Postgres).  

# Recall Pipeline (End-to-End)  

1. **Extraction:** When a note is saved, an async worker invokes an LLM to parse its content into structured “knowledge units” (facts, concepts, etc.). Each unit is given an initial *importance/durability* score (e.g. LLM confidences or heuristic flags). The system also records which entities/tags appear. The note and its metadata (including extracted units) are stored in `notes` (JSONB) and `note_entities`.  

2. **Concept Consolidation:** For each extracted “concept” or fact, compute its vector (using the same embedding model). Check if it’s similar (e.g. cosine > 0.9) to an existing `entities.name`. If yes, increment that entity’s mention count and update its `importance`; if no, create a new entity. Over time, recurring knowledge (“we’ve seen this idea in 3 notes”) naturally gains weight.  

3. **Eligibility Scoring:** Each potential recall candidate (a knowledge unit extracted) is scored by a deterministic formula. For example:  
   ```
   score = 0.3 * importance 
         + 0.2 * normalized_mention_count
         + 0.2 * related_note_count
         + 0.15 * recency_score 
         + 0.15 * user_interest_score
   ```  
   - *importance* = initial heuristic or LLM score for the concept.  
   - *mention_count* = times the same concept was extracted in other notes.  
   - *related_note_count* = how many *distinct* notes mention it.  
   - *recency_score* = gives slight bias to newer content (but with decay).  
   - *user_interest* = e.g. user-tagged or frequency of queries on that entity.  
   (Weights are tuned for MVP.) Concepts above a threshold (e.g. score>0.7) are marked *eligible* for recall. On overlap, duplicate cards are avoided by merging or rejecting lower-scoring ones.  

4. **Candidate Lifecycle:** A candidate moves through states: *{New → Candidate → (Suggested → Approved) → Active Card}*. Most high-scoring items may auto-create a card; borderline ones are queued for user review (“Add this card?”). This prevents overwhelming users with flashcards.  

5. **Card Generation:** When a card is approved or auto-pushed, the system generates **Question + Answer** via LLM. Importantly, the LLM is prompted with: (a) the source note text containing the knowledge, plus (b) the top ~2 other **related note snippets** (from retrieval) that mention this concept. The goal is to craft a question that tests the core idea spanning multiple contexts.  
   > *Example:* Notes: “AWS SQS visibility timeout is X” and “Our system needs to set visibility timeout to avoid duplicate processing.”  
   > **Q:** “What does SQS visibility timeout control?”  
   > **A:** “It controls how long a message remains hidden from other consumers after being retrieved (preventing duplicates if processing takes time).”  

   This cross-note context ensures the answer is grounded in the user’s own data (not hallucinated). The card’s `source_notes` and `entity_ids` are stored for traceability.  

6. **Review Scheduling (Spaced Repetition):** Northstar follows a spaced-repetition algorithm (like SM-2 or FSRS). When a user does a recall session, each card is shown with the Q only. The user *reflects* then taps “Reveal Answer”. After revealing, they self-assess (e.g. “Hard/Good/Easy”, mapped to e.g. grades 1–5). The system updates the card’s easiness and interval. This follows Anki-style logic: “cards shown just before you’d forget”—exploiting active recall for memory.  

7. **Provenance & Feedback:** Each card review stores a history record. Over time, cards answered easily are reviewed less often, while hard cards get shorter intervals. We can also use feedback: if a user frequently marks a card hard, perhaps boost its importance for future (meaning it’s still a shaky concept).  

8. **Thresholds & Adjustments:** In practice, we tune the **eligibility threshold** so that a few cards are introduced per week, not dozens. We might also limit per-note cards (max 1–2 per note) to avoid overload. The idea is to *augment* the user’s memory, not overwhelm them.  

# Retrieval Architecture  

We implement a **hybrid retrieval** system for both the “Ask Northstar” chat and supporting recall contexts:

- **Preprocessing:** Split long notes into chunks (e.g. per paragraph) if needed, each with its own embedding. Store all chunks’ embeddings (using pgvector or a vector DB) and also maintain a BM25 inverted index over the text. PostgreSQL (via Supabase) can serve as both the primary database and vector store. 

- **Query Time:** When the user asks a question, or when recall needs related context:
  1. **BM25 search:** Retrieve top-k exact matches (good for proper nouns, code tokens).  
  2. **Vector search:** Retrieve top-k semantically similar chunks (good for paraphrased knowledge).  
  3. **Fusion:** Combine the two lists by *score fusion* (e.g. Reciprocal Rank Fusion or weighted sum). For example, weighted sum: `score = α*BM25_norm + (1-α)*vect_norm`. Or use RRF to avoid score calibration.  
  4. **Rerank:** Optionally run a cross-encoder or LLM-based reranker on the top ~10 candidates to refine order. This yields the final “relevant context” for answer generation. 
   
  Studies show hybrid methods outperform either alone: they “combine BM25’s lexical precision with semantic embeddings to enhance relevance”. With proper tuning (e.g. α or RRF parameter), hybrid search typically boosts recall and precision.  

- **Caching & Latency:** Since real-time RAG can be slow, we budget retrieval ~100ms (using approximate kNN indexes like HNSW). BM25 queries and vector kNN run in parallel, then fuse results. We implement caching of frequent query results and ensure our service keeps p99 latency acceptable (e.g. sub-second overall).  

- **Ask Northstar Chat:** The chat interface simply uses the same retrieval pipeline. A user’s chat query triggers retrieval; the top chunks plus the user query are passed to the LLM (system prompt style) to answer. Unlike recall cards, chat answers can be generative and free-form, but we’ll ground them by quoting source snippets or at least showing links to relevant notes for transparency.  

- **Reprioritizing Chat:** We’ll label chat as “Ask Northstar” but intentionally keep it secondary. The home/dashboard UI highlights recall sessions and summary notifications first. This ensures Northstar’s identity stays as a memory tool, not a ChatGPT clone.  

# MCP/Calendar Integration  

Northstar will extract **commitment** or **deadline** intents from notes using the LLM. For example, if a note says “Finish monthly report by Friday,” the LLM flags a commitment with a date. The UI then can prompt:  

> “Detected a commitment: **Finish monthly report** (due Fri). Add to your Google Calendar?”  

If the user confirms, Northstar calls the Google Calendar API (via the GPT tool plugin or a direct OAuth flow). This minimal integration avoids building a full calendar UI. Over time, as a solo dev, use the GPTs Model Call Protocol (MCP) for event creation (so ChatGPT+), or simply hit Google’s calendar REST API.  

**Tradeoffs:** Deep calendar sync (bi-directional) is out-of-scope. Instead, we only push new events from notes and rely on Google’s native UI for reminders. This keeps the MVP focused while still delivering actionable value (deadlines become real calendar events).  

# UX Flows  

- **Capture Flow:** User enters a note (text editor). On save, show a “Processing…” state briefly. After processing, the note appears with its summary and extracted items (e.g. “Facts, Tasks, Decisions”) in collapsible sections.  

- **Recall Session:** Via a “Review” tab, the user sees a queue of due flashcards (question-only). For each card:  
  1. Show **Q:** … (user thinks)  
  2. Tap “Reveal Answer” → show the answer text.  
  3. Buttons: *“Again/Hard, Good, Easy”* (or *1-3*). This updates scheduling.  
  Cards are presented one-by-one; the session ends when all due cards are done or user stops.  

- **Candidate Approval:** In the Notes view, any time a new card is auto-created, show it as “Suggested flashcard” with Q/A preview. The user can *Accept* or *Reject* it. (For MVP, assume few such suggestions per week.)  

- **Daily/Weekly Review:** A dashboard page:  
  - **Today’s Highlights:** new notes, key learnings (extracted “concepts” from today), any unresolved decisions or risks.  
  - **Commitments & Events:** list tasks/due dates, with links to add to calendar if pending.  
  - **Recall:** shows “X cards due today” with a button to start review.  
  - **Weekly Summary:** (maybe in a tab or emailed). A bulleted overview of the week: new topics covered, problems, and upcoming actions.  

All interfaces are designed mobile-responsive (using a simple JS framework). Clarity and brevity are key; e.g., daily cards due is highlighted with a progress ring.

# Operational Engineering  

- **Async Pipeline (SQS):** We use AWS SQS to queue note-processing jobs. This decouples the frontend/API from heavy LLM work. Each job (note ID) triggers our worker (AWS Lambda or container) to call OpenAI APIs and update the database. SQS gives us auto-scaling, retries, and DLQs: we mark jobs idempotent (store results by note ID) so retries are safe.  
- **Idempotency:** Each worker invocation checks if a note’s extraction already exists to avoid duplicates. If a job fails (e.g. API error), it’s retried a few times. After N failures, it goes to a Dead-Letter Queue for manual inspection.  
- **Observability:** We log metrics for every stage: note queue depth, processing latency (mean/P95), LLM token usage, DB write times, recall-card generation count, recall success rate (cards accepted vs rejected). We use a monitoring tool (e.g. Datadog or Grafana) to chart queues and latencies. Alerts if processing backs up or error rate spikes.  
- **Error Handling:** Worker catches LLM failures (timeouts, rate limits). We also validate LLM outputs (e.g. answer not empty). If extraction results look invalid, we retry or flag for review.  
- **Testing Strategy:**  
  - *Unit tests* for scoring formulas, scheduling logic, DB queries.  
  - *Integration tests* for the pipeline (e.g. simulate note creation → queue → worker → DB).  
  - *Retrieval eval:* Build a small QA dataset (from user’s own notes) and measure recall@5 with pure BM25 vs vector vs hybrid. Ensure the hybrid improves metrics (emulating ESG results).  
  - *End-to-end:* Manual testing of note entry through recall session.  
- **Cost Controls:** Use a cheap LLM for embeddings (e.g. OpenAI’s cheaper embedding model) and a smaller model (GPT-3.5/GPT-4o-16k) for processing notes/cards. Only call the generative model for chat and card Q/A. Rate-limit heavy tasks if needed. For Postgres, we keep it in a free-tier (or use Supabase free tier) until scale demands vector DB.  

# Deployment & Infrastructure  

- **Hosting:** Backend as a container or AWS Lambda behind API Gateway. Frontend a static React app (host on S3/CloudFront or Vercel). Database on Supabase (Postgres + pgvector) or Amazon RDS with pgvector.  
- **Vector Index:** Use **pgvector** in Postgres (as shown by Supabase). This avoids a second DB. Alternatively, if scaling concerns arise, switch to a managed vector store (Pinecone, Weaviate).  
- **LLM & Embeddings:** For MVP, OpenAI GPT-3.5-Turbo for chat/Q&A, and “text-embedding-3-small” for embeddings. (GPT-4 could be overkill in cost.) Document sources: Databricks/IBM say RAG doesn’t need fine-tuning, so an API approach suffices.  
- **Other Services:** Google Calendar API for events (requires OAuth client). SQS (AWS) for queueing, possibly SES or SendGrid if we email weekly reviews.  
- **Infra-as-Code:** We’ll script resources with Terraform or Serverless Framework (in code, not on resume).  

# Timeline & Milestones (Solo Developer)  

| Milestone               | Description                                                   | Est. Effort (days) |
|-------------------------|---------------------------------------------------------------|-------------------:|
| **1. Core Backend**     | Set up DB schema, API endpoints, SQS pipeline & basic note saving. | 5–7               |
| **2. LLM Extraction**   | Integrate LLM to extract summary/tasks/etc., store metadata.      | 5–7               |
| **3. Embedding/Index**  | Compute/store embeddings on note save; implement simple BM25+vector retrieval (no fusion yet). | 4–5 |
| **4. Recall Engine V1** | Basic candidate scoring, create cards from single notes, simple scheduling (SM-2). | 5–7 |
| **5. Chat Interface**   | “Ask Northstar” chat UI that queries index (no reranker yet).    | 3–5               |
| **6. Recall UI**        | Flashcard review UI (Q/Reveal/grade), and suggestion workflow.   | 4–6               |
| **7. Summaries**        | Daily/weekly summary generation via LLM, and associated UI.     | 3–5               |
| **8. Calendar Integration** | Extract and confirm tasks → add to Google Calendar.         | 3–4               |
| **9. Hybrid Retrieval** | Implement retrieval fusion (RRF or weighted) and reranker improvement. | 5–7            |
| **10. Polishing/Testing** | UI polish, error handling, performance tuning, tests.         | 4–6               |

_Total time: ~8–10 weeks (2–3 months) at full-time pace._ 

# Presenting on Resume & Interviews  

**Resume narrative:** Emphasize engineering depth and learning. For example:  
- “Built **Northstar**, an asynchronous personal knowledge platform using AWS SQS/Lambda, FastAPI, and PostgreSQL with pgvector, to turn user notes into memory recall and actions.”  
- “Implemented a **hybrid RAG pipeline** (BM25 + dense + cross-encoder reranker) boosting retrieval recall by XX% (microbenchmark).”  
- “Designed a spaced-repetition system: automatic card generation and scheduling (SM-2/FSRS). Achieved >90% user recall success in weekly tests.”  
- “Integrated GPT-based knowledge extraction and Google Calendar tools (MCP) to auto-detect commitments and create events.”  

**Metrics to track (for bullets):**  
- **Processing scale:** e.g. “Processed ~N notes/day with 95th% latency of X sec.”  
- **Retrieval quality:** e.g. “Hybrid search improved recall@5 by +15% over BM25 alone in internal tests.”  
- **Recall effectiveness:** e.g. “XX flashcards generated; user self-reported improvement in retention.”  
- **Reliability:** e.g. “99.9% job success rate with automated retries/DLQ.”  
- **Cost:** e.g. “LLM cost <$Y per 100 notes with efficient batching.”  

**Interview Talking Points:**  
- My experience: emphasize strong backend/distributed skills (queues, idempotency, scaling) built on top of enterprise background.  
- Technical depth: explain why SQS+Lambda was chosen (reliability, no server to manage).  
- RAG architecture: articulate the role of hybrid retrieval and ground LLM answers with citations.  
- Recall system novelty: stress how this is not just another note app – it leverages cognitive science (active recall) and an interesting “knowledge score” model.  
- Data modeling: discuss trade-offs JSONB vs relational (we kept tasks/decisions normalized for queryability; free facts in JSONB until needed).  
- Testing/obs: mention how you measured retrieval improvements and monitored costs.  
- Positioning: highlight that this project demonstrates modern full-stack (React, Python), cloud infra (AWS), and AI (LLMs) – all skills beyond traditional .NET.  

Focus on **engineering results**, not just “AI features.” For example: “Built an async ingestion pipeline that reduced note-processing latency by 50% under load” or “configured PostgreSQL with pgvector for unified storage” – those sound like SDE2/3 tasks.  

# Solo Developer Tips & Priorities  

- **Prioritize Core Loop:** Focus on making the *memory loop* rock – capture, extract, review – rather than ancillary bells. The recall system and data pipeline should be reliable before polishing the UI.  
- **Avoid Over-Engineering:** Don’t build a full knowledge graph or complex ML models now. Keep scoring rules deterministic. Reserve model development for later if needed.  
- **Reusability:** Build a single **Retrieval Module** that both chat and recall use. This saves duplication and is a strong system design point.  
- **What Not to Build (yet):** Multi-user sharing, fancy AI agent orchestration, native mobile apps, full fine-tuning. Skip “generic chat engine” – chat is just a UI on retrieval.  
- **Interview Prep Checklist:**  
  - Understand SQS (FIFO vs standard, visibility timeout, retries, DLQ) and idempotency patterns.  
  - Explain BM25 vs embeddings vs hybrid (conceptual strengths).  
  - Be ready to discuss your API design, caching, and scaling choices (e.g. why async queue).  
  - Prepare metrics (above) to quantify your work.  
  - Practice whiteboard: e.g. sketch the system flow (see diagram below), data schemas, and how a query or note flows through.  

# Ask Before Starting  
- **Target Platform:** Is this only a web app, or also mobile? (Affects UI framework).  
- **Tech Stack:** Preferred front-end (React, Vue?) and backend (Node/Python)? Any existing company standards?  
- **Users:** Who is the initial user? (Tech-savvy devs? Students? Affects UI complexity/language).  
- **Scope Constraints:** Any deadlines or “must-have” features? (e.g. must integrate with Slack, etc.)  
- **Data Privacy:** Will notes be sensitive? Must database be self-hosted or encrypted?  
- **Calendar API:** Are Google OAuth creds/configured or should we stub it?  
- **Time Available:** How quickly does this need to be “demo-ready”? (affects how minimal MVP should be).  

```mermaid
flowchart TB
    subgraph Frontend
    A[User Note Entry] --> B[API Gateway]
    B --> C[Queue (SQS)]
    end

    subgraph Workers
    C --> D[Lambda: Summarize & Extract]
    D --> E[PostgreSQL (notes, entities, embeddings)]
    end

    subgraph RecallEngine
    E --> F[Identify Recall Candidates]
    F --> G{Eligible?}
    G -- Yes --> H[Generate Q/A Card]
    H --> I[recall_cards table]
    G -- No --> J[Maybe Suggest to User]
    end

    subgraph Retrieval
    E --> K[Hybrid Index (BM25 + Vector)]
    K --> L[Ask Northstar Chat]
    K --> M[Recall Context Fetch]
    end

    A --> N[Daily/Weekly Summary (uses notes)]
    N --> L
    N --> M
```

```mermaid
flowchart TB
    UserQuery --> A[Compute Query Embedding]
    A --> B[BM25 Search] 
    A --> C[Vector kNN Search]
    B --> D[Top-k BM25 results]
    C --> D[Top-k Vector results]
    D --> E[Score Fusion (e.g. RRF/Weighted)]
    E --> F[Top N merged results]
    F --> G[Cross-Encoder Reranker (optional)]
    G --> AnswerContext
    AnswerContext --> LLM_Response
```

**Sources:** We design this system using industry best-practices. RAG (Retrieval-Augmented Generation) grounds LLMs in external data. Hybrid search (BM25 + dense embeddings) boosts retrieval performance. Active recall and spaced repetition (as in Anki) drastically improve knowledge retention. These principles drive Northstar’s architecture.


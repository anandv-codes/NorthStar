# NorthStar

NorthStar is a personal work-memory application with a FastAPI backend, a React/Vite frontend, and an offline retrieval-evaluation harness. The evaluation suite uses only synthetic fixtures and measures sparse, dense, hybrid, reranked, and guarded-rewrite retrieval without writing to the production vector store.

## Quickstart (after cloning)

Follow these steps in order to get the app running locally.

### 1. Prerequisites

- Python 3.11 or later
- Node.js 18 or later with npm
- A Supabase project ([supabase.com](https://supabase.com), free tier is enough)
- A Gemini API key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey))

### 2. Set up the database

In your Supabase project's SQL editor, run these 9 files **in order** (they are idempotent, safe to re-run):

1. [backend/sql/auth_jwt.sql](backend/sql/auth_jwt.sql) — user accounts + refresh tokens
2. [backend/sql/chat_conversations.sql](backend/sql/chat_conversations.sql) — chat threads + messages + pending tool-call confirmations (`pending_chat_actions`)
3. [backend/sql/phase3_work_memory.sql](backend/sql/phase3_work_memory.sql) — notes + all extracted memory tables (tasks, facts, questions, decisions, risks, concepts, entities) + daily/weekly rollup summaries (`period_summaries`)
4. [backend/sql/phase4_recall.sql](backend/sql/phase4_recall.sql) — recall foundation: `note_entities`, entity importance, task due dates, `commitments`, `recall_candidates`, `recall_cards`, `review_history`, per-note `recall_enabled`/`recall_status`
5. [backend/sql/phase4_recall_scheduler.sql](backend/sql/phase4_recall_scheduler.sql) — Anki-style scheduler state on `recall_cards` (`state`, `learning_step`)
6. [backend/sql/phase4_recall_decks.sql](backend/sql/phase4_recall_decks.sql) — categorised recall decks: `recall_decks`, candidate/card `deck_id`, and the per-user General deck backfill
7. [backend/sql/phase4_recall_accept.sql](backend/sql/phase4_recall_accept.sql) — atomic, idempotent `accept_recall_candidate` RPC
8. [backend/sql/phase4_pgvector.sql](backend/sql/phase4_pgvector.sql) — pgvector retrieval: `note_chunks`, chunk/note/entity embeddings, HNSW indexes, `match_*` functions
9. [backend/sql/phase5_commitments.sql](backend/sql/phase5_commitments.sql) — user-authored long-term goals (`user_commitments`) and note-derived updates (`commitment_contributions`)

That's all 9 files needed for a brand-new database — no other migrations required. File 8 enables the `vector` extension (pre-installed on Supabase).

**Updating an existing database:** if you set up NorthStar before the daily/weekly summary, chat tool-calling, recall, or long-term goals features existed, re-run files 2–9 above — every statement in them uses `create table if not exists` / `alter table ... add column if not exists` / `create index if not exists`, so re-running is safe and only adds the tables/columns/indexes that are missing:

- `chat_conversations.sql` adds `pending_chat_actions` (tool actions the assistant proposed in chat and is waiting on explicit yes/no confirmation for).
- `phase3_work_memory.sql` adds `period_summaries` (generated daily/weekly recaps) and the `notes.context_note_ids` column.
- `phase4_recall.sql` adds the recall loop's state (`recall_candidates`, `recall_cards`, `review_history`, etc.), the `recall_candidates.text` column, per-note `recall_enabled`/`recall_status`, and the `entities.importance` / `tasks.due_date` scoring inputs.
- `phase4_recall_scheduler.sql` adds the scheduler columns (`recall_cards.state`, `learning_step`) — required for reviews to work.
- `phase4_recall_decks.sql` adds `recall_decks`, links candidates/cards to a deck, and backfills a General deck per existing user.
- `phase4_recall_accept.sql` adds the `accept_recall_candidate` RPC used by bulk acceptance.
- `phase4_pgvector.sql` adds the pgvector-backed retrieval index (`note_chunks`, `match_*`). After running it, backfill existing notes once with `python -m backend.scripts.backfill_pgvector`.
- `phase5_commitments.sql` adds `user_commitments` and `commitment_contributions`. The old extracted `commitments` table is left untouched for compatibility; the product now writes only to the new user-authored tables.

To confirm all tables exist, run in the SQL editor:

```sql
select table_name from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'users', 'refresh_tokens',
    'chat_threads', 'chat_messages', 'pending_chat_actions',
    'notes', 'extraction_runs', 'tasks', 'facts', 'questions',
    'decisions', 'risks', 'concepts', 'entities', 'memory_item_entities',
    'period_summaries',
    'note_entities', 'commitments', 'recall_candidates', 'recall_cards',
    'review_history', 'recall_decks', 'note_chunks',
    'user_commitments', 'commitment_contributions'
  )
order by table_name;
```

This should return all 25 names; any missing from the result means the corresponding `.sql` file above still needs to be run.

### 3. Configure the backend

Create `backend/.env` (do not commit it):

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
JWT_SECRET_KEY=replace-with-a-long-random-secret
GEMINI_API_KEY=your-gemini-api-key
PROCESS_NOTES_INLINE=true
```

`SUPABASE_URL`, `SUPABASE_KEY`, and `JWT_SECRET_KEY` are required for the normal application flows. `GEMINI_API_KEY` is required for note enrichment, chat, dense retrieval, hybrid retrieval, and guarded-rewrite evaluations.

`PROCESS_NOTES_INLINE=true` is **required for local runs** — it processes each note synchronously in-process instead of routing it through the real AWS SQS queue + EC2 `northstar-note-worker` used in the deployed environment. Without it, note creation fails locally (no AWS queue exists to receive the job).

Useful optional settings:

```dotenv
GEMINI_MODEL_ID=gemini-2.5-flash-lite
EMBEDDING_MODEL_ID=gemini-embedding-001
QUERY_RETRIEVAL_TOP_K=5
QUERY_RETRIEVAL_RRF_K=60
QUERY_RETRIEVAL_RERANKER=off
```

### 4. Install and run the backend

From the workspace root, create and activate a virtual environment, then install backend dependencies:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

Start FastAPI:

```powershell
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API runs at `http://localhost:8000`; interactive OpenAPI documentation is at `http://localhost:8000/docs`.

### 5. Install and run the frontend

Open a second terminal from the workspace root:

```powershell
Set-Location frontend
npm install
npm run dev
```

Vite prints the local application URL, normally `http://localhost:5173`. The frontend currently calls the backend at `http://localhost:8000`, so keep the backend running while using the UI.

Create a production frontend build with:

```powershell
npm run build
```

### 6. Try it out

1. Open the frontend URL, register a new account, then log in.
2. Go to "Add Note" and submit a note — with `PROCESS_NOTES_INLINE=true` it is enriched synchronously, so refreshing the dashboard shortly after shows the extracted summary, tasks, questions, decisions, risks, and concepts.
3. Try the chat page to ask about your notes.

## Deploying beyond local testing

See [docs/ec2_deployment.md](docs/ec2_deployment.md) for the full EC2 checklist
(instance/IAM/SQS setup, migrations, systemd services, Nginx, and frontend
build). The deployment work lives on the `prd-m1` branch; the guide's clone
command checks it out explicitly. In short: keep `PROCESS_NOTES_INLINE=false`,
run the always-on SQS consumer (`python -m app.workers.sqs_consumer`) as its own
service, build the frontend with `VITE_API_BASE_URL` pointing at the API, and
scope `CORS_ALLOW_ORIGINS` to the real frontend origin. For API and worker
latency measurement, see [loadtest/README.md](loadtest/README.md).

## Run Retrieval Evaluations

Run all commands from the workspace root with the Python environment activated. The suite writes JSON machine artifacts and scenario-level Markdown reports into `evals/results/`.

### Sparse Baselines

Sparse BM25 evaluates the production `BM25Index` against an in-memory synthetic corpus. It does not need Supabase, Chroma, Gemini, or `GEMINI_API_KEY`.

```powershell
# Small deterministic smoke benchmark
python -m evals.scripts.run_retrieval_eval

# Rebuild and validate the current focused v4 benchmark
python -m evals.scripts.build_rag_v4_focused_dataset
python -m evals.scripts.validate_rag_v4_dataset

# Save the v4 BM25 baseline
python -m evals.scripts.run_retrieval_eval `
  --cases evals/datasets/northstar_rag_v4.jsonl `
  --corpus evals/datasets/northstar_rag_v4_corpus.jsonl `
  --output evals/results/northstar_rag_v4_bm25.json

# Rebuild and validate the historical 100-question v1 fixture
python -m evals.scripts.build_rag_v1_expanded_dataset
python -m evals.scripts.validate_rag_v1_dataset

# Save the v1 BM25 baseline
python -m evals.scripts.run_retrieval_eval `
  --cases evals/datasets/northstar_rag_v1.jsonl `
  --corpus evals/datasets/northstar_rag_v1_corpus.jsonl `
  --output evals/results/northstar_rag_v1_bm25.json
```

V4 is the current focused benchmark: 50 questions over 63 synthetic daily notes, split into 10 MBA, 17 software-work, and 16 SDE interview-prep answerable cases plus 7 no-context cases. It has no conflict cases, so use v1 or v3 when evaluating conflict coverage.

### Dense, Hybrid, Reranker, And Rewrite Baselines

These commands require `chromadb`, `langchain-google-genai`, and `GEMINI_API_KEY`. They use an isolated Chroma path under `evals/.chroma` and reject the application `chroma_data` path and `notes` collection.

```powershell
# Dense Chroma only
python -m evals.scripts.run_dense_retrieval_eval

# Dense plus sparse Reciprocal Rank Fusion (RRF)
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf

# RRF followed by the production cross-encoder reranker
python -m evals.scripts.run_hybrid_retrieval_eval --mode rerank --strict-rerank

# RRF plus the guarded production query rewrite
python -m evals.scripts.run_hybrid_retrieval_eval --mode rewrite
```

Run the V4 hybrid baselines with an explicitly shared collection so the 63-note corpus is embedded once:

```powershell
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf `
  --cases evals/datasets/northstar_rag_v4.jsonl `
  --corpus evals/datasets/northstar_rag_v4_corpus.jsonl `
  --collection northstar_rag_v4_rrf_eval

python -m evals.scripts.run_hybrid_retrieval_eval --mode rerank --strict-rerank `
  --cases evals/datasets/northstar_rag_v4.jsonl `
  --corpus evals/datasets/northstar_rag_v4_corpus.jsonl `
  --collection northstar_rag_v4_rrf_eval --reuse-collection `
  --candidate-multiplier 3 `
  --reranker-model cross-encoder/ms-marco-MiniLM-L-6-v2
```

The guarded rewrite run uses an empty synthetic recent-memory input and records query quality, rewrite confidence, risk flags, and guard decisions for each case. It can make up to one Gemini request for each eligible v1 scenario.

### Saved Baseline Artifacts

| Configuration | JSON result | Markdown report |
| --- | --- | --- |
| v0 sparse smoke | `evals/results/northstar_rag_v0_smoke_bm25.json` | `evals/results/northstar_rag_v0_smoke_bm25.md` |
| v4 focused sparse BM25 | `evals/results/northstar_rag_v4_bm25.json` | `evals/results/northstar_rag_v4_bm25.md` |
| v4 hybrid RRF | `evals/results/northstar_rag_v4_rrf.json` | `evals/results/northstar_rag_v4_rrf.md` |
| v4 hybrid RRF plus cross-encoder | `evals/results/northstar_rag_v4_rerank.json` | `evals/results/northstar_rag_v4_rerank.md` |
| v1 sparse BM25 | `evals/results/northstar_rag_v1_bm25.json` | `evals/results/northstar_rag_v1_bm25.md` |
| v1 dense Chroma | `evals/results/northstar_rag_v1_dense.json` | `evals/results/northstar_rag_v1_dense.md` |
| v1 RRF | `evals/results/northstar_rag_v1_rrf.json` | `evals/results/northstar_rag_v1_rrf.md` |
| v1 RRF plus reranker (stale, pre-cross-encoder) | `evals/results/northstar_rag_v1_rerank.json` | `evals/results/northstar_rag_v1_rerank.md` |
| v1 guarded rewrite | `evals/results/northstar_rag_v1_rewrite.json` | `evals/results/northstar_rag_v1_rewrite.md` |

Each report records Precision@5, Recall@5, MRR@5, isolation failures, no-context behavior, conflict-evidence completeness, retrieval configuration, and source revision. Compare modes only after every configuration has been run against the same regenerated fixture. Use v4 for focused semantic retrieval and v1 for conflict coverage.

## CI Evaluation Workflow

[`.github/workflows/rag-eval.yml`](.github/workflows/rag-eval.yml) automates the retrieval suite:

- Qualifying pull requests run fixture validation plus v0, v4, and v1 sparse BM25 baselines.
- Qualifying pushes to `main` additionally run dense Chroma, RRF, RRF-plus-reranker, and the V4 hybrid/reranker baselines.
- Manual dispatch offers `run_dense` for dense/RRF/reranker and `run_rewrite` for the cost-bearing guarded-rewrite benchmark.

Set `GEMINI_API_KEY` as a GitHub repository or organization Actions secret before running secret-backed modes in GitHub Actions. The workflow currently publishes reports and artifacts but does not enforce metric thresholds as merge gates.

## Evaluation Boundaries

- Fixtures contain synthetic data only; never commit personal notes, tokens, or production chat history.
- Evaluation collections and artifacts are separate from the application vector store.
- Retrieval and generation implementations are evaluation subjects. Changes to the harness should remain under `evals/`, documentation, and CI workflow files unless the product behavior itself is intentionally being changed.
- See [docs/RAG_Evaluation_Plan.md](docs/RAG_Evaluation_Plan.md) for the benchmark design and [docs/evals/learning.md](docs/evals/learning.md) for decisions and observed results.
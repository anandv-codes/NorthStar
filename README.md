# NorthStar

NorthStar is a personal work-memory application with a FastAPI backend, a React/Vite frontend, and an offline retrieval-evaluation harness. The evaluation suite uses only synthetic fixtures and measures sparse, dense, hybrid, reranked, and guarded-rewrite retrieval without writing to the production vector store.

## Prerequisites

- Python 3.11 or later
- Node.js 18 or later with npm
- A Supabase project for the running application
- A Gemini API key for application generation and dense, hybrid, or rewrite evaluation

## Configuration

Create `backend/.env`. Do not commit it.

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
JWT_SECRET_KEY=replace-with-a-long-random-secret
GEMINI_API_KEY=your-gemini-api-key
```

The backend loads this file at startup. `SUPABASE_URL`, `SUPABASE_KEY`, and `JWT_SECRET_KEY` are required for the normal application flows. `GEMINI_API_KEY` is required for chat, dense retrieval, hybrid retrieval, and guarded-rewrite evaluations.

Useful optional settings:

```dotenv
GEMINI_MODEL_ID=gemini-2.5-flash
EMBEDDING_MODEL_ID=gemini-embedding-001
QUERY_RETRIEVAL_TOP_K=5
QUERY_RETRIEVAL_RRF_K=60
QUERY_RETRIEVAL_RERANKER=off
```

## Run The Backend

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

## Run The Frontend

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

## Run Retrieval Evaluations

Run all commands from the workspace root with the Python environment activated. The suite writes JSON machine artifacts and scenario-level Markdown reports into `evals/results/`.

### Sparse Baselines

Sparse BM25 evaluates the production `BM25Index` against an in-memory synthetic corpus. It does not need Supabase, Chroma, Gemini, or `GEMINI_API_KEY`.

```powershell
# Small deterministic smoke benchmark
python -m evals.scripts.run_retrieval_eval

# Rebuild and validate the 100-question v1 fixture
python -m evals.scripts.build_rag_v1_expanded_dataset
python -m evals.scripts.validate_rag_v1_dataset

# Save the v1 BM25 baseline
python -m evals.scripts.run_retrieval_eval `
  --cases evals/datasets/northstar_rag_v1.jsonl `
  --corpus evals/datasets/northstar_rag_v1_corpus.jsonl `
  --output evals/results/northstar_rag_v1_bm25.json
```

### Dense, Hybrid, Reranker, And Rewrite Baselines

These commands require `chromadb`, `langchain-google-genai`, and `GEMINI_API_KEY`. They use an isolated Chroma path under `evals/.chroma` and reject the application `chroma_data` path and `notes` collection.

```powershell
# Dense Chroma only
python -m evals.scripts.run_dense_retrieval_eval

# Dense plus sparse Reciprocal Rank Fusion (RRF)
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf

# RRF followed by the production token-overlap reranker
python -m evals.scripts.run_hybrid_retrieval_eval --mode rerank

# RRF plus the guarded production query rewrite
python -m evals.scripts.run_hybrid_retrieval_eval --mode rewrite
```

The guarded rewrite run uses an empty synthetic recent-memory input and records query quality, rewrite confidence, risk flags, and guard decisions for each case. It can make up to one Gemini request for each eligible v1 scenario.

### Saved Baseline Artifacts

| Configuration | JSON result | Markdown report |
| --- | --- | --- |
| v0 sparse smoke | `evals/results/northstar_rag_v0_smoke_bm25.json` | `evals/results/northstar_rag_v0_smoke_bm25.md` |
| v1 sparse BM25 | `evals/results/northstar_rag_v1_bm25.json` | `evals/results/northstar_rag_v1_bm25.md` |
| v1 dense Chroma | `evals/results/northstar_rag_v1_dense.json` | `evals/results/northstar_rag_v1_dense.md` |
| v1 RRF | `evals/results/northstar_rag_v1_rrf.json` | `evals/results/northstar_rag_v1_rrf.md` |
| v1 RRF plus reranker | `evals/results/northstar_rag_v1_rerank.json` | `evals/results/northstar_rag_v1_rerank.md` |
| v1 guarded rewrite | `evals/results/northstar_rag_v1_rewrite.json` | `evals/results/northstar_rag_v1_rewrite.md` |

Each report records Precision@5, Recall@5, MRR@5, isolation failures, no-context behavior, conflict-evidence completeness, retrieval configuration, and source revision. Compare modes only after every configuration has been run against the same regenerated v1 fixture.

## CI Evaluation Workflow

[`.github/workflows/rag-eval.yml`](.github/workflows/rag-eval.yml) automates the retrieval suite:

- Qualifying pull requests run fixture validation plus v0 and v1 sparse BM25 baselines.
- Qualifying pushes to `main` additionally run dense Chroma, RRF, and RRF-plus-reranker baselines.
- Manual dispatch offers `run_dense` for dense/RRF/reranker and `run_rewrite` for the cost-bearing guarded-rewrite benchmark.

Set `GEMINI_API_KEY` as a GitHub repository or organization Actions secret before running secret-backed modes in GitHub Actions. The workflow currently publishes reports and artifacts but does not enforce metric thresholds as merge gates.

## Evaluation Boundaries

- Fixtures contain synthetic data only; never commit personal notes, tokens, or production chat history.
- Evaluation collections and artifacts are separate from the application vector store.
- Retrieval and generation implementations are evaluation subjects. Changes to the harness should remain under `evals/`, documentation, and CI workflow files unless the product behavior itself is intentionally being changed.
- See [docs/RAG_Evaluation_Plan.md](docs/RAG_Evaluation_Plan.md) for the benchmark design and [docs/evals/learning.md](docs/evals/learning.md) for decisions and observed results.
# NorthStar Offline Evaluations

This directory contains deterministic, synthetic evaluation fixtures and report-only runners for NorthStar retrieval and chat quality.

## V0 Retrieval Smoke Baseline

The v0 dataset is a small implementation check, not the planned 40-case golden dataset. It exercises direct lookup, numeric lookup, a semantic phrasing, conflicting evidence, no-context behavior, and user-boundary filtering with synthetic notes.

Run it from the workspace root:

```powershell
python -m evals.scripts.run_retrieval_eval
```

The runner uses the production `BM25Index` directly with an in-memory synthetic corpus. It does not call Supabase, Chroma, Gemini, or external services. Every run writes both a machine-readable JSON artifact and a scenario-by-scenario Markdown report:

`evals/results/northstar_rag_v0_smoke_bm25.json`

`evals/results/northstar_rag_v0_smoke_bm25.md`

The initial scorecard contains:

- Precision@5 and Recall@5 for answerable cases.
- A zero-tolerance foreign-user result check.
- A no-context retrieval check.
- A conflict retrieval-completeness check that requires both conflicting notes to be retrieved.

V0 does not score final answers, claim support, conflict resolution language, latency, or LLM cost. Those belong to later phases of `docs/RAG_Evaluation_Plan.md`.

## Dense Chroma Baseline

The dense runner evaluates the immutable v1 fixtures using the existing Gemini embedding provider and a dedicated Chroma path and collection. It never uses the production `chroma_data` path or `notes` collection, and it recreates only its own evaluation collection before each run.

Prerequisites: install `backend/requirements.txt` in the active Python environment and set `GEMINI_API_KEY`. The runner uses `EMBEDDING_MODEL_ID` when configured, otherwise `gemini-embedding-001`.

```powershell
python -m evals.scripts.run_dense_retrieval_eval
```

It writes `evals/results/northstar_rag_v1_dense.json` and a matching scenario-by-scenario Markdown report. It measures retrieval only; it does not modify or evaluate generated answer wording.

## Fixture Rules

- Commit only synthetic, non-sensitive notes and queries.
- Keep source note IDs stable once a dataset version is baselined.
- Add a new dataset version rather than silently changing expected results.
- Do not make retrieval strategy claims from the v0 score alone; it is a smoke baseline, not a representative benchmark.
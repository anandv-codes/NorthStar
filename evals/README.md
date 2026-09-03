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

- Precision@5, Recall@5, and MRR@5 for answerable cases.
- A zero-tolerance foreign-user result check.
- A no-context retrieval check.
- A conflict retrieval-completeness check that requires both conflicting notes to be retrieved.

V0 does not score final answers, claim support, conflict resolution language, latency, or LLM cost. Those belong to later phases of `docs/RAG_Evaluation_Plan.md`.

## Expanded V1 Golden Dataset

V1 is the current detailed retrieval benchmark: 100 synthetic questions over 350 synthetic notes. It covers exact `ITEM-*` lookups, `DFX-*` datafix records and counts, progress updates, operational learnings, dependencies, deliberately ambiguous conflicts, no-context abstention, and identical identifiers across two synthetic users.

The v1 fixture is intentionally rebuilt in place. This retires the prior 40-case v1 baseline, so do not compare its historical scores with the current report. Rebuild and validate the checked-in fixture from the workspace root:

```powershell
python -m evals.scripts.build_rag_v1_expanded_dataset
python -m evals.scripts.validate_rag_v1_dataset
python -m evals.scripts.run_retrieval_eval --cases evals/datasets/northstar_rag_v1.jsonl --corpus evals/datasets/northstar_rag_v1_corpus.jsonl --output evals/results/northstar_rag_v1_bm25.json
```

The builder fixes the corpus at 250 primary-user notes and 100 secondary-user notes. The validator requires all expected note references, claims, category counts, and the 15-case `always_surface_ambiguity` policy to remain intact.

## Expanded V2 Merged Dataset

V2 is an enhanced composite dataset merging semantic reasoning from V1 with personal learning contexts: 200 synthetic questions over 548 synthetic notes. It combines the updated 100 V1 work-memory queries (item synthesis, datafix synthesis, dependency semantic, progress tracking, conflict detection) with the original 100 V2 learning-focused queries (DSA revision, project status, topic history, quiz scheduling, life status tracking).

Run BM25 retrieval evaluation from the workspace root:

```powershell
python -m evals.scripts.run_retrieval_eval --cases evals/datasets/northstar_rag_v2.jsonl --corpus evals/datasets/northstar_rag_v2_corpus.jsonl --output evals/results/northstar_rag_v2_bm25.json
```

This writes both a machine-readable JSON artifact and a scenario-by-scenario Markdown report:

`evals/results/northstar_rag_v2_bm25.json`

`evals/results/northstar_rag_v2_bm25.md`

V2 enables cross-domain evaluation: testing whether the retrieval and ranking strategies generalize from work-memory lookups to personal learning tracking, and vice versa. The corpus contains 548 notes split across domain-specific categories (work items, datafixes, progress updates, learning notes, quiz records, project artifacts).

## Semantic-Bias V3 Dataset

V1/V2 skew heavily toward exact-identifier lookups (`ITEM-*`, `DFX-*`), which BM25 solves trivially and which drown out any signal that hybrid or dense retrieval adds. V3 corrects for this: 228 cases built from 70 newly authored cases with weak-to-no lexical overlap between query and evidence (true paraphrase, colloquial-vs-jargon vocabulary mismatch, lexical near-miss traps where a high-overlap distractor should NOT win, multi-note synthesis with no shared identifier, and corrected cross-account synthesis), plus the 158 non-ID-anchored cases reused from V2 (the 31 exact/item-id-tagged cases, 6 legacy `seed` prototype duplicates, and 5 broken `isolation-synthesis-*` cases with dangling note references are excluded). The full V2 corpus (548 notes) is carried over unmodified, plus 95 new notes for the newly authored cases, for 643 notes total.

Rebuild and validate the checked-in fixture from the workspace root:

```powershell
python -m evals.scripts.build_rag_v3_semantic_bias_dataset
python -m evals.scripts.validate_rag_v3_dataset
```

Run any retrieval baseline against V3 by pointing `--cases`/`--corpus` at the V3 files, e.g.:

```powershell
python -m evals.scripts.run_retrieval_eval --cases evals/datasets/northstar_rag_v3.jsonl --corpus evals/datasets/northstar_rag_v3_corpus.jsonl --output evals/results/northstar_rag_v3_bm25.json
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf --cases evals/datasets/northstar_rag_v3.jsonl --corpus evals/datasets/northstar_rag_v3_corpus.jsonl --output evals/results/northstar_rag_v3_rrf.json
```

Cases carry a `v3` tag when newly authored (vs. reused from V2), plus a category tag (`paraphrase`, `vocabulary-mismatch`, `lexical-trap`, `synthesis`, `cross-account-synthesis`) so results can be broken down per category, not just as one flat average.

## Dense Chroma Baseline

The dense runner evaluates fixtures using the existing Gemini embedding provider and a dedicated Chroma path and collection. It never uses the production `chroma_data` path or `notes` collection, and it recreates only its own evaluation collection before each run.

Prerequisites: install `backend/requirements.txt` in the active Python environment and set `GEMINI_API_KEY`. The runner uses `EMBEDDING_MODEL_ID` when configured, otherwise `gemini-embedding-001`.

Run against V1 fixtures:

```powershell
python -m evals.scripts.run_dense_retrieval_eval
```

Or run against V2 merged dataset:

```powershell
python -m evals.scripts.run_dense_retrieval_eval --cases evals/datasets/northstar_rag_v2.jsonl --corpus evals/datasets/northstar_rag_v2_corpus.jsonl
```

For V1, output is written to:

`evals/results/northstar_rag_v1_dense.json`

`evals/results/northstar_rag_v1_dense.md`

For V2, specify output paths:

```powershell
python -m evals.scripts.run_dense_retrieval_eval --cases evals/datasets/northstar_rag_v2.jsonl --corpus evals/datasets/northstar_rag_v2_corpus.jsonl --output evals/results/northstar_rag_v2_dense.json
```

Both measure retrieval only; they do not modify or evaluate generated answer wording.

## RRF and Reranker Baselines

The hybrid runner compares the existing production RRF fusion with the same fusion followed by the existing token-overlap reranker. It also evaluates the current guarded production query rewrite against a controlled empty synthetic recent-memory input. It uses an isolated evaluation Chroma collection, an in-memory production `BM25Index`, and the shared scorecard. It does not call the production retrieval orchestrator, Supabase, or application vector collection.

Run against V1 fixtures:

```powershell
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf
python -m evals.scripts.run_hybrid_retrieval_eval --mode rerank
python -m evals.scripts.run_hybrid_retrieval_eval --mode rewrite
```

Or run against V2 merged dataset:

```powershell
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf --cases evals/datasets/northstar_rag_v2.jsonl --corpus evals/datasets/northstar_rag_v2_corpus.jsonl
python -m evals.scripts.run_hybrid_retrieval_eval --mode rerank --cases evals/datasets/northstar_rag_v2.jsonl --corpus evals/datasets/northstar_rag_v2_corpus.jsonl
python -m evals.scripts.run_hybrid_retrieval_eval --mode rewrite --cases evals/datasets/northstar_rag_v2.jsonl --corpus evals/datasets/northstar_rag_v2_corpus.jsonl
```

All commands have the same dependency and `GEMINI_API_KEY` requirements as the dense baseline. For V1, they write `evals/results/northstar_rag_v1_rrf.*`, `evals/results/northstar_rag_v1_rerank.*`, and `evals/results/northstar_rag_v1_rewrite.*`. For V2, explicitly specify output paths:

```powershell
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf --cases evals/datasets/northstar_rag_v2.jsonl --corpus evals/datasets/northstar_rag_v2_corpus.jsonl --output evals/results/northstar_rag_v2_rrf.json
```

Rewrite reports also retain each case's query quality, confidence, risk flags, and guard decision in JSON. Because the rewrite run makes one model call for each eligible case, CI runs it only through opted-in manual dispatch.

## Fixture Rules

- Commit only synthetic, non-sensitive notes and queries.
- Keep source note IDs stable once a dataset version is baselined.
- Add a new dataset version rather than silently changing expected results.
- Do not make retrieval strategy claims from the v0 score alone; it is a smoke baseline, not a representative benchmark.
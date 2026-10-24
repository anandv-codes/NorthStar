# NorthStar Offline Evaluations

This directory contains deterministic, synthetic evaluation fixtures and report-only runners for NorthStar retrieval and chat quality.

## Recall Question/Answer Generation Contract

`northstar_recall_generation_v1` replays recorded model responses through the production recall prompt builder and validators. It is a deterministic regression check for question-form matching, answer grounding, expected answer-point coverage, and multi-note context plumbing. It does not measure live model quality, latency, or cost.

```powershell
python -m evals.scripts.run_recall_generation_eval --fail-on-error
```

This writes `evals/results/northstar_recall_generation_v1.json` and `.md`. Multi-note cases require the answer to cover points from more than one related note, and fail if any related snippet is missing from the rendered prompt.

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

## Focused V4 Daily-Note Dataset

V4 is the current focused retrieval benchmark: 50 synthetic questions over 63 synthetic daily notes. It is deliberately SWE/interview-heavy: 43 answerable cases split into 10 MBA, 17 software-development work, and 16 SDE interview-prep questions, plus 7 no-context near-misses. Five secondary-user notes mirror primary-user facts for isolation checks.

V4 removes exact `ITEM-*`/`DFX-*` anchors and paraphrases most queries so BM25 cannot win on identifier lookup or shared vocabulary. It includes multi-note status, chronology, and learning-state questions. It has no conflict cases, so conflict checks report `0/0`; use V1/V3 for conflict coverage.

Rebuild, validate, and run the sparse baseline from the workspace root:

```powershell
python -m evals.scripts.build_rag_v4_focused_dataset
python -m evals.scripts.validate_rag_v4_dataset
python -m evals.scripts.run_retrieval_eval --cases evals/datasets/northstar_rag_v4.jsonl --corpus evals/datasets/northstar_rag_v4_corpus.jsonl --output evals/results/northstar_rag_v4_bm25.json
```

This writes `evals/results/northstar_rag_v4_bm25.json` and `.md`. The validator enforces the 50-case/63-note contract, answerable and no-context domain splits, source references, claim support references, and the 58/5 primary/secondary corpus split.

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

## Hybrid, Reranker, and Rewrite Baselines

The hybrid runner compares the production RRF fusion with the same fusion followed by the production cross-encoder reranker (`SentenceTransformerReranker`, `cross-encoder/ms-marco-MiniLM-L-6-v2`). It also evaluates the current guarded production query rewrite against a controlled empty synthetic recent-memory input. It uses an isolated evaluation Chroma collection, an in-memory production `BM25Index`, and the shared scorecard. It does not call the production retrieval orchestrator, Supabase, or application vector collection.

Candidate channels are fetched and fused at `k * 3` (mirroring `QUERY_RETRIEVAL_CANDIDATE_MULTIPLIER`), then truncated or reranked down to `k`. Reranking at the final cutoff only reorders five notes; the wider pool is what lets a reranker promote a gold note that fusion placed lower.

Default output and collection names are derived from the cases file, so `--cases evals/datasets/northstar_rag_v4.jsonl` writes `northstar_rag_v4_<mode>.json`/`.md` and uses collection `northstar_rag_v4_<mode>_eval`. V1 invocations keep their historical names.

Run against V4 (the current focused benchmark):

```powershell
# Dense plus sparse Reciprocal Rank Fusion (RRF)
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf `
  --cases evals/datasets/northstar_rag_v4.jsonl `
  --corpus evals/datasets/northstar_rag_v4_corpus.jsonl `
  --collection northstar_rag_v4_rrf_eval

# RRF followed by the production cross-encoder reranker, reusing the corpus embeddings
python -m evals.scripts.run_hybrid_retrieval_eval --mode rerank --strict-rerank `
  --cases evals/datasets/northstar_rag_v4.jsonl `
  --corpus evals/datasets/northstar_rag_v4_corpus.jsonl `
  --collection northstar_rag_v4_rrf_eval --reuse-collection `
  --candidate-multiplier 3 `
  --reranker-model cross-encoder/ms-marco-MiniLM-L-6-v2
```

Run against V1 fixtures:

```powershell
python -m evals.scripts.run_hybrid_retrieval_eval --mode rrf
python -m evals.scripts.run_hybrid_retrieval_eval --mode rerank --strict-rerank
python -m evals.scripts.run_hybrid_retrieval_eval --mode rewrite
```

Useful flags:

- `--collection`: override the derived collection name.
- `--candidate-multiplier`: per-channel fetch/fusion depth as a multiple of `--k` (default `3`).
- `--reranker-model`: cross-encoder model id for `--mode rerank`.
- `--reuse-collection`: skip re-embedding when the collection already holds the full corpus.
- `--strict-rerank`: fail the run when the reranker returns unscored candidates. The production reranker silently falls back to fusion order on a scoring error, so without this flag a broken model would be reported as "no effect".

All commands have the same dependency and `GEMINI_API_KEY` requirements as the dense baseline. Embedding calls retry with exponential backoff on provider rate limits. The reranker model is downloaded from the Hugging Face Hub on first use.

`northstar_rag_v1_rerank.*` predates the switch to the cross-encoder and records the retired token-overlap reranker. Re-run `--mode rerank` against V1 before comparing it with current results.

Rewrite reports retain each case's query quality, confidence, risk flags, and guard decision in JSON. Because the rewrite run makes one model call for each eligible case, CI runs it only through opted-in manual dispatch.

## Fixture Rules

- Commit only synthetic, non-sensitive notes and queries.
- Keep source note IDs stable once a dataset version is baselined.
- Add a new dataset version rather than silently changing expected results.
- Do not make retrieval strategy claims from the v0 score alone; it is a smoke baseline, not a representative benchmark.
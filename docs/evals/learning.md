# NorthStar RAG Evaluation Learnings

This log captures evaluation decisions, measured outcomes, and deliberate deferrals. It is updated after meaningful dataset, runner, retrieval, or answer-quality changes.

## 2026-08-11: Evaluation Foundation

### Decisions Made

- NorthStar is evaluated as a personal work-management application. The benchmark uses one primary synthetic user, plus a second synthetic user only to detect retrieval-isolation regressions.
- The first golden dataset is `northstar_rag_v1`: 40 synthetic, non-sensitive work-memory queries and their supporting corpus notes.
- V1 coverage includes 8 direct lookups, 6 exact identifiers/numbers/dates, 6 semantic paraphrases, 5 multi-note synthesis cases, 7 conflicting-source cases, 4 negation/status cases, 2 no-context cases, and 2 isolation cases.
- Conflicting-source evaluation is required from the first benchmark version. The expected behavior is context-dependent: resolve with provenance only when a later explicit decision or status clearly supersedes an earlier note; otherwise surface the conflict or abstain.
- Retrieval v1 uses report-only baselines. No score currently blocks a change.
- Every runner execution writes a JSON artifact for tools and a scenario-by-scenario Markdown report for review.
- V1 retrieval metrics are intentionally limited to Precision@5, Recall@5, a zero-tolerance isolation-failure count, no-context behavior, and conflict-evidence completeness.

### Decisions Avoided or Deferred

- **nDCG:** deferred because graded relevance labels would add annotation work before the initial retrieval baseline is stable.
- **MRR:** removed from the initial scorecard because first-result ordering is not yet a product requirement; Precision and Recall answer the immediate questions.
- **LLM-as-judge and claim decomposition:** deferred until the retrieval configurations can be compared against the v1 corpus. Retrieval quality must be understood before measuring generated-answer groundedness.
- **OpenTelemetry:** deferred until the offline benchmark is useful. Telemetry will explain production behavior but does not replace known-answer evaluation.
- **Production notes:** excluded from committed fixtures to prevent personal work data from entering the repository.
- **Blocking CI quality gates:** deferred until repeated baselines establish expected variance and defensible thresholds.

## 2026-08-11: V0 BM25 Smoke Baseline

**Artifacts:** `evals/results/northstar_rag_v0_smoke_bm25.json` and `evals/results/northstar_rag_v0_smoke_bm25.md`.

| Measure | Result |
| --- | ---: |
| Scenario count | 8 |
| Precision@5 | 0.786 |
| Recall@5 | 1.000 |
| Isolation failures | 0 |
| No-context checks | 1/1 |
| Conflict-evidence checks | 2/2 |

### Learning

- The existing in-memory `BM25Index` is a viable deterministic first evaluation seam once its Supabase dependency is loaded only in the production retrieval path.
- BM25 retrieved both sides of the two small conflict scenarios, which confirms that conflict evaluation can begin at the retrieval layer before judging final answer wording.
- Even in the small corpus, BM25 ranked an earlier launch target before the later superseding decision and retrieved related-but-unnecessary Atlas notes. Retrieval completeness alone is not sufficient for personal work memory.

## 2026-08-11: V1 BM25 Baseline

**Artifacts:** `evals/results/northstar_rag_v1_bm25.json` and `evals/results/northstar_rag_v1_bm25.md`.

| Measure | Result |
| --- | ---: |
| Scenario count | 40 |
| Precision@5 | 0.379 |
| Recall@5 | 0.974 |
| Isolation failures | 0 |
| No-context checks | 1/2 |
| Conflict-evidence checks | 7/7 |

### What Worked

- All seven conflict cases retrieved both required source notes. This is necessary, though not sufficient, for reliable conflict resolution later in the chat and grounding layers.
- The two isolation cases returned only the primary synthetic user's notes. The corpus includes intentionally similar second-user notes, so this validates the in-memory user partitioning used by the benchmark.
- Exact identifier lookup worked well: the `INC-482` scenario retrieved only its expected source note.
- All five multi-note synthesis scenarios retrieved their required evidence at `k=5`.

### Failures and Constraints Revealed

- Precision@5 is low because BM25 returns several lexically related notes for many single-note queries. This can dilute context for answer generation even when Recall@5 is high.
- The `semantic-knowledge` scenario had Recall@5 of 0.0: the query asks why the retrieval design should be documented, but the lexical index did not retrieve `s-knowledge`. Dense retrieval is needed to test whether semantic matching closes this gap.
- The `no-context-parking` scenario returned `e-flag`, producing a 1/2 no-context pass rate. The retrieval layer currently has no score threshold that reliably distinguishes weak lexical overlap from absence of evidence.
- Conflict completeness is not conflict resolution. The current BM25 report does not assess whether a later explicit decision is ranked first, whether ambiguity is surfaced, or whether the final answer preserves provenance.
- The zero isolation failures validate only this isolated in-memory BM25 benchmark. Chroma, hybrid fusion, request authentication, and production storage boundaries must be evaluated separately before making a stronger security claim.

### Next Experiment

Run the same immutable v1 dataset through dense Chroma retrieval, then compare it with the current hybrid RRF path. Keep the case IDs, relevant note IDs, and expected conflict behavior unchanged. Compare at minimum:

- Whether dense retrieval fixes `semantic-knowledge` without worsening no-context retrieval.
- Precision@5 changes for direct and exact-match cases.
- Recall@5 for multi-note and conflicting-source cases.
- Isolation failure count, which must remain zero.
- Conflict-evidence completeness, which must not regress below 7/7.

Do not tune rewrite thresholds, reranking, or response prompts until dense and hybrid retrieval results exist for the same dataset.

## 2026-08-11: Dense Chroma Runner Readiness

**Runner:** `evals/scripts/run_dense_retrieval_eval.py`.

### Implementation Decision

- Added an evaluation-only dense runner that uses the existing embedding provider as a read-only dependency, writes the same JSON and scenario-level Markdown format as BM25, and filters every query by synthetic `user_id`.
- The runner uses only `evals/.chroma` and `northstar_rag_v1_dense_eval`; it rejects the production `chroma_data` path and `notes` collection. It resets that isolated collection before each execution.
- Shared result scoring now lives in `evals/retrieval.py`, so sparse and dense runs calculate the same Precision@5, Recall@5, isolation, no-context, and conflict-evidence measurements.

### Execution Constraint

- No dense quality baseline was produced in this environment. The active Python environment has neither `chromadb` nor `langchain_google_genai`, and `GEMINI_API_KEY` is not configured.
- This is a local execution prerequisite, not a measured retrieval result. Do not compare dense quality with BM25 until the runner completes and writes `northstar_rag_v1_dense.json` and `.md` from the unchanged v1 fixtures.

### Next Experiment

Install `backend/requirements.txt` in the selected Python environment, configure `GEMINI_API_KEY`, then run `python -m evals.scripts.run_dense_retrieval_eval`. Record the per-scenario artifacts and compare them with the existing v1 BM25 report before implementing any hybrid measurement.
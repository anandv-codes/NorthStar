# NorthStar RAG Evaluation Learnings

This log captures evaluation decisions, measured outcomes, and deliberate deferrals. It is updated after meaningful dataset, runner, retrieval, or answer-quality changes.

## 2026-08-11: Evaluation Foundation

### Decisions Made

- NorthStar is evaluated as a personal work-management application. The benchmark uses one primary synthetic user, plus a second synthetic user only to detect retrieval-isolation regressions.
- The first golden dataset is `northstar_rag_v1`: 40 synthetic, non-sensitive work-memory queries and their supporting corpus notes.
- V1 coverage includes 8 direct lookups, 6 exact identifiers/numbers/dates, 6 semantic paraphrases, 5 multi-note synthesis cases, 7 conflicting-source cases, 4 negation/status cases, 2 no-context cases, and 2 isolation cases.
- Conflicting-source evaluation is required from the first benchmark version. The original context-dependent policy was superseded when v1 expanded to 100 cases: all current v1 ambiguity cases surface both positions and request clarification rather than resolving by timestamp.
- Retrieval v1 uses report-only baselines. No score currently blocks a change.
- Every runner execution writes a JSON artifact for tools and a scenario-by-scenario Markdown report for review.
- V1 retrieval metrics are intentionally limited to Precision@5, Recall@5, a zero-tolerance isolation-failure count, no-context behavior, and conflict-evidence completeness.

### Decisions Avoided or Deferred

- **nDCG:** deferred because graded relevance labels would add annotation work before the initial retrieval baseline is stable.
- **MRR:** included in the scorecard as MRR@5 to measure whether the first useful note appears early enough to reduce context noise. It complements Precision and Recall; it does not replace multi-note Recall or conflict-evidence completeness.
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
| MRR@5 | 0.929 |
| Isolation failures | 0 |
| No-context checks | 1/1 |
| Conflict-evidence checks | 2/2 |

### Learning

- The existing in-memory `BM25Index` is a viable deterministic first evaluation seam once its Supabase dependency is loaded only in the production retrieval path.
- BM25 retrieved both sides of the two small conflict scenarios, which confirms that conflict evaluation can begin at the retrieval layer before judging final answer wording.
- Even in the small corpus, BM25 ranked an earlier launch target before the later superseding decision and retrieved related-but-unnecessary Atlas notes. Retrieval completeness alone is not sufficient for personal work memory.

## 2026-08-11: Initial V1 BM25 Baseline (Retired)

The original 40-case fixture was expanded in place at the user's direction. Its prior results remain recorded below as historical context, but the corresponding v1 report artifacts were regenerated for the 100-case fixture and are no longer comparable.

| Measure | Result |
| --- | ---: |
| Scenario count | 40 |
| Precision@5 | 0.379 |
| Recall@5 | 0.974 |
| MRR@5 | 0.974 |
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

## 2026-08-11: Expanded V1 Golden Dataset and BM25 Baseline

**Artifacts:** `evals/datasets/northstar_rag_v1.jsonl`, `evals/datasets/northstar_rag_v1_corpus.jsonl`, `evals/results/northstar_rag_v1_bm25.json`, and `evals/results/northstar_rag_v1_bm25.md`.

| Measure | Result |
| --- | ---: |
| Scenario count | 100 |
| Synthetic notes | 350 |
| Precision@5 | 0.284 |
| Recall@5 | 1.000 |
| MRR@5 | 1.000 |
| Isolation failures | 0 |
| No-context checks | 3/5 |
| Conflict-evidence checks | 15/15 |

### Dataset Decisions

- V1 was expanded in place, so its earlier 40-case metrics are retired rather than treated as a score trend.
- The corpus is one connected synthetic delivery portfolio with 250 primary-user notes and 100 deliberately similar secondary-user notes.
- The 15 conflict cases always require ambiguity to be surfaced. A more recent timestamp does not justify choosing one conflicting note.
- Notes include a fixture-audit `note_type`, but all facts that retrieval should find are stated in `raw_text`. This prevents labels from becoming an unmeasured retrieval feature.
- `evals/scripts/build_rag_v1_expanded_dataset.py` deterministically rebuilds the fixture; `evals/scripts/validate_rag_v1_dataset.py` enforces its count, reference, category, and user-boundary contract.

### Baseline Learning

- Every answerable case has a relevant note in the top five, and the first relevant result is ranked first for this sparse baseline. The detailed fixture's exact identifiers make this a useful retrieval-reference result, not evidence of answer-level quality.
- Precision@5 drops in the denser corpus because five-candidate context includes related operational notes beyond the required evidence. This is the intended context-noise pressure for later dense and hybrid comparisons.
- BM25 retrieves both required notes for all 15 ambiguity cases, but retrieval completeness does not show whether a generated answer surfaces the disagreement. That remains a claim-evaluation task.
- The no-context baseline is only 3/5, so weak lexical overlap still yields unsupported candidates in two abstention scenarios.

### Next Experiment

Run this fixed 100-case v1 fixture through isolated dense Chroma retrieval, then compare dense and the current hybrid RRF path with the sparse result. Preserve all case IDs, relevant note IDs, expected claims, and ambiguity policies. Do not tune retrieval, rewriting, reranking, or response prompts until those comparisons exist.

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

## 2026-08-12: Retrieval-Mode Evaluation Methodology and CI

### Completed Methodology

- The benchmark has one shared scorer in `evals/retrieval.py`. Sparse, dense, RRF, reranker, and rewrite runs therefore calculate the same Precision@5, Recall@5, MRR@5, isolation, no-context, and conflict-evidence measures against the unchanged synthetic v1 fixture.
- Each run writes a machine-readable JSON artifact and a scenario-level Markdown report with configuration and Git revision metadata. This makes a result reviewable without treating a single aggregate score as sufficient evidence.
- The fixture builder and validator run before v1 evaluation. The validator enforces the 100-case and 350-note contract, source-note references, claim support references, category coverage, the 250/100 synthetic user split, and all 15 ambiguity-case policies.

### Retrieval Modes

- **Sparse BM25:** builds the production `BM25Index` in memory from synthetic notes. It is deterministic and does not access Supabase, Chroma, or Gemini.
- **Dense Chroma:** uses the existing embedding provider but writes only to a dedicated collection under `evals/.chroma`; every query filters on synthetic `user_id`.
- **RRF:** combines the synthetic sparse and dense candidate lists through the production `fuse_candidates` implementation.
- **Reranker:** applies the production `TokenOverlapReranker` after RRF fusion. It is measured separately from RRF so a ranking change is not attributed to fusion.
- **Guarded rewrite:** calls the production query rewriter with an explicit empty synthetic recent-memory input, then uses the production quality threshold, confidence threshold, and risk detector before adding rewritten dense candidates. Its JSON report retains the per-case rewrite decision, confidence, and risk flags.

### CI and Cost Decisions

- `.github/workflows/rag-eval.yml` runs fixture validation plus v0 and v1 sparse benchmarks for qualifying pull requests and qualifying pushes to `main`.
- Trusted `main` pushes run dense, RRF, and reranker baselines with `GEMINI_API_KEY`; pull requests do not receive that secret-backed work.
- Guarded rewrite is manual-dispatch only because an expanded v1 run can make up to one model call per case. This preserves measurable rewrite behavior while avoiding routine model cost on every push.
- The workflow publishes JSON and Markdown artifacts but remains report-only. There is no baseline-delta comparator, branch-protection requirement, or metric threshold yet.

### Boundaries and Remaining Evidence

- Retrieval and generation modules remain read-only evaluation subjects. The harness changes only `evals/`, documentation, and CI workflow files.
- The local environment does not currently have Chroma, the Gemini LangChain package, or `GEMINI_API_KEY`; no dense, RRF, reranker, or rewrite quality result has been claimed from it.
- Do not infer that RRF, reranking, or rewriting improves quality until their protected-run artifacts exist for the same v1 fixture. Compare category failures, no-context behavior, and conflict evidence alongside aggregate metrics.

## 2026-10-21: Focused V4 Daily-Note Retrieval Benchmark

**Artifacts:** `evals/datasets/northstar_rag_v4.jsonl`, `evals/datasets/northstar_rag_v4_corpus.jsonl`, `evals/results/northstar_rag_v4_bm25.json`, and `evals/results/northstar_rag_v4_bm25.md`.

| Measure | Result |
| --- | ---: |
| Scenario count | 50 |
| Synthetic notes | 63 |
| Precision@5 | 0.233 |
| Recall@5 | 0.733 |
| MRR@5 | 0.598 |
| Isolation failures | 0 |
| No-context checks | 0/7 |
| Conflict-evidence checks | 0/0 |

### Dataset Decisions

- V4 replaces the deferred 254-case plan with a focused benchmark for retrieval over daily notes, not a daily-summary quality benchmark.
- The 50 cases are 43 answerable questions and 7 no-context near-misses. Answerable cases split 10 MBA, 17 software-development work, and 16 SDE interview prep; no-context cases split 2 MBA, 3 software work, and 2 interview prep.
- The corpus has 63 notes: 58 primary-user notes and 5 deliberately similar secondary-user notes for isolation checks.
- Queries avoid exact `ITEM-*`/`DFX-*` anchors. They were rewritten to reduce lexical overlap: 36 of the 43 answerable queries share at most two tokens with their gold notes, and 8 share none.
- V4 has multi-note status, chronology, and learning-state cases but no conflict cases. Conflict metrics are therefore `0/0` and are not comparable with V1/V3 conflict coverage.
- `evals/scripts/build_rag_v4_focused_dataset.py` rebuilds the fixture deterministically; `evals/scripts/validate_rag_v4_dataset.py` enforces the case, note, domain, user, reference, and claim-support contract.
- The sparse CI job now rebuilds and validates V4 and publishes `northstar_rag_v4_bm25` alongside the v0 and v1 reports.

### Baseline Learning

- The sparse baseline is no longer near the ceiling: BM25 retrieves no gold note at all for 11 of 43 answerable cases and retrieves only one of two gold notes for another. This leaves room to measure whether dense or hybrid retrieval closes genuine semantic gaps.
- Precision@5 is 0.233 because short daily notes share broad domain words; top-five context is noisy even when a relevant note is present. Recall and MRR expose the larger semantic misses.
- BM25 fails all 7 no-context cases because it always returns positive-scoring notes for near-miss vocabulary. Retrieval alone cannot enforce abstention; answer generation needs a grounded refusal path.
- Zero isolation failures validate only the in-memory user partitioning for this fixture. Production storage boundaries still require separate verification.

### Next Experiment

Run the unchanged V4 fixture through isolated dense and hybrid retrieval, preserving all case IDs and gold note references. Compare category failures and no-context behavior against this sparse baseline before tuning candidate depth, fusion, or rewriting. Do not treat the V4 result as answer-quality evidence.

## 2026-10-24: Recall Question/Answer Generation Contract

**Artifacts:** `evals/datasets/northstar_recall_generation_v1.jsonl`, `evals/results/northstar_recall_generation_v1.json`, and `evals/results/northstar_recall_generation_v1.md`.

### Decisions Made

- Recall card generation is evaluated separately from retrieval. The replay runner feeds recorded model responses through the production prompt builder, `generate_question_with_answer`, and the deterministic validators, so it catches prompt, context, and validation regressions without calling Gemini.
- Question prompts no longer force a `How` question when the knowledge unit only supports a definition. The model chooses the form the note supports, and the answer prompt must answer in that same form.
- On-demand answers rehydrate the source note's `context_note_ids` and include up to two related snippets. Accepted cards keep those related note ids in `source_note_ids` when available from the candidate rationale or answer context.
- Multi-note cases require the answer to cover expected points from more than one related note and fail when any related snippet is missing from the rendered prompt.

### Coverage Limits

- The runner replays recorded responses; it does not judge live model output. A separate claim-level judge is still required before treating answer quality as measured.
- No production reveal/accept rates are recorded yet, so the cost/quality trade-off of pre-generated answers remains unmeasured.

## 2026-10-24: V4 Hybrid and Cross-Encoder Reranker

**Artifacts:** `evals/results/northstar_rag_v4_rrf.json`, `evals/results/northstar_rag_v4_rrf.md`, `evals/results/northstar_rag_v4_rerank.json`, and `evals/results/northstar_rag_v4_rerank.md`.

Both runs use the unchanged V4 fixture (50 cases over 63 notes), `gemini-embedding-001`, one shared Chroma collection (`northstar_rag_v4_rrf_eval`, corpus embedded once and reused), `k=5`, and a candidate depth of 15 per channel (`candidate_multiplier=3`) before truncation or reranking. The reranker is the production `SentenceTransformerReranker` (`cross-encoder/ms-marco-MiniLM-L-6-v2`) with `--strict-rerank`, so an unranked fallback would fail the run instead of silently reporting fusion order.

| Configuration | Precision@5 | Recall@5 | MRR@5 | Isolation failures | No-context |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sparse BM25 | 0.233 | 0.733 | 0.598 | 0 | 0/7 |
| Hybrid RRF | 0.223 | 0.953 | 0.818 | 0 | 0/7 |
| Hybrid RRF + cross-encoder | 0.200 | 0.884 | 0.809 | 0 | 0/7 |

Per-tag Recall/MRR for the answerable cases:

| Tag | n | BM25 | RRF | RRF + reranker |
| --- | ---: | --- | --- | --- |
| Software work | 17 | 0.647 / 0.569 | 0.912 / 0.725 | 0.735 / 0.678 |
| SDE interview prep | 16 | 0.781 / 0.611 | 0.969 / 0.833 | 0.969 / 0.891 |
| MBA | 10 | 0.800 / 0.625 | 1.000 / 0.950 | 1.000 / 0.900 |
| Synthesis | 8 | 0.562 / 0.542 | 0.875 / 0.771 | 0.625 / 0.604 |
| All semantic (`v4`) | 43 | 0.733 / 0.598 | 0.953 / 0.818 | 0.884 / 0.809 |

### Learning

- Hybrid RRF closes the semantic gap the sparse baseline exposed: Recall@5 rises from 0.733 to 0.953 and MRR@5 from 0.598 to 0.818, recovering 10 of the 11 cases where BM25 retrieved no gold note at all. Precision@5 slips slightly (0.233 to 0.223) because top-five context stays noisy; fusion buys coverage, not cleanliness.
- The cross-encoder reranker does **not** pay for itself on V4. It improves ranking on 5 cases (notably `v4-swe-pricing-rollback-01` — the single remaining RRF miss — which it promoted to rank 1) but regresses 10, and it drops gold notes out of the top five entirely on 5 cases. Net effect: Recall@5 0.953 to 0.884 and MRR@5 0.818 to 0.809.
- The regression is concentrated in software-work and synthesis queries, where the gold note is a short factual update and ms-marco favours longer, topical passages. Interview-prep and behavioral cases are the opposite: MRR improves (interview 0.833 to 0.891, behavioral 0.778 to 1.000), because those gold notes read like explanatory prose.
- RRF recall is now high enough that the reranker mostly has room to demote, not promote. Re-testing the reranker makes sense on a fixture with more headroom, a depth sweep, or a reranker trained on short notes; it does not make sense to enable `QUERY_RETRIEVAL_RERANKER` on this evidence. It remains `off` by default.
- No-context stays 0/7 for every retrieval configuration: all three return five positive-ranking notes for near-miss questions. Abstention must be enforced by grounding, not by retrieval.
- The checked-in `northstar_rag_v1_rerank.*` artifact predates the cross-encoder and reports the retired token-overlap reranker. It must be re-run before any V1 reranker comparison.


# NorthStar RAG Evaluation Plan

Created 2026-08-11.

## Scope and Decisions

NorthStar is a personal work-management application. This plan evaluates one user's work memory, not organization workspaces, team roles, or shared tenant data.

The initial approach is deliberately narrow:

- Build a versioned, 40-case golden dataset for personal work-memory questions.
- Include conflicting-source evaluation in the first dataset version.
- Begin with report-only results; do not block development until a baseline is trustworthy.
- Establish offline evaluation before adding OpenTelemetry tracing.
- Use an LLM judge for the first claim-based assessment loop; preserve inputs, rubric version, and outputs so a human review process can be added later.
- Keep a synthetic second-user corpus as a retrieval-isolation regression test, even though the product is personal rather than multi-tenant.

## Outcomes

The completed evaluation system will answer five questions for each retrieval and chat configuration:

1. Did NorthStar retrieve the note or notes needed to answer the question?
2. Did the answer address the user's question?
3. Is every material answer claim supported by retrieved context?
4. Did the system resolve, describe, or safely abstain on conflicting evidence?
5. Did query rewriting, hybrid fusion, or reranking improve quality enough to justify added latency and model cost?

## Existing Integration Points

| Surface | Current capability | Evaluation use |
| --- | --- | --- |
| `backend/app/domain/query_retrieval/services.py` | Produces sparse, dense, rewritten-query, fused, and optionally reranked candidates. | Run retrieval-only comparisons and calculate ranking metrics. |
| `backend/app/domain/chat/orchestrator.py` | Uses retrieved candidates to build a grounded Gemini prompt. | Run end-to-end answer evaluation using a stable chat configuration. |
| `backend/app/domain/chat/guardrails.py` | Emits `strong`, `weak`, `conflict`, or `no_context`, source references, and evidence. | Evaluate abstention and conflict-detection behavior separately from final answer quality. |
| `backend/app/infrastructure/vector/vectorstore.py` | Stores notes with a `user_id` metadata filter. | Assert that retrieval never returns a note from a different synthetic user. |

## Evaluation Model

```mermaid
flowchart LR
    Dataset[Versioned golden dataset] --> Ingest[Deterministic eval corpus ingestion]
    Ingest --> Retrieval[Retrieval-only runner]
    Retrieval --> Ranking[Precision and Recall]
    Retrieval --> Chat[End-to-end chat runner]
    Chat --> Claims[LLM claim decomposition]
    Claims --> Judge[LLM evidence judge]
    Judge --> Quality[Groundedness, relevance, conflict handling]
    Ranking --> Report[Versioned evaluation report]
    Quality --> Report
```

Keep the retrieval corpus, embedding model, vector-store configuration, retrieval settings, prompt versions, model IDs, and code revision with every report. An evaluation score without this provenance is not comparable across runs.

## Metrics

### Retrieval Quality

Calculate these metrics against `relevant_note_ids` in the golden dataset:

$$
\text{Precision@k} = \frac{\text{relevant retrieved notes in top k}}{k}
$$

$$
\text{Recall@k} = \frac{\text{relevant retrieved notes in top k}}{\text{all relevant notes}}
$$

- **Isolation failure rate:** any result from a different synthetic user is a critical failure, not an averaged metric.

Run the dataset under these configurations:

1. Sparse BM25 only.
2. Dense Chroma retrieval only.
3. Current dense plus sparse RRF fusion.
4. RRF plus guarded query rewrite.
5. RRF plus rewrite plus the configured reranker.

### Answer Quality and RAG Trinity

| RAG-trinity dimension | Metric | Definition |
| --- | --- | --- |
| Context relevance | Precision@k, Recall@k | Retrieved evidence is relevant and complete for the query. |
| Groundedness | Claim support rate, unsupported-claim rate, contradiction rate | Material answer claims are entailed by retrieved evidence. |
| Answer relevance | LLM-judge relevance score | The response directly addresses the user's question and requested format. |

For each generated answer, decompose the answer into atomic material claims. The judge labels each claim as `supported`, `partially_supported`, `unsupported`, or `contradicted` by comparing it only with the retrieved evidence.

$$
\text{Claim Support Rate} =
\frac{\text{supported} + 0.5 \times \text{partially supported}}
{\text{all material claims}}
$$

$$
\text{Unsupported Claim Rate} =
\frac{\text{unsupported material claims}}
{\text{all material claims}}
$$

A material contradicted claim should fail the individual example even if most other claims are supported.

### Conflict Handling

Each conflict case must specify the expected behavior, not just an expected sentence:

| Expected behavior | When to use it |
| --- | --- |
| `resolve_with_provenance` | A later, explicit decision clearly supersedes an earlier note. |
| `surface_conflict` | Sources disagree and neither source is clearly authoritative enough to resolve the disagreement. |
| `abstain_or_request_clarification` | Relevant evidence is missing, weak, or too ambiguous to answer safely. |

The v1 conflict policy is **context-dependent**:

- Prefer a later explicit decision when it is clearly more authoritative and directly addresses the same subject.
- Explain the conflict and cite both sources when authority, scope, or timing is ambiguous.
- Do not silently choose one source when the evidence does not justify doing so.

Score each conflict case for retrieval completeness, conflict detection, expected response behavior, and provenance coverage.

## Golden Dataset Specification

### Dataset Layout

Create the following structure:

```text
evals/
  datasets/
    northstar_rag_v1.jsonl
    northstar_rag_v1_corpus.jsonl
  configs/
    retrieval_baselines.json
    judge_rubric_v1.md
  results/
    .gitkeep
  scripts/
    run_retrieval_eval.py
    run_chat_eval.py
    summarize_results.py
  README.md
```

Use generated, non-sensitive notes for the first dataset. Do not commit personal notes, real tokens, emails, or production chat history.

### Required Case Schema

```json
{
  "id": "decision-conflict-001",
  "dataset_version": "northstar_rag_v1",
  "user_id": "eval-user-primary",
  "query": "When is the mobile launch planned?",
  "relevant_note_ids": ["note-launch-august", "note-launch-september"],
  "expected_claims": [
    {
      "claim": "The current mobile launch target is September 1.",
      "supporting_note_ids": ["note-launch-september"]
    },
    {
      "claim": "An earlier note listed August 15.",
      "supporting_note_ids": ["note-launch-august"]
    }
  ],
  "conflict": {
    "present": true,
    "policy": "prefer_latest_explicit_decision",
    "conflicting_note_ids": ["note-launch-august", "note-launch-september"],
    "expected_behavior": "resolve_with_provenance"
  },
  "expected_answer_behavior": "answer_with_sources",
  "tags": ["decision", "date", "conflict", "recency"]
}
```

### Forty-Case Coverage Target

| Category | Target cases | Purpose |
| --- | ---: | --- |
| Direct fact and decision lookup | 8 | Establish simple retrieval and answer baselines. |
| Exact names, project codes, dates, and numbers | 6 | Verify sparse retrieval and rewrite preservation. |
| Semantic paraphrase | 6 | Verify dense retrieval and hybrid fusion. |
| Multi-note synthesis | 5 | Require complete evidence rather than one-note answers. |
| Conflicting sources | 7 | Test resolution, explanation, and safe abstention. |
| Negation, tentative language, and status changes | 4 | Catch harmful rewrite and grounding errors. |
| No-context and abstention | 2 | Verify safe non-answer behavior. |
| Synthetic cross-user isolation | 2 | Verify `user_id` filtering in vector and sparse retrieval. |

The seven conflict cases should include:

- Later explicit decision supersedes an older plan.
- Older completed status conflicts with a later reopening.
- Tentative proposal conflicts with a confirmed decision.
- Equal-authority notes with no clear recency winner.
- Date conflict where one note omits a year or scope.
- Conflicting risks or priorities.
- Relevant but partially retrieved conflict, where the correct behavior is to avoid false certainty.

## Todo Plan

### Phase 1: Dataset and Retrieval Baseline

- [x] Add a v0 synthetic smoke corpus, BM25 runner, and report-only baseline before authoring the full golden dataset.
- [x] Write paired JSON and scenario-level Markdown results for the v0 retrieval baseline.
- [x] Create the `evals/` directory structure and a short runner README.
- [x] Define a JSONL schema for corpus notes and evaluation queries.
- [x] Write 40 synthetic personal work-memory cases using the coverage target above.
- [x] Assign relevant note IDs to every case.
- [x] Add expected claims and expected answer behavior to every end-to-end case.
- [x] Add conflict metadata and a context-dependent expected resolution policy to all conflict cases.
- [x] Add two synthetic second-user notes designed to be tempting false positives.
- [x] Create a deterministic ingestion/reset routine for the evaluation Chroma collection and sparse-retriever source data.
- [x] Implement a retrieval-only runner that calls the real retrieval strategies without a chat-model invocation.
- [x] Write ranking-metric functions for Precision@k, Recall@k, and isolation failure rate.
- [x] Emit JSON and Markdown baseline reports with retrieval configuration and code revision metadata.
- [ ] Run and save baseline results for sparse, dense, RRF, rewrite, and rerank configurations.

**Exit criterion:** each of the 40 cases runs deterministically against an isolated synthetic corpus, and the report compares all five retrieval configurations.

### Phase 2: End-to-End Claim Evaluation

- [ ] Freeze an initial chat model ID, prompt version, generation temperature, and retrieval configuration for reproducible baselines.
- [ ] Implement an end-to-end runner that records query, candidates, grounding output, final answer, model metadata, and latency.
- [ ] Define a versioned LLM-judge rubric that receives only the query, candidate evidence, expected behavior, and generated answer.
- [ ] Implement atomic claim decomposition and evidence-only claim verdicts.
- [ ] Require the judge to output structured JSON, including per-claim verdicts and evidence note IDs.
- [ ] Calculate claim support, unsupported-claim, contradiction, answer-relevance, and abstention-quality metrics.
- [ ] Add explicit scoring for `resolve_with_provenance`, `surface_conflict`, and `abstain_or_request_clarification` cases.
- [ ] Save individual failures with retrieved sources, judge rationale, and reproducibility metadata.
- [ ] Manually inspect an initial sample of LLM-judge decisions before treating summary scores as reliable.

**Exit criterion:** every dataset case produces a reproducible answer-evaluation record with claim-level verdicts and a reportable conflict-handling result.

### Phase 3: Calibration and Policy Tuning

- [ ] Record retrieval score, rewrite confidence, routing confidence, and grounding confidence for every case.
- [ ] Bucket grounding confidence into intervals and compare predicted confidence with observed claim support.
- [ ] Measure whether `strong`, `weak`, `conflict`, and `no_context` outcomes match expected behavior.
- [ ] Tune rewrite thresholds, retrieval depth, RRF constant, and reranking configuration only through controlled comparisons.
- [ ] Document the selected baseline configuration and the reason each threshold changed.
- [ ] Add regression cases for every high-severity false answer or conflict-handling failure found during tuning.

**Exit criterion:** confidence and guardrail policies are based on measured results, not only heuristic defaults.

### Phase 4: Quality Gates and Continuous Improvement

- [ ] Add a small, deterministic retrieval smoke subset to pull-request checks.
- [ ] Keep the full suite report-only until repeated runs establish stable metric variance.
- [ ] Define regression thresholds for Recall@5, unsupported-claim rate, conflict-handling pass rate, isolation failures, latency, and LLM cost.
- [ ] Promote the full suite to a blocking quality gate after thresholds are approved.
- [ ] Add reviewed production failures as anonymized synthetic or redacted cases in the next dataset version.
- [ ] Version datasets, judge rubrics, prompts, runner code, and reports together.

**Exit criterion:** changes to retrieval, prompts, grounding, or models have measurable quality evidence before release.

### Phase 5: OpenTelemetry After Offline Baselines

- [ ] Add OpenTelemetry tracing to FastAPI request handling and the note worker.
- [ ] Instrument spans for intent routing, dense retrieval, sparse retrieval, query rewriting, fusion, reranking, grounding assessment, Gemini generation, and persistence.
- [ ] Add non-sensitive span attributes: model ID, prompt version, retrieval mode, candidate count, rewrite use, grounding status, latency, tokens, and estimated cost.
- [ ] Hash user identifiers before telemetry export and prohibit raw notes, full chat content, tokens, credentials, and email addresses in telemetry attributes.
- [ ] Configure a collector and trace backend with retention and access policies.
- [ ] Correlate production traces with evaluation configuration versions, without exporting private user content.
- [ ] Use trace outliers and user-reported failures to identify candidates for reviewed golden-dataset additions.

**Exit criterion:** production traces explain where latency, cost, retrieval failure, or grounding failure occurred without leaking personal work data.

## LLM Judge Safeguards

The first pass uses an LLM judge only, so its output must be treated as an automated signal rather than ground truth.

- Keep the judge model and prompt/rubric version in every result.
- Instruct the judge that evidence outside retrieved candidate text is unavailable.
- Require JSON-schema validation of judge output.
- Randomize case order and do not disclose retrieval-strategy labels to the judge.
- Retain evaluator inputs and outputs so later human review can diagnose disagreements.
- Periodically add manually adjudicated examples before relying on score deltas for release decisions.
- Never use the evaluated answer itself as evidence for whether it is grounded.

## OpenTelemetry Position

OpenTelemetry is recommended after the offline runner is useful. It is an observability layer, not an evaluator:

- **Offline evaluation:** measures relevance, recall, groundedness, conflict handling, and regressions against known expectations.
- **OpenTelemetry:** explains the operational path taken by a real request, including latency, model usage, retrieval composition, and errors.

The sequence matters. Build the golden dataset first so traces can be interpreted against a known quality baseline rather than becoming detailed records of unmeasured behavior.

## Non-Negotiable Practices

- Never evaluate against a corpus that contains unredacted personal notes unless it is stored and accessed under an explicit privacy policy.
- Use a fresh, isolated vector collection and synthetic user IDs for each evaluation run.
- Make the corpus and ingestion process deterministic before comparing retrieval configurations.
- Preserve source-note IDs through candidate lists, grounding evidence, claim verdicts, and reports.
- Treat any cross-user retrieval result as a critical failure.
- Test numerical values, dates, negation, tentative language, and conflicts explicitly; aggregate averages hide these failure modes.
- Compare quality, latency, and cost together before enabling an LLM rewrite or reranker by default.
- Add a case to the golden dataset for every significant production failure after review and sanitization.
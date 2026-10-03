# Phase A Implementation Plan — Chat Latency (steps 1-8)

Source: [docs/latency_improvements.md](latency_improvements.md). This plan
covers steps **1-8** (measurement + low/medium-difficulty fixes). Steps
**9-12** (caching, background tasks, streaming, pipeline consolidation) are
deferred to **Phase B** and are out of scope here.

Goal: get real per-stage timing data, then remove pure overhead and
low-risk sequential bottlenecks from the chat critical path, without
changing answer quality/behavior.

---

## Sequencing

Do these in order — each step either produces the data needed for the next,
or reduces noise so later timing comparisons stay valid.

1. Step 1 (instrumentation) must land first — everything else is validated
   against the numbers it produces.
2. Steps 2, 5 are pure-overhead removals with no behavior change — safe to
   do immediately after instrumentation, any order.
3. Steps 3, 4, 6 are config/env changes — do one at a time, re-run the eval
   harness after each, so regressions are attributable.
4. Step 7 (parallelize retrieval I/O) is the only real code-behavior change
   in this phase — do it last, after the cheaper wins are banked and
   measured.
5. Step 8 (async route) is the largest-effort item — only pull it forward if
   steps 1-7 don't get you under the p95 target, since it's infra-level, not
   a per-stage win.

---

## Step 1 — Stage-level timing instrumentation

**Files:**
[backend/app/domain/chat/orchestrator.py](../backend/app/domain/chat/orchestrator.py),
[backend/app/domain/routing/orchestrator.py](../backend/app/domain/routing/orchestrator.py),
[backend/app/domain/query_retrieval/services.py](../backend/app/domain/query_retrieval/services.py),
[backend/app/domain/query_retrieval/hybrid_retriever.py](../backend/app/domain/query_retrieval/hybrid_retriever.py)

**Task:**
- Add a small timing helper (e.g. a `contextlib.contextmanager` in
  `prompt_logger.py`) that wraps a block, computes elapsed ms, and calls
  `append_pipeline_log(stage, [f"elapsed_ms: {elapsed:.1f}"])`.
- Wrap: intent classify, `retrieve_query_context` (and within it: rewrite
  call, dense-original fetch, BM25 fetch, dense-rewritten fetch, rerank),
  grounding assessment, final `generate_chat_answer` call.
- Also log a `total_elapsed_ms` for the whole `RoutingOrchestrator.route`
  call.

**Acceptance criteria:**
- Running a handful of representative chat messages produces a per-stage
  timing breakdown in the pipeline log for each one.
- No change to response content, routes, or status codes.

**Validation:** manual — send a few chat messages locally, inspect
`logs/gemini_prompt_response.txt`, confirm each stage has a timing line and
they roughly sum to total request time.

---

## Step 2 — Remove per-call log-path resolution overhead

**File:** [backend/app/infrastructure/llm/prompt_logger.py](../backend/app/infrastructure/llm/prompt_logger.py)

**Task:**
- Cache `get_log_path()`'s result (e.g. `functools.lru_cache(maxsize=1)` or a
  module-level `_LOG_PATH` computed once on first call) so the
  directory-candidate loop + `mkdir(parents=True, exist_ok=True)` only runs
  once per process instead of on every `append_pipeline_log` /
  `log_gemini_interaction` / `append_deterministic_resolution_log` call.
- Keep the existing fallback-directory behavior on first resolution; just
  don't repeat the filesystem probing afterward.

**Acceptance criteria:**
- `get_log_path()` only performs directory creation/probing once per process
  lifetime (verify by temporarily logging a counter, or by reasoning over
  the `lru_cache` — remove the debug counter before merging).
- Log file output is otherwise unchanged (same path, same content format).

**Validation:** Step 1's timing data — compare per-stage `elapsed_ms` before
and after this change; logging-adjacent stages should show a measurable drop
on Windows (where filesystem calls are relatively more expensive).

---

## Step 3 — Local embeddings (config only)

**File:** `.env` / deployment config (no code change —
[backend/app/infrastructure/vector/embeddings.py](../backend/app/infrastructure/vector/embeddings.py)
already supports this).

**Task:**
- Set `EMBEDDING_PROVIDER=local` (defaults to `all-MiniLM-L6-v2`).
- Re-embed the existing note corpus with the same local model so stored
  document embeddings and new query embeddings are comparable (check
  whichever ingestion path populates the vector store and re-run it, or
  write a one-off backfill script if one doesn't already exist).
- Run the existing `evals/` retrieval harness before/after to confirm
  recall/precision doesn't regress.

**Acceptance criteria:**
- Query embedding calls no longer hit the network (confirm via Step 1
  timing: embedding stage drops from ~100-400ms+ to low double-digit ms).
- Eval scores on `evals/datasets/` are within an acceptable tolerance of the
  pre-change baseline (define tolerance with the user/team before
  proceeding if no threshold exists yet).

**Rollback:** revert `EMBEDDING_PROVIDER` to `google`; re-run corpus
embedding backfill with the Gemini provider if needed.

---

## Step 4 — Tune retrieval/rerank/rewrite thresholds (config only)

**Files:** `.env` / deployment config — env vars already read by
[backend/app/domain/query_retrieval/services.py](../backend/app/domain/query_retrieval/services.py)
and
[backend/app/domain/query_retrieval/hybrid_retriever.py](../backend/app/domain/query_retrieval/hybrid_retriever.py).

**Task:**
- Lower `QUERY_RETRIEVAL_TOP_K` (and/or the orchestrator's
  `ChatRoutingConfig.retrieval_limit` default in
  [backend/app/domain/chat/orchestrator.py](../backend/app/domain/chat/orchestrator.py))
  from 5 to the smallest value that keeps eval scores acceptable.
- Raise `QUERY_REWRITE_MIN_QUERY_QUALITY` above the current `0.35` so fewer
  queries trigger a rewrite call; validate against eval set.
- Optionally test `QUERY_RETRIEVAL_RERANKER=off` as a measurement, to see
  the ceiling of what removing rerank entirely would save — only keep it off
  if eval quality holds.

**Acceptance criteria:**
- Each threshold change is tested independently against the eval harness
  before combining with the next, so regressions are attributable to a
  single change.
- Final chosen values documented (in `.env.example` or deployment config)
  with the eval scores that justified them.

**Rollback:** revert individual env vars to prior defaults.

---

## Step 5 — Reuse Gemini client instances instead of rebuilding per call

**Files:**
[backend/app/infrastructure/llm/gemini_client.py](../backend/app/infrastructure/llm/gemini_client.py)
(`generate_chat_answer`),
[backend/app/infrastructure/llm/query_rewriter.py](../backend/app/infrastructure/llm/query_rewriter.py)
(`rewrite_query_with_llm`).

**Task:**
- Replace the per-call `ChatGoogleGenerativeAI(...)` construction in both
  functions with a module-level singleton, following the same
  `lru_cache`/global-singleton pattern already used by `get_embeddings()`
  and `get_hybrid_retriever()`.
- Keep model id / temperature / retries / timeout resolved from env vars at
  construction time (first call), same as today — just don't reconstruct on
  every request.
- Watch for thread-safety: confirm `ChatGoogleGenerativeAI` instances are
  safe to share across concurrent requests (check library docs/source; if
  not thread-safe, use one instance per model-config key but still cache it
  rather than rebuilding per call).

**Acceptance criteria:**
- Client construction happens once per distinct `(model_id, temperature,
  max_retries, timeout)` combination per process, not per request.
- No change to generated answers/rewrites for identical prompts (behavior
  parity).

**Validation:** Step 1 timing — compare the rewrite/generate stage overhead
before and after on repeated requests.

---

## Step 6 — Cheaper/faster model for query rewriting (config only)

**File:** `.env` / deployment config — no code change required;
[backend/app/infrastructure/llm/query_rewriter.py](../backend/app/infrastructure/llm/query_rewriter.py)
already reads `QUERY_REWRITE_MODEL_ID` independently from `CHAT_MODEL_ID`.

**Task:**
- Set `QUERY_REWRITE_MODEL_ID` to a lighter model (e.g. a flash-lite /
  smaller variant, whichever is available in your Gemini model catalog) and
  leave `CHAT_MODEL_ID` on the current model for final answers.
- Validate rewrite quality via eval harness (rewrite confidence/risk-flag
  rates shouldn't noticeably regress).

**Acceptance criteria:**
- Rewrite-stage latency (Step 1 timing) drops.
- Rewrite confidence/risk-flag distribution on the eval set stays within
  acceptable bounds vs. baseline.

**Rollback:** unset `QUERY_REWRITE_MODEL_ID` (falls back to
`GEMINI_MODEL_ID`/`gemini-2.5-flash`).

---

## Step 7 — Parallelize independent retrieval I/O

**Files:**
[backend/app/domain/query_retrieval/hybrid_retriever.py](../backend/app/domain/query_retrieval/hybrid_retriever.py)
(`HybridRetriever.fetch`),
[backend/app/domain/query_retrieval/services.py](../backend/app/domain/query_retrieval/services.py)
(`retrieve_query_context`).

**Task:**
- In `HybridRetriever.fetch`: run `fetch_dense_embeddings` (original query),
  `fetch_sparse_results`, and (when `alternate_query_text` is provided)
  `fetch_dense_embeddings` (rewritten query) concurrently using
  `concurrent.futures.ThreadPoolExecutor` (simplest option, no async
  rewrite of the whole call chain needed). Preserve existing error handling
  — a failure in one branch shouldn't silently swallow the others; decide
  and document the desired behavior (e.g. a failed branch returns an empty
  list and logs, rather than failing the whole fetch).
- In `retrieve_query_context`: evaluate whether `query_recent_memory_for_user`
  can run concurrently with the rewrite call (they're independent); if so,
  use the same thread-pool approach.
- Preserve existing `append_pipeline_log` call ordering/content as much as
  possible — stage logs may need to record "started"/"completed" per branch
  rather than assuming strict sequential ordering.

**Acceptance criteria:**
- Retrieval stage wall-clock time (Step 1 timing) drops to roughly the
  slowest individual branch instead of the sum of all branches.
- Candidate results (note_id, scores, ranking) are unchanged vs. the
  sequential implementation for the same inputs — write/run a quick
  comparison test (same query, same corpus, compare `fetch()` output
  before/after) to confirm fusion logic isn't affected by call ordering.
- No new unhandled exceptions introduced (errors in one branch are caught
  and logged, not left to crash the whole request).

**Validation:** unit-level comparison of `fetch()` output before/after on a
fixed set of (user_id, query) pairs, plus eval harness run, plus Step 1
timing comparison.

---

## Step 8 — Async chat route (only if still needed after 1-7)

**Files:** [backend/app/api/routes/chat.py](../backend/app/api/routes/chat.py)
and the call chain beneath `handle_chat_message`.

**Task:**
- Convert `send_chat_message` to `async def`.
- Wrap remaining blocking calls (Supabase client calls, LangChain
  `.invoke()`) in `asyncio.to_thread(...)` at the call sites, or adopt async
  variants (`ainvoke`, async Supabase client) where available — pick one
  approach consistently rather than mixing.
- This step is primarily about **concurrent-request throughput** (multiple
  users sharing FastAPI's sync thread pool), not single-request latency —
  re-confirm with Step 1 data whether single-request p95 actually needs this
  before investing the effort.

**Acceptance criteria:**
- Existing single-request behavior/responses unchanged.
- Load test (even a simple concurrent `ab`/`locust`/`hey` run against
  `/chat/message`) shows improved throughput/tail latency under concurrent
  load compared to baseline.

**Validation:** concurrent load test before/after; functional regression
pass on chat endpoint (manual or existing test suite, if any exists under
`backend/`).

---

## Rollout notes

- Each step should be its own commit/PR so a regression can be bisected and
  reverted independently.
- Re-run the Step 1 timing instrumentation after every step in this phase
  to build a before/after table — that table is the artifact that proves
  (or disproves) the p95 < 5s target was reached, and determines whether
  Phase B (steps 9-12 in
  [docs/latency_improvements.md](latency_improvements.md)) is still needed.
- Env-var-only steps (3, 4, 6) should be tested in a staging/eval
  environment before production, since they can affect answer/retrieval
  quality, not just speed.

## Phase B (deferred, not in scope here)

See [docs/latency_improvements.md](latency_improvements.md) items 9-12:
short-TTL rewrite/embedding caching, moving non-critical work to background
tasks, streaming the final answer (SSE), and collapsing the pipeline to
fewer sequential LLM calls.

# Chat Latency Improvement Plan (target: p95 < 5s)

Based on tracing the live chat pipeline:
`POST /chat/message` → `handle_chat_message` → `RoutingOrchestrator.route` →
intent classify (rule-based, fast) → retrieval (`retrieve_query_context` →
query-rewrite LLM call → `HybridRetriever.fetch`: dense embed+query, BM25,
optional second dense embed+query, cross-encoder rerank) → grounding
(rule-based, fast) → final answer LLM call (`generate_chat_answer`).

On the "needs retrieval" path, a single user message can trigger **up to 3
sequential network calls to the Gemini API** (query rewrite, embedding,
final generation) plus a local cross-encoder rerank, all executed one after
another on one thread. That sequential chain is almost certainly the bulk of
your p95. Items below are ordered **easiest → hardest** to implement.

---

## 1. Measure before changing anything (~30 min)
Add stage-level timing around the existing `append_pipeline_log` calls in
[backend/app/domain/chat/orchestrator.py](../backend/app/domain/chat/orchestrator.py),
[backend/app/domain/routing/orchestrator.py](../backend/app/domain/routing/orchestrator.py)
and [backend/app/domain/query_retrieval/services.py](../backend/app/domain/query_retrieval/services.py)
(e.g. wrap each stage in `time.perf_counter()` and log the delta). You need
real numbers for: rewrite call, dense embed+query (x1-2), BM25, rerank, final
generate call. Without this you'll optimize the wrong thing.

## 2. Stop re-creating the log directory/file on every pipeline step (~15 min)
`append_pipeline_log` in
[backend/app/infrastructure/llm/prompt_logger.py](../backend/app/infrastructure/llm/prompt_logger.py)
calls `get_log_path()` — which does `mkdir(parents=True, exist_ok=True)` plus
an `open(..., "a")` — on **every** stage log call. A single chat request
triggers 10+ of these synchronous disk writes. Cache the resolved path once
at module import (or behind an `lru_cache`) and consider making this a no-op
in production unless `PROMPT_LOG_DIR`/a debug flag is explicitly set. Pure
overhead removal, zero behavior change.

## 3. Switch embeddings to a local model (~15 min, config only)
`get_embeddings()` in
[backend/app/infrastructure/vector/embeddings.py](../backend/app/infrastructure/vector/embeddings.py)
defaults to `EMBEDDING_PROVIDER=google`, meaning every retrieval does a
**network round-trip to Gemini just to embed the query**. Set
`EMBEDDING_PROVIDER=local` (uses `all-MiniLM-L6-v2` via
`sentence-transformers`, already wired up) to turn that into an in-process
CPU call (~5-20ms instead of 100-400ms+ of network RTT). This removes one of
the up-to-three sequential Gemini calls per message. Tradeoff: re-embed your
existing note corpus with the same model so query/doc embeddings stay
comparable, and validate recall doesn't regress using your existing
`evals/` harness.

## 4. Tune retrieval/rerank/rewrite thresholds down (~30 min, config only)
- Lower `QUERY_RETRIEVAL_TOP_K` / the orchestrator's `retrieval_limit`
  (default 5) if 3-4 candidates are enough — fewer candidates means less
  work for the cross-encoder reranker, which is the most CPU-expensive local
  step (`SentenceTransformerReranker` in
  [backend/app/domain/query_retrieval/reranker/semantic.py](../backend/app/domain/query_retrieval/reranker/semantic.py)).
- Raise `QUERY_REWRITE_MIN_QUERY_QUALITY` so the rewrite LLM call
  (`rewrite_query_with_llm`) is skipped more often for queries that don't
  really need it — it's currently attempted whenever quality score ≥ 0.35,
  which is a low bar.
- If recall without rerank is acceptable for your eval set, set
  `QUERY_RETRIEVAL_RERANKER=off` to drop the cross-encoder step entirely from
  the critical path.

## 5. Stop rebuilding the Gemini client object per request (~30-45 min)
Both `generate_chat_answer()` in
[backend/app/infrastructure/llm/gemini_client.py](../backend/app/infrastructure/llm/gemini_client.py)
and `rewrite_query_with_llm()` in
[backend/app/infrastructure/llm/query_rewriter.py](../backend/app/infrastructure/llm/query_rewriter.py)
construct a brand-new `ChatGoogleGenerativeAI(...)` instance on every single
call. Client construction does credential/config validation and can carry
non-trivial fixed overhead. Build each client once as a module-level
singleton (same `lru_cache`/global-singleton pattern already used for
`get_embeddings()` and `get_hybrid_retriever()`) and reuse it across
requests.

## 6. Use a cheaper/faster model for query rewriting (~30 min, config only)
The rewrite step only needs to reformulate a query, not produce a polished
answer — a good candidate for a lighter model (e.g.
`gemini-2.5-flash-lite` or similar) via a new `QUERY_REWRITE_MODEL_ID` env
var, independent of `CHAT_MODEL_ID`. This shaves latency off one of the two
sequential LLM calls without touching final-answer quality.

## 7. Parallelize independent retrieval I/O (~2-4 hrs)
`HybridRetriever.fetch()` in
[backend/app/domain/query_retrieval/hybrid_retriever.py](../backend/app/domain/query_retrieval/hybrid_retriever.py)
currently runs dense-original embed+query, then BM25, then (if rewrite was
used) a second dense embed+query — all **sequentially**, even though none
depend on each other's output. Same for `retrieve_query_context()`, which
fetches `recent_memory` before calling the rewriter when neither depends on
the other. Run these concurrently with `concurrent.futures.ThreadPoolExecutor`
(simplest, no async rewrite needed) and merge results after. This can cut
the retrieval stage's wall time roughly to its slowest single call instead
of the sum of all of them.

## 8. Make the chat endpoint truly async (~1 day)
`send_chat_message` in
[backend/app/api/routes/chat.py](../backend/app/api/routes/chat.py) and
everything it calls (`handle_chat_message` → orchestrator → Supabase repo
calls → LangChain SDK calls) is synchronous `def`. FastAPI runs sync routes
in a thread pool, so this is fine for single-request latency but means you
can't overlap I/O within a single request without the `ThreadPoolExecutor`
approach above, and concurrent users compete for the same limited thread
pool (hurts p95 under load even if per-request work is unchanged). Convert
the route to `async def` and push remaining blocking calls (Supabase client,
LangChain `.invoke()`) through `asyncio.to_thread(...)`, or migrate to the
async variants of these SDKs (`ainvoke`, Supabase async client) where
available.

## 9. Add short-TTL caching for rewrites/embeddings (~1 day)
Cache `(user_id, normalized_query) -> rewrite_result` and
`query_text -> embedding` for a short TTL (e.g. 2-5 minutes, in-process LRU
or Redis if you have multiple backend instances). Users frequently
re-ask/paraphrase within a session; this turns repeat or near-repeat queries
into cache hits and skips the rewrite/embedding network calls entirely.

## 10. Move non-critical-path work off the response latency budget (~1-2 days)
Chat history/summary persistence and pipeline logging don't need to block
the user-visible response. Move anything after "final answer produced" that
isn't needed to build the HTTP response (e.g. summary memory updates, full
pipeline trace logging) into a background task
(`BackgroundTasks` in FastAPI, or your existing `workers/` queue) so the
client gets the answer as soon as it's generated.

## 11. Stream the final answer (SSE) (~2-3 days)
Switch `generate_chat_answer` from `model.invoke(...)` to
`model.stream(...)` and expose a streaming endpoint (SSE or chunked
response) to the frontend. This doesn't reduce total model compute time, so
it won't move a strict "full response received" p95 metric — but it
collapses *perceived* latency (time-to-first-token) dramatically, which is
usually what "feels like 5s" is really measuring from a user's perspective.
Worth doing in parallel with the above if your p95 target is UX-driven
rather than a hard backend SLA.

## 12. Collapse the pipeline to fewer sequential LLM calls (~3-5 days)
The biggest structural win: the retrieval-needed path does rewrite → embed →
rerank → generate as four dependent-looking but partially-independent
stages. Consider:
- Skipping rewrite whenever grounding would end up "strong" without it
  (cheap heuristic pre-check before paying for the rewrite call).
- Merging the rewrite and final-generation prompts into a single call for
  the common case (ask the model to both reformulate internally and answer,
  using retrieval done against the original query first, falling back to a
  second retrieval pass only when grounding is weak). This removes an entire
  Gemini round-trip from the median-case latency, not just the tail.

This is a real behavior/quality change (not just infra), so validate against
your `evals/` retrieval datasets before and after to confirm you haven't
traded latency for answer quality or grounding accuracy.

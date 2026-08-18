Headline
On this dataset, bm25 and rrf are currently the strongest. Dense retrieval is useful for some semantic families, but it is weak on exact-ID lookup. rerank preserves recall but hurts rank ordering for item lookups. rewrite currently makes results worse because it fires mostly on exact-ID cases, and the rewritten/expanded dense query dilutes the identifier signal.
Overall Metrics
Mode Precision@5 Recall@5 MRR@5 No-context Conflict
bm25 0.284 1.000 1.000 3/5 15/15
dense 0.196 0.653 0.533 0/5 15/15
rrf 0.284 1.000 0.984 0/5 15/15
rerank 0.284 1.000 0.886 0/5 15/15
rewrite 0.278 0.968 0.938 0/5 15/15

v0_smoke_bm25 is not really comparable because it has only 8 simpler scenarios. It looks healthy, but the v1 suite is the meaningful benchmark.
Mode Breakdown
bm25
Best overall for this dataset. It gets perfect recall and perfect MRR on all answerable v1 families. That makes sense because many cases contain exact identifiers: ITEM-4103, DFX-7207, ITEM-5108, etc.
Weakness: no-context only passes 3/5. So even sparse search sometimes returns nothing, but not consistently enough to be a reliable abstention mechanism.
dense
Worst overall. It performs well on semantic-ish families:
progress_summary: R=1.000, MRR=1.000
learning_paraphrase: R=1.000, MRR=0.950
ambiguous_conflict: R=1.000, MRR=1.000
But it struggles badly on exact identifiers:
item_lookup: R=0.500, MRR=0.224
datafix_count: R=0.333, MRR=0.197
dependency_synthesis: R=0.400, MRR=0.347
isolation: R=0.600, MRR=0.353
Probable reason: embeddings treat many synthetic records as semantically similar, and exact IDs are not reliably preserved as retrieval anchors. For example, dense often returns nearby item IDs like ITEM-4110, ITEM-4119, etc. instead of the exact requested one.
rrf
Best production-style baseline right now. It keeps BM25’s perfect recall, but MRR drops slightly from 1.000 to 0.984.
The drop comes mostly from isolation cases, where dense noise nudges a related-but-wrong item above the exact BM25 hit. Example: isolation-item-01 ranks isolation-primary-05 before isolation-primary-01.
No-context gets worse: 0/5. This is expected because dense search always returns nearest neighbors unless you add a distance/score threshold.
rerank
Precision and recall stay equal to rrf, but MRR drops:
rrf MRR: 0.984
rerank MRR: 0.886
It improves isolation ordering back to perfect MRR, but hurts item lookups hard:
item_lookup MRR:
rrf: 1.000
rerank: 0.458
Probable reason: the token-overlap reranker overweights generic words like “owner”, “status”, “targeted”, “rollout”, etc., and underweights exact IDs. Example: for item-lookup-03, rerank promotes multi-01-scope above item-item-4103.
rewrite
Rewrite is currently a net negative:
rrf: P=0.284 R=1.000 MRR=0.984
rewrite: P=0.278 R=0.968 MRR=0.938
Only 8/100 rewrites were actually used. 92 were blocked by low_context, which is good conservative behavior, but the 8 accepted rewrites mostly hit exact-ID queries where rewrite is not needed.
Bad examples:
ITEM-4111 dropped from found-at-rank-1 to not found.
ITEM-4114 dropped from found-at-rank-1 to not found.
ITEM-4117 dropped from found-at-rank-1 to not found.
Probable reason: the expanded query includes generic likely_answer text like “specific metadata and scheduling information”, which adds semantic noise. Dense rewritten retrieval then contributes wrong neighboring IDs into RRF.
Main Findings
The dataset currently favors lexical retrieval
Exact IDs dominate. BM25 is naturally excellent here. Dense/rewrite cannot beat exact token matching unless the fusion logic gives exact identifiers special treatment.

Dense retrieval needs exact-token protection
Embeddings are bad at distinguishing ITEM-4111 from ITEM-4110 or ITEM-4119.

RRF is still the best hybrid baseline
It preserves BM25 recall while adding dense candidates. But dense noise should be gated.

The reranker needs ID-aware scoring
Token overlap alone is too blunt. It sees “owner/status/target” and promotes broad scope records.

Rewrite should not run on exact-ID queries
Rewriting exact-ID queries is actively harmful here.

No-context evaluation is exposing missing abstention logic
Dense/hybrid always return something. You need a score threshold or answer-stage abstention policy.

Recommended Improvements
Prompt improvements:
Add a rewrite rule: if the query contains exact IDs like ITEM-\d+, DFX-\d+, do not rewrite; return the original query.
Add a risk flag such as exact_identifier_query.
Do not include likely_answer in the expanded retrieval query unless it is grounded in supplied memory context.
For no-context-style queries, prompt the rewriter to lower confidence aggressively when memory context is empty.
Retrieval improvements:
Add exact-ID extraction before retrieval.If query contains ITEM-4111, boost notes containing exactly ITEM-4111.
Same for DFX-7207, checkpoint numbers, recovery windows, etc.

In RRF, weight BM25 higher than dense when exact identifiers are present.
Add dense distance thresholding for no-context detection.
Consider hybrid candidate policy:exact-ID query: BM25-first, dense secondary
semantic/paraphrase query: balanced RRF
no-context candidate: require minimum lexical or dense confidence

Reranker improvements:
Add ID-aware features:exact identifier match bonus
identifier mismatch penalty
numeric mismatch penalty

Preserve first-rank BM25 result when it exactly matches the requested ID.
Use reranker only after family detection, or only for non-ID semantic queries.
Chunking/indexing improvements:
Store structured metadata alongside text:item_id
datafix_id
checkpoint_number
note_type
project
owner
created_at

Use metadata filters or boosts when the query has structured IDs.
Consider dual indexing:one field optimized for exact lexical lookup
one field optimized for semantic summaries

Add small “title/header” text to each embedded chunk, e.g. ITEM-4111 owner status target, so dense embeddings have stronger anchors.
Dataset improvements:
Add more truly semantic cases where BM25 should struggle.
Add paraphrases without exact identifiers.
Add adversarial exact-ID near misses, e.g. query ITEM-4111 with distractors ITEM-4110, ITEM-4112.
Add no-context cases that share common words with real notes to test abstention more realistically.
Add expected ranking assertions, not just retrieved-set recall, because current precision/recall can hide poor ordering.
Priority Order
Keep rrf as the baseline.
Disable rewrite for exact-ID queries.
Add ID-aware reranking/boosting.
Add no-context thresholding.
Expand dataset with semantic cases where dense/rewrite can actually show value.

# NorthStar Retrieval Evaluation Result

- Runner: `hybrid_rrf_eval`
- Code revision: `86b31cc`
- Configuration: `k=5`, `mode=rrf`, `dataset={'cases': 'evals\\datasets\\northstar_rag_v4.jsonl', 'corpus': 'evals\\datasets\\northstar_rag_v4_corpus.jsonl'}`, `embedding_provider=google`, `embedding_model=gemini-embedding-001`, `collection=northstar_rag_v4_rrf_eval`, `storage_path=evals\.chroma`, `reuse_collection=True`, `fusion=production_rrf`, `candidate_multiplier=3.0`, `candidate_limit=15`, `reranker=off`, `reranker_model=None`, `strict_rerank=False`, `rewrite=off`, `rewrite_cache=off`, `rewrite_latency_seconds=0.0`, `refresh_rewrite_cache=False`
- Scenario count: 50

## Summary

| Metric | Result |
| --- | ---: |
| Precision@5 | 0.223 |
| Recall@5 | 0.953 |
| MRR@5 | 0.818 |
| Isolation failures | 0 |
| No-context checks | 0/7 |
| Conflict retrieval checks | 0/0 |

## Scenario Results

| Scenario | Query | Retrieved notes | Relevant notes | Precision | Recall | Reciprocal rank | Isolation | No context | Conflict evidence |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| v4-mba-positioning-01 | Which customer need did I decide the paid planning tool should own, and what alternatives do buyers weigh? | `mba-marketing-positioning`, `mba-funnel-done`, `mba-strategy-moat`, `int-revision-plan`, `mba-funnel-plan` | `mba-marketing-positioning` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-npv-01 | Why did the slower-payback option still win the capital budgeting case? | `mba-finance-npv`, `mba-pricing-econ`, `mba-acquisition-case`, `mba-strategy-moat`, `int-revision-done` | `mba-finance-npv` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-bottleneck-01 | Where did the work pile up once we added another person to the approval stage? | `swe-retro-estimates`, `mba-ops-bottleneck`, `int-revision-done`, `swe-trace-ids`, `swe-redis-cluster` | `mba-ops-bottleneck` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-mba-moat-01 | Why could the established vendor keep charging more in that enterprise software example? | `mba-strategy-moat`, `swe-session-new`, `mba-pricing-entry`, `mba-pricing-econ`, `mba-marketing-positioning` | `mba-strategy-moat` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-funnel-status-01 | Did the cohort drop-off review get finished, and where do new accounts stall? | `mba-funnel-done`, `mba-funnel-plan`, `mba-churn-case`, `swe-auth-scopes`, `swe-search-update` | `mba-funnel-plan`, `mba-funnel-done` | 0.400 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-wacc-01 | Why is the company's financing mix so sensitive to the cost of equity? | `mba-finance-wacc`, `mba-pricing-econ`, `mba-churn-case`, `mba-strategy-moat`, `mba-finance-npv` | `mba-finance-wacc` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-fulfillment-change-01 | What is my latest distribution setup recommendation, and what data overturned the first one? | `mba-ops-centralize`, `mba-ops-regional`, `swe-pricing-rollback`, `swe-dashboard-query`, `swe-search-plan` | `mba-ops-centralize`, `mba-ops-regional` | 0.400 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-pricing-synthesis-01 | What did I conclude about entering 15% cheaper, and what has to be true for that to work? | `mba-pricing-entry`, `mba-pricing-econ`, `swe-staging-cost`, `mba-strategy-moat`, `mba-finance-wacc` | `mba-pricing-entry`, `mba-pricing-econ` | 0.400 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-churn-nextstep-01 | What did I decide to look at first in the subscriber retention case? | `mba-churn-case`, `mba-funnel-plan`, `mba-funnel-done`, `mba-acquisition-case`, `mba-strategy-moat` | `mba-churn-case` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-delegation-01 | What made handing off the weekly numbers meeting succeed? | `mba-leadership`, `swe-auth-scopes`, `int-star-leadership`, `mba-funnel-plan`, `swe-retro-estimates` | `mba-leadership` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-checkout-rootcause-01 | What was really behind the order submission slowdown? | `swe-architecture-outbox`, `swe-order-backfill`, `swe-checkout-retry`, `swe-modal-focus`, `mba-ops-bottleneck` | `swe-checkout-retry` | 0.200 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-swe-sync-writes-01 | Why did we leave the purchase write path blocking instead of making it async? | `swe-architecture-outbox`, `int-booking-holds`, `swe-trace-ids`, `swe-flaky-tests`, `int-profile-cache` | `swe-architecture-outbox` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-retro-misses-01 | What did the team blame for missing its sprint commitments? | `swe-retro-estimates`, `int-star-leadership`, `swe-auth-scopes`, `mba-leadership`, `mba-finance-npv` | `swe-retro-estimates` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-search-status-01 | Where are we with the new retrieval rollout? | `mba-funnel-plan`, `swe-search-update`, `swe-retro-estimates`, `swe-api-freeze`, `swe-pricing-rollback` | `swe-search-plan`, `swe-search-update` | 0.200 | 0.500 | 0.500 | Pass | N/A | N/A |
| v4-swe-dashboard-p95-01 | Why did the slowest dashboard loads get faster? | `swe-dashboard-query`, `swe-trace-ids`, `swe-checkout-retry`, `swe-session-new`, `swe-order-backfill` | `swe-dashboard-query` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-pricing-rollback-01 | Why did we undo the checkout price display change? | `swe-checkout-retry`, `swe-retro-estimates`, `swe-flaky-tests`, `swe-review-risk`, `mba-pricing-entry` | `swe-pricing-rollback` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-swe-api-blocker-01 | What is holding up the interface agreement? | `int-star-conflict`, `int-star-leadership`, `swe-api-freeze`, `swe-auth-scopes`, `swe-search-update` | `swe-api-freeze`, `swe-auth-scopes` | 0.400 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-swe-billing-alerts-01 | What caused the duplicate pages from monitoring, and how was it fixed? | `swe-billing-cleanup`, `swe-oncall-runbook`, `swe-billing-alerts`, `swe-checkout-retry`, `int-payment-events` | `swe-billing-alerts`, `swe-billing-cleanup` | 0.400 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-session-storage-01 | What are we doing now for login state, and why did the original idea get dropped? | `swe-flaky-tests`, `swe-retro-estimates`, `swe-session-old`, `swe-session-new`, `swe-trace-ids` | `swe-session-old`, `swe-session-new` | 0.400 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-swe-staging-security-01 | What did the audit finding change in the test environment? | `swe-security-staging`, `swe-review-risk`, `swe-session-new`, `mba-funnel-done`, `mba-ops-simulation` | `swe-security-staging` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-oncall-page-01 | When should someone be woken up under the new incident policy? | `swe-checkout-retry`, `mba-funnel-plan`, `swe-oncall-runbook`, `int-star-conflict`, `swe-mobile-oncall` | `swe-oncall-runbook` | 0.200 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-swe-ci-time-01 | Why did the build pipeline get 12 minutes shorter? | `swe-flaky-tests`, `swe-oncall-runbook`, `swe-staging-cost`, `int-booking-holds`, `swe-retro-estimates` | `swe-flaky-tests` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-order-backfill-01 | How big was the timestamp repair, and what caused the missing values? | `swe-order-backfill`, `int-fintech-process`, `swe-checkout-retry`, `swe-pricing-rollback`, `swe-billing-cleanup` | `swe-order-backfill` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-modal-focus-01 | Why couldn't people tab through the dialog properly, and what fixed it? | `swe-modal-focus`, `swe-checkout-retry`, `mba-ops-centralize`, `int-profile-cache`, `int-mock-feedback` | `swe-modal-focus` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-trace-debug-01 | How did we connect worker logs to the originating request? | `swe-trace-ids`, `swe-architecture-outbox`, `swe-retro-estimates`, `int-profile-cache`, `swe-checkout-retry` | `swe-trace-ids` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-cloud-cost-01 | Where did we find the largest easy savings in our cloud bill? | `swe-staging-cost`, `swe-retro-estimates`, `swe-billing-cleanup`, `swe-trace-ids`, `swe-dashboard-query` | `swe-staging-cost` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-review-risk-01 | What new step did we add before approving database or permission changes? | `swe-security-staging`, `swe-review-risk`, `swe-retro-estimates`, `swe-session-new`, `mba-funnel-plan` | `swe-review-risk` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-int-sliding-pointer-01 | How do I move the start of the window when a character repeats? | `int-sliding-window`, `swe-session-old`, `int-binary-duplicates`, `int-mock-feedback`, `swe-modal-focus` | `int-sliding-window` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-knapsack-order-01 | Why does the one-array DP loop run from the top down? | `int-knapsack`, `int-house-robber`, `int-sliding-window`, `mba-ops-centralize`, `int-fintech-process` | `int-knapsack` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-toposort-cycle-01 | How can Kahn's method tell me that a directed graph is cyclic? | `int-toposort`, `swe-trace-ids`, `int-payment-events`, `int-knapsack`, `int-mock-feedback` | `int-toposort` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-binary-duplicates-01 | Which search variant finds the first matching slot when the array has repeated values? | `int-binary-duplicates`, `int-knapsack`, `int-mock-feedback`, `int-fintech-process`, `swe-search-plan` | `int-binary-duplicates` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-heap-build-01 | What is the time complexity of turning an unsorted array into a priority queue? | `int-mock-feedback`, `int-heap-build`, `int-knapsack`, `swe-trace-ids`, `int-binary-duplicates` | `int-heap-build` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-int-profile-cache-01 | What caching approach did I pick for the user profile service, and why not write to cache on updates? | `int-profile-cache`, `swe-architecture-outbox`, `int-chat-shard`, `int-booking-holds`, `swe-pricing-rollback` | `int-profile-cache` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-payment-retry-01 | How do I keep repeated charge attempts from creating duplicate payments? | `swe-billing-cleanup`, `int-payment-events`, `swe-billing-alerts`, `int-payments-prep`, `swe-order-backfill` | `int-payment-events` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-int-chat-shard-01 | What key did I choose to split message threads across machines? | `int-star-leadership`, `int-chat-shard`, `mba-funnel-done`, `swe-trace-ids`, `swe-redis-cluster` | `int-chat-shard` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-int-booking-holds-01 | How do I stop two people from taking the same seat without a distributed lock? | `int-booking-holds`, `swe-billing-alerts`, `int-payment-events`, `mba-ops-regional`, `swe-architecture-outbox` | `int-booking-holds` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-conflict-story-01 | What did the ownership dispute teach me about working with another engineer? | `int-star-conflict`, `int-star-leadership`, `int-revision-done`, `mba-marketing-positioning`, `swe-retro-estimates` | `int-star-conflict` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-deadline-story-01 | What did I change after missing the migration date? | `swe-order-backfill`, `swe-session-new`, `int-star-deadline`, `swe-k8s-ingress`, `swe-review-risk` | `int-star-deadline` | 0.200 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-int-leadership-story-01 | How did I divide work on the four-person effort so nobody had to work late? | `int-star-leadership`, `swe-staging-cost`, `swe-trace-ids`, `int-chat-shard`, `int-star-conflict` | `int-star-leadership` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-revision-status-01 | Which interview topics are still shaky after my last review? | `int-revision-done`, `int-google-prep`, `int-mock-feedback`, `swe-security-staging`, `int-fintech-process` | `int-revision-plan`, `int-revision-done` | 0.200 | 0.500 | 1.000 | Pass | N/A | N/A |
| v4-int-fintech-process-01 | What are the stages and expected wait time for the fintech role? | `mba-acquisition-case`, `int-fintech-process`, `swe-flaky-tests`, `int-mock-feedback`, `int-payments-prep` | `int-fintech-process` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-int-payments-focus-01 | What should I study before talking to the payments company? | `int-payments-prep`, `mba-funnel-plan`, `int-fintech-process`, `swe-order-backfill`, `int-mock-feedback` | `int-payments-prep` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-mock-feedback-01 | What did the practice interview reveal about how I should open a solution? | `int-mock-feedback`, `int-google-prep`, `int-fintech-process`, `int-house-robber`, `mba-funnel-plan` | `int-mock-feedback` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-nc-mba-acquisition-01 | What valuation did I settle on for the fintech acquisition case? | `mba-acquisition-case`, `int-fintech-process`, `mba-funnel-done`, `mba-finance-npv`, `mba-funnel-plan` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-mba-simulation-01 | Which professor graded the operations simulation? | `mba-ops-simulation`, `mba-ops-bottleneck`, `int-heap-build`, `mba-ops-regional`, `mba-acquisition-case` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-swe-k8s-upgrade-01 | What was the final Kubernetes upgrade date? | `swe-k8s-ingress`, `swe-pricing-rollback`, `swe-session-new`, `swe-api-freeze`, `swe-search-update` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-swe-redis-resize-01 | Who approved the Redis cluster resize? | `swe-redis-cluster`, `swe-session-old`, `swe-session-new`, `int-revision-done`, `swe-k8s-ingress` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-swe-mobile-oncall-01 | What is the current on-call rotation for the mobile team? | `swe-mobile-oncall`, `swe-billing-alerts`, `swe-oncall-runbook`, `swe-api-freeze`, `swe-auth-scopes` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-int-google-feedback-01 | What was the interviewer's feedback after the Google system design round? | `int-google-prep`, `int-fintech-process`, `int-revision-plan`, `int-booking-holds`, `int-mock-feedback` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-int-fintech-offers-01 | How many offers did the fintech company extend? | `int-fintech-process`, `mba-acquisition-case`, `int-payments-prep`, `mba-pricing-econ`, `mba-finance-wacc` | None | N/A | N/A | N/A | Pass | Fail | N/A |

## Interpretation

This is a deterministic BM25 smoke baseline over synthetic notes. It measures retrieval only; it does not evaluate generated answers, claim support, conflict resolution wording, latency, or model cost.

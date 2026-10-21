# NorthStar Retrieval Evaluation Result

- Runner: `bm25_smoke`
- Code revision: `3c5f29c`
- Configuration: `k=5`, `k1=1.5`, `b=0.75`
- Scenario count: 50

## Summary

| Metric | Result |
| --- | ---: |
| Precision@5 | 0.233 |
| Recall@5 | 0.733 |
| MRR@5 | 0.598 |
| Isolation failures | 0 |
| No-context checks | 0/7 |
| Conflict retrieval checks | 0/0 |

## Scenario Results

| Scenario | Query | Retrieved notes | Relevant notes | Precision | Recall | Reciprocal rank | Isolation | No context | Conflict evidence |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| v4-mba-positioning-01 | Which customer need did I decide the paid planning tool should own, and what alternatives do buyers weigh? | `int-revision-plan`, `mba-funnel-done`, `mba-strategy-moat`, `mba-marketing-positioning` | `mba-marketing-positioning` | 0.250 | 1.000 | 0.250 | Pass | N/A | N/A |
| v4-mba-npv-01 | Why did the slower-payback option still win the capital budgeting case? | `mba-finance-npv`, `int-revision-done`, `swe-architecture-outbox`, `mba-pricing-econ`, `mba-acquisition-case` | `mba-finance-npv` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-bottleneck-01 | Where did the work pile up once we added another person to the approval stage? | `swe-redis-cluster`, `int-revision-done`, `int-star-conflict`, `int-star-leadership`, `swe-retro-estimates` | `mba-ops-bottleneck` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-mba-moat-01 | Why could the established vendor keep charging more in that enterprise software example? | `swe-session-new`, `mba-strategy-moat` | `mba-strategy-moat` | 0.500 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-mba-funnel-status-01 | Did the cohort drop-off review get finished, and where do new accounts stall? | `mba-funnel-plan`, `mba-funnel-done`, `swe-auth-scopes`, `mba-churn-case`, `swe-review-risk` | `mba-funnel-plan`, `mba-funnel-done` | 0.400 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-wacc-01 | Why is the company's financing mix so sensitive to the cost of equity? | `mba-finance-wacc`, `int-payments-prep`, `mba-churn-case`, `int-toposort`, `swe-staging-cost` | `mba-finance-wacc` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-fulfillment-change-01 | What is my latest distribution setup recommendation, and what data overturned the first one? | `mba-ops-centralize`, `mba-ops-regional`, `swe-search-plan`, `int-binary-duplicates`, `int-mock-feedback` | `mba-ops-centralize`, `mba-ops-regional` | 0.400 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-pricing-synthesis-01 | What did I conclude about entering 15% cheaper, and what has to be true for that to work? | `mba-pricing-entry`, `swe-staging-cost`, `mba-pricing-econ` | `mba-pricing-entry`, `mba-pricing-econ` | 0.667 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-mba-churn-nextstep-01 | What did I decide to look at first in the subscriber retention case? | `swe-search-plan`, `int-binary-duplicates`, `int-mock-feedback`, `mba-acquisition-case`, `mba-funnel-plan` | `mba-churn-case` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-mba-delegation-01 | What made handing off the weekly numbers meeting succeed? | `swe-auth-scopes`, `mba-leadership`, `mba-funnel-plan`, `mba-funnel-done` | `mba-leadership` | 0.250 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-swe-checkout-rootcause-01 | What was really behind the order submission slowdown? | `swe-architecture-outbox`, `swe-modal-focus`, `swe-order-backfill` | `swe-checkout-retry` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-swe-sync-writes-01 | Why did we leave the purchase write path blocking instead of making it async? | `swe-architecture-outbox`, `swe-retro-estimates`, `swe-trace-ids`, `mba-strategy-moat`, `swe-flaky-tests` | `swe-architecture-outbox` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-retro-misses-01 | What did the team blame for missing its sprint commitments? | `swe-retro-estimates`, `mba-finance-npv`, `swe-order-backfill`, `swe-api-freeze`, `swe-auth-scopes` | `swe-retro-estimates` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-search-status-01 | Where are we with the new retrieval rollout? | `mba-funnel-plan`, `swe-retro-estimates` | `swe-search-plan`, `swe-search-update` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-swe-dashboard-p95-01 | Why did the slowest dashboard loads get faster? | `swe-dashboard-query` | `swe-dashboard-query` | 1.000 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-pricing-rollback-01 | Why did we undo the checkout price display change? | `mba-pricing-entry`, `swe-review-risk`, `swe-retro-estimates`, `swe-checkout-retry`, `swe-flaky-tests` | `swe-pricing-rollback` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-swe-api-blocker-01 | What is holding up the interface agreement? | `int-star-conflict`, `int-star-leadership` | `swe-api-freeze`, `swe-auth-scopes` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-swe-billing-alerts-01 | What caused the duplicate pages from monitoring, and how was it fixed? | `mba-ops-centralize`, `swe-oncall-runbook`, `swe-billing-cleanup`, `swe-billing-alerts`, `swe-checkout-retry` | `swe-billing-alerts`, `swe-billing-cleanup` | 0.400 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-swe-session-storage-01 | What are we doing now for login state, and why did the original idea get dropped? | `swe-retro-estimates`, `swe-flaky-tests`, `swe-trace-ids` | `swe-session-old`, `swe-session-new` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-swe-staging-security-01 | What did the audit finding change in the test environment? | `swe-security-staging`, `swe-review-risk`, `swe-session-new`, `mba-funnel-done` | `swe-security-staging` | 0.250 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-oncall-page-01 | When should someone be woken up under the new incident policy? | `mba-funnel-plan`, `int-star-conflict`, `swe-checkout-retry` | `swe-oncall-runbook` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-swe-ci-time-01 | Why did the build pipeline get 12 minutes shorter? | `swe-flaky-tests`, `swe-oncall-runbook`, `int-booking-holds` | `swe-flaky-tests` | 0.333 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-order-backfill-01 | How big was the timestamp repair, and what caused the missing values? | `swe-order-backfill`, `int-fintech-process` | `swe-order-backfill` | 0.500 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-modal-focus-01 | Why couldn't people tab through the dialog properly, and what fixed it? | `swe-modal-focus`, `mba-ops-centralize`, `int-profile-cache`, `swe-checkout-retry` | `swe-modal-focus` | 0.250 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-trace-debug-01 | How did we connect worker logs to the originating request? | `swe-trace-ids`, `swe-retro-estimates`, `int-profile-cache`, `swe-architecture-outbox` | `swe-trace-ids` | 0.250 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-cloud-cost-01 | Where did we find the largest easy savings in our cloud bill? | `swe-staging-cost`, `swe-retro-estimates` | `swe-staging-cost` | 0.500 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-swe-review-risk-01 | What new step did we add before approving database or permission changes? | `mba-funnel-plan`, `mba-churn-case`, `swe-review-risk`, `swe-security-staging`, `swe-session-new` | `swe-review-risk` | 0.200 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-int-sliding-pointer-01 | How do I move the start of the window when a character repeats? | `int-sliding-window`, `swe-session-old` | `int-sliding-window` | 0.500 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-knapsack-order-01 | Why does the one-array DP loop run from the top down? | `int-knapsack`, `int-house-robber`, `mba-ops-centralize`, `swe-dashboard-query`, `int-chat-shard` | `int-knapsack` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-toposort-cycle-01 | How can Kahn's method tell me that a directed graph is cyclic? | `int-toposort`, `int-payment-events`, `swe-trace-ids`, `mba-strategy-moat` | `int-toposort` | 0.250 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-binary-duplicates-01 | Which search variant finds the first matching slot when the array has repeated values? | `swe-search-plan`, `int-binary-duplicates`, `int-knapsack`, `int-fintech-process`, `swe-search-update` | `int-binary-duplicates` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-int-heap-build-01 | What is the time complexity of turning an unsorted array into a priority queue? | `int-mock-feedback`, `swe-trace-ids`, `int-knapsack`, `int-payment-events`, `int-heap-build` | `int-heap-build` | 0.200 | 1.000 | 0.200 | Pass | N/A | N/A |
| v4-int-profile-cache-01 | What caching approach did I pick for the user profile service, and why not write to cache on updates? | `int-profile-cache`, `int-chat-shard`, `swe-pricing-rollback`, `mba-ops-regional`, `swe-architecture-outbox` | `int-profile-cache` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-payment-retry-01 | How do I keep repeated charge attempts from creating duplicate payments? | `swe-session-new`, `swe-billing-cleanup`, `swe-billing-alerts`, `int-payments-prep`, `swe-order-backfill` | `int-payment-events` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-int-chat-shard-01 | What key did I choose to split message threads across machines? | `int-star-leadership`, `mba-funnel-done` | `int-chat-shard` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-int-booking-holds-01 | How do I stop two people from taking the same seat without a distributed lock? | `int-booking-holds`, `swe-billing-alerts`, `mba-ops-regional`, `mba-ops-simulation`, `int-star-leadership` | `int-booking-holds` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-conflict-story-01 | What did the ownership dispute teach me about working with another engineer? | `int-revision-done`, `mba-marketing-positioning`, `int-star-conflict`, `int-star-leadership` | `int-star-conflict` | 0.250 | 1.000 | 0.333 | Pass | N/A | N/A |
| v4-int-deadline-story-01 | What did I change after missing the migration date? | `swe-order-backfill`, `swe-k8s-ingress`, `swe-session-new`, `swe-review-risk`, `swe-search-update` | `int-star-deadline` | 0.000 | 0.000 | 0.000 | Pass | N/A | N/A |
| v4-int-leadership-story-01 | How did I divide work on the four-person effort so nobody had to work late? | `int-star-leadership`, `swe-staging-cost`, `int-knapsack`, `int-chat-shard`, `swe-trace-ids` | `int-star-leadership` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-revision-status-01 | Which interview topics are still shaky after my last review? | `int-revision-done`, `int-fintech-process`, `swe-security-staging`, `int-sliding-window`, `int-google-prep` | `int-revision-plan`, `int-revision-done` | 0.200 | 0.500 | 1.000 | Pass | N/A | N/A |
| v4-int-fintech-process-01 | What are the stages and expected wait time for the fintech role? | `mba-acquisition-case`, `int-fintech-process`, `int-mock-feedback`, `swe-flaky-tests`, `swe-trace-ids` | `int-fintech-process` | 0.200 | 1.000 | 0.500 | Pass | N/A | N/A |
| v4-int-payments-focus-01 | What should I study before talking to the payments company? | `int-payments-prep`, `mba-finance-wacc`, `swe-order-backfill`, `mba-funnel-plan`, `int-mock-feedback` | `int-payments-prep` | 0.200 | 1.000 | 1.000 | Pass | N/A | N/A |
| v4-int-mock-feedback-01 | What did the practice interview reveal about how I should open a solution? | `int-house-robber`, `int-fintech-process`, `int-google-prep`, `int-mock-feedback` | `int-mock-feedback` | 0.250 | 1.000 | 0.250 | Pass | N/A | N/A |
| v4-nc-mba-acquisition-01 | What valuation did I settle on for the fintech acquisition case? | `mba-acquisition-case`, `mba-funnel-plan`, `mba-churn-case`, `int-fintech-process`, `mba-funnel-done` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-mba-simulation-01 | Which professor graded the operations simulation? | `mba-ops-simulation`, `mba-ops-bottleneck`, `int-heap-build` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-swe-k8s-upgrade-01 | What was the final Kubernetes upgrade date? | `swe-k8s-ingress` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-swe-redis-resize-01 | Who approved the Redis cluster resize? | `swe-redis-cluster`, `swe-session-old`, `swe-session-new` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-swe-mobile-oncall-01 | What is the current on-call rotation for the mobile team? | `swe-mobile-oncall`, `swe-billing-alerts`, `swe-api-freeze`, `swe-auth-scopes`, `swe-oncall-runbook` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-int-google-feedback-01 | What was the interviewer's feedback after the Google system design round? | `int-google-prep`, `int-fintech-process`, `int-booking-holds`, `int-revision-plan`, `int-payment-events` | None | N/A | N/A | N/A | Pass | Fail | N/A |
| v4-nc-int-fintech-offers-01 | How many offers did the fintech company extend? | `int-fintech-process`, `int-payments-prep`, `mba-acquisition-case`, `mba-finance-wacc` | None | N/A | N/A | N/A | Pass | Fail | N/A |

## Interpretation

This is a deterministic BM25 smoke baseline over synthetic notes. It measures retrieval only; it does not evaluate generated answers, claim support, conflict resolution wording, latency, or model cost.

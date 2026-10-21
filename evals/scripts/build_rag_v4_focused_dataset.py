"""Build the v4 focused retrieval benchmark.

v4 is deliberately small: 50 retrieval questions over 63 synthetic daily notes.
It targets semantic and learning-based retrieval rather than exact identifiers:

- 43 answerable cases: 10 MBA, 17 software-development work, 16 SDE interview prep.
- 7 no-context near-miss cases: 2 MBA, 3 software work, 2 interview prep.
- No ITEM-*/DFX-* anchors, so sparse retrieval cannot win on identifier lookup.
- Multi-note synthesis, chronology, concept application, and learning status cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v4.jsonl"
CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v4_corpus.jsonl"

PRIMARY_USER = "eval-user-primary"
SECONDARY_USER = "eval-user-secondary"
DATASET_VERSION = "northstar_rag_v4"


def note(
    note_id: str,
    created_at: str,
    note_type: str,
    raw_text: str,
    user_id: str = PRIMARY_USER,
) -> dict[str, str]:
    return {
        "note_id": note_id,
        "user_id": user_id,
        "created_at": created_at,
        "note_type": note_type,
        "raw_text": raw_text,
    }


def claim(text: str, supporting_note_ids: list[str]) -> dict[str, Any]:
    return {"claim": text, "supporting_note_ids": supporting_note_ids}


def case(
    case_id: str,
    query: str,
    relevant_note_ids: list[str],
    expected_claims: list[dict[str, Any]],
    tags: list[str],
    expected_answer_behavior: str = "answer_with_sources",
) -> dict[str, Any]:
    return {
        "id": case_id,
        "dataset_version": DATASET_VERSION,
        "user_id": PRIMARY_USER,
        "query": query,
        "relevant_note_ids": relevant_note_ids,
        "expected_claims": expected_claims,
        "expected_answer_behavior": expected_answer_behavior,
        "tags": tags,
    }


def build_corpus() -> list[dict[str, str]]:
    return [
        # MBA learning and case notes.
        note(
            "mba-marketing-positioning",
            "2026-09-01T09:10:00Z",
            "learning_note",
            "Positioning note: for the premium study planner, the defensible position is structured accountability for working professionals, not an all-in-one productivity suite. Buyers compare us with planners and coaching, not with Notion.",
        ),
        note(
            "mba-finance-npv",
            "2026-09-02T18:20:00Z",
            "case_note",
            "Corporate finance case: chose Project B because its NPV at an 11% cost of capital was higher, even though its payback period was longer. The decision criterion was value creation, not speed.",
        ),
        note(
            "mba-ops-bottleneck",
            "2026-09-03T20:05:00Z",
            "learning_note",
            "Operations simulation takeaway: the bottleneck moved from intake to verification after adding a second reviewer. Throughput only improved once verification capacity increased.",
        ),
        note(
            "mba-strategy-moat",
            "2026-09-04T08:45:00Z",
            "reading_note",
            "Strategy reading: switching costs, not brand, explain the incumbent's pricing power in the workflow software case. Buyers face migration and retraining costs when they leave.",
        ),
        note(
            "mba-funnel-plan",
            "2026-09-05T09:00:00Z",
            "learning_plan",
            "Plan before the case competition: analyse the activation funnel by acquisition cohort and identify where new users drop off.",
        ),
        note(
            "mba-funnel-done",
            "2026-09-12T17:30:00Z",
            "learning_status",
            "Activation funnel analysis completed. The steepest drop-off is at email verification, and the pattern holds across paid and organic cohorts. I will use that finding in the case competition.",
        ),
        note(
            "mba-finance-wacc",
            "2026-09-06T10:15:00Z",
            "learning_note",
            "WACC study note: cost of equity dominates because the company is 80% equity financed and the debt tax shield is small. Raising debt would lower WACC only while leverage stays below the coverage covenant.",
        ),
        note(
            "mba-ops-centralize",
            "2026-09-07T18:00:00Z",
            "case_note",
            "Initial fulfillment recommendation: centralize distribution in one warehouse to reduce fixed cost.",
        ),
        note(
            "mba-ops-regional",
            "2026-09-14T18:40:00Z",
            "case_note",
            "After reviewing service-level data, the fulfillment recommendation changed to two regional hubs. Centralization would miss the two-day delivery promise for the west coast.",
        ),
        note(
            "mba-pricing-entry",
            "2026-09-08T11:20:00Z",
            "case_note",
            "Entry pricing conclusion: price 15% below the incumbent to overcome switching costs.",
        ),
        note(
            "mba-pricing-econ",
            "2026-09-15T21:10:00Z",
            "case_note",
            "Contribution margin check: the 15% entry discount only works if onboarding cost falls by one third. Without that cost reduction the payback period is too long.",
        ),
        note(
            "mba-churn-case",
            "2026-09-09T13:30:00Z",
            "case_note",
            "Subscription churn case: the best next step is cohort-level churn by acquisition channel before changing pricing. Aggregate churn hides the channel mix shift.",
        ),
        note(
            "mba-leadership",
            "2026-09-10T19:00:00Z",
            "reflection",
            "Leadership reflection: delegating the weekly metrics review worked because I gave a decision rule, not just the task. The team escalated fewer routine questions.",
        ),
        note(
            "mba-acquisition-case",
            "2026-09-11T16:00:00Z",
            "case_note",
            "Fintech acquisition case: compared revenue synergies and integration risk. No valuation conclusion was recorded.",
        ),
        note(
            "mba-ops-simulation",
            "2026-09-13T15:30:00Z",
            "case_note",
            "Operations simulation: ran two reviewer configurations and recorded throughput. No grading details were recorded.",
        ),
        # Software-development work notes.
        note(
            "swe-checkout-retry",
            "2026-09-01T22:10:00Z",
            "incident_note",
            "Checkout incident: the timeout spike came from connection-pool exhaustion after a retry storm, not from the payment provider. Adding jitter and capping retries fixed it.",
        ),
        note(
            "swe-architecture-outbox",
            "2026-09-02T14:25:00Z",
            "architecture_note",
            "Architecture decision: kept the order write path synchronous and moved notifications to an outbox worker. This protects order consistency while still allowing retries.",
        ),
        note(
            "swe-retro-estimates",
            "2026-09-03T17:45:00Z",
            "retro_note",
            "Sprint retro learning: estimate misses came from unplanned review cycles, not implementation. We will size review capacity separately next sprint.",
        ),
        note(
            "swe-search-plan",
            "2026-09-04T09:30:00Z",
            "project_note",
            "Search migration plan: reindex in staging first, verify relevance, then cut over production traffic.",
        ),
        note(
            "swe-search-update",
            "2026-09-11T16:15:00Z",
            "project_update",
            "Search migration update: the staging reindex is done. Production cutover is blocked on relevance review.",
        ),
        note(
            "swe-dashboard-query",
            "2026-09-05T12:00:00Z",
            "performance_note",
            "Dashboard latency: p95 improved after replacing N+1 calls in the summary query with one aggregate query. p50 was unchanged.",
        ),
        note(
            "swe-pricing-rollback",
            "2026-09-06T23:05:00Z",
            "release_note",
            "Release rollback: rolled back the pricing UI because the currency conversion cache served stale rates. No data corruption occurred.",
        ),
        note(
            "swe-api-freeze",
            "2026-09-07T10:40:00Z",
            "project_note",
            "API contract freeze depends on the auth team finalizing token scopes.",
        ),
        note(
            "swe-auth-scopes",
            "2026-09-13T11:15:00Z",
            "dependency_update",
            "The auth team delayed token scope sign-off to next week.",
        ),
        note(
            "swe-billing-alerts",
            "2026-09-08T08:20:00Z",
            "oncall_note",
            "On-call handoff: billing alerts are noisy because the same metric is emitted with duplicate labels.",
        ),
        note(
            "swe-billing-cleanup",
            "2026-09-15T10:05:00Z",
            "followup_note",
            "Duplicate metric labels were removed. Billing alert volume is back to normal.",
        ),
        note(
            "swe-session-old",
            "2026-09-09T14:10:00Z",
            "plan_note",
            "Plan: move session storage to a Redis cluster.",
        ),
        note(
            "swe-session-new",
            "2026-09-16T17:35:00Z",
            "decision_note",
            "After the load test, the session storage plan changed: keep managed Redis and add read replicas. The cluster migration is deferred.",
        ),
        note(
            "swe-security-staging",
            "2026-09-10T09:50:00Z",
            "security_note",
            "Security review: rotated the staging database password and enabled audit logging after the stale credential finding. Production was not affected.",
        ),
        note(
            "swe-oncall-runbook",
            "2026-09-12T20:30:00Z",
            "runbook_note",
            "On-call runbook: page only when the error rate exceeds 2% for five minutes; otherwise create a ticket. This cut false pages.",
        ),
        note(
            "swe-flaky-tests",
            "2026-09-14T15:00:00Z",
            "testing_note",
            "Testing note: replaced flaky end-to-end checkout tests with contract tests plus one smoke path. CI time dropped by 12 minutes.",
        ),
        note(
            "swe-order-backfill",
            "2026-09-17T13:25:00Z",
            "data_repair",
            "Data repair: backfilled missing order timestamps from the payments ledger and corrected 1,240 rows. Root cause was a nullable migration default.",
        ),
        note(
            "swe-modal-focus",
            "2026-09-18T11:40:00Z",
            "accessibility_note",
            "Accessibility fix: keyboard focus was trapped in the modal because the focus sentinel sat outside the dialog. Moving it inside restored tab order.",
        ),
        note(
            "swe-trace-ids",
            "2026-09-19T09:20:00Z",
            "observability_note",
            "Observability decision: added trace IDs to queue messages so worker logs can be joined to API requests. Debug time for async failures dropped.",
        ),
        note(
            "swe-staging-cost",
            "2026-09-20T18:00:00Z",
            "cost_note",
            "Cloud cost review: the largest avoidable spend was idle staging instances overnight. Scheduling shutdown outside work hours saved 28% of staging cost.",
        ),
        note(
            "swe-review-risk",
            "2026-09-21T10:10:00Z",
            "process_note",
            "Code review change: require a short risk note on migrations and auth changes. Review comments shifted from style to failure modes.",
        ),
        note(
            "swe-k8s-ingress",
            "2026-09-22T12:30:00Z",
            "infra_note",
            "Kubernetes notes: ingress retries and pod disruption budgets. No upgrade date was recorded.",
        ),
        note(
            "swe-redis-cluster",
            "2026-09-23T14:45:00Z",
            "infra_note",
            "Redis notes: cluster mode and memory eviction. No resize approval was recorded.",
        ),
        note(
            "swe-mobile-oncall",
            "2026-09-24T08:15:00Z",
            "oncall_note",
            "On-call notes: backend rotation handoff. The mobile rotation was not recorded.",
        ),
        # SDE interview prep notes.
        note(
            "int-sliding-window",
            "2026-09-01T07:30:00Z",
            "dsa_note",
            "Sliding window notes: for longest substring without repeats, move the left pointer to last seen index plus one. Store a character-to-index map.",
        ),
        note(
            "int-knapsack",
            "2026-09-02T07:35:00Z",
            "dsa_note",
            "DP notes: for 0/1 knapsack, iterate capacity backward in the 1D array so each item is used at most once.",
        ),
        note(
            "int-toposort",
            "2026-09-03T07:40:00Z",
            "dsa_note",
            "Graph notes: topological sort with Kahn's algorithm. If the processed node count is less than the total, a cycle exists.",
        ),
        note(
            "int-binary-duplicates",
            "2026-09-04T07:45:00Z",
            "dsa_note",
            "Binary search notes: use the lower-bound template when duplicates exist. Return the first index where the value is greater than or equal to the target.",
        ),
        note(
            "int-heap-build",
            "2026-09-05T07:50:00Z",
            "dsa_note",
            "Complexity note: heap operations are O(log n), but building a heap from n elements is O(n), not O(n log n).",
        ),
        note(
            "int-profile-cache",
            "2026-09-06T08:00:00Z",
            "system_design_note",
            "System design notes: for a read-heavy profile service, use cache-aside with a short TTL and request coalescing. Avoid write-through because profile writes are bursty.",
        ),
        note(
            "int-payment-events",
            "2026-09-07T08:05:00Z",
            "system_design_note",
            "System design notes: use idempotency keys and a dead-letter queue for payment events. Retries alone can duplicate charges.",
        ),
        note(
            "int-chat-shard",
            "2026-09-08T08:10:00Z",
            "system_design_note",
            "System design notes: shard chat messages by conversation ID, not user ID, so a thread read stays on one shard.",
        ),
        note(
            "int-booking-holds",
            "2026-09-09T08:15:00Z",
            "system_design_note",
            "System design notes: for the ticket booking flow, reserve inventory with a conditional write and expire holds after 10 minutes. This avoids overselling without distributed locks.",
        ),
        note(
            "int-star-conflict",
            "2026-09-10T21:00:00Z",
            "behavioral_story",
            "STAR story: conflict with a teammate over API ownership. I set up a written interface contract and a joint review. Delivery stayed on schedule.",
        ),
        note(
            "int-star-deadline",
            "2026-09-11T21:10:00Z",
            "behavioral_story",
            "STAR story: missed a deadline because I underestimated migration testing. I added a rollback rehearsal and a buffer to the next plan.",
        ),
        note(
            "int-star-leadership",
            "2026-09-12T21:20:00Z",
            "behavioral_story",
            "STAR story: led a four-person project. I split ownership by interface and ran short daily risk checks. The team shipped without overtime.",
        ),
        note(
            "int-revision-plan",
            "2026-09-13T07:20:00Z",
            "learning_plan",
            "Need to revise system design rate limiter and consistent hashing.",
        ),
        note(
            "int-revision-done",
            "2026-09-19T19:30:00Z",
            "learning_status",
            "Revision update: completed the rate limiter review. Consistent hashing is still weak and needs another pass.",
        ),
        note(
            "int-fintech-process",
            "2026-09-14T16:40:00Z",
            "interview_process",
            "Interview process note: the fintech company uses one coding screen, a system design round, and a values interview. The recruiter said feedback usually takes a week.",
        ),
        note(
            "int-payments-prep",
            "2026-09-15T17:00:00Z",
            "interview_prep",
            "Company prep: for the payments company, review idempotency, ledger consistency, and PCI boundaries. The recruiter emphasized debugging over trivia.",
        ),
        note(
            "int-mock-feedback",
            "2026-09-16T18:25:00Z",
            "mock_interview",
            "Mock interview feedback: I explained the algorithm before clarifying constraints. Next time, restate constraints and examples first, then discuss complexity.",
        ),
        note(
            "int-google-prep",
            "2026-09-17T18:30:00Z",
            "interview_prep",
            "Google prep: reviewed system design and coding. No interview feedback was recorded.",
        ),
        note(
            "int-house-robber",
            "2026-09-18T18:35:00Z",
            "dsa_note",
            "DP practice: solved House Robber with recursion and memoization.",
        ),
        # Tempting secondary-user notes for isolation checks.
        note(
            "sec-checkout-outage",
            "2026-09-01T22:30:00Z",
            "incident_note",
            "Checkout incident: the payment provider outage caused timeouts. A retry storm was not involved.",
            user_id=SECONDARY_USER,
        ),
        note(
            "sec-pricing-discount",
            "2026-09-08T11:30:00Z",
            "case_note",
            "Entry pricing conclusion: recommend a 25% discount for enterprise buyers.",
            user_id=SECONDARY_USER,
        ),
        note(
            "sec-search-migration",
            "2026-09-11T16:30:00Z",
            "project_update",
            "Search migration completed to production last quarter.",
            user_id=SECONDARY_USER,
        ),
        note(
            "sec-fulfillment-central",
            "2026-09-14T18:50:00Z",
            "case_note",
            "Fulfillment recommendation: centralize in one warehouse.",
            user_id=SECONDARY_USER,
        ),
        note(
            "sec-house-robber",
            "2026-09-18T18:45:00Z",
            "dsa_note",
            "DP practice: solved House Robber with tabulation.",
            user_id=SECONDARY_USER,
        ),
    ]


def build_cases() -> list[dict[str, Any]]:
    return [
        # MBA: 10 answerable cases.
        case(
            "v4-mba-positioning-01",
            "Which customer need did I decide the paid planning tool should own, and what alternatives do buyers weigh?",
            ["mba-marketing-positioning"],
            [
                claim(
                    "The position is structured accountability for working professionals, not an all-in-one productivity suite.",
                    ["mba-marketing-positioning"],
                ),
                claim(
                    "Buyers compare the planner with planners and coaching, not with Notion.",
                    ["mba-marketing-positioning"],
                ),
            ],
            ["v4", "semantic", "learning", "mba"],
        ),
        case(
            "v4-mba-npv-01",
            "Why did the slower-payback option still win the capital budgeting case?",
            ["mba-finance-npv"],
            [
                claim(
                    "Project B had the higher NPV at an 11% cost of capital.",
                    ["mba-finance-npv"],
                ),
                claim(
                    "The decision criterion was value creation rather than speed.",
                    ["mba-finance-npv"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "finance"],
        ),
        case(
            "v4-mba-bottleneck-01",
            "Where did the work pile up once we added another person to the approval stage?",
            ["mba-ops-bottleneck"],
            [
                claim(
                    "The bottleneck moved from intake to verification after adding a second reviewer.",
                    ["mba-ops-bottleneck"],
                ),
                claim(
                    "Throughput only improved once verification capacity increased.",
                    ["mba-ops-bottleneck"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "operations"],
        ),
        case(
            "v4-mba-moat-01",
            "Why could the established vendor keep charging more in that enterprise software example?",
            ["mba-strategy-moat"],
            [
                claim(
                    "Switching costs, not brand, explained the incumbent's pricing power.",
                    ["mba-strategy-moat"],
                ),
                claim(
                    "Buyers face migration and retraining costs when they leave.",
                    ["mba-strategy-moat"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "strategy"],
        ),
        case(
            "v4-mba-funnel-status-01",
            "Did the cohort drop-off review get finished, and where do new accounts stall?",
            ["mba-funnel-plan", "mba-funnel-done"],
            [
                claim(
                    "The plan was to analyse the activation funnel by acquisition cohort.",
                    ["mba-funnel-plan"],
                ),
                claim(
                    "The analysis was completed and found the steepest drop-off at email verification.",
                    ["mba-funnel-done"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "status", "synthesis"],
        ),
        case(
            "v4-mba-wacc-01",
            "Why is the company's financing mix so sensitive to the cost of equity?",
            ["mba-finance-wacc"],
            [
                claim(
                    "Cost of equity dominates because the company is 80% equity financed.",
                    ["mba-finance-wacc"],
                ),
                claim(
                    "Raising debt would lower WACC only while leverage stays below the coverage covenant.",
                    ["mba-finance-wacc"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "finance"],
        ),
        case(
            "v4-mba-fulfillment-change-01",
            "What is my latest distribution setup recommendation, and what data overturned the first one?",
            ["mba-ops-centralize", "mba-ops-regional"],
            [
                claim(
                    "The initial recommendation was to centralize distribution in one warehouse.",
                    ["mba-ops-centralize"],
                ),
                claim(
                    "The recommendation changed to two regional hubs because centralization would miss the two-day west-coast delivery promise.",
                    ["mba-ops-regional"],
                ),
            ],
            ["v4", "semantic", "mba", "operations", "chronology", "synthesis"],
        ),
        case(
            "v4-mba-pricing-synthesis-01",
            "What did I conclude about entering 15% cheaper, and what has to be true for that to work?",
            ["mba-pricing-entry", "mba-pricing-econ"],
            [
                claim(
                    "The entry price should be 15% below the incumbent to overcome switching costs.",
                    ["mba-pricing-entry"],
                ),
                claim(
                    "The discount only works if onboarding cost falls by one third.",
                    ["mba-pricing-econ"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "pricing", "synthesis"],
        ),
        case(
            "v4-mba-churn-nextstep-01",
            "What did I decide to look at first in the subscriber retention case?",
            ["mba-churn-case"],
            [
                claim(
                    "The next step is cohort-level churn by acquisition channel.",
                    ["mba-churn-case"],
                ),
                claim(
                    "Aggregate churn hides the channel mix shift.",
                    ["mba-churn-case"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "marketing"],
        ),
        case(
            "v4-mba-delegation-01",
            "What made handing off the weekly numbers meeting succeed?",
            ["mba-leadership"],
            [
                claim(
                    "Delegation worked because I gave a decision rule, not just the task.",
                    ["mba-leadership"],
                ),
                claim(
                    "The team escalated fewer routine questions.",
                    ["mba-leadership"],
                ),
            ],
            ["v4", "semantic", "learning", "mba", "leadership"],
        ),
        # Software-development work: 17 answerable cases.
        case(
            "v4-swe-checkout-rootcause-01",
            "What was really behind the order submission slowdown?",
            ["swe-checkout-retry"],
            [
                claim(
                    "The timeout spike came from connection-pool exhaustion after a retry storm, not from the payment provider.",
                    ["swe-checkout-retry"],
                ),
                claim(
                    "Adding jitter and capping retries fixed the issue.",
                    ["swe-checkout-retry"],
                ),
            ],
            ["v4", "semantic", "work", "software", "incident"],
        ),
        case(
            "v4-swe-sync-writes-01",
            "Why did we leave the purchase write path blocking instead of making it async?",
            ["swe-architecture-outbox"],
            [
                claim(
                    "Keeping order writes synchronous protects order consistency.",
                    ["swe-architecture-outbox"],
                ),
                claim(
                    "Notifications were moved to an outbox worker so retries could still happen.",
                    ["swe-architecture-outbox"],
                ),
            ],
            ["v4", "semantic", "work", "software", "architecture"],
        ),
        case(
            "v4-swe-retro-misses-01",
            "What did the team blame for missing its sprint commitments?",
            ["swe-retro-estimates"],
            [
                claim(
                    "Estimate misses came from unplanned review cycles, not implementation.",
                    ["swe-retro-estimates"],
                ),
                claim(
                    "The team will size review capacity separately next sprint.",
                    ["swe-retro-estimates"],
                ),
            ],
            ["v4", "semantic", "work", "software", "learning", "retro"],
        ),
        case(
            "v4-swe-search-status-01",
            "Where are we with the new retrieval rollout?",
            ["swe-search-plan", "swe-search-update"],
            [
                claim(
                    "The plan was to reindex in staging before cutting over production.",
                    ["swe-search-plan"],
                ),
                claim(
                    "The staging reindex is done, but production cutover is blocked on relevance review.",
                    ["swe-search-update"],
                ),
            ],
            ["v4", "semantic", "work", "software", "status", "synthesis"],
        ),
        case(
            "v4-swe-dashboard-p95-01",
            "Why did the slowest dashboard loads get faster?",
            ["swe-dashboard-query"],
            [
                claim(
                    "The summary query replaced N+1 calls with one aggregate query.",
                    ["swe-dashboard-query"],
                ),
                claim(
                    "p95 improved while p50 was unchanged.",
                    ["swe-dashboard-query"],
                ),
            ],
            ["v4", "semantic", "work", "software", "performance"],
        ),
        case(
            "v4-swe-pricing-rollback-01",
            "Why did we undo the checkout price display change?",
            ["swe-pricing-rollback"],
            [
                claim(
                    "The currency conversion cache served stale rates.",
                    ["swe-pricing-rollback"],
                ),
                claim(
                    "No data corruption occurred.",
                    ["swe-pricing-rollback"],
                ),
            ],
            ["v4", "semantic", "work", "software", "release"],
        ),
        case(
            "v4-swe-api-blocker-01",
            "What is holding up the interface agreement?",
            ["swe-api-freeze", "swe-auth-scopes"],
            [
                claim(
                    "The API contract freeze depends on the auth team finalizing token scopes.",
                    ["swe-api-freeze"],
                ),
                claim(
                    "Token scope sign-off was delayed to next week.",
                    ["swe-auth-scopes"],
                ),
            ],
            ["v4", "semantic", "work", "software", "dependency", "synthesis"],
        ),
        case(
            "v4-swe-billing-alerts-01",
            "What caused the duplicate pages from monitoring, and how was it fixed?",
            ["swe-billing-alerts", "swe-billing-cleanup"],
            [
                claim(
                    "The alerts were noisy because the same metric was emitted with duplicate labels.",
                    ["swe-billing-alerts"],
                ),
                claim(
                    "Removing the duplicate labels brought alert volume back to normal.",
                    ["swe-billing-cleanup"],
                ),
            ],
            ["v4", "semantic", "work", "software", "oncall", "synthesis"],
        ),
        case(
            "v4-swe-session-storage-01",
            "What are we doing now for login state, and why did the original idea get dropped?",
            ["swe-session-old", "swe-session-new"],
            [
                claim(
                    "The original plan was to move session storage to a Redis cluster.",
                    ["swe-session-old"],
                ),
                claim(
                    "The current plan keeps managed Redis and adds read replicas, deferring the cluster migration.",
                    ["swe-session-new"],
                ),
            ],
            ["v4", "semantic", "work", "software", "chronology", "synthesis"],
        ),
        case(
            "v4-swe-staging-security-01",
            "What did the audit finding change in the test environment?",
            ["swe-security-staging"],
            [
                claim(
                    "The staging database password was rotated.",
                    ["swe-security-staging"],
                ),
                claim(
                    "Audit logging was enabled after the stale credential finding.",
                    ["swe-security-staging"],
                ),
            ],
            ["v4", "semantic", "work", "software", "security"],
        ),
        case(
            "v4-swe-oncall-page-01",
            "When should someone be woken up under the new incident policy?",
            ["swe-oncall-runbook"],
            [
                claim(
                    "Page only when the error rate exceeds 2% for five minutes.",
                    ["swe-oncall-runbook"],
                ),
                claim(
                    "Otherwise create a ticket.",
                    ["swe-oncall-runbook"],
                ),
            ],
            ["v4", "semantic", "work", "software", "oncall"],
        ),
        case(
            "v4-swe-ci-time-01",
            "Why did the build pipeline get 12 minutes shorter?",
            ["swe-flaky-tests"],
            [
                claim(
                    "Flaky end-to-end checkout tests were replaced with contract tests plus one smoke path.",
                    ["swe-flaky-tests"],
                ),
                claim(
                    "CI time dropped by 12 minutes.",
                    ["swe-flaky-tests"],
                ),
            ],
            ["v4", "semantic", "work", "software", "testing"],
        ),
        case(
            "v4-swe-order-backfill-01",
            "How big was the timestamp repair, and what caused the missing values?",
            ["swe-order-backfill"],
            [
                claim(
                    "1,240 rows were corrected.",
                    ["swe-order-backfill"],
                ),
                claim(
                    "The root cause was a nullable migration default.",
                    ["swe-order-backfill"],
                ),
            ],
            ["v4", "semantic", "work", "software", "data-repair"],
        ),
        case(
            "v4-swe-modal-focus-01",
            "Why couldn't people tab through the dialog properly, and what fixed it?",
            ["swe-modal-focus"],
            [
                claim(
                    "The focus sentinel sat outside the dialog.",
                    ["swe-modal-focus"],
                ),
                claim(
                    "Moving the sentinel inside the dialog restored tab order.",
                    ["swe-modal-focus"],
                ),
            ],
            ["v4", "semantic", "work", "software", "accessibility"],
        ),
        case(
            "v4-swe-trace-debug-01",
            "How did we connect worker logs to the originating request?",
            ["swe-trace-ids"],
            [
                claim(
                    "Trace IDs were added to queue messages.",
                    ["swe-trace-ids"],
                ),
                claim(
                    "This let worker logs be joined to API requests and reduced debug time.",
                    ["swe-trace-ids"],
                ),
            ],
            ["v4", "semantic", "work", "software", "observability"],
        ),
        case(
            "v4-swe-cloud-cost-01",
            "Where did we find the largest easy savings in our cloud bill?",
            ["swe-staging-cost"],
            [
                claim(
                    "Idle staging instances overnight were the largest avoidable spend.",
                    ["swe-staging-cost"],
                ),
                claim(
                    "Scheduling shutdown outside work hours saved 28% of staging cost.",
                    ["swe-staging-cost"],
                ),
            ],
            ["v4", "semantic", "work", "software", "cost"],
        ),
        case(
            "v4-swe-review-risk-01",
            "What new step did we add before approving database or permission changes?",
            ["swe-review-risk"],
            [
                claim(
                    "Migrations and auth changes now require a short risk note.",
                    ["swe-review-risk"],
                ),
                claim(
                    "Review comments shifted from style to failure modes.",
                    ["swe-review-risk"],
                ),
            ],
            ["v4", "semantic", "work", "software", "process"],
        ),
        # SDE interview prep: 16 answerable cases.
        case(
            "v4-int-sliding-pointer-01",
            "How do I move the start of the window when a character repeats?",
            ["int-sliding-window"],
            [
                claim(
                    "Move the left pointer to last seen index plus one.",
                    ["int-sliding-window"],
                ),
                claim(
                    "Store a character-to-index map.",
                    ["int-sliding-window"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "dsa"],
        ),
        case(
            "v4-int-knapsack-order-01",
            "Why does the one-array DP loop run from the top down?",
            ["int-knapsack"],
            [
                claim(
                    "Iterating capacity backward ensures each item is used at most once.",
                    ["int-knapsack"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "dsa"],
        ),
        case(
            "v4-int-toposort-cycle-01",
            "How can Kahn's method tell me that a directed graph is cyclic?",
            ["int-toposort"],
            [
                claim(
                    "Use Kahn's algorithm and compare the processed node count with the total.",
                    ["int-toposort"],
                ),
                claim(
                    "A lower processed count means a cycle exists.",
                    ["int-toposort"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "dsa"],
        ),
        case(
            "v4-int-binary-duplicates-01",
            "Which search variant finds the first matching slot when the array has repeated values?",
            ["int-binary-duplicates"],
            [
                claim(
                    "Use the lower-bound template for duplicates.",
                    ["int-binary-duplicates"],
                ),
                claim(
                    "Return the first index where the value is greater than or equal to the target.",
                    ["int-binary-duplicates"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "dsa"],
        ),
        case(
            "v4-int-heap-build-01",
            "What is the time complexity of turning an unsorted array into a priority queue?",
            ["int-heap-build"],
            [
                claim(
                    "Building a heap from n elements is O(n).",
                    ["int-heap-build"],
                ),
                claim(
                    "Individual heap operations remain O(log n).",
                    ["int-heap-build"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "dsa"],
        ),
        case(
            "v4-int-profile-cache-01",
            "What caching approach did I pick for the user profile service, and why not write to cache on updates?",
            ["int-profile-cache"],
            [
                claim(
                    "Use cache-aside with a short TTL and request coalescing.",
                    ["int-profile-cache"],
                ),
                claim(
                    "Write-through was avoided because profile writes are bursty.",
                    ["int-profile-cache"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "system-design"],
        ),
        case(
            "v4-int-payment-retry-01",
            "How do I keep repeated charge attempts from creating duplicate payments?",
            ["int-payment-events"],
            [
                claim(
                    "Use idempotency keys and a dead-letter queue.",
                    ["int-payment-events"],
                ),
                claim(
                    "Retries alone can duplicate charges.",
                    ["int-payment-events"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "system-design"],
        ),
        case(
            "v4-int-chat-shard-01",
            "What key did I choose to split message threads across machines?",
            ["int-chat-shard"],
            [
                claim(
                    "Shard by conversation ID, not user ID.",
                    ["int-chat-shard"],
                ),
                claim(
                    "This keeps a thread read on one shard.",
                    ["int-chat-shard"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "system-design"],
        ),
        case(
            "v4-int-booking-holds-01",
            "How do I stop two people from taking the same seat without a distributed lock?",
            ["int-booking-holds"],
            [
                claim(
                    "Reserve inventory with a conditional write.",
                    ["int-booking-holds"],
                ),
                claim(
                    "Expire holds after 10 minutes to avoid overselling.",
                    ["int-booking-holds"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "system-design"],
        ),
        case(
            "v4-int-conflict-story-01",
            "What did the ownership dispute teach me about working with another engineer?",
            ["int-star-conflict"],
            [
                claim(
                    "A written interface contract and joint review resolved the ownership conflict.",
                    ["int-star-conflict"],
                ),
                claim(
                    "Delivery stayed on schedule.",
                    ["int-star-conflict"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "behavioral"],
        ),
        case(
            "v4-int-deadline-story-01",
            "What did I change after missing the migration date?",
            ["int-star-deadline"],
            [
                claim(
                    "The miss came from underestimating migration testing.",
                    ["int-star-deadline"],
                ),
                claim(
                    "The next plan added a rollback rehearsal and a buffer.",
                    ["int-star-deadline"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "behavioral"],
        ),
        case(
            "v4-int-leadership-story-01",
            "How did I divide work on the four-person effort so nobody had to work late?",
            ["int-star-leadership"],
            [
                claim(
                    "Ownership was split by interface.",
                    ["int-star-leadership"],
                ),
                claim(
                    "Short daily risk checks helped the team ship without overtime.",
                    ["int-star-leadership"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "behavioral"],
        ),
        case(
            "v4-int-revision-status-01",
            "Which interview topics are still shaky after my last review?",
            ["int-revision-plan", "int-revision-done"],
            [
                claim(
                    "Both topics were planned for revision.",
                    ["int-revision-plan"],
                ),
                claim(
                    "The rate limiter review is complete, but consistent hashing is still weak.",
                    ["int-revision-done"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "status", "synthesis"],
        ),
        case(
            "v4-int-fintech-process-01",
            "What are the stages and expected wait time for the fintech role?",
            ["int-fintech-process"],
            [
                claim(
                    "The process has one coding screen, a system design round, and a values interview.",
                    ["int-fintech-process"],
                ),
                claim(
                    "Feedback usually takes a week.",
                    ["int-fintech-process"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "process"],
        ),
        case(
            "v4-int-payments-focus-01",
            "What should I study before talking to the payments company?",
            ["int-payments-prep"],
            [
                claim(
                    "Review idempotency, ledger consistency, and PCI boundaries.",
                    ["int-payments-prep"],
                ),
                claim(
                    "The recruiter emphasized debugging over trivia.",
                    ["int-payments-prep"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "prep"],
        ),
        case(
            "v4-int-mock-feedback-01",
            "What did the practice interview reveal about how I should open a solution?",
            ["int-mock-feedback"],
            [
                claim(
                    "Restate constraints and examples before explaining the algorithm.",
                    ["int-mock-feedback"],
                ),
                claim(
                    "Then discuss complexity.",
                    ["int-mock-feedback"],
                ),
            ],
            ["v4", "semantic", "learning", "interview", "feedback"],
        ),
        # No-context near misses: 7 cases.
        case(
            "v4-nc-mba-acquisition-01",
            "What valuation did I settle on for the fintech acquisition case?",
            [],
            [],
            ["v4", "no-context", "near-miss", "mba"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
        case(
            "v4-nc-mba-simulation-01",
            "Which professor graded the operations simulation?",
            [],
            [],
            ["v4", "no-context", "near-miss", "mba"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
        case(
            "v4-nc-swe-k8s-upgrade-01",
            "What was the final Kubernetes upgrade date?",
            [],
            [],
            ["v4", "no-context", "near-miss", "software"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
        case(
            "v4-nc-swe-redis-resize-01",
            "Who approved the Redis cluster resize?",
            [],
            [],
            ["v4", "no-context", "near-miss", "software"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
        case(
            "v4-nc-swe-mobile-oncall-01",
            "What is the current on-call rotation for the mobile team?",
            [],
            [],
            ["v4", "no-context", "near-miss", "software"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
        case(
            "v4-nc-int-google-feedback-01",
            "What was the interviewer's feedback after the Google system design round?",
            [],
            [],
            ["v4", "no-context", "near-miss", "interview"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
        case(
            "v4-nc-int-fintech-offers-01",
            "How many offers did the fintech company extend?",
            [],
            [],
            ["v4", "no-context", "near-miss", "interview"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    corpus = build_corpus()
    cases = build_cases()
    write_jsonl(CORPUS_PATH, corpus)
    write_jsonl(CASES_PATH, cases)
    print(f"Wrote {len(cases)} cases to {CASES_PATH}")
    print(f"Wrote {len(corpus)} notes to {CORPUS_PATH}")


if __name__ == "__main__":
    main()

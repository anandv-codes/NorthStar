"""Build the v3 semantic-bias dataset.

v3 targets the structural gap identified in evals/analysis/v1_analysis.md: most
v1/v2 cases carry a unique lexical anchor (an exact ITEM-*/DFX-* id) that BM25
solves trivially, which drowns out any advantage hybrid/dense retrieval offers.

v3 = 70 newly authored cases with weak-to-no lexical overlap between query and
evidence, plus the 158 viable non-ID-anchored cases reused from v2 (the 31
exact/item-id-tagged cases, 6 legacy `seed` prototype cases, and 5 broken
`isolation-synthesis-*` cases with dangling note references are excluded).
The full v2 corpus is carried over unmodified so existing v2 distractors still
apply, and 95 new notes are added to support the 65 brand-new cases (the 5
cross-account synthesis cases reuse existing v2 corpus notes).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v3.jsonl"
CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v3_corpus.jsonl"
SOURCE_V2_CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v2.jsonl"
SOURCE_V2_CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v2_corpus.jsonl"

PRIMARY_USER = "eval-user-primary"
EXCLUDED_TAGS = {"exact", "item-id", "seed"}
# These 5 v2 cases point at note ids that don't exist in the v2 corpus (a pre-existing
# data bug) and are secretly ITEM-8101-anchored despite lacking exact/item-id tags, so
# they are excluded rather than reused broken. See CROSS_USER_SEMANTIC_SYNTHESIS below
# for the corrected replacement cases built on the real corpus notes.
EXCLUDED_CASE_IDS = {
    "isolation-synthesis-01",
    "isolation-synthesis-02",
    "isolation-synthesis-03",
    "isolation-synthesis-04",
    "isolation-synthesis-05",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def note(note_id: str, created_at: str, note_type: str, raw_text: str, user_id: str = PRIMARY_USER) -> dict[str, str]:
    return {
        "note_id": note_id,
        "user_id": user_id,
        "created_at": created_at,
        "note_type": note_type,
        "raw_text": raw_text,
    }


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
        "dataset_version": "northstar_rag_v3",
        "user_id": PRIMARY_USER,
        "query": query,
        "relevant_note_ids": relevant_note_ids,
        "expected_claims": expected_claims,
        "expected_answer_behavior": expected_answer_behavior,
        "tags": tags,
    }


def claim(text: str, supporting_note_ids: list[str]) -> dict[str, Any]:
    return {"claim": text, "supporting_note_ids": supporting_note_ids}


def load_reused_v2_subset() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reuse the 158 v2 cases that are not exact-ID-anchored, legacy seed duplicates,
    or broken (see EXCLUDED_CASE_IDS)."""
    v2_cases = load_jsonl(SOURCE_V2_CASES_PATH)
    v2_corpus = load_jsonl(SOURCE_V2_CORPUS_PATH)

    reused_cases: list[dict[str, Any]] = []
    for item in v2_cases:
        tags = set(item.get("tags", []))
        if tags & EXCLUDED_TAGS or item["id"] in EXCLUDED_CASE_IDS:
            continue
        reused = dict(item)
        reused["id"] = f"v2-{item['id']}"
        reused["dataset_version"] = "northstar_rag_v3"
        reused_cases.append(reused)

    return reused_cases, v2_corpus


# 20 true-paraphrase cases: query and note deliberately share almost no vocabulary.
TRUE_PARAPHRASE = [
    ("billing-etl", "The nightly ETL pipeline that reconciles the billing ledger against the payments gateway completed without any manual intervention this week.",
     "Did anyone have to step in and fix the overnight billing sync job?",
     "The nightly billing ETL pipeline finished on its own without manual intervention."),
    ("checkout-postmortem", "Priya finished writing the incident postmortem for the checkout outage and circulated it to the team on Thursday.",
     "Has the write-up explaining what caused the checkout downtime gone out yet?",
     "Priya completed and shared the checkout outage postmortem on Thursday."),
    ("onboarding-laptop", "The onboarding guide for new hires now includes a section about requesting laptop replacements.",
     "Can new employees find instructions for getting a new laptop somewhere?",
     "The onboarding guide now covers how to request a laptop replacement."),
    ("feedback-board", "Marco moved the customer feedback board from Trello to Linear last week.",
     "Where do we track what customers are saying about the product these days?",
     "Customer feedback tracking moved from Trello to Linear."),
    ("hiring-freeze", "The quarterly budget review pushed the hiring freeze decision to next month.",
     "Are we still allowed to bring on new people right now?",
     "A hiring freeze decision was postponed to next month, so headcount plans remain paused."),
    ("staging-creds", "Jordan swapped the staging database credentials after the audit flagged a stale rotation policy.",
     "Did someone update the passwords for the test environment recently?",
     "Jordan rotated the staging database credentials following an audit finding."),
    ("refund-macros", "The support macro library was reorganized so agents can find refund templates faster.",
     "Is it easier now for the help desk folks to locate the money-back reply templates?",
     "The support macro library was reorganized to make refund templates easier to find."),
    ("dashboard-sunset", "Elena's team decided to sunset the legacy reporting dashboard by the end of the quarter.",
     "Is the old analytics dashboard going away soon?",
     "The legacy reporting dashboard is being sunset by end of quarter."),
    ("travel-form", "A new travel reimbursement form was rolled out that no longer requires manager countersignature.",
     "Do I still need my manager to sign off before I get reimbursed for a work trip?",
     "The new travel reimbursement form no longer requires manager countersignature."),
    ("checkout-latency", "Samir found that the checkout latency spike traced back to a missing database index on the orders table.",
     "What turned out to be causing checkout to slow down?",
     "The checkout latency spike was caused by a missing database index on the orders table."),
    ("oncall-exempt", "The weekend on-call rotation now excludes anyone who worked the previous holiday shift.",
     "Who is exempt from being on call this weekend?",
     "Anyone who worked the previous holiday shift is excluded from the weekend on-call rotation."),
    ("async-standup", "Tessa's proposal to move stand-up to async written updates was accepted by the team.",
     "Are we doing daily meetings out loud still, or writing them up instead?",
     "The team adopted async written updates instead of a spoken daily stand-up."),
    ("vendor-renewal", "Noah confirmed the vendor contract renewal terms stayed flat for another year.",
     "Did our supplier agreement pricing change this year?",
     "The vendor contract renewal kept the same pricing terms for another year."),
    ("color-tokens", "The design system's color tokens were renamed to match the new brand palette.",
     "Did the naming for our UI colors change with the rebrand?",
     "Color tokens in the design system were renamed to match the new brand palette."),
    ("crash-sdk", "Mina discovered that the mobile app crash cluster was tied to a third-party analytics SDK update.",
     "What's behind the recent wave of app crashes on phones?",
     "The mobile app crash cluster was traced to a third-party analytics SDK update."),
    ("interview-loop", "The recruiting team shortened the interview loop from five rounds to three.",
     "Is the hiring process quicker for candidates now?",
     "The interview loop was shortened from five rounds to three."),
    ("wiki-migration", "Priya's team migrated the internal wiki from Confluence to Notion over the weekend.",
     "Where does internal documentation live now?",
     "The internal wiki was migrated from Confluence to Notion."),
    ("webhook-retry", "The payments team added a retry with exponential backoff for failed webhook deliveries.",
     "How do failed webhook calls get handled now?",
     "Failed webhook deliveries are retried using exponential backoff."),
    ("refund-double-count", "Marco's investigation showed the weekly report was double-counting refunded orders.",
     "Was there a bug that inflated the numbers in the weekly report?",
     "The weekly report was double-counting refunded orders."),
    ("printer-move", "The office relocated the printer closer to the kitchen after repeated complaints.",
     "Did they finally move the printer somewhere more convenient?",
     "The printer was relocated closer to the kitchen after complaints."),
]

# 15 vocabulary-mismatch cases: colloquial question phrasing vs jargon-heavy note text.
VOCABULARY_MISMATCH = [
    ("idempotency", "The idempotency key middleware now rejects duplicate POST /orders requests within a 30-second window to prevent double charges.",
     "If I accidentally click submit twice on an order really fast, am I gonna get charged twice?",
     "Duplicate order submissions within 30 seconds are rejected to prevent double charges."),
    ("circuit-breaker", "The circuit breaker on the recommendation service trips after five consecutive timeouts and falls back to a cached response.",
     "What happens if the 'you might also like' thing on the site just stops responding?",
     "The recommendation service falls back to a cached response after repeated timeouts."),
    ("autoscaling", "Horizontal pod autoscaling for the ingestion service now targets 65% CPU utilization instead of 80%.",
     "Did they make the servers add more copies of themselves sooner when things get busy?",
     "Autoscaling for the ingestion service now triggers at 65% CPU instead of 80%."),
    ("canary-rollout", "The feature flag rollout uses a canary cohort of 2% of traffic before promoting to general availability.",
     "Do they test new stuff on just a few users first before everyone gets it?",
     "New features are tested on a 2% canary cohort before general rollout."),
    ("vacuum-job", "The nightly cron job vacuums dead tuples from the notes table to reclaim disk space.",
     "Is there some overnight cleanup that frees up storage space in the database?",
     "A nightly job vacuums dead tuples from the notes table to reclaim disk space."),
    ("rate-limit", "Rate limiting on the public API was changed to a token bucket algorithm with burst capacity of 50 requests.",
     "Can I still send a bunch of requests all at once to the API without getting blocked?",
     "The API now uses a token bucket rate limiter allowing bursts of 50 requests."),
    ("wal-archiving", "The team enabled write-ahead log archiving to support point-in-time recovery.",
     "If the database gets messed up, can we roll it back to some earlier moment?",
     "Write-ahead log archiving was enabled to support point-in-time recovery."),
    ("tls-termination", "TLS termination was moved from the application layer to the load balancer.",
     "Where does the encryption get unwrapped now, at the app or somewhere in front of it?",
     "TLS termination now happens at the load balancer instead of the application."),
    ("activation-funnel", "The onboarding cohort's activation funnel showed a steep drop-off at the email verification step.",
     "Where are new users bailing out the most when they first sign up?",
     "New users drop off most at the email verification step."),
    ("blue-green", "The team adopted blue-green deployment to eliminate downtime during releases.",
     "How come releases don't cause the site to go down anymore?",
     "Blue-green deployment was adopted to eliminate release downtime."),
    ("read-model", "A denormalized read model was introduced to avoid the N+1 query problem on the dashboard.",
     "Why did the dashboard stop making so many slow repeated database calls?",
     "A denormalized read model was introduced to avoid the N+1 query problem."),
    ("sla-threshold", "The support queue's SLA breach threshold was tightened from four hours to two.",
     "How fast does support have to respond before it counts as late now?",
     "The support SLA breach threshold was tightened from four hours to two."),
    ("dlq-alert", "Dead letter queue depth alerts now page on-call after 100 unprocessed messages instead of 500.",
     "At what point does someone get woken up if messages are piling up unprocessed?",
     "On-call now pages after 100 unprocessed messages instead of 500."),
    ("pessimistic-ui", "The mobile team switched from optimistic UI updates to a pessimistic pattern for the checkout button.",
     "Does the checkout button wait for confirmation now before showing success?",
     "Checkout button updates switched from optimistic to pessimistic, waiting for confirmation."),
    ("schema-migration", "Schema migrations now run through a backward-compatible expand-and-contract pattern.",
     "How do they change the database structure without breaking things that are still running?",
     "Schema migrations use an expand-and-contract pattern to stay backward compatible."),
]

# 15 lexical near-miss traps: a high-overlap distractor outranks the low-overlap correct note under BM25.
LEXICAL_NEAR_MISS = [
    ("atlas-migration", "What's the current status of the Atlas migration?",
     "Atlas migration planning kickoff notes: brainstormed possible migration approaches for Atlas, no decisions made yet, purely exploratory.",
     "The move of the Atlas workstream to the new cluster finished last night; all traffic has been cut over.",
     "The Atlas migration to the new cluster is complete; traffic has been cut over."),
    ("payment-retry", "Is the payment retry logic still flaky?",
     "Payment retry logic design doc: describes retry logic options for payments, still in draft, flaky sections need retry review.",
     "The transient failure handling for charges was stabilized after the exponential backoff fix landed Tuesday.",
     "Payment retry handling was stabilized after a backoff fix landed Tuesday."),
    ("search-relevance", "Did the search relevance experiment work?",
     "Search relevance experiment brainstorm: listed several relevance experiment ideas for search, none run yet.",
     "The ranking test that swapped in the new scoring model showed a measurable click-through lift.",
     "The new scoring model test showed a measurable click-through lift."),
    ("onboarding-flow", "Is the onboarding flow finished?",
     "Onboarding flow backlog: collected onboarding flow feedback and flow diagrams, still just notes.",
     "The new-user welcome sequence shipped to all sign-ups this morning.",
     "The new-user welcome sequence has shipped to all sign-ups."),
    ("checkout-redesign", "What happened with the checkout redesign?",
     "Checkout redesign inspiration board: saved checkout redesign references and redesign mood boards.",
     "The updated purchase flow went live to 100% of shoppers after the A/B test won.",
     "The updated purchase flow is live to all shoppers after winning its A/B test."),
    ("data-pipeline", "Is the data pipeline reliable now?",
     "Data pipeline reliability wishlist: ideas to make the pipeline more reliable, unprioritized.",
     "The ETL job hasn't failed once since the retry queue was added two weeks ago.",
     "The ETL job has run without failure since the retry queue was added two weeks ago."),
    ("notification-bug", "What's the deal with the notification bug?",
     "Notification bug backlog grooming: triaged several notification bug tickets, no fixes yet.",
     "Duplicate push alerts stopped after the dedup key fix deployed Friday.",
     "Duplicate push notifications stopped after the dedup key fix deployed Friday."),
    ("login-redesign", "Any update on the login redesign?",
     "Login redesign concepts: sketched a few login redesign concepts for feedback.",
     "The revamped sign-in screen is now the default experience for every user.",
     "The revamped sign-in screen is now the default for every user."),
    ("billing-reconciliation", "Is the billing reconciliation fixed?",
     "Billing reconciliation notes: general reconciliation notes for billing, still exploratory.",
     "The mismatch between invoices and ledger entries was resolved after correcting the currency rounding rule.",
     "The invoice-to-ledger mismatch was resolved by fixing the currency rounding rule."),
    ("api-rate-limit", "What's happening with the API rate limit rollout?",
     "API rate limit rollout planning: discussed rate limit rollout timing options for the API.",
     "Throttling for external callers is already active in production as of Monday.",
     "Throttling for external callers is active in production as of Monday."),
    ("caching-layer", "Did the caching layer get deployed?",
     "Caching layer research: compared caching layer vendors, deployment plan not finalized.",
     "Read latency dropped sharply after the new response cache went live last week.",
     "The new response cache went live last week and reduced read latency."),
    ("fraud-model", "Is the fraud detection model live?",
     "Fraud detection model roadmap: outlined future fraud detection model milestones.",
     "The new risk-scoring classifier started blocking suspicious signups yesterday.",
     "The new risk-scoring classifier started blocking suspicious signups yesterday."),
    ("search-index", "What's the status of the search index rebuild?",
     "Search index rebuild notes: jotted down search index rebuild considerations, nothing scheduled.",
     "Reindexing finished overnight and query results now reflect the latest catalog.",
     "Reindexing finished overnight, so query results reflect the latest catalog."),
    ("mobile-crash-fix", "Did the mobile crash fix ship?",
     "Mobile crash fix backlog: listed candidate mobile crash fix approaches for triage.",
     "The patch for the startup freeze went out in yesterday's app store release.",
     "The startup freeze patch shipped in yesterday's app store release."),
    ("invoice-export", "Is the invoice export tool working again?",
     "Invoice export tool complaints: gathered invoice export tool complaints from support.",
     "Downloads of billing statements succeeded for every customer in this morning's batch.",
     "Billing statement downloads succeeded for every customer this morning."),
]

# 15 multi-note synthesis cases: two notes with no shared identifier must be combined.
MULTI_NOTE_SYNTHESIS = [
    ("relay-legal", "Priya mentioned in standup that the Relay workstream is waiting on legal sign-off.",
     "Legal approved the Relay data-sharing agreement this morning.",
     "Is Relay still blocked on legal?",
     "Relay was waiting on legal, but legal approved the agreement this morning, so it is no longer blocked."),
    ("harbor-cache", "The Harbor project needs the new caching layer before it can launch.",
     "The caching layer finished rollout to all regions yesterday.",
     "Can Harbor launch now?",
     "Harbor was waiting on the caching layer, which finished rolling out yesterday, so Harbor can launch."),
    ("search-revert", "Support tickets about slow search spiked after last week's index change.",
     "The index change was reverted this morning.",
     "Should search feel faster again soon?",
     "Slow search complaints followed an index change that was reverted this morning, so performance should recover."),
    ("marco-approver", "Marco is out until next Wednesday.",
     "Marco is the only approver for vendor invoices over $5,000.",
     "Can a large vendor invoice get approved this week?",
     "Large vendor invoices need Marco's approval, and Marco is out until next Wednesday, so approval will be delayed."),
    ("beacon-permissions", "The Beacon rollout depends on the new permissions service.",
     "The permissions service hit a critical bug during load testing yesterday.",
     "Is Beacon still on track?",
     "Beacon depends on the permissions service, which hit a critical bug yesterday, putting the rollout at risk."),
    ("audit-compliance", "Elena's team finished the audit logging feature last Friday.",
     "Compliance review requires audit logging to be complete before certification can proceed.",
     "Can the compliance certification move forward?",
     "Compliance certification needed audit logging, which finished last Friday, so certification can proceed."),
    ("mobile-release", "The mobile release train slipped a week because of the crash cluster.",
     "The crash cluster was root-caused and fixed yesterday.",
     "Will the mobile release go out on the new date?",
     "The release slipped due to a crash cluster that was fixed yesterday, so the new date should hold."),
    ("migration-rehearsal", "Samir is waiting on a database snapshot before running the migration rehearsal.",
     "The database snapshot job completed successfully this afternoon.",
     "Can the migration rehearsal start?",
     "The migration rehearsal needed a database snapshot, which completed this afternoon, so it can start."),
    ("reporting-double-count", "Jordan flagged that the reporting numbers looked off after the schema change.",
     "The schema change was found to double-count one join condition.",
     "Why did the reporting numbers look wrong?",
     "The reporting numbers looked off because the schema change introduced a double-counted join condition."),
    ("vendor-finance", "The vendor contract renewal needs finance sign-off before the end of the month.",
     "Finance completed sign-off on the vendor contract this morning.",
     "Is the vendor contract fully approved?",
     "The vendor contract needed finance sign-off, which was completed this morning, so it is fully approved."),
    ("checkout-design-review", "The design review for the new checkout flow was pushed back a week.",
     "Engineering can't start building checkout until the design review finishes.",
     "When can engineering start on the new checkout flow?",
     "Engineering is waiting on the design review, which was pushed back a week, so their start date slips accordingly."),
    ("staging-unstable", "Noah reported the staging environment has been unstable since Monday.",
     "All pre-release testing must run in the staging environment.",
     "Can pre-release testing happen this week?",
     "Pre-release testing needs staging, which has been unstable since Monday, so testing may be blocked."),
    ("security-audit", "Tessa's team completed the third-party security audit with no critical findings.",
     "Launch approval requires a clean third-party security audit.",
     "Is launch approval cleared from a security standpoint?",
     "Launch approval needed a clean security audit, which finished with no critical findings, so that requirement is cleared."),
    ("training-backfill", "Mina found that the recommendation model's training data was missing the last two weeks of events.",
     "The missing events were backfilled successfully last night.",
     "Is the recommendation model's training data complete now?",
     "The training data was missing two weeks of events, which were backfilled last night, so it is now complete."),
    ("ledger-reconciliation", "The Ledger workstream can't close out until the reconciliation report is signed off.",
     "The reconciliation report was signed off by finance this afternoon.",
     "Can Ledger be closed out now?",
     "Ledger needed the reconciliation report signed off, which happened this afternoon, so it can be closed out."),
]

# 5 corrected cross-account synthesis cases, reusing the existing (uncorrupted) v2
# isolation-*-semantic-* corpus notes in place of the broken isolation-synthesis-* cases.
CROSS_USER_SEMANTIC_SYNTHESIS = [
    ("isolation-primary-semantic-01", "isolation-secondary-semantic-01",
     "How does my DSA revision progress compare to how the other account is tracking the same topic?",
     "Primary user still needs revision on DSA topics, while the other account already finished all revision for the same topic."),
    ("isolation-primary-semantic-02", "isolation-secondary-semantic-02",
     "Between the two tracked accounts, whose college project is further along?",
     "The primary account's project is waiting on teacher review, while the other account submitted a different project altogether."),
    ("isolation-primary-semantic-03", "isolation-secondary-semantic-03",
     "Do both tracked accounts have their geography quiz on the same date?",
     "The primary account's quiz is on the 22nd, while the other account's quiz is on the 12th."),
    ("isolation-primary-semantic-04", "isolation-secondary-semantic-04",
     "Is the AWS learning progress the same across both tracked accounts?",
     "The primary account completed SQS retries, while the other account is still studying Lambda."),
    ("isolation-primary-semantic-05", "isolation-secondary-semantic-05",
     "Did both tracked accounts finish RRF at the same stage?",
     "The primary account completed RRF, while the other account only ever planned to learn it."),
]


def build_new_v3_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    corpus: list[dict[str, Any]] = []

    for index, (slug, note_text, query, claim_text) in enumerate(TRUE_PARAPHRASE):
        note_id = f"v3-paraphrase-{slug}"
        corpus.append(note(note_id, f"2026-07-{index + 1:02d}T10:00:00Z", "work_note", note_text))
        cases.append(
            case(
                f"v3-paraphrase-{index + 1:02d}",
                query,
                [note_id],
                [claim(claim_text, [note_id])],
                ["semantic", "paraphrase", "no-shared-tokens", "v3"],
            )
        )

    for index, (slug, note_text, query, claim_text) in enumerate(VOCABULARY_MISMATCH):
        note_id = f"v3-vocab-{slug}"
        corpus.append(note(note_id, f"2026-07-{index + 1:02d}T13:00:00Z", "technical_note", note_text))
        cases.append(
            case(
                f"v3-vocab-mismatch-{index + 1:02d}",
                query,
                [note_id],
                [claim(claim_text, [note_id])],
                ["semantic", "vocabulary-mismatch", "v3"],
            )
        )

    for index, (slug, query, distractor_text, target_text, claim_text) in enumerate(LEXICAL_NEAR_MISS):
        target_id = f"v3-trap-target-{slug}"
        distractor_id = f"v3-trap-distractor-{slug}"
        corpus.append(note(distractor_id, f"2026-06-{index + 1:02d}T09:00:00Z", "backlog_note", distractor_text))
        corpus.append(note(target_id, f"2026-07-{index + 1:02d}T15:00:00Z", "status_update", target_text))
        cases.append(
            case(
                f"v3-lexical-trap-{index + 1:02d}",
                query,
                [target_id],
                [claim(claim_text, [target_id])],
                ["semantic", "lexical-trap", "near-miss", "v3"],
            )
        )

    for index, (slug, note_a_text, note_b_text, query, claim_text) in enumerate(MULTI_NOTE_SYNTHESIS):
        note_a_id = f"v3-synthesis-{slug}-a"
        note_b_id = f"v3-synthesis-{slug}-b"
        corpus.append(note(note_a_id, f"2026-07-{index + 1:02d}T08:00:00Z", "status_update", note_a_text))
        corpus.append(note(note_b_id, f"2026-07-{index + 1:02d}T17:00:00Z", "status_update", note_b_text))
        cases.append(
            case(
                f"v3-multi-note-{index + 1:02d}",
                query,
                [note_a_id, note_b_id],
                [claim(claim_text, [note_a_id, note_b_id])],
                ["semantic", "multi-note", "synthesis", "v3"],
            )
        )

    for index, (note_a_id, note_b_id, query, claim_text) in enumerate(CROSS_USER_SEMANTIC_SYNTHESIS):
        cases.append(
            case(
                f"v3-cross-account-{index + 1:02d}",
                query,
                [note_a_id, note_b_id],
                [claim(claim_text, [note_a_id, note_b_id])],
                ["semantic", "multi-user", "cross-account-synthesis", "v3"],
            )
        )

    if len(cases) != 70:
        raise ValueError(f"Expected 70 new v3 cases, built {len(cases)}")
    return cases, corpus


def build_dataset() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reused_cases, reused_corpus = load_reused_v2_subset()
    new_cases, new_corpus = build_new_v3_cases()

    cases = reused_cases + new_cases
    corpus = reused_corpus + new_corpus

    if len(reused_cases) != 158:
        raise ValueError(f"Expected 158 reused v2 cases, found {len(reused_cases)}")
    if len(cases) != 228:
        raise ValueError(f"Expected 228 total v3 cases, built {len(cases)}")
    return cases, corpus


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    cases, corpus = build_dataset()
    write_jsonl(CASES_PATH, cases)
    write_jsonl(CORPUS_PATH, corpus)
    print(f"Wrote {len(cases)} cases to {CASES_PATH.relative_to(WORKSPACE_ROOT)}")
    print(f"Wrote {len(corpus)} notes to {CORPUS_PATH.relative_to(WORKSPACE_ROOT)}")


if __name__ == "__main__":
    main()

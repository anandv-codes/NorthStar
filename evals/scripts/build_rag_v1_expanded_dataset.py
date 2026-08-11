from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v1.jsonl"
CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v1_corpus.jsonl"
PRIMARY_USER = "eval-user-primary"
SECONDARY_USER = "eval-user-secondary"

WORKSTREAMS = ["Atlas", "Relay", "Ledger", "Beacon", "Harbor"]
OWNERS = ["Priya", "Marco", "Jordan", "Elena", "Samir", "Tessa", "Noah", "Mina"]
STATUSES = ["on track", "at risk", "in progress", "blocked", "ready for review"]


def note(
    note_id: str,
    user_id: str,
    created_at: str,
    note_type: str,
    raw_text: str,
) -> dict[str, str]:
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
    conflict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": case_id,
        "dataset_version": "northstar_rag_v1",
        "user_id": PRIMARY_USER,
        "query": query,
        "relevant_note_ids": relevant_note_ids,
        "expected_claims": expected_claims,
        "expected_answer_behavior": expected_answer_behavior,
        "tags": tags,
    }
    if conflict:
        result["conflict"] = conflict
    return result


def build_dataset() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corpus: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    # 20 exact work-item lookups with owners, status, target, and dependencies.
    for index in range(20):
        item_id = f"ITEM-{4101 + index}"
        stream = WORKSTREAMS[index % len(WORKSTREAMS)]
        owner = OWNERS[index % len(OWNERS)]
        status = STATUSES[index % len(STATUSES)]
        target_day = 10 + index
        note_id = f"item-{item_id.lower()}"
        target = f"2026-09-{target_day:02d}"
        corpus.append(
            note(
                note_id,
                PRIMARY_USER,
                f"2026-08-{index + 1:02d}T09:00:00Z",
                "work_item",
                (
                    f"{item_id} delivery record for the {stream} workstream. {owner} is the directly responsible owner; "
                    f"the item is {status} and targets {target}. Acceptance requires the audit event, rollback note, "
                    f"and owner handoff to be reviewed together. The dependency is the prior {stream} schema checkpoint."
                ),
            )
        )
        cases.append(
            case(
                f"item-lookup-{index + 1:02d}",
                f"Who owns {item_id}, what is its status, and when is it targeted?",
                [note_id],
                [
                    {
                        "claim": f"{owner} owns {item_id}; it is {status} and targets {target}.",
                        "supporting_note_ids": [note_id],
                    }
                ],
                ["exact", "item-id", "owner", "status"],
            )
        )

    # 15 precise data-fix records, including quantities, validation, and rollback conditions.
    for index in range(15):
        datafix_id = f"DFX-{7201 + index}"
        item_id = f"ITEM-{4101 + (index % 20)}"
        row_count = 18420 + index * 937
        table = ["memory_entries", "task_links", "note_vectors", "audit_events", "work_items"][index % 5]
        owner = OWNERS[(index + 2) % len(OWNERS)]
        note_id = f"datafix-{datafix_id.lower()}"
        corpus.append(
            note(
                note_id,
                PRIMARY_USER,
                f"2026-08-{index + 1:02d}T11:30:00Z",
                "datafix",
                (
                    f"Datafix {datafix_id} corrected {row_count:,} {table} rows linked to {item_id}. {owner} ran the "
                    f"idempotent job after sampling 250 records and reconciling the checksum against the warehouse export. "
                    f"Rollback remains available until the next Ledger checkpoint; no customer-visible records were deleted."
                ),
            )
        )
        cases.append(
            case(
                f"datafix-count-{index + 1:02d}",
                f"How many rows did {datafix_id} correct, and which record set did it affect?",
                [note_id],
                [
                    {
                        "claim": f"{datafix_id} corrected {row_count:,} {table} rows.",
                        "supporting_note_ids": [note_id],
                    }
                ],
                ["exact", "datafix", "number", "identifier"],
            )
        )

    # 10 progress checkpoints require chronology-aware multi-note synthesis without contradiction.
    for index in range(10):
        stream = WORKSTREAMS[index % len(WORKSTREAMS)]
        checkpoint = index + 1
        baseline_id = f"progress-{checkpoint:02d}-baseline"
        current_id = f"progress-{checkpoint:02d}-current"
        completed = 38 + index * 4
        blocker = [
            "the access-review sample",
            "a delayed partner export",
            "the rollback rehearsal",
            "a missing ownership approval",
            "the staging audit feed",
        ][index % 5]
        corpus.extend(
            [
                note(
                    baseline_id,
                    PRIMARY_USER,
                    f"2026-07-{10 + index:02d}T10:00:00Z",
                    "progress_update",
                    (
                        f"{stream} checkpoint {checkpoint} baseline: the team planned a 60 percent completion target and "
                        f"identified {blocker} as the main delivery risk. This is planning context, not a final status."
                    ),
                ),
                note(
                    current_id,
                    PRIMARY_USER,
                    f"2026-08-{10 + index:02d}T16:00:00Z",
                    "progress_update",
                    (
                        f"{stream} checkpoint {checkpoint} progress update: {completed} percent of scoped work is complete. "
                        f"The active blocker is {blocker}; the next step is a documented owner decision before the checkpoint "
                        f"can move to review. The earlier 60 percent target remains planning context only."
                    ),
                ),
            ]
        )
        cases.append(
            case(
                f"progress-summary-{checkpoint:02d}",
                f"Summarize the current progress and blocker for {stream} checkpoint {checkpoint}.",
                [baseline_id, current_id],
                [
                    {
                        "claim": f"{stream} checkpoint {checkpoint} is {completed} percent complete.",
                        "supporting_note_ids": [current_id],
                    },
                    {
                        "claim": f"The active blocker is {blocker}.",
                        "supporting_note_ids": [current_id],
                    },
                ],
                ["progress", "multi-note", "chronology"],
            )
        )

    # 10 operational learnings use paraphrased questions to exercise semantic retrieval.
    learning_topics = [
        ("retry storms", "bounded retries with a persisted backoff decision prevent duplicate side effects"),
        ("unowned alerts", "every operational alert needs one named escalation owner before release"),
        ("prompt exports", "redaction must run before any prompt payload leaves the application boundary"),
        ("stale embeddings", "vector refresh must follow the durable-note update rather than precede it"),
        ("silent data fixes", "each correction needs a reversible runbook and an independently checked count"),
        ("ambiguous status reports", "a status update must distinguish confirmed facts from a tentative forecast"),
        ("retrieval noise", "context budgets should favor direct evidence over loosely related keyword matches"),
        ("handoff gaps", "a decision record needs an explicit owner and due date before it can be closed"),
        ("schema drift", "contract checks must run before asynchronous workers process a new payload shape"),
        ("incident summaries", "a post-incident note should separate cause, impact, mitigation, and follow-up"),
    ]
    for index, (topic, lesson) in enumerate(learning_topics, start=1):
        note_id = f"learning-{index:02d}"
        corpus.append(
            note(
                note_id,
                PRIMARY_USER,
                f"2026-08-{index + 2:02d}T14:15:00Z",
                "learning",
                (
                    f"Learning review {index}: after investigating {topic}, the team concluded that {lesson}. "
                    f"This learning applies to the NorthStar delivery portfolio and should shape future runbooks and reviews."
                ),
            )
        )
        cases.append(
            case(
                f"learning-paraphrase-{index:02d}",
                f"What did the team learn about handling {topic}?",
                [note_id],
                [{"claim": lesson.capitalize() + ".", "supporting_note_ids": [note_id]}],
                ["semantic", "learning", "paraphrase"],
            )
        )

    # 15 dependency cases require two distinct, detailed notes to answer completely.
    for index in range(15):
        stream = WORKSTREAMS[index % len(WORKSTREAMS)]
        proposal_id = f"ITEM-{5101 + index}"
        prerequisite_id = f"ITEM-{6101 + index}"
        scope_id = f"multi-{index + 1:02d}-scope"
        dependency_id = f"multi-{index + 1:02d}-dependency"
        owner = OWNERS[(index + 3) % len(OWNERS)]
        corpus.extend(
            [
                note(
                    scope_id,
                    PRIMARY_USER,
                    f"2026-08-{index + 1:02d}T12:00:00Z",
                    "decision",
                    (
                        f"{stream} proposal {proposal_id}: {owner} owns the rollout package, which includes the audit event, "
                        f"support handoff, and a staged customer cohort. The package excludes automated deletion until sign-off."
                    ),
                ),
                note(
                    dependency_id,
                    PRIMARY_USER,
                    f"2026-08-{index + 1:02d}T13:00:00Z",
                    "dependency",
                    (
                        f"Dependency record for {proposal_id}: rollout cannot begin until {prerequisite_id} completes the "
                        f"schema verification and publishes a rollback checksum. This is a hard dependency, not a forecast."
                    ),
                ),
            ]
        )
        cases.append(
            case(
                f"dependency-synthesis-{index + 1:02d}",
                f"For {proposal_id}, who owns the rollout and what must finish before it begins?",
                [scope_id, dependency_id],
                [
                    {"claim": f"{owner} owns the {proposal_id} rollout package.", "supporting_note_ids": [scope_id]},
                    {
                        "claim": f"{prerequisite_id} must complete schema verification and publish a rollback checksum first.",
                        "supporting_note_ids": [dependency_id],
                    },
                ],
                ["multi-note", "dependency", "item-id"],
            )
        )

    # 15 genuine conflicts are intentionally unresolved, regardless of timestamps.
    conflict_subjects = [
        "the production rollout window",
        "the customer export retention period",
        "the Relay notification fallback",
        "the Ledger reconciliation threshold",
        "the Atlas migration cohort",
        "the Beacon audit evidence format",
        "the Harbor support escalation route",
        "the datafix approval owner",
        "the work-item completion definition",
        "the incident severity threshold",
        "the embedding refresh cadence",
        "the model-cost reporting method",
        "the release-readiness checklist",
        "the prompt-log retention policy",
        "the partner contract review date",
    ]
    for index, subject in enumerate(conflict_subjects, start=1):
        first_id = f"conflict-{index:02d}-a"
        second_id = f"conflict-{index:02d}-b"
        first_position = ["approved", "seven days", "enabled", "0.5 percent", "external pilot", "free-form notes", "on-call rotation", "engineering", "feature complete", "customer impact", "daily", "invoice total", "security review", "30 days", "September 12"][index - 1]
        second_position = ["not approved", "thirty days", "disabled", "1.0 percent", "internal cohort", "structured evidence", "support desk", "product", "validated rollback", "any data mismatch", "weekly", "usage events", "support sign-off", "90 days", "September 19"][index - 1]
        corpus.extend(
            [
                note(
                    first_id,
                    PRIMARY_USER,
                    f"2026-07-{index:02d}T09:00:00Z",
                    "status_update",
                    (
                        f"Status record A for {subject}: the recorded position is {first_position}. The author did not attach "
                        f"an approval reference or explain how this position relates to the competing programme record."
                    ),
                ),
                note(
                    second_id,
                    PRIMARY_USER,
                    f"2026-08-{index:02d}T09:00:00Z",
                    "status_update",
                    (
                        f"Status record B for {subject}: the recorded position is {second_position}. This note also lacks "
                        f"a shared authority reference, so it cannot safely supersede the other record on timestamp alone."
                    ),
                ),
            ]
        )
        cases.append(
            case(
                f"ambiguous-conflict-{index:02d}",
                f"What is the agreed decision for {subject}?",
                [first_id, second_id],
                [
                    {
                        "claim": f"The notes conflict: one records {first_position}, while another records {second_position}.",
                        "supporting_note_ids": [first_id, second_id],
                    }
                ],
                ["conflict", "ambiguous", "surface-conflict"],
                expected_answer_behavior="surface_conflict",
                conflict={
                    "present": True,
                    "policy": "always_surface_ambiguity",
                    "conflicting_note_ids": [first_id, second_id],
                    "expected_behavior": "surface_conflict",
                },
            )
        )

    # 10 cross-user collision cases share an ITEM identifier but must retrieve only primary-user evidence.
    for index in range(10):
        item_id = f"ITEM-{8101 + index}"
        primary_id = f"isolation-primary-{index + 1:02d}"
        foreign_id = f"isolation-foreign-{index + 1:02d}"
        primary_window = 6 + index
        foreign_window = 20 + index
        corpus.extend(
            [
                note(
                    primary_id,
                    PRIMARY_USER,
                    f"2026-08-{index + 1:02d}T08:30:00Z",
                    "work_item",
                    (
                        f"Primary-user recovery record for {item_id}: the approved recovery window is {primary_window} hours "
                        f"after a verified rollback, with Priya confirming the audit export before closure."
                    ),
                ),
                note(
                    foreign_id,
                    SECONDARY_USER,
                    f"2026-08-{index + 1:02d}T08:45:00Z",
                    "work_item",
                    (
                        f"Secondary-user recovery record for {item_id}: this unrelated portfolio uses a {foreign_window}-hour "
                        f"recovery window and a different approval process. It must never be returned for the primary user."
                    ),
                ),
            ]
        )
        cases.append(
            case(
                f"isolation-item-{index + 1:02d}",
                f"What is my approved recovery window for {item_id}?",
                [primary_id],
                [
                    {
                        "claim": f"The approved recovery window for {item_id} is {primary_window} hours after a verified rollback.",
                        "supporting_note_ids": [primary_id],
                    }
                ],
                ["isolation", "item-id", "cross-user-collision"],
            )
        )

    # Five abstention cases deliberately have no relevant note in either corpus.
    no_context_questions = [
        "What is the office parking reimbursement policy?",
        "Which dental insurer covers contractor dependents?",
        "What was the keynote speaker's travel itinerary?",
        "When does the company cafeteria close on Fridays?",
        "What is the corporate holiday gift budget?",
    ]
    for index, query in enumerate(no_context_questions, start=1):
        cases.append(
            case(
                f"no-context-{index:02d}",
                query,
                [],
                [],
                ["no-context", "abstention"],
                expected_answer_behavior="abstain_or_request_clarification",
            )
        )

    # Add 115 detailed primary-user distractors that create realistic topical and lexical density.
    for index in range(115):
        stream = WORKSTREAMS[index % len(WORKSTREAMS)]
        owner = OWNERS[(index + 4) % len(OWNERS)]
        status = STATUSES[(index + 1) % len(STATUSES)]
        reference_id = f"ARCH-{9001 + index}"
        corpus.append(
            note(
                f"context-primary-{index + 1:03d}",
                PRIMARY_USER,
                f"2026-06-{(index % 28) + 1:02d}T{8 + (index % 8):02d}:20:00Z",
                "reference",
                (
                    f"{stream} portfolio context {reference_id}: {owner} recorded a {status} review covering audit events, "
                    f"schema checks, work-item ownership, rollback evidence, and support handoff. The note is historical context; "
                    f"it does not decide any ITEM or DFX record in the golden questions. Follow-up is tracked in the weekly review."
                ),
            )
        )

    # Add 90 secondary-user distractors to make user filtering observable under similar vocabulary.
    for index in range(90):
        stream = WORKSTREAMS[(index + 2) % len(WORKSTREAMS)]
        owner = OWNERS[(index + 5) % len(OWNERS)]
        corpus.append(
            note(
                f"context-secondary-{index + 1:03d}",
                SECONDARY_USER,
                f"2026-06-{(index % 28) + 1:02d}T{9 + (index % 7):02d}:40:00Z",
                "reference",
                (
                    f"Secondary-user {stream} portfolio note SEC-{9501 + index}: {owner} reviewed an independent delivery "
                    f"programme with work-item status, datafix reconciliation, audit evidence, rollback, and customer support. "
                    f"This text intentionally overlaps the primary vocabulary but belongs to another user boundary."
                ),
            )
        )

    if len(cases) != 100:
        raise ValueError(f"Expected 100 cases, built {len(cases)}")
    if len(corpus) != 350:
        raise ValueError(f"Expected 350 notes, built {len(corpus)}")
    return cases, corpus


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
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
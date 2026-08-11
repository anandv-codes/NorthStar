from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from evals.scripts.build_rag_v1_expanded_dataset import (
    CASES_PATH,
    CORPUS_PATH,
    PRIMARY_USER,
    SECONDARY_USER,
)


EXPECTED_CASE_TAG_COUNTS = {
    "item-id": 45,
    "datafix": 15,
    "progress": 10,
    "learning": 10,
    "dependency": 15,
    "conflict": 15,
    "isolation": 10,
    "no-context": 5,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(cases: list[dict[str, Any]], corpus: list[dict[str, Any]]) -> None:
    require(len(cases) == 100, f"Expected 100 cases, found {len(cases)}")
    require(len(corpus) == 350, f"Expected 350 notes, found {len(corpus)}")

    case_ids = [str(item.get("id")) for item in cases]
    note_ids = [str(item.get("note_id")) for item in corpus]
    require(len(case_ids) == len(set(case_ids)), "Case IDs must be unique")
    require(len(note_ids) == len(set(note_ids)), "Note IDs must be unique")

    notes_by_id = {str(item["note_id"]): item for item in corpus}
    note_users = Counter(str(item.get("user_id")) for item in corpus)
    require(note_users == Counter({PRIMARY_USER: 250, SECONDARY_USER: 100}), "Unexpected user corpus split")

    tag_counts: Counter[str] = Counter()
    conflict_count = 0
    for item in corpus:
        for field in ("note_id", "user_id", "created_at", "note_type", "raw_text"):
            require(bool(item.get(field)), f"Note {item.get('note_id')} is missing {field}")

    for item in cases:
        case_id = str(item.get("id"))
        for field in (
            "dataset_version",
            "user_id",
            "query",
            "relevant_note_ids",
            "expected_claims",
            "expected_answer_behavior",
            "tags",
        ):
            require(field in item, f"Case {case_id} is missing {field}")
        require(item["dataset_version"] == "northstar_rag_v1", f"Case {case_id} has wrong dataset version")
        require(item["user_id"] == PRIMARY_USER, f"Case {case_id} has wrong evaluation user")

        relevant_ids = {str(note_id) for note_id in item["relevant_note_ids"]}
        for note_id in relevant_ids:
            require(note_id in notes_by_id, f"Case {case_id} references missing note {note_id}")
            require(
                notes_by_id[note_id]["user_id"] == PRIMARY_USER,
                f"Case {case_id} marks foreign note {note_id} as relevant",
            )

        for expected_claim in item["expected_claims"]:
            supporting_ids = {str(note_id) for note_id in expected_claim["supporting_note_ids"]}
            require(supporting_ids, f"Case {case_id} has a claim without supporting notes")
            require(
                supporting_ids.issubset(relevant_ids),
                f"Case {case_id} claim references notes outside relevant_note_ids",
            )

        tags = {str(tag) for tag in item["tags"]}
        tag_counts.update(tags)
        is_no_context = "no-context" in tags
        require(
            bool(relevant_ids) != is_no_context,
            f"Case {case_id} has inconsistent no-context relevance labels",
        )
        if is_no_context:
            require(
                item["expected_answer_behavior"] == "abstain_or_request_clarification",
                f"No-context case {case_id} must expect abstention",
            )

        conflict = item.get("conflict")
        if conflict:
            conflict_count += 1
            conflict_ids = {str(note_id) for note_id in conflict["conflicting_note_ids"]}
            require(conflict["policy"] == "always_surface_ambiguity", f"Case {case_id} has wrong ambiguity policy")
            require(conflict["expected_behavior"] == "surface_conflict", f"Case {case_id} has wrong conflict behavior")
            require(conflict_ids.issubset(relevant_ids), f"Case {case_id} omits conflict evidence")
            require(item["expected_answer_behavior"] == "surface_conflict", f"Case {case_id} must surface conflict")

    for tag, expected_count in EXPECTED_CASE_TAG_COUNTS.items():
        require(tag_counts[tag] == expected_count, f"Expected {expected_count} {tag} cases, found {tag_counts[tag]}")
    require(conflict_count == 15, f"Expected 15 conflict cases, found {conflict_count}")


def main() -> None:
    cases = load_jsonl(CASES_PATH)
    corpus = load_jsonl(CORPUS_PATH)
    validate(cases, corpus)
    print("Dataset validation passed: 100 cases, 350 notes, 15 ambiguity conflicts, 10 isolation cases.")


if __name__ == "__main__":
    main()
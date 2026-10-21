"""Validate the v4 focused dataset: counts, schema, refs, and semantic-bias guarantees."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evals.scripts.build_rag_v4_focused_dataset import (
    CASES_PATH,
    CORPUS_PATH,
    DATASET_VERSION,
    PRIMARY_USER,
    SECONDARY_USER,
)


EXACT_ID_PATTERN = re.compile(r"\b(?:ITEM|DFX)-[A-Z0-9-]+", re.IGNORECASE)
DOMAIN_TAGS = {"mba", "software", "interview"}
EXCLUDED_TAGS = {"exact", "item-id", "seed"}
EXPECTED_DOMAIN_COUNTS = {"mba": 10, "software": 17, "interview": 16}
EXPECTED_NO_CONTEXT_DOMAIN_COUNTS = {"mba": 2, "software": 3, "interview": 2}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(cases: list[dict[str, Any]], corpus: list[dict[str, Any]]) -> None:
    require(len(cases) == 50, f"Expected 50 cases, found {len(cases)}")
    require(len(corpus) == 63, f"Expected 63 notes, found {len(corpus)}")

    case_ids = [str(item.get("id")) for item in cases]
    note_ids = [str(item.get("note_id")) for item in corpus]
    require(len(case_ids) == len(set(case_ids)), "Case IDs must be unique")
    require(len(note_ids) == len(set(note_ids)), "Note IDs must be unique")

    notes_by_id = {str(item["note_id"]): item for item in corpus}
    note_users = Counter(str(item.get("user_id")) for item in corpus)
    require(
        note_users == Counter({PRIMARY_USER: 58, SECONDARY_USER: 5}),
        f"Unexpected user corpus split: {dict(note_users)}",
    )

    for item in corpus:
        note_id = str(item.get("note_id"))
        for field in ("note_id", "user_id", "created_at", "note_type", "raw_text"):
            require(bool(item.get(field)), f"Note {note_id} is missing {field}")
        require(
            not EXACT_ID_PATTERN.search(str(item["raw_text"])),
            f"Note {note_id} contains an exact identifier anchor",
        )

    answerable_domain_counts: Counter[str] = Counter()
    no_context_domain_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
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
        require(item["dataset_version"] == DATASET_VERSION, f"Case {case_id} has wrong dataset version")
        require(item["user_id"] == PRIMARY_USER, f"Case {case_id} has wrong evaluation user")
        require(bool(str(item["query"]).strip()), f"Case {case_id} has an empty query")
        require(
            not EXACT_ID_PATTERN.search(str(item["query"])),
            f"Case {case_id} contains an exact identifier anchor",
        )

        tags = {str(tag) for tag in item["tags"]}
        tag_counts.update(tags)
        require("v4" in tags, f"Case {case_id} is missing the v4 tag")
        require(not (tags & EXCLUDED_TAGS), f"Case {case_id} carries an excluded tag {tags & EXCLUDED_TAGS}")
        require(
            len(tags & DOMAIN_TAGS) == 1,
            f"Case {case_id} must have exactly one domain tag, found {tags & DOMAIN_TAGS}",
        )
        domain = next(iter(tags & DOMAIN_TAGS))

        relevant_ids = {str(note_id) for note_id in item["relevant_note_ids"]}
        require(
            len(relevant_ids) == len(item["relevant_note_ids"]),
            f"Case {case_id} has duplicate relevant note IDs",
        )
        is_no_context = "no-context" in tags
        require(bool(relevant_ids) != is_no_context, f"Case {case_id} has inconsistent no-context relevance labels")

        if is_no_context:
            no_context_domain_counts[domain] += 1
            require(not item["expected_claims"], f"No-context case {case_id} must not define expected claims")
            require(
                item["expected_answer_behavior"] == "abstain_or_request_clarification",
                f"No-context case {case_id} must expect abstention",
            )
        else:
            answerable_domain_counts[domain] += 1
            require(bool(item["expected_claims"]), f"Answerable case {case_id} needs expected claims")

        for note_id in relevant_ids:
            require(note_id in notes_by_id, f"Case {case_id} references missing note {note_id}")
            require(
                notes_by_id[note_id]["user_id"] == PRIMARY_USER,
                f"Case {case_id} marks foreign note {note_id} as relevant",
            )

        for expected_claim in item["expected_claims"]:
            require(bool(str(expected_claim.get("claim", "")).strip()), f"Case {case_id} has an empty claim")
            supporting_ids = {str(note_id) for note_id in expected_claim["supporting_note_ids"]}
            require(bool(supporting_ids), f"Case {case_id} has a claim without supporting notes")
            require(
                supporting_ids.issubset(relevant_ids),
                f"Case {case_id} claim references notes outside relevant_note_ids",
            )

    require(
        dict(answerable_domain_counts) == EXPECTED_DOMAIN_COUNTS,
        f"Unexpected answerable domain counts: {dict(answerable_domain_counts)}",
    )
    require(
        dict(no_context_domain_counts) == EXPECTED_NO_CONTEXT_DOMAIN_COUNTS,
        f"Unexpected no-context domain counts: {dict(no_context_domain_counts)}",
    )
    require(tag_counts["no-context"] == 7, f"Expected 7 no-context cases, found {tag_counts['no-context']}")
    require(tag_counts["synthesis"] == 8, f"Expected 8 synthesis cases, found {tag_counts['synthesis']}")
    require(tag_counts["chronology"] == 2, f"Expected 2 chronology cases, found {tag_counts['chronology']}")
    require(tag_counts["status"] == 3, f"Expected 3 status cases, found {tag_counts['status']}")


def main() -> None:
    cases = load_jsonl(CASES_PATH)
    corpus = load_jsonl(CORPUS_PATH)
    validate(cases, corpus)
    print(
        "Dataset validation passed: 50 cases "
        "(10 MBA / 17 software / 16 interview answerable, 7 no-context), "
        "63 notes, 5 secondary-user distractors."
    )


if __name__ == "__main__":
    main()

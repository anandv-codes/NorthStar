"""Validate the v3 semantic-bias dataset: counts, schema, and no-ID-anchor guarantees."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from evals.scripts.build_rag_v3_semantic_bias_dataset import CASES_PATH, CORPUS_PATH, PRIMARY_USER


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(cases: list[dict[str, Any]], corpus: list[dict[str, Any]]) -> None:
    require(len(cases) == 228, f"Expected 228 cases, found {len(cases)}")

    case_ids = [str(item.get("id")) for item in cases]
    note_ids = [str(item.get("note_id")) for item in corpus]
    require(len(case_ids) == len(set(case_ids)), "Case IDs must be unique")
    require(len(note_ids) == len(set(note_ids)), "Note IDs must be unique")

    notes_by_id = {str(item["note_id"]): item for item in corpus}
    excluded_tags = {"exact", "item-id", "seed"}

    tag_counts: Counter[str] = Counter()
    new_case_tag_counts: Counter[str] = Counter()
    for item in cases:
        case_id = str(item.get("id"))
        for field in ("dataset_version", "user_id", "query", "relevant_note_ids", "expected_claims", "expected_answer_behavior", "tags"):
            require(field in item, f"Case {case_id} is missing {field}")
        require(item["dataset_version"] == "northstar_rag_v3", f"Case {case_id} has wrong dataset version")

        tags = {str(tag) for tag in item["tags"]}
        tag_counts.update(tags)
        if "v3" in tags:
            new_case_tag_counts.update(tags)
        require(not (tags & excluded_tags), f"Case {case_id} carries an excluded tag {tags & excluded_tags}")

        relevant_ids = {str(note_id) for note_id in item["relevant_note_ids"]}
        is_no_context = "no-context" in tags
        require(bool(relevant_ids) != is_no_context, f"Case {case_id} has inconsistent no-context relevance labels")
        for note_id in relevant_ids:
            require(note_id in notes_by_id, f"Case {case_id} references missing note {note_id}")

        for expected_claim in item["expected_claims"]:
            supporting_ids = {str(note_id) for note_id in expected_claim["supporting_note_ids"]}
            require(supporting_ids.issubset(relevant_ids), f"Case {case_id} claim references notes outside relevant_note_ids")

    require(tag_counts["v3"] == 70, f"Expected 70 newly authored v3 cases, found {tag_counts['v3']}")
    require(len(cases) - tag_counts["v3"] == 158, "Expected 158 reused v2 cases")
    require(new_case_tag_counts["paraphrase"] == 20, f"Expected 20 paraphrase cases, found {new_case_tag_counts['paraphrase']}")
    require(new_case_tag_counts["vocabulary-mismatch"] == 15, f"Expected 15 vocabulary-mismatch cases, found {new_case_tag_counts['vocabulary-mismatch']}")
    require(new_case_tag_counts["lexical-trap"] == 15, f"Expected 15 lexical-trap cases, found {new_case_tag_counts['lexical-trap']}")
    require(new_case_tag_counts["synthesis"] == 15, f"Expected 15 multi-note synthesis cases, found {new_case_tag_counts['synthesis']}")
    require(new_case_tag_counts["cross-account-synthesis"] == 5, f"Expected 5 cross-account synthesis cases, found {new_case_tag_counts['cross-account-synthesis']}")

    for field in ("note_id", "user_id", "created_at", "note_type", "raw_text"):
        for item in corpus:
            require(bool(item.get(field)), f"Note {item.get('note_id')} is missing {field}")


def main() -> None:
    cases = load_jsonl(CASES_PATH)
    corpus = load_jsonl(CORPUS_PATH)
    validate(cases, corpus)
    print(f"Dataset validation passed: {len(cases)} cases, {len(corpus)} notes, 0 excluded-tag leaks.")


if __name__ == "__main__":
    main()

"""Tests for building/scoring recall candidates from an extraction."""
from backend.app.domain.recall.candidate_engine import attach_item_ids, build_candidates
from backend.app.domain.recall.candidate_scoring import (
    ELIGIBLE,
    REJECTED,
    ScoringConfig,
)


def _extraction(**overrides):
    base = {
        "summary": "note",
        "tasks": [],
        "facts": [],
        "concepts": [],
        "questions": [],
        "decisions": [],
        "risks": [],
        "entities": [],
        "commitments": [],
    }
    base.update(overrides)
    return base


CONFIG = ScoringConfig(eligibility_threshold=0.3, min_confidence=0.0)


def test_default_config_allows_a_realistic_first_note():
    """Regression: 0.65 threshold rejected every first-note unit."""
    extraction = _extraction(
        facts=[
            {"content": "SQS visibility timeout controls hiding", "importance": 0.9, "confidence": 0.95},
            {"content": "minor trivia", "importance": 0.2, "confidence": 0.95},
        ]
    )
    candidates = build_candidates(extraction, source_note_id="note-1", config=ScoringConfig())
    assert [c["text"] for c in candidates] == ["SQS visibility timeout controls hiding"]


def test_candidates_are_sorted_by_descending_score():
    extraction = _extraction(
        facts=[
            {"content": "low", "importance": 0.1, "confidence": 1.0},
            {"content": "high", "importance": 1.0, "confidence": 1.0},
        ]
    )
    candidates = build_candidates(extraction, source_note_id="note-1", config=CONFIG)
    assert [c["text"] for c in candidates] == ["high", "low"]
    assert candidates[0]["score"] > candidates[1]["score"]


def test_low_confidence_units_are_rejected():
    extraction = _extraction(facts=[{"content": "shakey", "importance": 1.0, "confidence": 0.1}])
    config = ScoringConfig(eligibility_threshold=0.3, min_confidence=0.6)
    assert build_candidates(extraction, source_note_id="n", config=config) == []

    with_rejected = build_candidates(
        extraction, source_note_id="n", config=config, include_rejected=True
    )
    assert with_rejected[0]["status"] == REJECTED


def test_dedupe_key_is_stable_and_type_scoped():
    extraction = _extraction(
        facts=[{"content": "SQS   visibility timeout", "confidence": 1.0}],
        concepts=[{"concept": "sqs visibility timeout", "confidence": 1.0}],
    )
    candidates = build_candidates(extraction, source_note_id="n", config=CONFIG)
    keys = {c["item_type"]: c["dedupe_key"] for c in candidates}
    assert keys["fact"] != keys["concept"]  # same text, different type
    again = build_candidates(extraction, source_note_id="n", config=CONFIG)
    assert {(c["item_type"], c["dedupe_key"]) for c in candidates} == {
        (c["item_type"], c["dedupe_key"]) for c in again
    }


def test_entity_mentions_and_related_notes_increase_score():
    extraction = _extraction(
        facts=[
            {"content": "pgvector indexing", "importance": 0.5, "confidence": 1.0, "entities": ["pgvector"]}
        ]
    )
    baseline = build_candidates(extraction, source_note_id="n", config=CONFIG)[0]["score"]
    boosted = build_candidates(
        extraction,
        source_note_id="n",
        related_note_ids=["note-1", "note-2", "note-3"],
        entity_mention_counts={"pgvector": 7},
        config=CONFIG,
    )[0]["score"]
    assert boosted > baseline


def test_no_per_note_cap_by_default():
    extraction = _extraction(
        facts=[{"content": f"fact {i}", "importance": 0.9, "confidence": 1.0} for i in range(15)]
    )
    assert len(build_candidates(extraction, source_note_id="n", config=CONFIG)) == 15

    capped = ScoringConfig(eligibility_threshold=0.3, min_confidence=0.0, max_items_per_note=5)
    assert len(build_candidates(extraction, source_note_id="n", config=capped)) == 5


def test_attach_item_ids_matches_persisted_rows():
    extraction = _extraction(concepts=[{"concept": "Visibility timeout", "confidence": 1.0}])
    candidates = build_candidates(extraction, source_note_id="n", config=CONFIG)
    linked = attach_item_ids(
        candidates,
        {"concept": [{"concept": "Visibility timeout", "concept_id": "c-1"}]},
    )
    assert linked[0]["item_id"] == "c-1"

    unlinked = attach_item_ids(candidates, {})
    assert unlinked[0]["item_id"] is None

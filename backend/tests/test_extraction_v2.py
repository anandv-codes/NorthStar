"""Tests for extraction v2 helpers (scoring, due dates, projection)."""
from datetime import date, datetime

from backend.app.domain.memory.extraction_v2 import (
    build_note_metadata,
    clamp_score,
    commitment_rows,
    entity_importance_delta,
    item_durability,
    item_importance,
    normalize_due_date,
    task_rows_with_scoring,
)


def test_clamp_score_bounds_and_defaults():
    assert clamp_score(1.5) == 1.0
    assert clamp_score(-0.2) == 0.0
    assert clamp_score("0.4") == 0.4
    assert clamp_score(None) is None
    assert clamp_score("nope", default=0.3) == 0.3


def test_normalize_due_date_accepts_common_forms():
    assert normalize_due_date("2026-06-13") == "2026-06-13"
    assert normalize_due_date("due 2026-06-13 by EOD") == "2026-06-13"
    assert normalize_due_date(date(2026, 6, 13)) == "2026-06-13"
    assert normalize_due_date(datetime(2026, 6, 13, 9, 0)) == "2026-06-13"
    assert normalize_due_date("next Friday") is None
    assert normalize_due_date(None) is None


def test_item_importance_falls_back_to_confidence_then_default():
    assert item_importance({"importance": 0.9, "confidence": 0.1}) == 0.9
    assert item_importance({"confidence": 0.6}) == 0.6
    assert item_importance({}) == 0.5
    assert item_durability({"durability": 0.8}) == 0.8
    assert item_durability({}) == 0.5


def test_build_note_metadata_normalizes_scores_and_keeps_all_types():
    extraction = {
        "summary": "did things",
        "tasks": [{"description": "ship PR5", "confidence": 0.8, "due_date": "2026-06-13"}],
        "facts": [{"content": "fact", "importance": 0.6}],
        "concepts": [{"concept": "concept", "durability": 0.9}],
        "questions": [{"question": "why?"}],
        "decisions": [{"decision": "decided"}],
        "entities": [{"name": "pgvector"}],
        "commitment_contributions": [
            {"commitment_id": "goal-1", "comment": "Sent the report."}
        ],
    }
    metadata = build_note_metadata(extraction)

    assert metadata["schema_version"] == 2
    assert metadata["tasks"][0]["importance"] == 0.8
    assert metadata["tasks"][0]["durability"] == 0.5
    assert metadata["facts"][0]["importance"] == 0.6
    assert metadata["concepts"][0]["durability"] == 0.9
    assert metadata["questions"] == [{"question": "why?"}]
    assert "risks" not in metadata
    assert metadata["commitment_contributions"] == [
        {"commitment_id": "goal-1", "comment": "Sent the report."}
    ]


def test_commitment_rows_skip_blank_titles_and_normalize():
    rows = commitment_rows(
        {
            "commitments": [
                {"title": "Send report", "due_date": "2026-06-13", "confidence": 2},
                {"title": "  "},
            ]
        },
        user_id="user-1",
        source_note_id="note-1",
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Send report"
    assert rows[0]["due_date"] == "2026-06-13"
    assert rows[0]["confidence"] == 1.0
    assert rows[0]["status"] == "pending"


def test_task_rows_with_scoring_adds_due_date_and_scores():
    rows = task_rows_with_scoring([{"description": "ship", "confidence": 0.7}])
    assert rows[0]["due_date"] is None
    assert rows[0]["importance"] == 0.7
    assert rows[0]["durability"] == 0.5


def test_entity_importance_delta_is_deduplicated_and_capped():
    assert entity_importance_delta(["SQS", "sqs", "AWS"]) == 0.2
    assert entity_importance_delta([]) == 0.0
    assert entity_importance_delta([str(i) for i in range(100)]) == 1.0

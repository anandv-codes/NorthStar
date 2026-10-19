"""Tests for persisting candidates via the RecallRepository port."""
from backend.app.domain.recall.candidate_scoring import ScoringConfig
from backend.app.domain.recall.candidate_service import generate_candidates
from backend.tests.fakes import InMemoryRecallRepository

CONFIG = ScoringConfig(eligibility_threshold=0.3, min_confidence=0.0)


def test_generate_candidates_persists_and_dedupes():
    repo = InMemoryRecallRepository()
    extraction = {
        "facts": [{"content": "SQS visibility timeout", "importance": 0.9, "confidence": 1.0}],
        "concepts": [],
    }

    first = generate_candidates("user-1", "note-1", extraction, config=CONFIG, repo=repo)
    second = generate_candidates("user-1", "note-1", extraction, config=CONFIG, repo=repo)

    assert len(first) == 1
    assert first[0]["candidate_id"] == second[0]["candidate_id"]
    assert len(repo.query_candidates("user-1")) == 1


def test_reprocessing_does_not_clobber_a_suggested_candidate():
    repo = InMemoryRecallRepository()
    extraction = {"facts": [{"content": "SQS visibility timeout", "importance": 0.9, "confidence": 1.0}]}
    first = generate_candidates("user-1", "note-1", extraction, config=CONFIG, repo=repo)[0]
    repo.update_candidate(
        "user-1",
        first["candidate_id"],
        {"status": "suggested", "prompt": "What does SQS visibility timeout control?"},
    )

    second = generate_candidates("user-1", "note-1", extraction, config=CONFIG, repo=repo)

    assert second == []
    stored = repo.get_candidate("user-1", first["candidate_id"])
    assert stored["status"] == "suggested"
    assert stored["prompt"] == "What does SQS visibility timeout control?"


def test_generate_candidates_links_typed_rows():
    repo = InMemoryRecallRepository()
    extraction = {"concepts": [{"concept": "Visibility timeout", "importance": 0.8, "confidence": 1.0}]}
    rows = generate_candidates(
        "user-1",
        "note-1",
        extraction,
        typed_rows={"concept": [{"concept": "Visibility timeout", "concept_id": "c-9"}]},
        config=CONFIG,
        repo=repo,
    )
    assert rows[0]["item_id"] == "c-9"


def test_generate_candidates_returns_empty_when_nothing_eligible():
    repo = InMemoryRecallRepository()
    extraction = {"facts": [{"content": "trivia", "importance": 0.0, "confidence": 0.0}]}
    assert generate_candidates("user-1", "note-1", extraction, config=CONFIG, repo=repo) == []

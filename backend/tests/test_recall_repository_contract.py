"""Contract tests for the recall persistence surface.

These run against the in-memory fake in ``backend/tests/fakes.py``. The fake
mirrors ``SupabaseRecallRepository`` semantics so the domain (PR6) can be
developed and tested against the port without a database.
"""
import pytest

from backend.app.domain.ports import RecallRepository
from backend.tests.fakes import InMemoryRecallRepository

USER = "user-1"
OTHER = "user-2"


@pytest.fixture
def repo() -> InMemoryRecallRepository:
    return InMemoryRecallRepository()


def test_fake_satisfies_recall_repository_protocol(repo):
    assert isinstance(repo, RecallRepository)


def test_candidate_upsert_is_idempotent_by_dedupe_key(repo):
    first = repo.upsert_candidate(
        USER, {"item_type": "concept", "dedupe_key": "concept:sqs", "score": 0.5}
    )
    second = repo.upsert_candidate(
        USER, {"item_type": "concept", "dedupe_key": "concept:sqs", "score": 0.9}
    )

    assert first["candidate_id"] == second["candidate_id"]
    assert len(repo.query_candidates(USER)) == 1
    assert repo.get_candidate(USER, first["candidate_id"])["score"] == 0.9


def test_candidates_are_user_scoped_and_sorted_by_score(repo):
    repo.insert_candidates(USER, [{"item_type": "fact", "score": 0.2}])
    repo.insert_candidates(USER, [{"item_type": "fact", "score": 0.8}])
    repo.insert_candidates(OTHER, [{"item_type": "fact", "score": 0.99}])

    scores = [c["score"] for c in repo.query_candidates(USER)]
    assert scores == [0.8, 0.2]
    assert len(repo.query_candidates(OTHER)) == 1


def test_query_candidates_filters_by_status(repo):
    repo.insert_candidates(
        USER,
        [
            {"item_type": "concept", "score": 0.9, "status": "suggested"},
            {"item_type": "concept", "score": 0.8, "status": "carded"},
        ],
    )
    suggested = repo.query_candidates(USER, status="suggested")
    assert [c["status"] for c in suggested] == ["suggested"]


def test_candidate_status_update(repo):
    candidate = repo.insert_candidates(USER, [{"item_type": "fact", "score": 0.9}])[0]
    updated = repo.update_candidate(USER, candidate["candidate_id"], {"status": "approved"})
    assert updated["status"] == "approved"
    assert repo.update_candidate(OTHER, candidate["candidate_id"], {"status": "approved"}) == {}


def test_get_candidates_by_ids_is_bulk_and_user_scoped(repo):
    first, second = repo.insert_candidates(
        USER, [{"item_type": "fact"}, {"item_type": "fact"}]
    )
    other = repo.insert_candidates(OTHER, [{"item_type": "fact"}])[0]

    rows = repo.get_candidates_by_ids(
        USER,
        [first["candidate_id"], second["candidate_id"], other["candidate_id"]],
    )

    assert {row["candidate_id"] for row in rows} == {
        first["candidate_id"],
        second["candidate_id"],
    }
    assert repo.get_candidates_by_ids(USER, []) == []


def test_cards_due_query_and_schedule_update(repo):
    repo.create_card(
        USER,
        {"question": "q1", "answer": "a1", "next_due": "2026-01-01T00:00:00+00:00"},
    )
    due_card = repo.create_card(
        USER,
        {"question": "q2", "answer": "a2", "next_due": "2026-06-01T00:00:00+00:00"},
    )
    repo.create_card(
        OTHER,
        {"question": "q3", "answer": "a3", "next_due": "2025-01-01T00:00:00+00:00"},
    )

    due = repo.query_cards(USER, status="active", due_before="2026-02-01T00:00:00+00:00")
    assert [c["question"] for c in due] == ["q1"]

    updated = repo.update_card(USER, due_card["card_id"], {"interval": 7, "review_count": 1})
    assert updated["interval"] == 7
    assert repo.get_card(USER, due_card["card_id"])["review_count"] == 1
    assert repo.get_card(OTHER, due_card["card_id"]) is None


def test_card_lookup_by_candidate_is_user_scoped(repo):
    card = repo.create_card(
        USER, {"candidate_id": "cand-1", "question": "q", "answer": "a"}
    )

    assert repo.get_card_by_candidate(USER, "cand-1")["card_id"] == card["card_id"]
    assert repo.get_card_by_candidate(OTHER, "cand-1") is None


def test_fake_rejects_two_cards_for_one_candidate(repo):
    repo.create_card(USER, {"candidate_id": "cand-1", "question": "q", "answer": "a"})

    with pytest.raises(RuntimeError, match="unique constraint"):
        repo.create_card(USER, {"candidate_id": "cand-1", "question": "q2", "answer": "a2"})


def test_accept_atomic_returns_card_and_marks_candidate(repo):
    candidate = repo.insert_candidates(USER, [{"item_type": "fact", "score": 0.9}])[0]

    outcome = repo.accept_candidate_atomic(
        USER,
        candidate["candidate_id"],
        {"candidate_id": candidate["candidate_id"], "question": "q", "answer": "a"},
        "2026-01-01T00:00:00+00:00",
    )

    assert outcome["status"] == "carded"
    assert outcome["card"]["candidate_id"] == candidate["candidate_id"]
    assert repo.get_candidate(USER, candidate["candidate_id"])["status"] == "carded"


def test_accept_atomic_is_idempotent(repo):
    candidate = repo.insert_candidates(USER, [{"item_type": "fact"}])[0]
    card = {"candidate_id": candidate["candidate_id"], "question": "q", "answer": "a"}

    first = repo.accept_candidate_atomic(USER, candidate["candidate_id"], card, "2026-01-01T00:00:00+00:00")
    second = repo.accept_candidate_atomic(USER, candidate["candidate_id"], card, "2026-01-02T00:00:00+00:00")

    assert second["status"] == "carded"
    assert second["card"]["card_id"] == first["card"]["card_id"]
    assert len(repo.cards) == 1


def test_accept_atomic_reports_missing_and_inconsistent(repo):
    assert repo.accept_candidate_atomic(USER, "missing", {}, "2026-01-01T00:00:00+00:00") == {
        "status": "not_found"
    }

    candidate = repo.insert_candidates(USER, [{"item_type": "fact"}])[0]
    repo.update_candidate(USER, candidate["candidate_id"], {"status": "carded"})
    assert repo.accept_candidate_atomic(
        USER, candidate["candidate_id"], {}, "2026-01-01T00:00:00+00:00"
    ) == {"status": "already_carded"}


def test_review_history_roundtrip_is_newest_first(repo):
    card = repo.create_card(USER, {"question": "q", "answer": "a"})
    repo.insert_review_history(
        USER,
        {"card_id": card["card_id"], "grade": 3, "reviewed_at": "2026-01-01T00:00:00+00:00"},
    )
    repo.insert_review_history(
        USER,
        {"card_id": card["card_id"], "grade": 5, "reviewed_at": "2026-02-01T00:00:00+00:00"},
    )
    repo.insert_review_history(
        OTHER, {"card_id": card["card_id"], "grade": 5}
    )

    history = repo.query_review_history(USER, card["card_id"])
    assert [entry["grade"] for entry in history] == [5, 3]


def test_commitments_roundtrip_and_status_filter(repo):
    repo.upsert_commitment(
        USER, {"source_note_id": "note-1", "title": "Ship PR3", "status": "pending"}
    )
    repo.upsert_commitment(
        USER, {"source_note_id": "note-2", "title": "Write docs", "status": "confirmed"}
    )

    assert len(repo.query_commitments(USER)) == 2
    pending = repo.query_commitments(USER, status="pending")
    assert [c["title"] for c in pending] == ["Ship PR3"]

    updated = repo.update_commitment(USER, pending[0]["commitment_id"], {"status": "scheduled"})
    assert updated["status"] == "scheduled"


def test_models_validate_recall_payloads():
    pytest.importorskip("pydantic")
    from pydantic import ValidationError

    from backend.app.schemas.models import (
        CommitmentCreate,
        RecallCardCreate,
        ReviewHistoryCreate,
    )

    card = RecallCardCreate(user_id=USER, question="Q?", answer="A")
    assert card.easiness == 2.5
    assert card.status == "active"

    commitment = CommitmentCreate(user_id=USER, source_note_id="note-1", title="Ship")
    assert commitment.status == "pending"

    review = ReviewHistoryCreate(user_id=USER, card_id="card-1", grade=5)
    assert review.grade == 5

    with pytest.raises(ValidationError):
        ReviewHistoryCreate(user_id=USER, card_id="card-1", grade=6)

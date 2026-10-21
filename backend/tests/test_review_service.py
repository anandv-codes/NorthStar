"""Tests for the review service: candidate decisions + card review (PR8)."""
from datetime import datetime, timezone

import pytest

from backend.app.domain.recall.review_service import (
    accept_candidate,
    accept_candidates,
    due_cards,
    list_suggestions,
    reject_candidate,
    review_card,
    update_suggestion,
)
from backend.app.domain.recall.scheduling.scheduler import AnkiScheduler, SchedulerConfig
from backend.tests.fakes import InMemoryRecallRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
SCHED = AnkiScheduler(SchedulerConfig(learning_steps=(1, 10)))

TEXT = "SQS visibility timeout controls how long a message stays hidden after retrieval."
ANSWER = "It controls how long a message stays hidden after retrieval."


class FakeClock:
    def now(self):
        return NOW


def _suggested_candidate(repo, text=TEXT, prompt="What does SQS visibility timeout control?"):
    return repo.upsert_candidate(
        "user-1",
        {
            "item_type": "fact",
            "source_note_id": "note-1",
            "text": text,
            "prompt": prompt,
            "answer": ANSWER,
            "score": 0.9,
            "status": "suggested",
            "dedupe_key": f"fact:{text}",
            "rationale": {},
        },
    )


def test_list_suggestions_are_scored_desc():
    repo = InMemoryRecallRepository()
    _suggested_candidate(repo, text="a")
    _suggested_candidate(repo, text="b")
    rows = list_suggestions("user-1", repo=repo)
    assert len(rows) == 2


def test_accept_candidate_creates_scheduled_card():
    repo = InMemoryRecallRepository()
    candidate = _suggested_candidate(repo)

    result = accept_candidate(
        "user-1", candidate["candidate_id"], repo=repo, now=NOW
    )

    assert result["status"] == "carded"
    card = result["card"]
    assert card["answer"] == ANSWER
    assert card["state"] == "new"
    assert card["next_due"] == NOW.isoformat()
    stored = repo.get_candidate("user-1", candidate["candidate_id"])
    assert stored["status"] == "carded"


def test_accept_candidate_requires_question():
    repo = InMemoryRecallRepository()
    candidate = _suggested_candidate(repo, prompt=None)
    with pytest.raises(ValueError):
        accept_candidate("user-1", candidate["candidate_id"], repo=repo, now=NOW)


def test_accept_candidate_missing_raises_lookup():
    repo = InMemoryRecallRepository()
    with pytest.raises(LookupError):
        accept_candidate("user-1", "nope", repo=repo, now=NOW)


def test_reject_candidate_marks_rejected():
    repo = InMemoryRecallRepository()
    candidate = _suggested_candidate(repo)
    result = reject_candidate("user-1", candidate["candidate_id"], repo=repo, now=NOW)
    assert result["status"] == "rejected"
    assert repo.get_candidate("user-1", candidate["candidate_id"])["status"] == "rejected"


def test_review_card_persists_state_and_history():
    repo = InMemoryRecallRepository()
    candidate = _suggested_candidate(repo)
    accepted = accept_candidate("user-1", candidate["candidate_id"], repo=repo, now=NOW)
    card_id = accepted["card"]["card_id"]

    result = review_card(
        "user-1",
        card_id,
        4,
        repo=repo,
        scheduler=SCHED,
        now=NOW,
        elapsed_ms=1234,
    )

    assert result["card"]["learning_step"] == 1
    history = repo.query_review_history("user-1", card_id)
    assert len(history) == 1
    assert history[0]["grade"] == 4
    assert history[0]["elapsed_ms"] == 1234


def test_review_card_invalid_grade():
    repo = InMemoryRecallRepository()
    for grade in (0, 2, 9):
        with pytest.raises(ValueError):
            review_card("user-1", "card", grade, repo=repo, now=NOW)


def test_due_cards_returns_active_due():
    repo = InMemoryRecallRepository()
    candidate = _suggested_candidate(repo)
    accept_candidate("user-1", candidate["candidate_id"], repo=repo, now=NOW)
    cards = due_cards("user-1", repo=repo, clock=FakeClock())
    assert len(cards) == 1


def test_accept_candidate_requires_stored_answer():
    repo = InMemoryRecallRepository()
    candidate = _suggested_candidate(repo)
    candidate["answer"] = None
    with pytest.raises(ValueError, match="candidate_has_no_answer"):
        accept_candidate("user-1", candidate["candidate_id"], repo=repo, now=NOW)


def test_update_suggestion_edits_only_suggested_candidates():
    repo = InMemoryRecallRepository()
    candidate = _suggested_candidate(repo)

    updated = update_suggestion(
        "user-1",
        candidate["candidate_id"],
        repo=repo,
        question="Which SQS setting prevents duplicate processing?",
        answer="The visibility timeout.",
        now=NOW,
    )

    assert updated["prompt"] == "Which SQS setting prevents duplicate processing?"
    assert updated["answer"] == "The visibility timeout."

    repo.update_candidate("user-1", candidate["candidate_id"], {"status": "carded"})
    with pytest.raises(ValueError, match="candidate_not_editable"):
        update_suggestion("user-1", candidate["candidate_id"], repo=repo, answer="x")


def test_accept_candidates_reports_partial_failures():
    repo = InMemoryRecallRepository()
    first = _suggested_candidate(repo, text="first")
    second = _suggested_candidate(repo, text="second")
    second["answer"] = None

    result = accept_candidates(
        "user-1",
        [first["candidate_id"], second["candidate_id"], "missing"],
        repo=repo,
        now=NOW,
    )

    assert result["accepted"] == 1
    assert result["failed"] == 2
    assert repo.get_candidate("user-1", first["candidate_id"])["status"] == "carded"
    assert {item["candidate_id"] for item in result["results"] if item["status"] == "failed"} == {
        second["candidate_id"],
        "missing",
    }

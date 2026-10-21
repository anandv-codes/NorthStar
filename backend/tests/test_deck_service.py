"""Tests for categorised recall decks (PR11)."""
from datetime import datetime, timezone

import pytest

from backend.app.domain.recall.deck_service import (
    archive_deck,
    assign_candidates_to_deck,
    create_deck,
    ensure_default_deck,
    list_cards,
    list_decks_with_stats,
    move_card_to_deck,
    restore_deck,
    update_deck,
)
from backend.app.domain.recall.review_service import accept_candidate
from backend.tests.fakes import InMemoryRecallRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
USER = "user-1"


class FakeClock:
    def now(self):
        return NOW


def _candidate(repo, *, text="SQS visibility timeout", status="suggested"):
    return repo.upsert_candidate(
        USER,
        {
            "item_type": "fact",
            "source_note_id": "note-1",
            "text": text,
            "prompt": "What controls SQS visibility timeout?",
            "answer": "The visibility timeout.",
            "score": 0.9,
            "status": status,
            "dedupe_key": f"fact:{text}",
            "rationale": {},
        },
    )


def _card(repo, deck_id, *, question="q", status="active", next_due=NOW.isoformat()):
    return repo.create_card(
        USER,
        {
            "deck_id": deck_id,
            "question": question,
            "answer": "a",
            "status": status,
            "next_due": next_due,
        },
    )


def test_default_deck_is_created_once_and_listed_first():
    repo = InMemoryRecallRepository()

    first = ensure_default_deck(USER, repo=repo, now=NOW)
    second = ensure_default_deck(USER, repo=repo, now=NOW)

    assert first["deck_id"] == second["deck_id"]
    assert first["name"] == "General"
    assert first["is_default"] is True
    assert [deck["deck_id"] for deck in list_decks_with_stats(USER, repo=repo, now=NOW)] == [
        first["deck_id"]
    ]


def test_duplicate_deck_names_are_rejected_case_insensitively():
    repo = InMemoryRecallRepository()
    create_deck(USER, repo=repo, name="Algorithms", now=NOW)

    with pytest.raises(ValueError, match="deck_name_taken"):
        create_deck(USER, repo=repo, name=" algorithms ", now=NOW)


def test_update_deck_rejects_other_users_and_duplicate_names():
    repo = InMemoryRecallRepository()
    first = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    create_deck(USER, repo=repo, name="Systems", now=NOW)

    with pytest.raises(ValueError, match="deck_name_taken"):
        update_deck(USER, first["deck_id"], repo=repo, name="systems")

    with pytest.raises(LookupError):
        update_deck("other", first["deck_id"], repo=repo, name="New name")


def test_update_deck_can_clear_an_existing_description():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", description="Graphs", now=NOW)

    updated = update_deck(
        USER,
        deck["deck_id"],
        repo=repo,
        description=None,
        description_provided=True,
    )

    assert updated["description"] is None


def test_deck_stats_count_due_new_and_suspended_cards():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    _card(repo, deck["deck_id"], question="due", next_due="2025-01-01T00:00:00+00:00")
    _card(repo, deck["deck_id"], question="future", next_due="2027-01-01T00:00:00+00:00")
    _card(repo, deck["deck_id"], question="suspended", status="suspended")

    row = next(
        d for d in list_decks_with_stats(USER, repo=repo, now=NOW) if d["deck_id"] == deck["deck_id"]
    )

    assert row["total_cards"] == 2
    assert row["due_cards"] == 1
    assert row["new_cards"] == 2
    assert row["suspended_cards"] == 1


def test_archive_suspends_cards_and_restore_reactivates_them():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    card = _card(repo, deck["deck_id"])

    archived = archive_deck(USER, deck["deck_id"], repo=repo, now=NOW)

    assert archived["archived_at"] == NOW.isoformat()
    assert repo.get_card(USER, card["card_id"])["status"] == "suspended"
    assert list_decks_with_stats(USER, repo=repo, now=NOW)[0]["deck_id"] != deck["deck_id"]

    restored = restore_deck(USER, deck["deck_id"], repo=repo)

    assert restored["archived_at"] is None
    assert repo.get_card(USER, card["card_id"])["status"] == "active"


def test_default_deck_cannot_be_archived():
    repo = InMemoryRecallRepository()
    default = ensure_default_deck(USER, repo=repo, now=NOW)

    with pytest.raises(ValueError, match="default_deck_protected"):
        archive_deck(USER, default["deck_id"], repo=repo, now=NOW)


def test_assign_candidates_to_deck_is_user_scoped_and_validated():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    first = _candidate(repo, text="first")
    second = _candidate(repo, text="second")

    assign_candidates_to_deck(USER, [first["candidate_id"], second["candidate_id"]], deck["deck_id"], repo=repo)

    assert repo.get_candidate(USER, first["candidate_id"])["deck_id"] == deck["deck_id"]
    assert repo.get_candidate(USER, second["candidate_id"])["deck_id"] == deck["deck_id"]

    with pytest.raises(LookupError):
        assign_candidates_to_deck(USER, [first["candidate_id"]], "missing", repo=repo)


def test_accept_candidate_copies_its_deck_to_the_card():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    candidate = _candidate(repo)
    repo.update_candidate(USER, candidate["candidate_id"], {"deck_id": deck["deck_id"]})

    result = accept_candidate(USER, candidate["candidate_id"], repo=repo, now=NOW)

    assert result["card"]["deck_id"] == deck["deck_id"]
    assert repo.get_candidate(USER, candidate["candidate_id"])["deck_id"] == deck["deck_id"]


def test_accept_candidate_falls_back_to_general_and_honours_override():
    repo = InMemoryRecallRepository()
    explicit = create_deck(USER, repo=repo, name="Systems", now=NOW)

    first = _candidate(repo, text="fallback")
    fallback = accept_candidate(USER, first["candidate_id"], repo=repo, now=NOW)
    default = ensure_default_deck(USER, repo=repo, now=NOW)
    assert fallback["card"]["deck_id"] == default["deck_id"]

    second = _candidate(repo, text="override")
    overridden = accept_candidate(
        USER, second["candidate_id"], repo=repo, now=NOW, deck_id=explicit["deck_id"]
    )
    assert overridden["card"]["deck_id"] == explicit["deck_id"]


def test_move_card_to_deck_and_list_cards_by_deck():
    repo = InMemoryRecallRepository()
    first = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    second = create_deck(USER, repo=repo, name="Systems", now=NOW)
    card = _card(repo, first["deck_id"], next_due="2027-01-01T00:00:00+00:00")

    moved = move_card_to_deck(USER, card["card_id"], second["deck_id"], repo=repo)

    assert moved["deck_id"] == second["deck_id"]
    assert list_cards(
        USER,
        repo=repo,
        deck_id=second["deck_id"],
        include_not_due=True,
        clock=FakeClock(),
    )[0]["card_id"] == card["card_id"]
    assert list_cards(
        USER,
        repo=repo,
        deck_id=second["deck_id"],
        include_not_due=False,
        clock=FakeClock(),
    ) == []

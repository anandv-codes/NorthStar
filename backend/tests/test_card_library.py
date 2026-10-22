"""Tests for the recall card library and bulk management."""
from datetime import datetime, timezone

import pytest

from backend.app.domain.recall.card_library import (
    browse_cards,
    bulk_update_cards,
    update_card,
)
from backend.app.domain.recall.deck_service import create_deck, ensure_default_deck
from backend.tests.fakes import InMemoryRecallRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
USER = "user-1"


def _card(repo, deck_id, *, question="q", answer="a", next_due=None, **extra):
    return repo.create_card(
        USER,
        {
            "deck_id": deck_id,
            "question": question,
            "answer": answer,
            "state": extra.pop("state", "new"),
            "status": extra.pop("status", "active"),
            "next_due": next_due,
            "source_note_ids": extra.pop("source_note_ids", []),
            "review_count": extra.pop("review_count", 0),
            "lapses": extra.pop("lapses", 0),
            **extra,
        },
    )


def test_browse_cards_filters_and_paginates():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    _card(
        repo,
        deck["deck_id"],
        question="What is a heap?",
        next_due="2025-01-01T00:00:00+00:00",
        source_note_ids=["note-1"],
        review_count=5,
    )
    _card(
        repo,
        deck["deck_id"],
        question="What is a trie?",
        answer="A prefix tree.",
        next_due="2027-01-01T00:00:00+00:00",
        source_note_ids=["note-2"],
        lapses=3,
    )

    due = browse_cards(
        USER,
        repo=repo,
        deck_id=deck["deck_id"],
        q="heap",
        due="due",
        now=NOW,
    )
    assert due["total"] == 1
    assert due["cards"][0]["question"] == "What is a heap?"

    by_note = browse_cards(
        USER, repo=repo, source_note_id="note-2", sort="newest", now=NOW
    )
    assert by_note["total"] == 1
    assert by_note["cards"][0]["answer"] == "A prefix tree."

    page = browse_cards(
        USER,
        repo=repo,
        deck_id=deck["deck_id"],
        sort="reviews",
        limit=1,
        offset=1,
        now=NOW,
    )
    assert page["total"] == 2
    assert page["cards"][0]["question"] == "What is a trie?"


def test_browse_cards_validates_filters_and_deck_ownership():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", now=NOW)

    with pytest.raises(LookupError):
        browse_cards(USER, repo=repo, deck_id="missing")
    with pytest.raises(LookupError):
        browse_cards("other", repo=repo, deck_id=deck["deck_id"])
    with pytest.raises(ValueError, match="invalid_card_state"):
        browse_cards(USER, repo=repo, state="archived")
    with pytest.raises(ValueError, match="invalid_card_sort"):
        browse_cards(USER, repo=repo, sort="random")


def test_update_card_moves_suspends_and_requires_fields():
    repo = InMemoryRecallRepository()
    first = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    second = create_deck(USER, repo=repo, name="Systems", now=NOW)
    card = _card(repo, first["deck_id"])

    moved = update_card(
        USER, card["card_id"], repo=repo, deck_id=second["deck_id"], deck_provided=True
    )
    assert moved["deck_id"] == second["deck_id"]

    suspended = update_card(USER, card["card_id"], repo=repo, status="suspended")
    assert suspended["status"] == "suspended"

    with pytest.raises(ValueError, match="no_fields_to_update"):
        update_card(USER, card["card_id"], repo=repo)
    with pytest.raises(LookupError):
        update_card("other", card["card_id"], repo=repo, status="active")


def test_bulk_update_cards_is_user_scoped_and_moves_selection():
    repo = InMemoryRecallRepository()
    first = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    second = create_deck(USER, repo=repo, name="Systems", now=NOW)
    keep = _card(repo, first["deck_id"], question="keep")
    move = _card(repo, first["deck_id"], question="move")
    other = repo.create_card(
        "other",
        {
            "deck_id": first["deck_id"],
            "question": "other",
            "answer": "a",
            "source_note_ids": [],
        },
    )

    updated = bulk_update_cards(
        USER,
        [keep["card_id"], move["card_id"], other["card_id"], "missing"],
        repo=repo,
        deck_id=second["deck_id"],
        deck_provided=True,
    )

    assert {row["card_id"] for row in updated} == {keep["card_id"], move["card_id"]}
    assert repo.get_card(USER, keep["card_id"])["deck_id"] == second["deck_id"]
    assert repo.get_card("other", other["card_id"])["deck_id"] == first["deck_id"]

    bulk_update_cards(
        USER,
        [keep["card_id"], move["card_id"]],
        repo=repo,
        status="suspended",
    )
    assert repo.get_card(USER, keep["card_id"])["status"] == "suspended"


def test_bulk_update_rejects_archived_deck_and_empty_fields():
    repo = InMemoryRecallRepository()
    deck = create_deck(USER, repo=repo, name="Algorithms", now=NOW)
    card = _card(repo, deck["deck_id"])
    default = ensure_default_deck(USER, repo=repo, now=NOW)

    with pytest.raises(ValueError, match="no_fields_to_update"):
        bulk_update_cards(USER, [card["card_id"]], repo=repo)
    with pytest.raises(LookupError):
        bulk_update_cards(
            USER,
            [card["card_id"]],
            repo=repo,
            deck_id="missing",
            deck_provided=True,
        )

    from backend.app.domain.recall.deck_service import archive_deck

    archive_deck(USER, deck["deck_id"], repo=repo, now=NOW)
    with pytest.raises(ValueError, match="deck_archived"):
        update_card(USER, card["card_id"], repo=repo, status="active")
    with pytest.raises(ValueError, match="deck_archived"):
        bulk_update_cards(USER, [card["card_id"]], repo=repo, status="active")
    assert default["deck_id"]

"""Browsing and bulk management for approved recall cards."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .deck_service import get_active_deck
from .scheduling import SystemClock

CARD_STATES = ("new", "learning", "review", "relearning")
CARD_STATUSES = ("active", "suspended")
CARD_SORTS = ("due", "newest", "reviews", "lapses")


def browse_cards(
    user_id: str,
    *,
    repo: Any,
    deck_id: str | None = None,
    status: str | None = None,
    state: str | None = None,
    q: str | None = None,
    due: str | None = None,
    source_note_id: str | None = None,
    sort: str = "due",
    limit: int = 50,
    offset: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    if deck_id is not None and repo.get_deck(user_id, deck_id) is None:
        raise LookupError("deck_not_found")
    if status is not None and status not in CARD_STATUSES:
        raise ValueError("invalid_card_status")
    if state is not None and state not in CARD_STATES:
        raise ValueError("invalid_card_state")
    if due not in (None, "due", "not_due"):
        raise ValueError("invalid_due_filter")
    if sort not in CARD_SORTS:
        raise ValueError("invalid_card_sort")

    current = (now or SystemClock().now()).isoformat()
    return repo.query_cards_page(
        user_id,
        deck_id=deck_id,
        status=status,
        state=state,
        q=q,
        due_before=current if due == "due" else None,
        due_after=current if due == "not_due" else None,
        source_note_id=source_note_id,
        sort=sort,
        limit=limit,
        offset=offset,
    )


def update_card(
    user_id: str,
    card_id: str,
    *,
    repo: Any,
    deck_id: str | None = None,
    deck_provided: bool = False,
    status: str | None = None,
) -> dict[str, Any]:
    card = repo.get_card(user_id, card_id)
    if card is None:
        raise LookupError("card_not_found")

    updates: dict[str, Any] = {}
    if deck_provided:
        if deck_id is not None:
            get_active_deck(user_id, deck_id, repo=repo)
        updates["deck_id"] = deck_id
    if status is not None:
        if status not in CARD_STATUSES:
            raise ValueError("invalid_card_status")
        target_deck_id = deck_id if deck_provided else card.get("deck_id")
        if status == "active" and target_deck_id:
            deck = repo.get_deck(user_id, target_deck_id)
            if deck is not None and deck.get("archived_at"):
                raise ValueError("deck_archived")
        updates["status"] = status
    if not updates:
        raise ValueError("no_fields_to_update")

    updated = repo.update_card(user_id, card_id, updates)
    return updated or {**card, **updates}


def bulk_update_cards(
    user_id: str,
    card_ids: list[str],
    *,
    repo: Any,
    deck_id: str | None = None,
    deck_provided: bool = False,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if deck_provided and deck_id is not None:
        get_active_deck(user_id, deck_id, repo=repo)
    if status is not None and status not in CARD_STATUSES:
        raise ValueError("invalid_card_status")
    if not deck_provided and status is None:
        raise ValueError("no_fields_to_update")

    updates: dict[str, Any] = {}
    if deck_provided:
        updates["deck_id"] = deck_id
    if status is not None:
        updates["status"] = status

    cards = [
        card
        for card_id in dict.fromkeys(card_ids)
        if (card := repo.get_card(user_id, card_id)) is not None
    ]
    if status == "active" and not deck_provided:
        for card in cards:
            if not card.get("deck_id"):
                continue
            deck = repo.get_deck(user_id, card["deck_id"])
            if deck is not None and deck.get("archived_at"):
                raise ValueError("deck_archived")

    updated: list[dict[str, Any]] = []
    for card in cards:
        row = repo.update_card(user_id, card["card_id"], updates)
        updated.append(row or {**card, **updates})
    return updated

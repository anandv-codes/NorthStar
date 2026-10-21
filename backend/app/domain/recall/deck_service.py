"""Categorised recall decks.

Decks are user-defined buckets for approved recall cards. Cards belong to
exactly one deck; the per-user ``General`` deck is created lazily and cannot be
archived. Archiving suspends a deck's cards instead of deleting its review
history, so a deck can be restored later.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .scheduling import SystemClock

DEFAULT_DECK_NAME = "General"
DECK_COLORS = ("neutral", "amber", "emerald", "sky", "violet", "rose")
DECK_NAME_MAX = 60
DECK_DESCRIPTION_MAX = 240


def _now(now: datetime | None = None) -> datetime:
    return now or SystemClock().now()


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_due(row: dict[str, Any], now: datetime) -> bool:
    due = _parse_timestamp(row.get("next_due"))
    if due is None:
        return False
    if due.tzinfo is None and now.tzinfo is not None:
        due = due.replace(tzinfo=now.tzinfo)
    return due <= now


def _validate_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("deck_name_required")
    if len(normalized) > DECK_NAME_MAX:
        raise ValueError("deck_name_too_long")
    return normalized


def _validate_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = str(description).strip()
    if not normalized:
        return None
    if len(normalized) > DECK_DESCRIPTION_MAX:
        raise ValueError("deck_description_too_long")
    return normalized


def _validate_color(color: str | None) -> str:
    normalized = str(color or "neutral").strip().lower()
    if normalized not in DECK_COLORS:
        raise ValueError("invalid_deck_color")
    return normalized


def ensure_default_deck(
    user_id: str, *, repo: Any, now: datetime | None = None
) -> dict[str, Any]:
    """Return the user's General deck, creating it once if needed."""
    now = _now(now)
    decks = repo.query_decks(user_id)
    for deck in decks:
        if deck.get("is_default"):
            return deck

    existing = repo.find_deck_by_name(user_id, DEFAULT_DECK_NAME)
    if existing is not None:
        updated = repo.update_deck(
            user_id, existing["deck_id"], {"is_default": True}
        )
        return updated or {**existing, "is_default": True}

    try:
        return repo.create_deck(
            user_id,
            {
                "name": DEFAULT_DECK_NAME,
                "description": "Cards that aren't assigned to a category yet.",
                "color": "neutral",
                "is_default": True,
                "created_at": now.isoformat(),
            },
        )
    except Exception:  # noqa: BLE001 - unique index may have raced another call
        for deck in repo.query_decks(user_id):
            if deck.get("is_default"):
                return deck
        raise


def get_active_deck(user_id: str, deck_id: str, *, repo: Any) -> dict[str, Any]:
    """Fetch a deck owned by the user and reject archived decks."""
    deck = repo.get_deck(user_id, deck_id)
    if deck is None:
        raise LookupError("deck_not_found")
    if deck.get("archived_at"):
        raise ValueError("deck_archived")
    return deck


def _stats_by_deck(
    user_id: str, *, repo: Any, now: datetime
) -> dict[str | None, dict[str, int]]:
    stats: dict[str | None, dict[str, int]] = {}
    for row in repo.query_card_stats(user_id):
        deck_id = row.get("deck_id")
        bucket = stats.setdefault(
            deck_id,
            {"total_cards": 0, "due_cards": 0, "new_cards": 0, "suspended_cards": 0},
        )
        status = row.get("status") or "active"
        if status == "suspended":
            bucket["suspended_cards"] += 1
            continue
        if status != "active":
            continue
        bucket["total_cards"] += 1
        if _is_due(row, now):
            bucket["due_cards"] += 1
        if (row.get("state") or "new") == "new":
            bucket["new_cards"] += 1
    return stats


def list_decks_with_stats(
    user_id: str,
    *,
    repo: Any,
    now: datetime | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    now = _now(now)
    ensure_default_deck(user_id, repo=repo, now=now)
    stats = _stats_by_deck(user_id, repo=repo, now=now)
    decks = repo.query_decks(user_id, include_archived=include_archived)
    rows = []
    for deck in decks:
        bucket = stats.get(deck["deck_id"], {})
        rows.append(
            {
                **deck,
                "total_cards": bucket.get("total_cards", 0),
                "due_cards": bucket.get("due_cards", 0),
                "new_cards": bucket.get("new_cards", 0),
                "suspended_cards": bucket.get("suspended_cards", 0),
            }
        )
    rows.sort(key=lambda d: (not d.get("is_default"), d.get("sort_order") or 0, d.get("created_at") or ""))
    return rows


def create_deck(
    user_id: str,
    *,
    repo: Any,
    name: str,
    description: str | None = None,
    color: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = _now(now)
    normalized_name = _validate_name(name)
    if repo.find_deck_by_name(user_id, normalized_name) is not None:
        raise ValueError("deck_name_taken")
    return repo.create_deck(
        user_id,
        {
            "name": normalized_name,
            "description": _validate_description(description),
            "color": _validate_color(color),
            "created_at": now.isoformat(),
        },
    )


def update_deck(
    user_id: str,
    deck_id: str,
    *,
    repo: Any,
    name: str | None = None,
    description: str | None = None,
    description_provided: bool = False,
    color: str | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    deck = repo.get_deck(user_id, deck_id)
    if deck is None:
        raise LookupError("deck_not_found")

    updates: dict[str, Any] = {}
    if name is not None:
        normalized_name = _validate_name(name)
        duplicate = repo.find_deck_by_name(user_id, normalized_name)
        if duplicate is not None and duplicate["deck_id"] != deck_id:
            raise ValueError("deck_name_taken")
        updates["name"] = normalized_name
    if description is not None or description_provided:
        updates["description"] = _validate_description(description)
    if color is not None:
        updates["color"] = _validate_color(color)
    if sort_order is not None:
        updates["sort_order"] = max(0, int(sort_order))

    if not updates:
        raise ValueError("no_fields_to_update")
    updated = repo.update_deck(user_id, deck_id, updates)
    return updated or {**deck, **updates}


def archive_deck(
    user_id: str, deck_id: str, *, repo: Any, now: datetime | None = None
) -> dict[str, Any]:
    now = _now(now)
    deck = repo.get_deck(user_id, deck_id)
    if deck is None:
        raise LookupError("deck_not_found")
    if deck.get("is_default"):
        raise ValueError("default_deck_protected")
    if deck.get("archived_at"):
        return deck

    updated = repo.update_deck(
        user_id, deck_id, {"archived_at": now.isoformat()}
    ) or {**deck, "archived_at": now.isoformat()}
    for card in repo.query_cards(
        user_id, status="active", deck_id=deck_id, limit=100000
    ):
        repo.update_card(user_id, card["card_id"], {"status": "suspended"})
    return updated


def restore_deck(
    user_id: str, deck_id: str, *, repo: Any
) -> dict[str, Any]:
    deck = repo.get_deck(user_id, deck_id)
    if deck is None:
        raise LookupError("deck_not_found")
    if not deck.get("archived_at"):
        return deck

    duplicate = repo.find_deck_by_name(user_id, deck["name"])
    if duplicate is not None and duplicate["deck_id"] != deck_id:
        raise ValueError("deck_name_taken")

    updated = repo.update_deck(user_id, deck_id, {"archived_at": None}) or {
        **deck,
        "archived_at": None,
    }
    for card in repo.query_cards(
        user_id, status="suspended", deck_id=deck_id, limit=100000
    ):
        repo.update_card(user_id, card["card_id"], {"status": "active"})
    return updated


def assign_candidates_to_deck(
    user_id: str,
    candidate_ids: list[str],
    deck_id: str,
    *,
    repo: Any,
) -> list[dict[str, Any]]:
    get_active_deck(user_id, deck_id, repo=repo)
    return repo.assign_candidates_to_deck(user_id, candidate_ids, deck_id)


def move_card_to_deck(
    user_id: str, card_id: str, deck_id: str | None, *, repo: Any
) -> dict[str, Any]:
    card = repo.get_card(user_id, card_id)
    if card is None:
        raise LookupError("card_not_found")
    if deck_id is not None:
        get_active_deck(user_id, deck_id, repo=repo)
    updated = repo.update_card(user_id, card_id, {"deck_id": deck_id})
    return updated or {**card, "deck_id": deck_id}


def list_cards(
    user_id: str,
    *,
    repo: Any,
    deck_id: str | None = None,
    include_not_due: bool = False,
    status: str = "active",
    clock: Any | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    if deck_id is not None:
        deck = repo.get_deck(user_id, deck_id)
        if deck is None:
            raise LookupError("deck_not_found")
    now = (clock or SystemClock()).now()
    due_before = None if include_not_due else now.isoformat()
    return repo.query_cards(
        user_id,
        status=status,
        due_before=due_before,
        limit=limit,
        deck_id=deck_id,
    )

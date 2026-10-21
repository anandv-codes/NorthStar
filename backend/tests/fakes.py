"""In-memory fakes for the domain ports.

Used by contract tests so the recall persistence surface can be exercised
without a live Supabase instance. The behavior intentionally mirrors
``SupabaseRecallRepository``: user-scoped reads, newest-first ordering, and
dedupe upserts keyed by ``(user_id, dedupe_key)``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryRecallRepository:
    def __init__(self) -> None:
        self.candidates: dict[str, dict[str, Any]] = {}
        self.cards: dict[str, dict[str, Any]] = {}
        self.decks: dict[str, dict[str, Any]] = {}
        self.reviews: list[dict[str, Any]] = []
        self.commitments: dict[str, dict[str, Any]] = {}

    # -- Candidates --------------------------------------------------------

    def insert_candidates(
        self, user_id: str, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        inserted = []
        for candidate in candidates:
            candidate_id = candidate.get("candidate_id") or str(uuid.uuid4())
            row = {
                "status": "new",
                **candidate,
                "candidate_id": candidate_id,
                "user_id": user_id,
                "created_at": candidate.get("created_at") or _now(),
                "updated_at": _now(),
            }
            self.candidates[candidate_id] = row
            inserted.append(row)
        return inserted

    def upsert_candidate(self, user_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
        dedupe_key = candidate.get("dedupe_key")
        if dedupe_key is not None:
            for existing in self.candidates.values():
                if existing["user_id"] == user_id and existing.get("dedupe_key") == dedupe_key:
                    existing.update({**candidate, "updated_at": _now()})
                    return existing
        return self.insert_candidates(user_id, [candidate])[0]

    def get_candidate(self, user_id: str, candidate_id: str) -> dict[str, Any] | None:
        row = self.candidates.get(candidate_id)
        return row if row and row["user_id"] == user_id else None

    def query_candidates(
        self,
        user_id: str,
        status: str | None = None,
        limit: int = 100,
        source_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.candidates.values()
            if row["user_id"] == user_id
            and (status is None or row.get("status") == status)
            and (source_note_id is None or row.get("source_note_id") == source_note_id)
        ]
        rows.sort(key=lambda row: row.get("score") or 0, reverse=True)
        return rows[:limit]

    def update_candidate(
        self, user_id: str, candidate_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        row = self.get_candidate(user_id, candidate_id)
        if row is None:
            return {}
        row.update({**updates, "updated_at": _now()})
        return row

    def assign_candidates_to_deck(
        self, user_id: str, candidate_ids: list[str], deck_id: str | None
    ) -> list[dict[str, Any]]:
        updated = []
        for candidate_id in candidate_ids:
            row = self.get_candidate(user_id, candidate_id)
            if row is not None:
                row.update({"deck_id": deck_id, "updated_at": _now()})
                updated.append(row)
        return updated

    # -- Decks -------------------------------------------------------------

    def create_deck(self, user_id: str, deck: dict[str, Any]) -> dict[str, Any]:
        deck_id = deck.get("deck_id") or str(uuid.uuid4())
        row = {
            "description": None,
            "color": "neutral",
            "is_default": False,
            "sort_order": 0,
            "archived_at": None,
            **deck,
            "deck_id": deck_id,
            "user_id": user_id,
            "created_at": deck.get("created_at") or _now(),
            "updated_at": _now(),
        }
        self.decks[deck_id] = row
        return row

    def get_deck(self, user_id: str, deck_id: str) -> dict[str, Any] | None:
        row = self.decks.get(deck_id)
        return row if row and row["user_id"] == user_id else None

    def find_deck_by_name(self, user_id: str, name: str) -> dict[str, Any] | None:
        for row in self.decks.values():
            if (
                row["user_id"] == user_id
                and row.get("archived_at") is None
                and row["name"].lower() == name.lower()
            ):
                return row
        return None

    def query_decks(
        self, user_id: str, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.decks.values()
            if row["user_id"] == user_id
            and (include_archived or row.get("archived_at") is None)
        ]
        rows.sort(key=lambda row: (row.get("sort_order") or 0, row.get("created_at") or ""))
        return rows

    def update_deck(
        self, user_id: str, deck_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        row = self.get_deck(user_id, deck_id)
        if row is None:
            return {}
        row.update({**updates, "updated_at": _now()})
        return row

    def query_card_stats(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {
                "deck_id": row.get("deck_id"),
                "state": row.get("state"),
                "status": row.get("status"),
                "next_due": row.get("next_due"),
            }
            for row in self.cards.values()
            if row["user_id"] == user_id
        ]

    # -- Cards -------------------------------------------------------------

    def create_card(self, user_id: str, card: dict[str, Any]) -> dict[str, Any]:
        card_id = card.get("card_id") or str(uuid.uuid4())
        row = {
            "status": "active",
            **card,
            "card_id": card_id,
            "user_id": user_id,
            "created_at": card.get("created_at") or _now(),
            "updated_at": _now(),
        }
        self.cards[card_id] = row
        return row

    def get_card(self, user_id: str, card_id: str) -> dict[str, Any] | None:
        row = self.cards.get(card_id)
        return row if row and row["user_id"] == user_id else None

    def query_cards(
        self,
        user_id: str,
        status: str | None = None,
        due_before: str | None = None,
        limit: int = 100,
        deck_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.cards.values()
            if row["user_id"] == user_id
            and (status is None or row.get("status") == status)
            and (deck_id is None or row.get("deck_id") == deck_id)
        ]
        if due_before is not None:
            rows = [row for row in rows if (row.get("next_due") or "") <= due_before]
        rows.sort(key=lambda row: row.get("next_due") or "")
        return rows[:limit]

    def update_card(self, user_id: str, card_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        row = self.get_card(user_id, card_id)
        if row is None:
            return {}
        row.update({**updates, "updated_at": _now()})
        return row

    # -- Review history ----------------------------------------------------

    def insert_review_history(self, user_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        row = {
            **entry,
            "review_id": entry.get("review_id") or str(uuid.uuid4()),
            "user_id": user_id,
            "reviewed_at": entry.get("reviewed_at") or _now(),
        }
        self.reviews.append(row)
        return row

    def query_review_history(self, user_id: str, card_id: str) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.reviews
            if row["user_id"] == user_id and row["card_id"] == card_id
        ]
        return sorted(rows, key=lambda row: row["reviewed_at"], reverse=True)

    # -- Commitments -------------------------------------------------------

    def upsert_commitment(self, user_id: str, commitment: dict[str, Any]) -> dict[str, Any]:
        commitment_id = commitment.get("commitment_id") or str(uuid.uuid4())
        row = {
            "status": "pending",
            **commitment,
            "commitment_id": commitment_id,
            "user_id": user_id,
            "created_at": commitment.get("created_at") or _now(),
            "updated_at": _now(),
        }
        self.commitments[commitment_id] = row
        return row

    def query_commitments(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.commitments.values()
            if row["user_id"] == user_id and (status is None or row.get("status") == status)
        ]
        return sorted(rows, key=lambda row: row["created_at"], reverse=True)

    def update_commitment(
        self, user_id: str, commitment_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        row = self.commitments.get(commitment_id)
        if row is None or row["user_id"] != user_id:
            return {}
        row.update({**updates, "updated_at": _now()})
        return row

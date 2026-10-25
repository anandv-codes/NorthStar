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

    def get_candidates_by_ids(
        self, user_id: str, candidate_ids: list[str]
    ) -> list[dict[str, Any]]:
        wanted = set(candidate_ids)
        return [
            row
            for row in self.candidates.values()
            if row["user_id"] == user_id and row["candidate_id"] in wanted
        ]

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

    def update_candidate_if_status(
        self,
        user_id: str,
        candidate_id: str,
        expected_status: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        row = self.get_candidate(user_id, candidate_id)
        if row is None or row.get("status") != expected_status:
            return {}
        row.update({**updates, "updated_at": _now()})
        return row

    def accept_candidate_atomic(
        self,
        user_id: str,
        candidate_id: str,
        card: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        """Mirror the SQL RPC: lock-by-key, return an existing card, else insert."""
        candidate = self.get_candidate(user_id, candidate_id)
        if candidate is None:
            return {"status": "not_found"}

        existing = self.get_card_by_candidate(user_id, candidate_id)
        if existing is not None:
            candidate.update(
                {
                    "status": "carded",
                    "deck_id": existing.get("deck_id"),
                    "decided_at": candidate.get("decided_at") or now,
                    "updated_at": _now(),
                }
            )
            return {"status": "carded", "card": existing}

        if candidate.get("status") == "carded":
            return {"status": "already_carded"}

        row = self.create_card(user_id, card)
        candidate.update(
            {
                "status": "carded",
                "deck_id": row.get("deck_id"),
                "decided_at": now,
                "updated_at": _now(),
            }
        )
        return {"status": "carded", "card": row}

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
        candidate_id = card.get("candidate_id")
        if candidate_id and any(
            row["user_id"] == user_id and row.get("candidate_id") == candidate_id
            for row in self.cards.values()
        ):
            # Mirrors idx_recall_cards_user_candidate in phase4_recall.sql.
            raise RuntimeError("duplicate key value violates unique constraint")
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

    def get_card_by_candidate(
        self, user_id: str, candidate_id: str
    ) -> dict[str, Any] | None:
        for row in self.cards.values():
            if row["user_id"] == user_id and row.get("candidate_id") == candidate_id:
                return row
        return None

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

    def query_cards_page(
        self,
        user_id: str,
        *,
        deck_id: str | None = None,
        status: str | None = None,
        state: str | None = None,
        q: str | None = None,
        due_before: str | None = None,
        due_after: str | None = None,
        source_note_id: str | None = None,
        sort: str = "due",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        search = str(q or "").strip().lower()
        rows = [
            row
            for row in self.cards.values()
            if row["user_id"] == user_id
            and (deck_id is None or row.get("deck_id") == deck_id)
            and (status is None or row.get("status") == status)
            and (state is None or row.get("state") == state)
            and (
                due_before is None
                or (row.get("next_due") is not None and row["next_due"] <= due_before)
            )
            and (
                due_after is None
                or row.get("next_due") is None
                or row["next_due"] > due_after
            )
            and (
                source_note_id is None
                or source_note_id in (row.get("source_note_ids") or [])
            )
            and (
                not search
                or search in str(row.get("question") or "").lower()
                or search in str(row.get("answer") or "").lower()
            )
        ]
        if sort == "newest":
            rows.sort(key=lambda row: row.get("created_at") or "", reverse=True)
        elif sort == "reviews":
            rows.sort(key=lambda row: row.get("review_count") or 0, reverse=True)
        elif sort == "lapses":
            rows.sort(key=lambda row: row.get("lapses") or 0, reverse=True)
        else:
            rows.sort(key=lambda row: row.get("next_due") or "")
        total = len(rows)
        page = rows[max(0, offset) : max(0, offset) + max(1, limit)]
        return {
            "cards": page,
            "total": total,
            "limit": max(1, limit),
            "offset": max(0, offset),
        }

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


class InMemoryCommitmentRepository:
    """User-authored goal persistence mirroring the Supabase repository."""

    def __init__(self) -> None:
        self.commitments: dict[str, dict[str, Any]] = {}
        self.contributions: dict[str, dict[str, Any]] = {}

    def create_commitment(self, user_id: str, text: str) -> dict[str, Any]:
        commitment_id = str(uuid.uuid4())
        now = _now()
        row = {
            "commitment_id": commitment_id,
            "user_id": user_id,
            "text": text,
            "progress": 0,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        self.commitments[commitment_id] = row
        return row

    def get_commitment(
        self, user_id: str, commitment_id: str
    ) -> dict[str, Any] | None:
        row = self.commitments.get(commitment_id)
        return row if row and row["user_id"] == user_id else None

    def query_commitments(
        self, user_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.commitments.values()
            if row["user_id"] == user_id
            and (status is None or row.get("status") == status)
        ]
        return sorted(rows, key=lambda row: row["created_at"], reverse=True)

    def update_commitment(
        self, user_id: str, commitment_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        row = self.get_commitment(user_id, commitment_id)
        if row is None:
            return {}
        row.update({**updates, "updated_at": _now()})
        return row

    def delete_commitment(self, user_id: str, commitment_id: str) -> bool:
        if self.get_commitment(user_id, commitment_id) is None:
            return False
        del self.commitments[commitment_id]
        for contribution_id, contribution in list(self.contributions.items()):
            if contribution["commitment_id"] == commitment_id:
                del self.contributions[contribution_id]
        return True

    def count_contributions_by_commitment(
        self, user_id: str, commitment_ids: list[str]
    ) -> dict[str, int]:
        wanted = set(commitment_ids)
        counts: dict[str, int] = {}
        for row in self.contributions.values():
            if row["user_id"] == user_id and row["commitment_id"] in wanted:
                counts[row["commitment_id"]] = counts.get(row["commitment_id"], 0) + 1
        return counts

    def insert_contribution(
        self, user_id: str, commitment_id: str, note_id: str, comment: str
    ) -> dict[str, Any] | None:
        if any(
            row["user_id"] == user_id
            and row["commitment_id"] == commitment_id
            and row["note_id"] == note_id
            for row in self.contributions.values()
        ):
            return None
        contribution_id = str(uuid.uuid4())
        now = _now()
        row = {
            "contribution_id": contribution_id,
            "commitment_id": commitment_id,
            "user_id": user_id,
            "note_id": note_id,
            "comment": comment,
            "created_at": now,
            "updated_at": now,
            "edited_at": None,
        }
        self.contributions[contribution_id] = row
        return row

    def get_contribution(
        self, user_id: str, contribution_id: str
    ) -> dict[str, Any] | None:
        row = self.contributions.get(contribution_id)
        return row if row and row["user_id"] == user_id else None

    def query_contributions(
        self, user_id: str, commitment_id: str
    ) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.contributions.values()
            if row["user_id"] == user_id and row["commitment_id"] == commitment_id
        ]
        return sorted(rows, key=lambda row: row["created_at"], reverse=True)

    def update_contribution(
        self, user_id: str, contribution_id: str, comment: str
    ) -> dict[str, Any]:
        row = self.get_contribution(user_id, contribution_id)
        if row is None:
            return {}
        now = _now()
        row.update({"comment": comment, "updated_at": now, "edited_at": now})
        return row

    def delete_contribution(self, user_id: str, contribution_id: str) -> bool:
        if self.get_contribution(user_id, contribution_id) is None:
            return False
        del self.contributions[contribution_id]
        return True

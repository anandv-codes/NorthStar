"""Supabase-backed implementation of the domain ``RecallRepository`` port.

Stores the recall loop's persistent state: scored candidates, approved cards
with SM-2 scheduling fields, immutable review history, and confirmable
commitments. Scoring and scheduling logic lives in the domain layer; this
module only persists what the domain decides.
"""
from __future__ import annotations

import os
from typing import Any

from postgrest import APIError

from .supabase_client import supabase
from .memory_repository import _execute_insert, _execute_upsert, _new_id, _utc_now

RECALL_CANDIDATES_TABLE = os.getenv("SUPABASE_RECALL_CANDIDATES_TABLE", "recall_candidates")
RECALL_CARDS_TABLE = os.getenv("SUPABASE_RECALL_CARDS_TABLE", "recall_cards")
RECALL_DECKS_TABLE = os.getenv("SUPABASE_RECALL_DECKS_TABLE", "recall_decks")
REVIEW_HISTORY_TABLE = os.getenv("SUPABASE_REVIEW_HISTORY_TABLE", "review_history")
COMMITMENTS_TABLE = os.getenv("SUPABASE_COMMITMENTS_TABLE", "commitments")


def _run(query: Any) -> list[dict[str, Any]]:
    try:
        response = query.execute()
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    return response.data if isinstance(response.data, list) else []


def _first(query: Any) -> dict[str, Any] | None:
    rows = _run(query)
    return rows[0] if rows else None


class SupabaseRecallRepository:
    """Concrete recall persistence backed by Supabase."""

    # -- Candidates --------------------------------------------------------

    def insert_candidates(
        self, user_id: str, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        now = _utc_now()
        rows = [
            {
                **candidate,
                "candidate_id": candidate.get("candidate_id") or _new_id(),
                "user_id": user_id,
                "created_at": candidate.get("created_at") or now,
                "updated_at": now,
            }
            for candidate in candidates
        ]
        return _execute_insert(RECALL_CANDIDATES_TABLE, rows)

    def upsert_candidate(self, user_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        row = {
            **candidate,
            "candidate_id": candidate.get("candidate_id") or _new_id(),
            "user_id": user_id,
            "created_at": candidate.get("created_at") or now,
            "updated_at": now,
        }
        inserted = _execute_upsert(
            RECALL_CANDIDATES_TABLE, row, on_conflict="user_id,dedupe_key"
        )
        return inserted[0] if isinstance(inserted, list) and inserted else row

    def get_candidate(self, user_id: str, candidate_id: str) -> dict[str, Any] | None:
        return _first(
            supabase.table(RECALL_CANDIDATES_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("candidate_id", candidate_id)
            .limit(1)
        )

    def query_candidates(
        self,
        user_id: str,
        status: str | None = None,
        limit: int = 100,
        source_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = supabase.table(RECALL_CANDIDATES_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        if source_note_id:
            query = query.eq("source_note_id", source_note_id)
        return _run(query.order("score", desc=True).limit(max(1, limit)))

    def update_candidate(
        self, user_id: str, candidate_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        rows = _run(
            supabase.table(RECALL_CANDIDATES_TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .eq("candidate_id", candidate_id)
        )
        return rows[0] if rows else {}

    def assign_candidates_to_deck(
        self, user_id: str, candidate_ids: list[str], deck_id: str | None
    ) -> list[dict[str, Any]]:
        if not candidate_ids:
            return []
        payload = {"deck_id": deck_id, "updated_at": _utc_now()}
        return _run(
            supabase.table(RECALL_CANDIDATES_TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .in_("candidate_id", candidate_ids)
        )

    # -- Decks -------------------------------------------------------------

    def create_deck(self, user_id: str, deck: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        row = {
            "description": None,
            "color": "neutral",
            "is_default": False,
            "sort_order": 0,
            **deck,
            "deck_id": deck.get("deck_id") or _new_id(),
            "user_id": user_id,
            "created_at": deck.get("created_at") or now,
            "updated_at": now,
        }
        inserted = _execute_insert(RECALL_DECKS_TABLE, row)
        return inserted[0] if isinstance(inserted, list) and inserted else row

    def get_deck(self, user_id: str, deck_id: str) -> dict[str, Any] | None:
        return _first(
            supabase.table(RECALL_DECKS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("deck_id", deck_id)
            .limit(1)
        )

    def find_deck_by_name(self, user_id: str, name: str) -> dict[str, Any] | None:
        return _first(
            supabase.table(RECALL_DECKS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .ilike("name", name)
            .is_("archived_at", None)
            .limit(1)
        )

    def query_decks(
        self, user_id: str, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        query = supabase.table(RECALL_DECKS_TABLE).select("*").eq("user_id", user_id)
        if not include_archived:
            query = query.is_("archived_at", None)
        return _run(query.order("sort_order", desc=False).order("created_at", desc=False))

    def update_deck(
        self, user_id: str, deck_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        rows = _run(
            supabase.table(RECALL_DECKS_TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .eq("deck_id", deck_id)
        )
        return rows[0] if rows else {}

    def query_card_stats(self, user_id: str) -> list[dict[str, Any]]:
        """Minimal card fields for deck counts, aggregated by the domain."""
        return _run(
            supabase.table(RECALL_CARDS_TABLE)
            .select("deck_id,state,status,next_due")
            .eq("user_id", user_id)
        )

    # -- Cards -------------------------------------------------------------

    def create_card(self, user_id: str, card: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        row = {
            **card,
            "card_id": card.get("card_id") or _new_id(),
            "user_id": user_id,
            "created_at": card.get("created_at") or now,
            "updated_at": now,
        }
        inserted = _execute_insert(RECALL_CARDS_TABLE, row)
        return inserted[0] if isinstance(inserted, list) and inserted else row

    def get_card(self, user_id: str, card_id: str) -> dict[str, Any] | None:
        return _first(
            supabase.table(RECALL_CARDS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("card_id", card_id)
            .limit(1)
        )

    def query_cards(
        self,
        user_id: str,
        status: str | None = None,
        due_before: str | None = None,
        limit: int = 100,
        deck_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = supabase.table(RECALL_CARDS_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        if due_before:
            query = query.lte("next_due", due_before)
        if deck_id:
            query = query.eq("deck_id", deck_id)
        return _run(query.order("next_due", desc=False).limit(max(1, limit)))

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
        search = str(q or "").strip()[:100]
        for char in ',%_()*"\\':
            search = search.replace(char, " ")
        search = " ".join(search.split())
        page_limit = max(1, min(int(limit), 100))
        page_offset = max(0, int(offset))

        query = (
            supabase.table(RECALL_CARDS_TABLE)
            .select("*", count="exact")
            .eq("user_id", user_id)
        )
        if deck_id:
            query = query.eq("deck_id", deck_id)
        if status:
            query = query.eq("status", status)
        if state:
            query = query.eq("state", state)
        if due_before:
            query = query.lte("next_due", due_before)
        if due_after:
            query = query.gt("next_due", due_after)
        if source_note_id:
            query = query.contains("source_note_ids", [source_note_id])
        if search:
            query = query.or_(f"question.ilike.%{search}%,answer.ilike.%{search}%")

        if sort == "newest":
            query = query.order("created_at", desc=True)
        elif sort == "reviews":
            query = query.order("review_count", desc=True)
        elif sort == "lapses":
            query = query.order("lapses", desc=True)
        else:
            query = query.order("next_due", desc=False)

        try:
            response = query.range(page_offset, page_offset + page_limit - 1).execute()
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        rows = response.data if isinstance(response.data, list) else []
        total = int(response.count) if response.count is not None else page_offset + len(rows)
        return {
            "cards": rows,
            "total": total,
            "limit": page_limit,
            "offset": page_offset,
        }

    def update_card(self, user_id: str, card_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        rows = _run(
            supabase.table(RECALL_CARDS_TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .eq("card_id", card_id)
        )
        return rows[0] if rows else {}

    # -- Review history ----------------------------------------------------

    def insert_review_history(self, user_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        row = {
            **entry,
            "review_id": entry.get("review_id") or _new_id(),
            "user_id": user_id,
            "reviewed_at": entry.get("reviewed_at") or _utc_now(),
        }
        inserted = _execute_insert(REVIEW_HISTORY_TABLE, row)
        return inserted[0] if isinstance(inserted, list) and inserted else row

    def query_review_history(self, user_id: str, card_id: str) -> list[dict[str, Any]]:
        return _run(
            supabase.table(REVIEW_HISTORY_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("card_id", card_id)
            .order("reviewed_at", desc=True)
        )

    # -- Commitments -------------------------------------------------------

    def upsert_commitment(self, user_id: str, commitment: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        row = {
            **commitment,
            "commitment_id": commitment.get("commitment_id") or _new_id(),
            "user_id": user_id,
            "created_at": commitment.get("created_at") or now,
            "updated_at": now,
        }
        inserted = _execute_upsert(COMMITMENTS_TABLE, row, on_conflict="commitment_id")
        return inserted[0] if isinstance(inserted, list) and inserted else row

    def query_commitments(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
        query = supabase.table(COMMITMENTS_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        return _run(query.order("created_at", desc=True))

    def update_commitment(
        self, user_id: str, commitment_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        rows = _run(
            supabase.table(COMMITMENTS_TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .eq("commitment_id", commitment_id)
        )
        return rows[0] if rows else {}


_DEFAULT_RECALL_REPOSITORY: SupabaseRecallRepository | None = None


def get_recall_repository() -> SupabaseRecallRepository:
    """Return the process-wide default ``RecallRepository`` implementation."""
    global _DEFAULT_RECALL_REPOSITORY
    if _DEFAULT_RECALL_REPOSITORY is None:
        _DEFAULT_RECALL_REPOSITORY = SupabaseRecallRepository()
    return _DEFAULT_RECALL_REPOSITORY

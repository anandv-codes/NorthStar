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
    ) -> list[dict[str, Any]]:
        query = supabase.table(RECALL_CARDS_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        if due_before:
            query = query.lte("next_due", due_before)
        return _run(query.order("next_due", desc=False).limit(max(1, limit)))

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

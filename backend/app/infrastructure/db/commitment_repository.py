"""Supabase persistence for user-authored commitments and contributions."""
from __future__ import annotations

import os
from typing import Any

from postgrest import APIError

from .memory_repository import _execute_insert, _new_id, _utc_now
from .supabase_client import supabase

USER_COMMITMENTS_TABLE = os.getenv(
    "SUPABASE_USER_COMMITMENTS_TABLE", "user_commitments"
)
COMMITMENT_CONTRIBUTIONS_TABLE = os.getenv(
    "SUPABASE_COMMITMENT_CONTRIBUTIONS_TABLE", "commitment_contributions"
)
NOTES_TABLE = os.getenv("SUPABASE_NOTES_TABLE", "notes")


def _run(query: Any) -> list[dict[str, Any]]:
    try:
        response = query.execute()
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    return response.data if isinstance(response.data, list) else []


def _first(query: Any) -> dict[str, Any] | None:
    rows = _run(query)
    return rows[0] if rows else None


def _is_duplicate_error(exc: APIError) -> bool:
    payload = f"{getattr(exc, 'code', '')} {exc}".lower()
    return "23505" in payload or "duplicate key" in payload


class SupabaseCommitmentRepository:
    """Concrete commitment persistence backed by Supabase."""

    def create_commitment(self, user_id: str, text: str) -> dict[str, Any]:
        now = _utc_now()
        row = {
            "commitment_id": _new_id(),
            "user_id": user_id,
            "text": text,
            "progress": 0,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        inserted = _execute_insert(USER_COMMITMENTS_TABLE, row)
        return inserted[0] if isinstance(inserted, list) and inserted else row

    def get_commitment(
        self, user_id: str, commitment_id: str
    ) -> dict[str, Any] | None:
        return _first(
            supabase.table(USER_COMMITMENTS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("commitment_id", commitment_id)
            .limit(1)
        )

    def query_commitments(
        self, user_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        query = (
            supabase.table(USER_COMMITMENTS_TABLE)
            .select("*")
            .eq("user_id", user_id)
        )
        if status:
            query = query.eq("status", status)
        return _run(query.order("created_at", desc=True))

    def update_commitment(
        self, user_id: str, commitment_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        rows = _run(
            supabase.table(USER_COMMITMENTS_TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .eq("commitment_id", commitment_id)
        )
        return rows[0] if rows else {}

    def delete_commitment(self, user_id: str, commitment_id: str) -> bool:
        if self.get_commitment(user_id, commitment_id) is None:
            return False
        _run(
            supabase.table(USER_COMMITMENTS_TABLE)
            .delete()
            .eq("user_id", user_id)
            .eq("commitment_id", commitment_id)
        )
        return True

    def count_contributions_by_commitment(
        self, user_id: str, commitment_ids: list[str]
    ) -> dict[str, int]:
        if not commitment_ids:
            return {}
        rows = _run(
            supabase.table(COMMITMENT_CONTRIBUTIONS_TABLE)
            .select("commitment_id")
            .eq("user_id", user_id)
            .in_("commitment_id", commitment_ids)
        )
        counts: dict[str, int] = {}
        for row in rows:
            commitment_id = str(row.get("commitment_id") or "")
            if commitment_id:
                counts[commitment_id] = counts.get(commitment_id, 0) + 1
        return counts

    def insert_contribution(
        self,
        user_id: str,
        commitment_id: str,
        note_id: str,
        comment: str,
    ) -> dict[str, Any] | None:
        now = _utc_now()
        row = {
            "contribution_id": _new_id(),
            "commitment_id": commitment_id,
            "user_id": user_id,
            "note_id": note_id,
            "comment": comment,
            "created_at": now,
            "updated_at": now,
            "edited_at": None,
        }
        try:
            response = supabase.table(COMMITMENT_CONTRIBUTIONS_TABLE).insert(row).execute()
        except APIError as exc:
            if _is_duplicate_error(exc):
                return None
            raise RuntimeError(str(exc)) from exc
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else None

    def get_contribution(
        self, user_id: str, contribution_id: str
    ) -> dict[str, Any] | None:
        return _first(
            supabase.table(COMMITMENT_CONTRIBUTIONS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("contribution_id", contribution_id)
            .limit(1)
        )

    def query_contributions(
        self, user_id: str, commitment_id: str
    ) -> list[dict[str, Any]]:
        rows = _run(
            supabase.table(COMMITMENT_CONTRIBUTIONS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("commitment_id", commitment_id)
            .order("created_at", desc=True)
        )
        note_ids = [str(row.get("note_id")) for row in rows if row.get("note_id")]
        if not note_ids:
            return rows

        notes = _run(
            supabase.table(NOTES_TABLE)
            .select("note_id,created_at,raw_text")
            .eq("user_id", user_id)
            .in_("note_id", note_ids)
        )
        notes_by_id = {str(note.get("note_id")): note for note in notes}
        enriched: list[dict[str, Any]] = []
        for row in rows:
            note = notes_by_id.get(str(row.get("note_id") or ""), {})
            raw_text = str(note.get("raw_text") or "")
            enriched.append(
                {
                    **row,
                    "source_note_created_at": note.get("created_at"),
                    "source_note_excerpt": raw_text[:160].strip() or None,
                }
            )
        return enriched

    def update_contribution(
        self, user_id: str, contribution_id: str, comment: str
    ) -> dict[str, Any]:
        now = _utc_now()
        rows = _run(
            supabase.table(COMMITMENT_CONTRIBUTIONS_TABLE)
            .update({"comment": comment, "updated_at": now, "edited_at": now})
            .eq("user_id", user_id)
            .eq("contribution_id", contribution_id)
        )
        return rows[0] if rows else {}

    def delete_contribution(self, user_id: str, contribution_id: str) -> bool:
        if self.get_contribution(user_id, contribution_id) is None:
            return False
        _run(
            supabase.table(COMMITMENT_CONTRIBUTIONS_TABLE)
            .delete()
            .eq("user_id", user_id)
            .eq("contribution_id", contribution_id)
        )
        return True


_DEFAULT_REPOSITORY: SupabaseCommitmentRepository | None = None


def get_commitment_repository() -> SupabaseCommitmentRepository:
    """Return the process-wide default ``CommitmentRepository`` implementation."""
    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = SupabaseCommitmentRepository()
    return _DEFAULT_REPOSITORY

"""Supabase-backed implementation of the domain ``PeriodSummaryRepository`` port."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from postgrest import APIError

from .supabase_client import supabase

PERIOD_SUMMARIES_TABLE = os.getenv("SUPABASE_PERIOD_SUMMARIES_TABLE", "period_summaries")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabasePeriodSummaryRepository:
    """Concrete daily/weekly summary persistence backed by Supabase."""

    def get_period_summary(self, user_id: str, period_type: str, period_start: str) -> dict[str, Any] | None:
        try:
            response = (
                supabase.table(PERIOD_SUMMARIES_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("period_type", period_type)
                .eq("period_start", period_start)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else None

    def list_period_summaries_in_range(
        self, user_id: str, period_type: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(PERIOD_SUMMARIES_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("period_type", period_type)
                .gte("period_start", start_date)
                .lt("period_start", end_date)
                .order("period_start")
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def upsert_period_summary(
        self,
        user_id: str,
        period_type: str,
        period_start: str,
        period_end: str,
        narrative: str,
        stats: dict[str, Any],
        source_note_count: int,
    ) -> dict[str, Any]:
        row = {
            "summary_id": str(uuid.uuid4()),
            "user_id": user_id,
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "narrative": narrative,
            "stats": stats,
            "source_note_count": source_note_count,
            "generated_at": _utc_now(),
        }
        try:
            response = (
                supabase.table(PERIOD_SUMMARIES_TABLE)
                .upsert(row, on_conflict="user_id,period_type,period_start")
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else row


_DEFAULT_REPOSITORY: SupabasePeriodSummaryRepository | None = None


def get_period_summary_repository() -> SupabasePeriodSummaryRepository:
    """Return the process-wide default ``PeriodSummaryRepository`` implementation."""
    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = SupabasePeriodSummaryRepository()
    return _DEFAULT_REPOSITORY

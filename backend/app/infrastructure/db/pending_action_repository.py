"""Supabase-backed implementation of the domain ``PendingChatActionRepository`` port."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from postgrest import APIError

from .supabase_client import supabase

PENDING_CHAT_ACTIONS_TABLE = os.getenv("SUPABASE_PENDING_CHAT_ACTIONS_TABLE", "pending_chat_actions")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabasePendingChatActionRepository:
    """Concrete pending tool-action persistence backed by Supabase."""

    def create_pending_action(
        self,
        user_id: str,
        thread_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        description: str,
        confirmed_message: str,
        expires_at: str,
    ) -> dict[str, Any]:
        # Only one pending action per thread at a time.
        existing = self.get_latest_pending_action(user_id=user_id, thread_id=thread_id)
        if existing:
            self.resolve_pending_action(
                user_id=user_id, pending_action_id=existing["pending_action_id"], status="cancelled"
            )

        row = {
            "pending_action_id": str(uuid.uuid4()),
            "user_id": user_id,
            "thread_id": thread_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "description": description,
            "confirmed_message": confirmed_message,
            "status": "pending",
            "created_at": _utc_now(),
            "resolved_at": None,
            "expires_at": expires_at,
        }
        try:
            response = supabase.table(PENDING_CHAT_ACTIONS_TABLE).insert(row).execute()
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else row

    def get_latest_pending_action(self, user_id: str, thread_id: str) -> dict[str, Any] | None:
        try:
            response = (
                supabase.table(PENDING_CHAT_ACTIONS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("thread_id", thread_id)
                .eq("status", "pending")
                .gt("expires_at", _utc_now())
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else None

    def resolve_pending_action(self, user_id: str, pending_action_id: str, status: str) -> dict[str, Any]:
        updates = {"status": status, "resolved_at": _utc_now()}
        try:
            response = (
                supabase.table(PENDING_CHAT_ACTIONS_TABLE)
                .update(updates)
                .eq("user_id", user_id)
                .eq("pending_action_id", pending_action_id)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else {}


_DEFAULT_REPOSITORY: SupabasePendingChatActionRepository | None = None


def get_pending_chat_action_repository() -> SupabasePendingChatActionRepository:
    """Return the process-wide default ``PendingChatActionRepository`` implementation."""
    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = SupabasePendingChatActionRepository()
    return _DEFAULT_REPOSITORY

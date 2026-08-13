"""Supabase-backed implementation of the domain ``ChatRepository`` port.

Thin adapter over ``supabase_client``'s chat thread/message functions so the
domain layer depends on the ``ChatRepository`` protocol instead of importing
``supabase_client`` directly.
"""
from __future__ import annotations

from typing import Any

from . import supabase_client


class SupabaseChatRepository:
    """Concrete chat thread/message persistence backed by Supabase."""

    def create_chat_thread(self, user_id: str, title: str | None = None) -> dict[str, Any]:
        return supabase_client.create_chat_thread(user_id=user_id, title=title)

    def get_chat_thread_item(self, user_id: str, thread_id: str) -> dict[str, Any]:
        return supabase_client.get_chat_thread_item(user_id=user_id, thread_id=thread_id)

    def update_chat_thread_item(self, user_id: str, thread_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        return supabase_client.update_chat_thread_item(user_id=user_id, thread_id=thread_id, updates=updates)

    def touch_chat_thread_item(self, user_id: str, thread_id: str) -> dict[str, Any]:
        return supabase_client.touch_chat_thread_item(user_id=user_id, thread_id=thread_id)

    def insert_chat_message_item(
        self,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return supabase_client.insert_chat_message_item(
            user_id=user_id,
            thread_id=thread_id,
            role=role,
            content=content,
            intent=intent,
            metadata=metadata,
        )

    def query_chat_messages_for_thread(self, user_id: str, thread_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return supabase_client.query_chat_messages_for_thread(user_id=user_id, thread_id=thread_id, limit=limit)


_DEFAULT_REPOSITORY: SupabaseChatRepository | None = None


def get_chat_repository() -> SupabaseChatRepository:
    """Return the process-wide default ``ChatRepository`` implementation."""
    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = SupabaseChatRepository()
    return _DEFAULT_REPOSITORY

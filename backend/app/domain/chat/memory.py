from __future__ import annotations

from typing import Any

from ..constants import SHORT_TERM_WINDOW, SUMMARY_MAX_CHARS, SUMMARY_TRIGGER_MESSAGES
from ...infrastructure.db.chat_repository import get_chat_repository
from ..ports import ChatRepository


def ensure_chat_thread(
    user_id: str, thread_id: str | None, title: str | None = None, repo: ChatRepository | None = None
) -> dict[str, Any]:
    repo = repo or get_chat_repository()
    if thread_id:
        thread = repo.get_chat_thread_item(user_id=user_id, thread_id=thread_id)
        if thread:
            return thread
    return repo.create_chat_thread(user_id=user_id, title=title)


def store_chat_message(
    user_id: str,
    thread_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    metadata: dict[str, Any] | None = None,
    repo: ChatRepository | None = None,
) -> dict[str, Any]:
    repo = repo or get_chat_repository()
    message = repo.insert_chat_message_item(
        user_id=user_id,
        thread_id=thread_id,
        role=role,
        content=content,
        intent=intent,
        metadata=metadata,
    )
    repo.touch_chat_thread_item(user_id=user_id, thread_id=thread_id)
    return message


def load_recent_chat_messages(
    user_id: str, thread_id: str, limit: int = SHORT_TERM_WINDOW, repo: ChatRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_chat_repository()
    return repo.query_chat_messages_for_thread(user_id=user_id, thread_id=thread_id, limit=limit)


def build_short_term_context(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "No recent chat context."

    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user").strip().capitalize()
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "No recent chat context."


def should_refresh_summary(messages: list[dict[str, Any]], existing_summary: str | None) -> bool:
    if len(messages) <= SUMMARY_TRIGGER_MESSAGES:
        return False

    summary_length = len(str(existing_summary or "").strip())
    return summary_length < SUMMARY_MAX_CHARS


def refresh_thread_summary(
    user_id: str,
    thread_id: str,
    messages: list[dict[str, Any]],
    existing_summary: str | None = None,
    repo: ChatRepository | None = None,
) -> str | None:
    repo = repo or get_chat_repository()
    if not should_refresh_summary(messages, existing_summary):
        return existing_summary

    older_messages = messages[:-SHORT_TERM_WINDOW]
    if not older_messages:
        return existing_summary

    summary_lines: list[str] = []
    if existing_summary:
        summary_lines.append(str(existing_summary).strip())

    for message in older_messages[-SUMMARY_TRIGGER_MESSAGES:]:
        role = str(message.get("role") or "user").strip().capitalize()
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        summary_lines.append(f"{role}: {content[:180]}")

    summary = "\n".join(line for line in summary_lines if line).strip()
    if not summary:
        return existing_summary

    updated = repo.update_chat_thread_item(
        user_id=user_id,
        thread_id=thread_id,
        updates={
            "summary": summary[:SUMMARY_MAX_CHARS],
        },
    )
    return str(updated.get("summary") or summary)

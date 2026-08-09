from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ...infrastructure.db.supabase_client import get_chat_thread_item
from ...infrastructure.llm.prompt_logger import append_pipeline_log
from ..routing.contracts import RoutingContext
from .memory import (
    SHORT_TERM_WINDOW,
    ensure_chat_thread,
    load_recent_chat_messages,
    refresh_thread_summary,
    store_chat_message,
)
from .orchestrator import build_chat_routing_orchestrator


CHAT_ROUTING_ORCHESTRATOR = build_chat_routing_orchestrator()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _title_from_message(message: str) -> str:
    cleaned = " ".join(str(message or "").strip().split())
    if not cleaned:
        return "New chat"
    return cleaned[:60]


def handle_chat_message(user_id: str, message: str, thread_id: str | None = None) -> dict[str, Any]:
    normalized_message = str(message or "").strip()
    if not normalized_message:
        raise ValueError("message is required")

    append_pipeline_log(
        "chat service",
        [
            "chat message received",
            f"user: {user_id}",
            f"thread: {thread_id or 'new'}",
            f"message: {_shorten(normalized_message)}",
        ],
    )

    thread = ensure_chat_thread(user_id=user_id, thread_id=thread_id, title=_title_from_message(normalized_message))
    thread_id = str(thread.get("thread_id") or "")
    if not thread_id:
        thread_id = str(uuid.uuid4())
    append_pipeline_log(
        "chat service",
        [
            f"thread ready: {thread_id}",
            f"title: {_shorten(str(thread.get('title') or _title_from_message(normalized_message)))}",
        ],
    )

    user_message_row = store_chat_message(
        user_id=user_id,
        thread_id=thread_id,
        role="user",
        content=normalized_message,
        metadata={"created_at": _utc_now()},
    )
    append_pipeline_log(
        "chat service",
        [
            f"user message stored: {user_message_row.get('message_id')}",
        ],
    )

    recent_messages = _load_recent_messages(
        user_id=user_id,
        thread_id=thread_id,
        user_message_id=str(user_message_row.get("message_id") or ""),
        user_message=normalized_message,
    )
    thread_summary = str(thread.get("summary") or "").strip()

    routing_context = RoutingContext(
        user_id=user_id,
        thread_id=thread_id,
        message=normalized_message,
        recent_messages=recent_messages,
        thread_summary=thread_summary or None,
    )
    try:
        outcome = CHAT_ROUTING_ORCHESTRATOR.route(routing_context)
    except Exception as exc:
        append_pipeline_log(
            "chat service",
            [
                f"chat routing failed: {exc}",
            ],
        )
        raise
    append_pipeline_log(
        "chat service",
        [
            f"chat routing completed: {outcome.decision.route}",
            f"intent: {outcome.decision.intent_kind}",
        ],
    )

    assistant_message = outcome.assistant_message or outcome.decision.fallback_message or _default_fallback(normalized_message)
    assistant_message_row = store_chat_message(
        user_id=user_id,
        thread_id=thread_id,
        role="assistant",
        content=assistant_message,
        intent=outcome.decision.intent_kind,
        metadata={
            "routing": outcome.metadata,
            "route": outcome.decision.route,
            "knowledge_error": outcome.metadata.get("knowledge_error"),
        },
    )
    append_pipeline_log(
        "chat service",
        [
            f"assistant message stored: {assistant_message_row.get('message_id')}",
            f"fallback used: {assistant_message == outcome.decision.fallback_message or assistant_message == _default_fallback(normalized_message)}",
        ],
    )

    full_messages = load_recent_chat_messages(user_id=user_id, thread_id=thread_id, limit=100)
    updated_summary = refresh_thread_summary(
        user_id=user_id,
        thread_id=thread_id,
        messages=full_messages,
        existing_summary=thread_summary or None,
    )
    updated_thread = thread
    if updated_summary != thread_summary:
        updated_thread = get_chat_thread_item(user_id=user_id, thread_id=thread_id) or thread

    thread_payload = {
        "thread_id": thread_id,
        "user_id": user_id,
        "title": updated_thread.get("title") or _title_from_message(normalized_message),
        "summary": updated_summary,
        "summary_updated_at": updated_thread.get("summary_updated_at"),
        "created_at": updated_thread.get("created_at"),
        "updated_at": updated_thread.get("updated_at"),
        "messages": full_messages,
    }

    return {
        "thread": thread_payload,
        "user_message": user_message_row,
        "assistant_message": assistant_message_row,
        "intent": outcome.metadata.get("intent"),
        "routing": _routing_payload(outcome),
        "plan": outcome.metadata.get("plan", []),
        "knowledge_error": outcome.metadata.get("knowledge_error"),
        "grounding": outcome.metadata.get("grounding"),
    }


def _load_recent_messages(user_id: str, thread_id: str, user_message_id: str, user_message: str) -> list[dict[str, Any]]:
    recent_messages = load_recent_chat_messages(user_id=user_id, thread_id=thread_id, limit=SHORT_TERM_WINDOW)
    filtered_messages = [
        item
        for item in recent_messages
        if str(item.get("message_id") or "") != user_message_id
    ]
    filtered_messages.append(
        {
            "message_id": user_message_id,
            "role": "user",
            "content": user_message,
            "created_at": _utc_now(),
        }
    )
    return filtered_messages


def _routing_payload(outcome: Any) -> dict[str, Any]:
    decision = outcome.decision
    return {
        "route": decision.route,
        "confidence": decision.confidence,
        "allow_answer": decision.allow_answer,
        "reasons": list(decision.reasons),
        "source_refs": list(decision.source_refs),
        "fallback_message": decision.fallback_message,
    }


def _default_fallback(message: str) -> str:
    return f"I couldn't find enough grounded context for '{message}'."


def _shorten(text: str, limit: int = 96) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ...infrastructure.db.chat_repository import get_chat_repository
from ...infrastructure.db.pending_action_repository import get_pending_chat_action_repository
from ...infrastructure.llm.llm_config import PENDING_ACTION_EXPIRY_MINUTES
from ...infrastructure.llm.prompt_logger import append_pipeline_log
from ..ports import ChatRepository, PendingChatActionRepository
from .confirmation import classify_confirmation
from .tool_resolver import execute_tool_call, resolve_tool_call
from .routing_contracts import RoutingContext
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


def handle_chat_message(
    user_id: str,
    message: str,
    thread_id: str | None = None,
    repo: ChatRepository | None = None,
    pending_repo: PendingChatActionRepository | None = None,
) -> dict[str, Any]:
    repo = repo or get_chat_repository()
    pending_repo = pending_repo or get_pending_chat_action_repository()
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

    thread = ensure_chat_thread(
        user_id=user_id, thread_id=thread_id, title=_title_from_message(normalized_message), repo=repo
    )
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
        repo=repo,
    )
    append_pipeline_log(
        "chat service",
        [
            f"user message stored: {user_message_row.get('message_id')}",
        ],
    )

    pending_outcome = _try_resolve_pending_action(
        user_id=user_id,
        thread_id=thread_id,
        normalized_message=normalized_message,
        thread=thread,
        repo=repo,
        pending_repo=pending_repo,
    )
    if pending_outcome is not None:
        return pending_outcome

    recent_messages = _load_recent_messages(
        user_id=user_id,
        thread_id=thread_id,
        user_message_id=str(user_message_row.get("message_id") or ""),
        user_message=normalized_message,
        repo=repo,
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
    pending_action_proposed = None
    if outcome.decision.needs_tools:
        pending_action_proposed = _try_propose_tool_call(
            user_id=user_id,
            thread_id=thread_id,
            normalized_message=normalized_message,
            pending_repo=pending_repo,
        )
        if pending_action_proposed is not None:
            assistant_message = f"{pending_action_proposed['description']} Should I go ahead? (yes/no)"

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
            "pending_action": pending_action_proposed,
        },
        repo=repo,
    )
    append_pipeline_log(
        "chat service",
        [
            f"assistant message stored: {assistant_message_row.get('message_id')}",
            f"fallback used: {assistant_message == outcome.decision.fallback_message or assistant_message == _default_fallback(normalized_message)}",
        ],
    )

    full_messages = load_recent_chat_messages(user_id=user_id, thread_id=thread_id, limit=100, repo=repo)
    updated_summary = refresh_thread_summary(
        user_id=user_id,
        thread_id=thread_id,
        messages=full_messages,
        existing_summary=thread_summary or None,
        repo=repo,
    )
    updated_thread = thread
    if updated_summary != thread_summary:
        updated_thread = repo.get_chat_thread_item(user_id=user_id, thread_id=thread_id) or thread

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
        "pending_action": pending_action_proposed,
    }


def _try_resolve_pending_action(
    user_id: str,
    thread_id: str,
    normalized_message: str,
    thread: dict[str, Any],
    repo: ChatRepository,
    pending_repo: PendingChatActionRepository,
) -> dict[str, Any] | None:
    """If there's a pending tool action awaiting yes/no for this thread, resolve it and
    short-circuit the normal routing pipeline. Returns the full response dict if handled,
    or None if there was no pending action (caller should continue with normal routing)."""
    pending = pending_repo.get_latest_pending_action(user_id=user_id, thread_id=thread_id)
    if not pending:
        return None

    decision = classify_confirmation(normalized_message)
    if decision == "unclear":
        assistant_text = (
            f"Just to confirm — did you want me to {pending['description']}? Please reply yes or no."
        )
    elif decision == "confirm":
        try:
            execute_tool_call(user_id=user_id, tool_name=pending["tool_name"], args=pending["tool_args"])
            pending_repo.resolve_pending_action(
                user_id=user_id, pending_action_id=pending["pending_action_id"], status="confirmed"
            )
            assistant_text = pending["confirmed_message"]
        except Exception as exc:
            pending_repo.resolve_pending_action(
                user_id=user_id, pending_action_id=pending["pending_action_id"], status="cancelled"
            )
            append_pipeline_log("chat service", [f"pending tool action execution failed: {exc}"])
            assistant_text = "Sorry, I couldn't make that change — please try again."
    else:  # deny
        pending_repo.resolve_pending_action(
            user_id=user_id, pending_action_id=pending["pending_action_id"], status="cancelled"
        )
        assistant_text = "Okay, I won't make that change."

    assistant_message_row = store_chat_message(
        user_id=user_id,
        thread_id=thread_id,
        role="assistant",
        content=assistant_text,
        intent="tool_confirmation",
        metadata={"pending_action_resolution": decision, "pending_action_id": pending["pending_action_id"]},
        repo=repo,
    )

    full_messages = load_recent_chat_messages(user_id=user_id, thread_id=thread_id, limit=100, repo=repo)
    user_message_row = next(
        (item for item in reversed(full_messages) if str(item.get("role")) == "user"),
        {"message_id": "", "role": "user", "content": normalized_message},
    )
    thread_payload = {
        "thread_id": thread_id,
        "user_id": user_id,
        "title": thread.get("title") or _title_from_message(normalized_message),
        "summary": thread.get("summary"),
        "summary_updated_at": thread.get("summary_updated_at"),
        "created_at": thread.get("created_at"),
        "updated_at": thread.get("updated_at"),
        "messages": full_messages,
    }
    return {
        "thread": thread_payload,
        "user_message": user_message_row,
        "assistant_message": assistant_message_row,
        "intent": {
            "kind": "tool_confirmation",
            "confidence": 1.0,
            "needs_retrieval": False,
            "needs_tools": True,
            "direct_answer": True,
            "reasons": [f"pending_action:{decision}"],
        },
        "routing": {
            "route": "tool",
            "confidence": 1.0,
            "allow_answer": True,
            "reasons": [f"pending_action:{decision}"],
            "source_refs": [],
            "fallback_message": None,
        },
        "plan": [],
        "knowledge_error": None,
        "grounding": None,
        "pending_action": None,
    }


def _try_propose_tool_call(
    user_id: str,
    thread_id: str,
    normalized_message: str,
    pending_repo: PendingChatActionRepository,
) -> dict[str, Any] | None:
    try:
        proposal = resolve_tool_call(user_id=user_id, message=normalized_message)
    except Exception as exc:
        append_pipeline_log("chat service", [f"tool resolution failed: {exc}"])
        return None
    if proposal is None:
        return None

    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=PENDING_ACTION_EXPIRY_MINUTES)).isoformat()
    pending_row = pending_repo.create_pending_action(
        user_id=user_id,
        thread_id=thread_id,
        tool_name=proposal.tool_name,
        tool_args=proposal.args,
        description=proposal.description,
        confirmed_message=proposal.confirmed_message,
        expires_at=expires_at,
    )
    return {
        "pending_action_id": pending_row.get("pending_action_id"),
        "tool_name": proposal.tool_name,
        "description": proposal.description,
    }


def _load_recent_messages(
    user_id: str, thread_id: str, user_message_id: str, user_message: str, repo: ChatRepository | None = None
) -> list[dict[str, Any]]:
    recent_messages = load_recent_chat_messages(user_id=user_id, thread_id=thread_id, limit=SHORT_TERM_WINDOW, repo=repo)
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

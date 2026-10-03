import os
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import httpx
from postgrest import APIError
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_NOTES_TABLE = os.getenv("SUPABASE_NOTES_TABLE", "notes")
CHAT_THREADS_TABLE = os.getenv("SUPABASE_CHAT_THREADS_TABLE", "chat_threads")
CHAT_MESSAGES_TABLE = os.getenv("SUPABASE_CHAT_MESSAGES_TABLE", "chat_messages")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in the environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def _execute_with_retry(build_request: Callable[[], Any], retries: int = 1) -> Any:
    """Call `.execute()` on a freshly-built query, retrying once on a dead pooled connection.

    `supabase` above is a single process-wide client reused for the app's lifetime; if its
    underlying httpx connection sits idle too long (e.g. between SQS-polled note jobs), Supabase's
    infra can close the socket server-side. Reusing that pooled connection then raises
    httpx.RemoteProtocolError ("Server disconnected without sending a response") instead of a
    normal APIError. `build_request` must construct the query from scratch so the retry opens a
    new connection rather than resending an already-consumed request.
    """
    last_exc: httpx.RemoteProtocolError | None = None
    for attempt in range(retries + 1):
        try:
            return build_request().execute()
        except httpx.RemoteProtocolError as exc:
            last_exc = exc
            logger.warning(f"Supabase request hit a stale connection (attempt {attempt + 1}); retrying: {exc}")
    assert last_exc is not None
    raise last_exc


#Insert new note
def put_note_item(item: Dict[str, Any]) -> Any:
    logger.info(f"Inserting note: {item.get('note_id')}")
    try:
        response = _execute_with_retry(lambda: supabase.table(SUPABASE_NOTES_TABLE).insert(item))
    except APIError as e:
        raise RuntimeError(str(e))
    logger.info("Note inserted successfully")
    return response.data

#Update existing note 
def update_note_item(user_id: str, note_id: str, updates: Dict[str, Any]) -> Any:
    logger.info(f"Updating note: {note_id} user:{user_id} with status={updates.get('status')}")
    try:
        response = _execute_with_retry(
            lambda: supabase.table(SUPABASE_NOTES_TABLE)
            .update(updates)
            .eq("user_id", user_id)
            .eq("note_id", note_id)
        )
    except APIError as e:
        raise RuntimeError(str(e))
    logger.info("Note updated successfully")
    return response.data

#Fetch single note by user_id and note_id
def get_note_item(user_id: str, note_id: str) -> Dict[str, Any]:
    logger.info(f"Fetching note: {note_id}")
    try:
        response = _execute_with_retry(
            lambda: supabase.table(SUPABASE_NOTES_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("note_id", note_id)
            .maybe_single()
        )
    except APIError as e:
        logger.warning(f"Fetch error: {e}")
        return {}
    if response is None:
        logger.info("No note found")
        return {}
    result = response.data if isinstance(response.data, dict) else {}
    logger.info(f"Note found, status: {result.get('status')}")
    return result

#Query notes for a user, optionally filtering by status
def query_notes_for_user(user_id: str, status: str | None = None) -> List[Dict[str, Any]]:
    logger.info(f"Querying notes for user: {user_id}, status={status}")
    def build_query():
        query = supabase.table(SUPABASE_NOTES_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        return query

    try:
        response = _execute_with_retry(build_query)
    except APIError as e:
        raise RuntimeError(str(e))
    result = response.data if isinstance(response.data, list) else []
    logger.info(f"Found {len(result)} notes")
    return result


class SupabaseNoteRepository:
    """Concrete ``NoteRepository`` implementation backed by Supabase."""

    def query_notes_for_user(self, user_id: str, status: str | None = None) -> List[Dict[str, Any]]:
        return query_notes_for_user(user_id=user_id, status=status)


_DEFAULT_NOTE_REPOSITORY: SupabaseNoteRepository | None = None


def get_note_repository() -> SupabaseNoteRepository:
    """Return the process-wide default ``NoteRepository`` implementation."""
    global _DEFAULT_NOTE_REPOSITORY
    if _DEFAULT_NOTE_REPOSITORY is None:
        _DEFAULT_NOTE_REPOSITORY = SupabaseNoteRepository()
    return _DEFAULT_NOTE_REPOSITORY


def create_chat_thread(user_id: str, title: str | None = None) -> Dict[str, Any]:
    row = {
        "thread_id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": title,
        "summary": "",
        "summary_updated_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = _execute_with_retry(lambda: supabase.table(CHAT_THREADS_TABLE).insert(row))
    except APIError as e:
        raise RuntimeError(str(e))
    result = response.data if isinstance(response.data, list) and response.data else row
    return result[0] if isinstance(result, list) and result else result


def get_chat_thread_item(user_id: str, thread_id: str) -> Dict[str, Any]:
    try:
        response = _execute_with_retry(
            lambda: supabase.table(CHAT_THREADS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("thread_id", thread_id)
            .maybe_single()
        )
    except APIError as e:
        raise RuntimeError(str(e))
    if response is None or response.data is None:
        return {}
    return response.data if isinstance(response.data, dict) else {}


def update_chat_thread_item(user_id: str, thread_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    updates = {**updates, "updated_at": datetime.now(timezone.utc).isoformat()}
    if "summary" in updates:
        updates["summary_updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        response = _execute_with_retry(
            lambda: supabase.table(CHAT_THREADS_TABLE)
            .update(updates)
            .eq("user_id", user_id)
            .eq("thread_id", thread_id)
        )
    except APIError as e:
        raise RuntimeError(str(e))
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else {}


def touch_chat_thread_item(user_id: str, thread_id: str) -> Dict[str, Any]:
    return update_chat_thread_item(user_id=user_id, thread_id=thread_id, updates={})


def insert_chat_message_item(
    user_id: str,
    thread_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row = {
        "message_id": str(uuid.uuid4()),
        "thread_id": thread_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "intent": intent,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = _execute_with_retry(lambda: supabase.table(CHAT_MESSAGES_TABLE).insert(row))
    except APIError as e:
        raise RuntimeError(str(e))
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else row


def query_chat_messages_for_thread(user_id: str, thread_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    clamped_limit = max(1, min(limit, 100))
    try:
        response = _execute_with_retry(
            lambda: supabase.table(CHAT_MESSAGES_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("thread_id", thread_id)
            .order("created_at", desc=True)
            .limit(clamped_limit)
        )
    except APIError as e:
        raise RuntimeError(str(e))
    rows = response.data if isinstance(response.data, list) else []
    return list(reversed(rows))

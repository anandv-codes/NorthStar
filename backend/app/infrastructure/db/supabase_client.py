import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from postgrest import APIError
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_NOTES_TABLE = os.getenv("SUPABASE_NOTES_TABLE", "notes")
CHAT_THREADS_TABLE = os.getenv("SUPABASE_CHAT_THREADS_TABLE", "chat_threads")
CHAT_MESSAGES_TABLE = os.getenv("SUPABASE_CHAT_MESSAGES_TABLE", "chat_messages")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in the environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

#Insert new note
def put_note_item(item: Dict[str, Any]) -> Any:
    print(f"[SUPABASE] Inserting note: {item.get('note_id')}")
    try:
        response = supabase.table(SUPABASE_NOTES_TABLE).insert(item).execute()
    except APIError as e:
        raise RuntimeError(str(e))
    print(f"[SUPABASE] Note inserted successfully")
    return response.data

#Update existing note 
def update_note_item(user_id: str, note_id: str, updates: Dict[str, Any]) -> Any:
    print(f"[SUPABASE] Updating note: {note_id} user:{user_id} with status={updates.get('status')}")
    try:
        response = (
            supabase.table(SUPABASE_NOTES_TABLE)
            .update(updates)
            .eq("user_id", user_id)
            .eq("note_id", note_id)
            .execute()
        )
    except APIError as e:
        raise RuntimeError(str(e))
    print(f"[SUPABASE] Note updated successfully")
    return response.data

#Fetch single note by user_id and note_id
def get_note_item(user_id: str, note_id: str) -> Dict[str, Any]:
    print(f"[SUPABASE] Fetching note: {note_id}")
    try:
        response = (
            supabase.table(SUPABASE_NOTES_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("note_id", note_id)
            .maybe_single()
            .execute()
        )
    except APIError as e:
        print(f"[SUPABASE] Fetch error: {e}")
        return {}
    if response is None:
        print("[SUPABASE] No note found")
        return {}
    result = response.data if isinstance(response.data, dict) else {}
    print(f"[SUPABASE] Note found, status: {result.get('status')}")
    return result

#Query notes for a user, optionally filtering by status
def query_notes_for_user(user_id: str, status: str | None = None) -> List[Dict[str, Any]]:
    print(f"[SUPABASE] Querying notes for user: {user_id}, status={status}")
    query = supabase.table(SUPABASE_NOTES_TABLE).select("*").eq("user_id", user_id)
    if status:
        query = query.eq("status", status)
    try:
        response = query.execute()
    except APIError as e:
        raise RuntimeError(str(e))
    result = response.data if isinstance(response.data, list) else []
    print(f"[SUPABASE] Found {len(result)} notes")
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
        response = supabase.table(CHAT_THREADS_TABLE).insert(row).execute()
    except APIError as e:
        raise RuntimeError(str(e))
    result = response.data if isinstance(response.data, list) and response.data else row
    return result[0] if isinstance(result, list) and result else result


def get_chat_thread_item(user_id: str, thread_id: str) -> Dict[str, Any]:
    try:
        response = (
            supabase.table(CHAT_THREADS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("thread_id", thread_id)
            .maybe_single()
            .execute()
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
        response = (
            supabase.table(CHAT_THREADS_TABLE)
            .update(updates)
            .eq("user_id", user_id)
            .eq("thread_id", thread_id)
            .execute()
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
        response = supabase.table(CHAT_MESSAGES_TABLE).insert(row).execute()
    except APIError as e:
        raise RuntimeError(str(e))
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else row


def query_chat_messages_for_thread(user_id: str, thread_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    clamped_limit = max(1, min(limit, 100))
    try:
        response = (
            supabase.table(CHAT_MESSAGES_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("thread_id", thread_id)
            .order("created_at", desc=True)
            .limit(clamped_limit)
            .execute()
        )
    except APIError as e:
        raise RuntimeError(str(e))
    rows = response.data if isinstance(response.data, list) else []
    return list(reversed(rows))

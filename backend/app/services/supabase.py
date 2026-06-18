import os
import json
from typing import Any, Dict, List, Optional
from postgrest import APIError
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_NOTES_TABLE = os.getenv("SUPABASE_NOTES_TABLE", "notes")

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

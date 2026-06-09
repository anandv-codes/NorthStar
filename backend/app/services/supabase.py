import os
from typing import Any, Dict, List
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_NOTES_TABLE = os.getenv("SUPABASE_NOTES_TABLE", "notes")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in the environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def put_note_item(item: Dict[str, Any]) -> Any:
    response = supabase.table(SUPABASE_NOTES_TABLE).insert(item).execute()
    if response.error:
        raise RuntimeError(response.error.message)
    return response.data


def update_note_item(user_id: str, note_id: str, updates: Dict[str, Any]) -> Any:
    response = (
        supabase.table(SUPABASE_NOTES_TABLE)
        .update(updates)
        .eq("user_id", user_id)
        .eq("note_id", note_id)
        .execute()
    )
    if response.error:
        raise RuntimeError(response.error.message)
    return response.data


def get_note_item(user_id: str, note_id: str) -> Dict[str, Any]:
    response = (
        supabase.table(SUPABASE_NOTES_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("note_id", note_id)
        .limit(1)
        .execute()
    )
    if response.error:
        # Supabase may return an error when no rows are found in some versions.
        if response.status_code == 406 or not response.data:
            return {}
        raise RuntimeError(response.error.message)
    return response.data[0] if response.data else {}


def query_notes_for_user(user_id: str, status: str = None) -> List[Dict[str, Any]]:
    query = supabase.table(SUPABASE_NOTES_TABLE).select("*").eq("user_id", user_id)
    if status:
        query = query.eq("status", status)
    response = query.execute()
    if response.error:
        raise RuntimeError(response.error.message)
    return response.data or []

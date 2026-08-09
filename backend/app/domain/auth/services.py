import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from postgrest import APIError

from ...infrastructure.db.supabase_client import supabase


USERS_TABLE = os.getenv("SUPABASE_USERS_TABLE", "users")
REFRESH_TOKENS_TABLE = os.getenv("SUPABASE_REFRESH_TOKENS_TABLE", "refresh_tokens")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_user(email: str, password_hash: str) -> dict[str, Any]:
    now = utc_now()
    row = {
        "user_id": str(uuid4()),
        "email": email,
        "password_hash": password_hash,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    try:
        response = supabase.table(USERS_TABLE).insert(row).execute()
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else row


def get_user_by_email(email: str) -> dict[str, Any]:
    try:
        response = (
            supabase.table(USERS_TABLE)
            .select("*")
            .eq("email", email)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else {}


def get_user_by_id(user_id: str) -> dict[str, Any]:
    try:
        response = (
            supabase.table(USERS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else {}


def store_refresh_token(
    user_id: str,
    jti: str,
    token_hash: str,
    expires_at: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    row = {
        "token_id": str(uuid4()),
        "jti": jti,
        "user_id": user_id,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "revoked_at": None,
        "created_at": utc_now(),
        "user_agent": user_agent,
        "ip_address": ip_address,
    }
    try:
        response = supabase.table(REFRESH_TOKENS_TABLE).insert(row).execute()
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else row


def get_refresh_token_by_jti(jti: str) -> dict[str, Any]:
    try:
        response = (
            supabase.table(REFRESH_TOKENS_TABLE)
            .select("*")
            .eq("jti", jti)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else {}


def revoke_refresh_token(jti: str) -> dict[str, Any]:
    try:
        response = (
            supabase.table(REFRESH_TOKENS_TABLE)
            .update({"revoked_at": utc_now()})
            .eq("jti", jti)
            .is_("revoked_at", None)
            .execute()
        )
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else {}

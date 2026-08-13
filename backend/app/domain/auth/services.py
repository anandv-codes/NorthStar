from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...infrastructure.db.user_repository import get_user_repository
from ..ports import UserRepository


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_user(email: str, password_hash: str, repo: UserRepository | None = None) -> dict[str, Any]:
    repo = repo or get_user_repository()
    return repo.create_user(email=email, password_hash=password_hash)


def get_user_by_email(email: str, repo: UserRepository | None = None) -> dict[str, Any]:
    repo = repo or get_user_repository()
    return repo.get_user_by_email(email=email)


def get_user_by_id(user_id: str, repo: UserRepository | None = None) -> dict[str, Any]:
    repo = repo or get_user_repository()
    return repo.get_user_by_id(user_id=user_id)


def store_refresh_token(
    user_id: str,
    jti: str,
    token_hash: str,
    expires_at: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
    repo: UserRepository | None = None,
) -> dict[str, Any]:
    repo = repo or get_user_repository()
    return repo.store_refresh_token(
        user_id=user_id,
        jti=jti,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )


def get_refresh_token_by_jti(jti: str, repo: UserRepository | None = None) -> dict[str, Any]:
    repo = repo or get_user_repository()
    return repo.get_refresh_token_by_jti(jti=jti)


def revoke_refresh_token(jti: str, repo: UserRepository | None = None) -> dict[str, Any]:
    repo = repo or get_user_repository()
    return repo.revoke_refresh_token(jti=jti)

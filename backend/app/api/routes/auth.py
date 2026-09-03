import hmac
import re
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..deps import get_current_user_id
from ...domain.auth.services import (
    create_user,
    get_refresh_token_by_jti,
    get_user_by_email,
    get_user_by_id,
    revoke_refresh_token,
    store_refresh_token,
)
from ...infrastructure.auth.jwt_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)
from ...schemas.models import (
    AuthTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UserProfileResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(
            status_code=400,
            detail="Password must include at least one letter and one number",
        )


def _to_profile(user: dict) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=str(user.get("user_id", "")),
        email=str(user.get("email", "")),
        is_active=bool(user.get("is_active", True)),
    )


def _issue_auth_tokens(
    user_id: str,
    email: str,
    user_agent: str | None,
    ip_address: str | None,
) -> AuthTokenResponse:
    access_token = create_access_token(user_id=user_id)
    refresh_token, refresh_jti = create_refresh_token(user_id=user_id)
    store_refresh_token(
        user_id=user_id,
        jti=refresh_jti,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_token_expires_at(),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        email=email,
    )


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request):
    email = _normalize_email(payload.email)
    _validate_password_strength(payload.password)

    existing_user = get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = create_user(email=email, password_hash=hash_password(payload.password))
    return _issue_auth_tokens(
        user_id=str(user["user_id"]),
        email=email,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, request: Request):
    email = _normalize_email(payload.email)
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    password_hash = str(user.get("password_hash") or "")
    if not password_hash or not verify_password(payload.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="User is inactive")

    return _issue_auth_tokens(
        user_id=str(user["user_id"]),
        email=email,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh(payload: RefreshRequest, request: Request):
    try:
        decoded = decode_token(payload.refresh_token, expected_type="refresh")
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    refresh_jti = str(decoded.get("jti") or "")
    user_id = str(decoded.get("sub") or "")
    if not refresh_jti or not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    stored = get_refresh_token_by_jti(refresh_jti)
    if not stored or stored.get("revoked_at"):
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    stored_hash = str(stored.get("token_hash") or "")
    if not stored_hash or not hmac.compare_digest(stored_hash, hash_refresh_token(payload.refresh_token)):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    expires_at_raw = str(stored.get("expires_at") or "")
    if not expires_at_raw:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = get_user_by_id(user_id=user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    revoke_refresh_token(refresh_jti)
    return _issue_auth_tokens(
        user_id=user_id,
        email=str(user.get("email", "")),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest):
    try:
        decoded = decode_token(payload.refresh_token, expected_type="refresh")
    except (jwt.PyJWTError, ValueError):
        return
    refresh_jti = str(decoded.get("jti") or "")
    if refresh_jti:
        revoke_refresh_token(refresh_jti)


@router.get("/me", response_model=UserProfileResponse)
def me(user_id: str = Depends(get_current_user_id)):
    user = get_user_by_id(user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="User is inactive")
    return _to_profile(user)

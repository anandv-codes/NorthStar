import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user_id
from ...domain.auth.services import (
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from ...infrastructure.auth.jwt_service import (
    create_access_token,
    hash_password,
    verify_password,
)
from ...schemas.models import (
    AuthTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserProfileResponse,
)


logger = logging.getLogger(__name__)
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


def _issue_access_token(user_id: str, email: str) -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token=create_access_token(user_id=user_id),
        user_id=user_id,
        email=email,
    )


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    email = _normalize_email(payload.email)
    _validate_password_strength(payload.password)

    existing_user = get_user_by_email(email)
    if existing_user:
        logger.info(f"Register failed: email already registered ({email})")
        raise HTTPException(status_code=409, detail="Email already registered")

    user = create_user(email=email, password_hash=hash_password(payload.password))
    logger.info(f"Registered new user: {user['user_id']}")
    return _issue_access_token(user_id=str(user["user_id"]), email=email)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest):
    email = _normalize_email(payload.email)
    user = get_user_by_email(email)
    if not user:
        logger.info(f"Login failed: no account for {email}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    password_hash = str(user.get("password_hash") or "")
    if not password_hash or not verify_password(payload.password, password_hash):
        logger.info(f"Login failed: wrong password for {email}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.get("is_active") is False:
        logger.info(f"Login failed: inactive account {email}")
        raise HTTPException(status_code=403, detail="User is inactive")

    logger.info(f"Login succeeded: {user['user_id']}")
    return _issue_access_token(user_id=str(user["user_id"]), email=email)


@router.post("/refresh", status_code=status.HTTP_410_GONE)
def refresh():
    """Refresh tokens are disabled; clients hold a single long-lived JWT.

    Kept as an explicit 410 rather than a 404 so stale bundles get a clear,
    actionable error instead of a generic "not found".
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Refresh tokens are disabled. Sign in again.",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    """No-op: tokens are stateless, so the client just discards its copy.

    Kept so older clients can still call it without erroring.
    """
    return None


@router.get("/me", response_model=UserProfileResponse)
def me(user_id: str = Depends(get_current_user_id)):
    user = get_user_by_id(user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="User is inactive")
    return _to_profile(user)

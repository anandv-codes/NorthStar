import os
from datetime import datetime, timezone
from typing import Any

import jwt
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "northstar-backend")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "northstar-client")
# Stateless, access-token-only auth: there is no refresh flow, so the token is
# long-lived (7 days) and the client signs in again once it expires.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))


def _require_jwt_secret() -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY must be set in the environment")
    return JWT_SECRET_KEY


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _access_token_payload(user_id: str) -> dict[str, Any]:
    now = int(datetime.now(timezone.utc).timestamp())
    return {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "nbf": now,
        "exp": now + ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }


def create_access_token(user_id: str) -> str:
    return jwt.encode(
        _access_token_payload(user_id), _require_jwt_secret(), algorithm=JWT_ALGORITHM
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        _require_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )
    if payload.get("type") != expected_type:
        raise ValueError("Invalid token type")
    return payload

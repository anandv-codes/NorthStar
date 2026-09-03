import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..infrastructure.auth.jwt_service import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Decode the bearer access token and return the authenticated user's id."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        decoded = decode_token(credentials.credentials, expected_type="access")
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc

    user_id = str(decoded.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid access token")
    return user_id

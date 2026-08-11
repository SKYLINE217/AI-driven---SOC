"""
JWT Auth Middleware — FastAPI dependency for role-based access control.

Issued by: POST /api/auth/login (mock login, document OIDC path for production)
Algorithm: HS256
Claims: sub (email), role (analyst|senior_analyst|approver), exp

Usage:
    @router.get("/sensitive")
    async def sensitive(user=Depends(require_role("approver"))):
        ...
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, UTC
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8-hour session

ROLE_LEVELS: dict[str, int] = {
    "analyst": 1,
    "senior_analyst": 2,
    "approver": 3,
}

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(email: str, role: str) -> str:
    """Issue a short-lived JWT with role claim."""
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """FastAPI dependency: validates Bearer JWT and returns claims dict."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)


def require_role(*roles: str):
    """
    FastAPI dependency factory: validates JWT and enforces minimum role level.

    Example:
        @router.post("/approve")
        async def approve(user=Depends(require_role("approver"))):
            ...
    """
    required_level = max(ROLE_LEVELS.get(r, 0) for r in roles)

    def _check(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_level = ROLE_LEVELS.get(user.get("role", ""), 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {' or '.join(roles)}",
            )
        return user

    return _check

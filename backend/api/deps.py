"""
FastAPI dependency: extracts and verifies JWT from Authorization header.
"""

from __future__ import annotations

import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError

JWT_SECRET = os.environ.get("JWT_SECRET", "dev_secret_change_me")
JWT_ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {
    "analyst": ["analyst"],
    "senior_analyst": ["analyst", "senior_analyst"],
    "approver": ["analyst", "senior_analyst", "approver"],
}


def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing bearer token"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid token"},
        )


def require_role(*roles: str):
    """Returns a FastAPI dependency that enforces role-based access."""
    def _checker(claims: dict = Depends(get_current_claims)) -> dict:
        current_role = claims.get("role", "")
        effective = ROLE_HIERARCHY.get(current_role, [])
        if not any(r in effective for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": f"Requires one of: {roles}"},
            )
        return claims
    return _checker

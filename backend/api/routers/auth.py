"""
Backend Auth Router — mock login endpoint for demo mode.
Issues JWTs; in production this is replaced by OIDC.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from jose import jwt

router = APIRouter()

JWT_SECRET = os.environ.get("JWT_SECRET", "dev_secret_change_me")
JWT_ALGORITHM = "HS256"

Role = Literal["analyst", "senior_analyst", "approver"]

DEMO_USERS: dict[Role, str] = {
    "analyst": "analyst@example.com",
    "senior_analyst": "senior@example.com",
    "approver": "approver@example.com",
}


class LoginRequest(BaseModel):
    username: str | None = None
    role: Role


class LoginResponse(BaseModel):
    access_token: str
    role: Role
    email: str
    expires_in: int


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    sub = body.username or DEMO_USERS[body.role]
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": body.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return LoginResponse(
        access_token=token,
        role=body.role,
        email=sub,
        expires_in=3600,
    )

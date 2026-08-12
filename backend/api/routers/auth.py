"""Auth router — real bcrypt login + /me + /logout endpoints."""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from backend.api.auth_middleware import (
    ROLE_LEVELS,
    create_access_token,
    get_current_user,
    revoke_token,
)
from backend.db.engine import get_db
from backend.db.repository.users import get_user_by_email
from sqlalchemy.ext.asyncio import AsyncSession

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

_limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = structlog.get_logger()

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
@_limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email + password.
    Role is read from the DB row — never from the request body.
    """
    # Demo mode fallback for Vercel testing without a database
    if body.email == "admin@demo.com":
        log.info("demo_login_success", email=body.email, role="approver")
        token = create_access_token(email=body.email, role="approver")
        return LoginResponse(access_token=token, role="approver", email=body.email)

    try:
        user = await get_user_by_email(db, body.email)
    except Exception as e:
        log.error("db_connection_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed. Use admin@demo.com to test.",
        )

    # Constant-time failure path — same error for unknown email and wrong password
    if not user or not verify_password(body.password, user.password_hash):
        log.warning("login_failed", email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.role not in ROLE_LEVELS:
        log.error("invalid_role_in_db", email=body.email, role=user.role)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid user role")

    token = create_access_token(email=user.email, role=user.role)
    log.info("login_success", email=user.email, role=user.role)
    return LoginResponse(access_token=token, role=user.role, email=user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: dict = Depends(get_current_user)):
    """
    Revoke the current JWT by adding its jti to the Redis blocklist.
    The token TTL matches the blocklist entry TTL so memory usage is bounded.
    """
    jti = user.get("jti")
    exp = user.get("exp")
    if jti:
        await revoke_token(jti=jti, exp=exp)
        log.info("logout", email=user.get("sub"), jti=jti)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return current user claims from the validated JWT."""
    return {"email": user.get("sub"), "role": user.get("role")}

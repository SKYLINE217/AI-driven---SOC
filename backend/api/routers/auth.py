"""Auth router — mock login + /me endpoint."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status, Depends

from backend.api.auth_middleware import create_access_token, ROLE_LEVELS, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    role: str  # analyst | senior_analyst | approver


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """
    Mock login endpoint (demo only).
    Production path: validate credentials against SSO/OIDC provider.
    """
    role = body.role.lower()
    if role not in ROLE_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of: {list(ROLE_LEVELS.keys())}",
        )
    token = create_access_token(email=body.email, role=role)
    return LoginResponse(access_token=token, role=role, email=body.email)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return current user claims."""
    return {"email": user.get("sub"), "role": user.get("role")}

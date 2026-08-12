"""
JWT Auth Middleware — RS256 asymmetric signing with jti revocation.

Key management:
  - Private key (signing):   JWT_PRIVATE_KEY env var (PEM string) or path via JWT_PRIVATE_KEY_PATH
  - Public key (verification): JWT_PUBLIC_KEY env var (PEM string) or path via JWT_PUBLIC_KEY_PATH
  - Fallback for local dev: auto-generates an ephemeral RS256 keypair if no keys are configured

Revocation:
  - Logout adds the token's jti to Redis SET soc:revoked_jtis with TTL = token's remaining lifetime
  - Every request checks Redis before accepting the token

Usage:
    @router.get("/sensitive")
    async def sensitive(user=Depends(require_role("approver"))):
        ...
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any, Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = structlog.get_logger()

# ── Algorithm ─────────────────────────────────────────────────────────────────

ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8-hour session

ROLE_LEVELS: dict[str, int] = {
    "analyst": 1,
    "senior_analyst": 2,
    "approver": 3,
}

bearer_scheme = HTTPBearer(auto_error=False)


# ── Key Loading ───────────────────────────────────────────────────────────────

def _load_key(env_var: str, path_env_var: str) -> Optional[str]:
    """Load PEM key from env var (direct PEM string) or file path."""
    direct = os.environ.get(env_var, "")
    if direct:
        return direct
    path = os.environ.get(path_env_var, "")
    if path and Path(path).exists():
        return Path(path).read_text()
    return None


def _get_keypair() -> tuple[Any, Any]:
    """Return (private_key, public_key). Falls back to ephemeral keypair in dev."""
    import jwt as pyjwt  # PyJWT

    private_pem = _load_key("JWT_PRIVATE_KEY", "JWT_PRIVATE_KEY_PATH")
    public_pem = _load_key("JWT_PUBLIC_KEY", "JWT_PUBLIC_KEY_PATH")

    if private_pem and public_pem:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
        private_key = load_pem_private_key(private_pem.encode(), password=None)
        public_key = load_pem_public_key(public_pem.encode())
        return private_key, public_key

    # ── Dev fallback: ephemeral RSA keypair ──────────────────────────────────
    log.warning(
        "jwt_dev_keypair",
        msg="No JWT_PRIVATE_KEY configured — using ephemeral dev keypair. DO NOT use in production.",
    )
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    return private_key, private_key.public_key()


_private_key, _public_key = _get_keypair()


# ── Token Operations ──────────────────────────────────────────────────────────

def create_access_token(email: str, role: str) -> str:
    """Issue a short-lived RS256 JWT with role + jti claims."""
    import jwt as pyjwt

    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": email,
        "role": role,
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return pyjwt.encode(payload, _private_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate an RS256 JWT. Raises HTTPException on failure."""
    import jwt as pyjwt

    try:
        return pyjwt.decode(token, _public_key, algorithms=[ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Redis Blocklist ───────────────────────────────────────────────────────────

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_BLOCKLIST_KEY_PREFIX = "soc:revoked_jtis:"


async def _is_token_revoked(jti: str) -> bool:
    """Check if the jti is in the Redis revocation set."""
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        result = await client.exists(f"{_BLOCKLIST_KEY_PREFIX}{jti}")
        await client.aclose()
        return bool(result)
    except Exception as exc:
        log.warning("redis_blocklist_check_failed", error=str(exc))
        return False  # Fail open — don't block valid tokens if Redis is down


async def revoke_token(jti: str, exp: Optional[int]) -> None:
    """Add a jti to the Redis blocklist. TTL = token's remaining lifetime."""
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        ttl = 60  # fallback TTL if exp is missing
        if exp:
            remaining = exp - int(datetime.now(UTC).timestamp())
            ttl = max(remaining, 1)
        await client.setex(f"{_BLOCKLIST_KEY_PREFIX}{jti}", ttl, "1")
        await client.aclose()
    except Exception as exc:
        log.error("redis_revoke_failed", jti=jti, error=str(exc))


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """FastAPI dependency: validates Bearer JWT, checks blocklist, returns claims."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_token(credentials.credentials)

    # Revocation check
    jti = claims.get("jti")
    if jti and await _is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


def require_role(*roles: str):
    """
    FastAPI dependency factory: validates JWT and enforces minimum role level.

    Example:
        @router.post("/approve")
        async def approve(user=Depends(require_role("approver"))):
            ...
    """
    required_level = max(ROLE_LEVELS.get(r, 0) for r in roles)

    async def _check(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_level = ROLE_LEVELS.get(user.get("role", ""), 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {' or '.join(roles)}",
            )
        return user

    return _check

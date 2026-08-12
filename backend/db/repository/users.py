"""
SOC Triager — User Repository.

Provides async DB operations for the users table.
Used by the auth router for credential verification.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.orm_models import UserORM


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[UserORM]:
    """Fetch a user row by email address. Returns None if not found."""
    result = await db.execute(select(UserORM).where(UserORM.email == email))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    role: str,
) -> UserORM:
    """Insert a new user. Caller must ensure email is unique."""
    user = UserORM(email=email, password_hash=password_hash, role=role)
    db.add(user)
    await db.flush()  # Get the generated id without committing
    return user

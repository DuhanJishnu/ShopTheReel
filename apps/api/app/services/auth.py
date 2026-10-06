"""Auth + profile business logic (services). Kept thin for testability."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.db import models


async def get_user_by_email(session: AsyncSession, email: str) -> models.User | None:
    res = await session.execute(select(models.User).where(models.User.email == email.lower()))
    return res.scalars().first()


async def register(session: AsyncSession, email: str, password: str) -> models.User:
    if await get_user_by_email(session, email):
        raise ValueError("email already registered")
    user = models.User(email=email.lower(), password_hash=security.hash_password(password))
    session.add(user)
    await session.flush()
    session.add(models.Profile(user_id=user.id))
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> models.User | None:
    user = await get_user_by_email(session, email)
    if user is None or not security.verify_password(password, user.password_hash):
        return None
    return user


async def issue_pair(session: AsyncSession, user_id: str) -> tuple[str, str]:
    access = security.create_access_token(user_id)
    refresh = security.create_refresh_token(user_id)
    session.add(
        models.RefreshToken(
            user_id=user_id,
            token_hash=security.hash_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_days),
        )
    )
    await session.commit()
    return access, refresh


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def rotate_refresh(session: AsyncSession, refresh_token: str) -> tuple[str, str] | None:
    try:
        user_id = security.decode_token(refresh_token, "refresh")
    except Exception:
        return None
    res = await session.execute(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == security.hash_token(refresh_token))
    )
    stored = res.scalars().first()
    if stored is None or stored.revoked_at is not None or _aware(stored.expires_at) < datetime.now(UTC):
        return None
    stored.revoked_at = datetime.now(UTC)
    await session.flush()
    return await issue_pair(session, user_id)


async def revoke_refresh(session: AsyncSession, refresh_token: str) -> None:
    res = await session.execute(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == security.hash_token(refresh_token))
    )
    stored = res.scalars().first()
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await session.commit()

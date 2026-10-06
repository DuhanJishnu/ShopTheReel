"""Request dependencies: DB session, current user, storage."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.storage import FakeStore, MinIOStore, ObjectStore
from app.core import security
from app.core.config import settings
from app.core.logging import get_logger
from app.db import models
from app.db.session import get_session

log = get_logger()
_bearer = HTTPBearer(auto_error=False)
_store: ObjectStore | None = None


def get_store() -> ObjectStore:
    global _store
    if _store is None:
        _store = FakeStore() if settings.app_env == "test" else MinIOStore()
    return _store


def set_store(store: ObjectStore) -> None:
    global _store
    _store = store


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> models.User:
    if creds is None or not creds.credentials:
        raise _unauth(request, "missing bearer token")
    try:
        user_id = security.decode_token(creds.credentials, "access")
    except Exception:
        raise _unauth(request, "invalid or expired token")
    user = await session.get(models.User, user_id)
    if user is None:
        raise _unauth(request, "user not found")
    return user


def _unauth(request: Request, detail: str):  # type: ignore[no-untyped-def]
    from fastapi import HTTPException

    return HTTPException(status_code=401, detail=detail)


async def ensure_profile(session: AsyncSession, user_id: str) -> models.Profile:
    profile = await session.get(models.Profile, user_id)
    if profile is None:
        profile = models.Profile(user_id=user_id)
        session.add(profile)
        await session.flush()
    return profile

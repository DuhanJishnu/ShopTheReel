"""Password hashing (Argon2) + JWT access/refresh helpers."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_ph = PasswordHasher()

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _encode(sub: str, expires: datetime, kind: str) -> str:
    payload = {"sub": sub, "exp": expires, "iat": datetime.now(UTC), "kind": kind, "jti": str(uuid.uuid4())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_access_token(user_id: str) -> str:
    return _encode(user_id, datetime.now(UTC) + timedelta(minutes=settings.jwt_access_minutes), "access")


def create_refresh_token(user_id: str) -> str:
    return _encode(user_id, datetime.now(UTC) + timedelta(days=settings.jwt_refresh_days), "refresh")


def decode_token(token: str, expected_kind: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    if payload.get("kind") != expected_kind:
        raise jwt.InvalidTokenError(f"expected {expected_kind} token")
    return str(payload["sub"])


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

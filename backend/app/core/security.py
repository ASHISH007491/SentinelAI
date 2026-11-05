"""Password hashing and JWT (access + refresh) creation/verification.

Uses bcrypt directly (passlib is unmaintained and breaks against bcrypt >= 4.1).
Access tokens are short-lived and carry the user's role; refresh tokens are
long-lived and only mint new access tokens.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
_MAX_BCRYPT_BYTES = 72


def _prepare(plain: str) -> bytes:
    return plain.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _encode(payload: dict, expires_minutes: int) -> str:
    data = payload | {"exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)}
    return jwt.encode(data, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str = "viewer") -> str:
    return _encode({"sub": subject, "role": role, "type": "access"}, ACCESS_TOKEN_EXPIRE_MINUTES)


def create_refresh_token(subject: str) -> str:
    return _encode({"sub": subject, "type": "refresh"}, REFRESH_TOKEN_EXPIRE_MINUTES)


def decode_token(token: str, expected_type: str = "access") -> dict | None:
    """Return the JWT payload if valid and of the expected type, else None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload

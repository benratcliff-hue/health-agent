"""Token generation, hashing, and session JWTs.

Magic-link tokens are random and stored only as a SHA-256 hash, so a database leak does
not expose usable login links. Session state is a signed JWT in an httpOnly cookie
(PRD 11.1).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from health_api.config import get_settings


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Visible prefix so a leaked key is recognizable and greppable in logs/configs.
API_KEY_PREFIX = "hak_"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    # Peppered with the app secret (PRD 11.2). Rotating SECRET_KEY invalidates existing
    # keys, which is the intended yearly-rotation behaviour.
    pepper = get_settings().secret_key
    return hashlib.sha256(f"{pepper}:{key}".encode()).hexdigest()


def create_session_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.session_ttl_days)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_session_token(token: str) -> str | None:
    """Return the user id from a valid session token, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")

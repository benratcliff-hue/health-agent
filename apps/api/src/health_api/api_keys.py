"""Per-user ingest API keys.

Management endpoints are session-authed (a logged-in user manages their own keys). The
keys themselves authenticate the machine ingest endpoints (HAE, Shortcuts) and are scoped
to ingest only: they cannot read data or change settings (PRD 11.1).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from health_api.auth import get_current_user
from health_api.db import get_db
from health_api.security import generate_api_key, hash_api_key
from health_db.models import ApiKey, User

router = APIRouter(prefix="/v1/api-keys")

INGEST_SCOPE = "ingest"


class ApiKeyCreate(BaseModel):
    label: str


class ApiKeyCreated(BaseModel):
    id: str
    label: str
    key: str  # plaintext, shown exactly once
    created_at: datetime


class ApiKeyOut(BaseModel):
    id: str
    label: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


def _out(k: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(k.id),
        label=k.label,
        created_at=k.created_at,
        last_used_at=k.last_used_at,
        revoked_at=k.revoked_at,
    )


@router.post("", status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    raw = generate_api_key()
    key = ApiKey(
        user_id=user.id,
        key_hash=hash_api_key(raw),
        label=body.label,
        scopes=[INGEST_SCOPE],
    )
    db.add(key)
    db.flush()
    return ApiKeyCreated(id=str(key.id), label=key.label, key=raw, created_at=key.created_at)


@router.get("")
def list_api_keys(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKeyOut]:
    keys = db.scalars(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    ).all()
    return [_out(k) for k in keys]


@router.delete("/{key_id}", status_code=204)
def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    key = db.get(ApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(status_code=404, detail="api key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)


def get_ingest_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate an ingest request by its `Authorization: Bearer <key>` header.

    Returns the owning user (and records last_used_at). Raises 401 for missing/invalid/
    revoked keys. This is the only credential ingest endpoints accept; sessions are not.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    raw = authorization.split(" ", 1)[1].strip()
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw)))
    if key is None or key.revoked_at is not None:
        raise HTTPException(status_code=401, detail="invalid api key")
    key.last_used_at = datetime.now(UTC)
    return db.get(User, key.user_id)

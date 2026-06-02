"""Meal photos (PRD 8.3).

M1 scope is *basic acceptance*: accept a photo, store it in object storage (R2), and
persist a `meal` row. The vision pipeline that estimates calories/macros is M2, so those
fields are left null here.

Two upload paths share one `store_meal` helper:
- POST /v1/ingest/meal  — API-key auth, for the Apple "Log meal" Shortcut (in ingest.py).
- POST /v1/meals        — session auth, for uploading from the web app.
GET /v1/meals lists recent meals with a freshly minted presigned photo URL.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from health_api.auth import get_current_user
from health_api.db import get_db
from health_db.models import Meal, User
from health_shared import ObjectStorage, get_object_storage

logger = logging.getLogger("health_api.meals")

router = APIRouter(prefix="/v1/meals")

MAX_PHOTO_BYTES = 15 * 1024 * 1024  # 15 MB; phone photos are well under this.
_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/webp": ".webp",
}
_PRESIGN_TTL = 3600  # 1 hour; long enough to view a list, short enough to stay private.


def get_storage() -> ObjectStorage:
    # Wrapped in a dependency so tests can override it with an in-memory stub.
    return get_object_storage()


class MealOut(BaseModel):
    id: str
    photo_url: str
    eaten_at: datetime
    note: str | None
    kcal_est: int | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    source: str
    created_at: datetime


def _out(meal: Meal, storage: ObjectStorage) -> MealOut:
    return MealOut(
        id=str(meal.id),
        photo_url=storage.presigned_get_url(meal.photo_key, _PRESIGN_TTL),
        eaten_at=meal.eaten_at,
        note=meal.note,
        kcal_est=meal.kcal_est,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        source=meal.source,
        created_at=meal.created_at,
    )


def _parse_eaten_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="eaten_at must be ISO-8601") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def store_meal(
    db: Session,
    user: User,
    file: UploadFile,
    storage: ObjectStorage,
    *,
    source: str,
    eaten_at: str | None = None,
    note: str | None = None,
) -> Meal:
    """Validate + upload the photo and persist a meal row. Shared by both upload paths."""
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="photo too large (max 15 MB)")

    ext = _EXT_BY_TYPE.get(content_type, ".bin")
    key = f"meals/{user.id}/{uuid.uuid4().hex}{ext}"
    storage.put(key, data, content_type)

    meal = Meal(
        user_id=user.id,
        photo_key=key,
        eaten_at=_parse_eaten_at(eaten_at),
        note=note,
        source=source,
    )
    db.add(meal)
    db.flush()
    logger.info(
        "meal stored",
        extra={"user_id": str(user.id), "meal_id": str(meal.id), "source": source},
    )
    return meal


@router.post("", status_code=201)
def upload_meal(
    file: UploadFile = File(...),
    eaten_at: str | None = Form(default=None),
    note: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
) -> MealOut:
    """Web upload (session-authed)."""
    meal = store_meal(db, user, file, storage, source="web", eaten_at=eaten_at, note=note)
    return _out(meal, storage)


@router.get("")
def list_meals(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
) -> list[MealOut]:
    limit = max(1, min(limit, 100))
    meals = db.scalars(
        select(Meal).where(Meal.user_id == user.id).order_by(Meal.eaten_at.desc()).limit(limit)
    ).all()
    return [_out(m, storage) for m in meals]

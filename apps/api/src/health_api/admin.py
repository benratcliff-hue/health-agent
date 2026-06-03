"""Ingest observability (PRD 15.2: verify HAE is posting, Whoop is syncing).

A read-only, session-authed summary of the current user's data freshness: connected
devices and their last sync, per-metric sample counts and recency, recent meals, and the
last briefing per kind. Scoped to the logged-in user (multi-tenant; PRD 10.1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from health_api.auth import get_current_user
from health_api.db import get_db
from health_db.models import Briefing, Device, Meal, MetricSample, User

router = APIRouter(prefix="/v1/admin")


class DeviceStatus(BaseModel):
    kind: str
    external_id: str | None
    last_sync_at: datetime | None
    created_at: datetime


class MetricStatus(BaseModel):
    metric_type: str
    total: int
    count_24h: int
    count_7d: int
    last_recorded_at: datetime | None


class BriefingStatus(BaseModel):
    kind: str
    last_generated_at: datetime | None
    last_delivered_at: datetime | None


class IngestStatus(BaseModel):
    now: datetime
    total_samples: int
    last_ingested_at: datetime | None
    devices: list[DeviceStatus]
    metrics: list[MetricStatus]
    meals_total: int
    last_meal_at: datetime | None
    briefings: list[BriefingStatus]


@router.get("/ingest")
def ingest_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IngestStatus:
    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    devices = db.scalars(
        select(Device).where(Device.user_id == user.id).order_by(Device.kind)
    ).all()

    metric_rows = db.execute(
        select(
            MetricSample.metric_type,
            func.count().label("total"),
            func.count(case((MetricSample.recorded_at >= since_24h, 1))).label("count_24h"),
            func.count(case((MetricSample.recorded_at >= since_7d, 1))).label("count_7d"),
            func.max(MetricSample.recorded_at).label("last_recorded_at"),
        )
        .where(MetricSample.user_id == user.id)
        .group_by(MetricSample.metric_type)
        .order_by(func.max(MetricSample.recorded_at).desc())
    ).all()

    total_samples = (
        db.scalar(
            select(func.count()).select_from(MetricSample).where(MetricSample.user_id == user.id)
        )
        or 0
    )
    last_ingested_at = db.scalar(
        select(func.max(MetricSample.ingested_at)).where(MetricSample.user_id == user.id)
    )

    meals_total = (
        db.scalar(select(func.count()).select_from(Meal).where(Meal.user_id == user.id)) or 0
    )
    last_meal_at = db.scalar(select(func.max(Meal.eaten_at)).where(Meal.user_id == user.id))

    briefing_rows = db.execute(
        select(
            Briefing.kind,
            func.max(Briefing.generated_at),
            func.max(Briefing.delivered_at),
        )
        .where(Briefing.user_id == user.id)
        .group_by(Briefing.kind)
        .order_by(Briefing.kind)
    ).all()

    return IngestStatus(
        now=now,
        total_samples=total_samples,
        last_ingested_at=last_ingested_at,
        devices=[
            DeviceStatus(
                kind=d.kind,
                external_id=d.external_id,
                last_sync_at=d.last_sync_at,
                created_at=d.created_at,
            )
            for d in devices
        ],
        metrics=[
            MetricStatus(
                metric_type=r.metric_type,
                total=r.total,
                count_24h=r.count_24h,
                count_7d=r.count_7d,
                last_recorded_at=r.last_recorded_at,
            )
            for r in metric_rows
        ],
        meals_total=meals_total,
        last_meal_at=last_meal_at,
        briefings=[
            BriefingStatus(kind=k, last_generated_at=g, last_delivered_at=d)
            for (k, g, d) in briefing_rows
        ],
    )

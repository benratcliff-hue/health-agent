"""Ingest endpoints for device data.

M1: HealthKit batches from Health Auto Export (HAE). The HAE JSON shape varies by data
type, so we normalize what we recognize into metric_sample and keep the raw sample in
value_json rather than rejecting unknown shapes (PRD 8.1). Authenticated by API key only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from health_api.api_keys import get_ingest_user
from health_api.db import get_db
from health_db.models import MetricSample, User

logger = logging.getLogger("health_api.ingest")

router = APIRouter(prefix="/v1/ingest")

SOURCE = "apple_health_hae"
# HAE timestamps: "yyyy-MM-dd HH:mm:ss Z", e.g. "2026-05-31 08:00:00 -0700".
_HAE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, _HAE_DATE_FORMAT)
    except ValueError:
        return None


def _sample_value(sample: dict[str, Any]) -> float | None:
    # Common metrics carry `qty`; heart rate carries Min/Avg/Max. Prefer a single
    # representative number, keeping the full sample in value_json regardless.
    for key in ("qty", "Avg", "avg"):
        if isinstance(sample.get(key), (int, float)):
            return float(sample[key])
    return None


def _normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a HAE payload into metric_sample-shaped dicts (without user_id)."""
    data = payload.get("data", payload)
    rows: list[dict[str, Any]] = []

    for metric in data.get("metrics", []) or []:
        name = metric.get("name")
        if not name:
            continue
        unit = metric.get("units")
        for sample in metric.get("data", []) or []:
            recorded_at = _parse_date(sample.get("date") or sample.get("startDate"))
            if recorded_at is None:
                continue
            rows.append(
                {
                    "metric_type": name,
                    "unit": unit,
                    "recorded_at": recorded_at,
                    "value_numeric": _sample_value(sample),
                    "value_json": sample,
                }
            )

    for workout in data.get("workouts", []) or []:
        recorded_at = _parse_date(workout.get("start") or workout.get("startDate"))
        if recorded_at is None:
            continue
        rows.append(
            {
                "metric_type": "workout",
                "unit": None,
                "recorded_at": recorded_at,
                "value_numeric": None,
                "value_json": workout,
            }
        )

    return rows


@router.post("/healthkit")
def ingest_healthkit(
    payload: dict[str, Any] = Body(...),
    user: User = Depends(get_ingest_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    rows = _normalize(payload)
    if not rows:
        return {"accepted": 0, "skipped": 0}

    # Idempotency: a HAE retry re-sends overlapping samples. Dedup within the batch, then
    # against what is already stored, keyed on (metric_type, recorded_at) for this user.
    seen: set[tuple[str, datetime]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = (row["metric_type"], row["recorded_at"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    keys = list(seen)
    existing = set(
        db.execute(
            select(MetricSample.metric_type, MetricSample.recorded_at).where(
                MetricSample.user_id == user.id,
                tuple_(MetricSample.metric_type, MetricSample.recorded_at).in_(keys),
            )
        ).all()
    )

    accepted = 0
    for row in deduped:
        if (row["metric_type"], row["recorded_at"]) in existing:
            continue
        db.add(MetricSample(user_id=user.id, source=SOURCE, **row))
        accepted += 1

    skipped = len(rows) - accepted
    logger.info(
        "healthkit ingest",
        extra={"user_id": str(user.id), "accepted": accepted, "skipped": skipped},
    )
    return {"accepted": accepted, "skipped": skipped}

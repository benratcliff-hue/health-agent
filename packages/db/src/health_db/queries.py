"""Reusable query helpers."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from health_db.models import MetricSample

# Postgres allows at most 65535 bind parameters per statement. Each (metric_type,
# recorded_at) tuple is 2 params, so 1000 tuples = 2000 params, comfortably under.
_KEY_CHUNK = 1000


def existing_metric_keys(
    db: Session, user_id: UUID, keys: list[tuple[str, datetime]]
) -> set[tuple[str, datetime]]:
    """Return which (metric_type, recorded_at) keys already exist for this user.

    Queried in chunks so a large ingest batch (e.g. a month of high-frequency HealthKit
    samples) cannot exceed Postgres's parameter limit.
    """
    found: set[tuple[str, datetime]] = set()
    for start in range(0, len(keys), _KEY_CHUNK):
        batch = keys[start : start + _KEY_CHUNK]
        found.update(
            db.execute(
                select(MetricSample.metric_type, MetricSample.recorded_at).where(
                    MetricSample.user_id == user_id,
                    tuple_(MetricSample.metric_type, MetricSample.recorded_at).in_(batch),
                )
            ).all()
        )
    return found

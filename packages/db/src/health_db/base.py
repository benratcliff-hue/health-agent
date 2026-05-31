"""Declarative base and shared column helpers.

All times are stored timezone-aware in UTC (PRD section 7). IDs are UUIDs generated
application-side so a row has its identity before it touches the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def created_at_column() -> Mapped[datetime]:
    # server_default=now() so rows created outside the ORM (migrations, raw SQL) still
    # get a timestamp.
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

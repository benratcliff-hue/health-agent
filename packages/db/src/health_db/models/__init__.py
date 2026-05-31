"""SQLAlchemy models for PRD section 7.

M1 scope: the tables needed for auth, ingest, the coach, and briefings. meal,
lab_report, and biomarker are deferred to their milestones (M2/M3) to avoid speculative
schema. magic_link_token is an auth implementation detail not listed in section 7.

All personal-data rows carry user_id (PRD section 10.1, multi-tenant from day one).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from health_db.base import Base, created_at_column, uuid_pk


class Household(Base):
    __tablename__ = "household"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    created_at: Mapped[datetime] = created_at_column()

    users: Mapped[list[User]] = relationship(back_populates="household")


class User(Base):
    # "user" is a reserved word in Postgres; SQLAlchemy quotes it automatically.
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = uuid_pk()
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("household.id"))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="member")
    coach_tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    household: Mapped[Household] = relationship(back_populates="users")


class ApiKey(Base):
    __tablename__ = "api_key"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    # Only the hash is stored; the plaintext is shown once at creation (PRD 11.1).
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    scopes: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Goal(Base):
    __tablename__ = "goal"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    type: Mapped[str] = mapped_column(String(32))  # weight/sleep/hr/biomarker/custom
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_column()


class Device(Base):
    __tablename__ = "device"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    kind: Mapped[str] = mapped_column(String(32))  # apple_health_hae/whoop/scale/cgm
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Encrypted at the application layer before storage (PRD 11.2); JSONB holds the
    # ciphertext envelope.
    oauth_tokens: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class MetricSample(Base):
    __tablename__ = "metric_sample"
    # Hot path for the coach: last-N of a metric for a user (PRD 7.2).
    __table_args__ = (
        Index(
            "ix_metric_sample_user_type_recorded",
            "user_id",
            "metric_type",
            "recorded_at",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    source: Mapped[str] = mapped_column(String(32))
    metric_type: Mapped[str] = mapped_column(String(64))
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = created_at_column()


class DailySummary(Base):
    __tablename__ = "daily_summary"
    # Cheap source of truth for last-N-days queries (PRD 7.2): PK is (user_id, date).
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_summary_user_date"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    sleep_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strain: Mapped[float | None] = mapped_column(Float, nullable=True)
    hrv: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kcal_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kcal_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    started_at: Mapped[datetime] = created_at_column()
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "message"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id"))
    role: Mapped[str] = mapped_column(String(16))  # user/assistant/system
    content: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Briefing(Base):
    __tablename__ = "briefing"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    kind: Mapped[str] = mapped_column(String(16))  # morning/evening/weekly
    generated_at: Mapped[datetime] = created_at_column()
    content_md: Mapped[str] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_channel: Mapped[str] = mapped_column(String(16), default="email")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Nullable: some actions (e.g. failed logins) have no resolved user.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class MagicLinkToken(Base):
    """Single-use, short-lived login token. Only the hash is stored."""

    __tablename__ = "magic_link_token"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


__all__ = [
    "Household",
    "User",
    "ApiKey",
    "Goal",
    "Device",
    "MetricSample",
    "DailySummary",
    "Conversation",
    "Message",
    "Briefing",
    "AuditLog",
    "MagicLinkToken",
]

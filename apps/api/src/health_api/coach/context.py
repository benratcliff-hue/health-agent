"""Assemble the coach's context from the database (PRD 9.3).

M1 grounds the coach in goals + a compact 7-day summary of metric_sample (the data we
actually have from HAE and Whoop) plus recent conversation turns. Daily-summary rollups
and z-score anomaly detection are a later enhancement; this keeps the coach grounded in
real data today.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from health_api.coach.llm import ChatMessage
from health_api.coach.prompts import DEFAULT_TONE, SYSTEM_TEMPLATE
from health_db.models import Conversation, Goal, Message, MetricSample, User

HISTORY_LIMIT = 10


def _goals_block(db: Session, user_id) -> str:
    goals = db.scalars(select(Goal).where(Goal.user_id == user_id, Goal.active.is_(True))).all()
    if not goals:
        return "  (none set yet)"
    lines = []
    for g in goals:
        target = f" -> target {g.target_value}" if g.target_value is not None else ""
        lines.append(f"  - {g.type}{target}")
    return "\n".join(lines)


def _recent_data_block(db: Session, user_id) -> str:
    since = datetime.now(UTC) - timedelta(days=7)
    rows = db.execute(
        select(
            MetricSample.metric_type,
            MetricSample.unit,
            func.count(),
            func.avg(MetricSample.value_numeric),
        )
        .where(MetricSample.user_id == user_id, MetricSample.recorded_at >= since)
        .group_by(MetricSample.metric_type, MetricSample.unit)
        .order_by(MetricSample.metric_type)
    ).all()
    if not rows:
        return "  (no data in the last 7 days)"
    lines = []
    for metric_type, unit, count, avg in rows:
        avg_str = f", avg {avg:.1f}{' ' + unit if unit else ''}" if avg is not None else ""
        lines.append(f"  - {metric_type}: {count} samples{avg_str}")
    return "\n".join(lines)


def build_system_prompt(db: Session, user: User) -> str:
    return SYSTEM_TEMPLATE.format(
        name=user.name,
        tone=user.coach_tone or DEFAULT_TONE,
        goals=_goals_block(db, user.id),
        recent_data=_recent_data_block(db, user.id),
    )


def load_history(db: Session, conversation: Conversation) -> list[ChatMessage]:
    """Last N turns, oldest-first, as Anthropic-shaped messages."""
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]

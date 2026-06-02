"""Morning/evening briefings: generation, email delivery, and due-time dispatch.

A periodic task (every 15 min) finds users whose 6am/8pm local briefing is due and enqueues
one generate job per user; each job builds the coach context, generates the briefing on
Haiku, stores it, and emails it. Idempotent per (user, kind, local day).
"""

from __future__ import annotations

import html as html_lib
import logging
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from health_db import get_sessionmaker
from health_db.models import Briefing, Household, User
from health_shared import EmailMessage, get_email_sender
from health_shared.coach import Coach, get_coach
from health_shared.coach.context import build_briefing

logger = logging.getLogger("health_worker.briefing")

MORNING_HOUR = 6
EVENING_HOUR = 20


def compute_due_kind(local_dt: datetime) -> str | None:
    """Which briefing (if any) is due in the 15-min window at the top of the hour."""
    if local_dt.minute >= 15:
        return None
    if local_dt.hour == MORNING_HOUR:
        return "morning"
    if local_dt.hour == EVENING_HOUR:
        return "evening"
    return None


def _coach() -> Coach:
    return get_coach(
        os.environ.get("ANTHROPIC_API_KEY"),
        os.environ.get("COACH_MODEL", "claude-haiku-4-5"),
        int(os.environ.get("COACH_MAX_TOKENS", "1024")),
    )


def _to_html(text: str) -> str:
    return f'<div style="font-family:system-ui;white-space:pre-wrap">{html_lib.escape(text)}</div>'


def generate_briefing(db, user: User, kind: str, coach: Coach, sender) -> Briefing:
    """Generate, persist, and email one briefing. Coach + sender injected for testability."""
    system, messages = build_briefing(db, user, kind)
    text, usage = coach.complete(system, messages)

    briefing = Briefing(user_id=user.id, kind=kind, content_md=text, delivery_channel="email")
    db.add(briefing)
    db.flush()

    sender.send(
        EmailMessage(
            to=user.email,
            subject=f"Your {kind} health briefing",
            html=_to_html(text),
            text=text,
        )
    )
    briefing.delivered_at = datetime.now(UTC)
    db.commit()
    logger.info("briefing sent", extra={"user_id": str(user.id), "kind": kind, **usage})
    return briefing


def run_briefing(user_id: str, kind: str) -> None:
    """Task entry: wire real coach + email sender + session, then generate."""
    sessionmaker = get_sessionmaker(os.environ["DATABASE_URL"])
    with sessionmaker() as db:
        user = db.get(User, user_id)
        if user is None:
            logger.warning("briefing: user missing", extra={"user_id": user_id})
            return
        generate_briefing(db, user, kind, _coach(), get_email_sender())


def _already_sent(db, user_id, kind: str, local_now: datetime) -> bool:
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = local_midnight.astimezone(UTC)
    found = db.scalar(
        select(Briefing.id).where(
            Briefing.user_id == user_id,
            Briefing.kind == kind,
            Briefing.generated_at >= since,
        )
    )
    return found is not None


def dispatch_due_now() -> list[tuple[str, str]]:
    """Return (user_id, kind) for users whose morning/evening briefing is due now."""
    sessionmaker = get_sessionmaker(os.environ["DATABASE_URL"])
    now_utc = datetime.now(UTC)
    due: list[tuple[str, str]] = []
    with sessionmaker() as db:
        rows = db.execute(
            select(User.id, Household.timezone).join(Household, User.household_id == Household.id)
        ).all()
        for user_id, tz in rows:
            try:
                local_now = now_utc.astimezone(ZoneInfo(tz or "UTC"))
            except Exception:
                local_now = now_utc
            kind = compute_due_kind(local_now)
            if kind and not _already_sent(db, user_id, kind, local_now):
                due.append((str(user_id), kind))
    return due

"""Briefing generation (shared by the worker's scheduled jobs and the api's on-demand test).

Builds the coach context, generates the briefing, stores a Briefing row, and emails it.
Coach + email sender are injected so callers supply their own (api config vs worker env)
and tests can stub them.
"""

from __future__ import annotations

import html as html_lib
import logging
from datetime import UTC, datetime

from health_db.models import Briefing, User
from health_shared.coach.context import build_briefing
from health_shared.coach.llm import Coach
from health_shared.email import EmailMessage

logger = logging.getLogger("health_shared.coach.briefing")


def _to_html(text: str) -> str:
    return f'<div style="font-family:system-ui;white-space:pre-wrap">{html_lib.escape(text)}</div>'


def generate_briefing(db, user: User, kind: str, coach: Coach, sender) -> Briefing:
    """Generate, persist, and email one briefing."""
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

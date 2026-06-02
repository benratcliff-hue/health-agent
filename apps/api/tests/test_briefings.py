"""Briefing generation + due-time logic.

compute_due_kind is pure (no DB); generation is DB-gated like the other DB tests.
"""

import os
import uuid
from datetime import UTC

import pytest


def test_compute_due_kind():
    from datetime import datetime

    from health_worker.briefing import compute_due_kind

    utc = UTC
    assert compute_due_kind(datetime(2026, 6, 1, 6, 5, tzinfo=utc)) == "morning"
    assert compute_due_kind(datetime(2026, 6, 1, 20, 10, tzinfo=utc)) == "evening"
    assert compute_due_kind(datetime(2026, 6, 1, 6, 20, tzinfo=utc)) is None  # outside window
    assert compute_due_kind(datetime(2026, 6, 1, 12, 0, tzinfo=utc)) is None  # wrong hour


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; briefing test needs a database",
)
def test_generate_briefing_persists_and_emails():
    from sqlalchemy import select

    from health_db import Base, get_engine, get_sessionmaker
    from health_db.models import Briefing, Household, User
    from health_shared.coach.llm import StubCoach
    from health_worker.briefing import generate_briefing

    url = os.environ["DATABASE_URL"]
    Base.metadata.create_all(get_engine(url))
    sm = get_sessionmaker(url)

    class CapturingSender:
        def __init__(self):
            self.sent = []

        def send(self, message):
            self.sent.append(message)

    sender = CapturingSender()
    with sm() as db:
        household = Household(name="Briefing Test")
        db.add(household)
        db.flush()
        user = User(
            household_id=household.id, name="ben", email=f"brief-{uuid.uuid4()}@example.com"
        )
        db.add(user)
        db.flush()

        briefing = generate_briefing(db, user, "morning", StubCoach("claude-haiku-4-5"), sender)

        assert briefing.content_md  # has text
        assert briefing.delivered_at is not None  # marked delivered after send
        assert briefing.delivery_channel == "email"
        assert len(sender.sent) == 1
        assert sender.sent[0].to == user.email
        assert sender.sent[0].subject == "Your morning health briefing"

        stored = db.scalar(select(Briefing).where(Briefing.id == briefing.id))
        assert stored is not None and stored.kind == "morning"

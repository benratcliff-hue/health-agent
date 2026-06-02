"""On-demand test briefing, generated synchronously in the api.

Uses the api's own coach + email config (already set), so it delivers immediately without
depending on the worker's environment. Scheduled briefings still run on the worker.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from health_api.auth import get_current_user
from health_api.config import get_settings
from health_api.db import get_db
from health_db.models import User
from health_shared import get_email_sender
from health_shared.coach import get_coach
from health_shared.coach.briefing import generate_briefing

logger = logging.getLogger("health_api.briefings")

router = APIRouter(prefix="/v1/briefings")


@router.post("/test")
def send_test_briefing(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Generate and email a one-off morning briefing to the current user, right now."""
    settings = get_settings()
    coach = get_coach(settings.anthropic_api_key, settings.coach_model, settings.coach_max_tokens)
    briefing = generate_briefing(db, user, "morning", coach, get_email_sender())
    return {"sent": True, "kind": briefing.kind}

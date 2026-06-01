"""Magic-link authentication and session management.

Flow: POST /auth/magic-link emails a single-use link -> GET /auth/callback verifies it,
sets a session cookie, and redirects to the web app. No passwords, no public sign-up
(emails must be allow-listed to bootstrap), per PRD 11.1.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from health_api.config import Settings, get_settings
from health_api.db import get_db
from health_api.security import (
    create_session_token,
    decode_session_token,
    generate_token,
    hash_token,
)
from health_db.models import Household, MagicLinkToken, User
from health_shared import EmailMessage, get_email_sender

logger = logging.getLogger("health_api.auth")

router = APIRouter()


class MagicLinkRequest(BaseModel):
    email: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    household_id: str
    coach_tone: str | None = None


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        household_id=str(user.household_id),
        coach_tone=user.coach_tone,
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the logged-in user from the session cookie, or raise 401."""
    from fastapi import HTTPException  # local import keeps the module's top imports lean

    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    user_id = decode_session_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="not authenticated")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite_value(),  # type: ignore[arg-type]
        path="/",
    )


def _get_or_create_bootstrap_user(db: Session, email: str, settings: Settings) -> User | None:
    """Return the user for this email, creating it only if the email is allow-listed.

    Returning None (not raising) for unknown, non-allow-listed emails lets the endpoint
    respond identically whether or not an account exists (no email enumeration).
    """
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    if email not in settings.allowed_emails_set():
        return None
    household = db.scalar(select(Household))
    if household is None:
        household = Household(name=settings.household_name)
        db.add(household)
        db.flush()
    user = User(household_id=household.id, name=email.split("@")[0], email=email)
    db.add(user)
    db.flush()
    return user


@router.post("/auth/magic-link")
def request_magic_link(body: MagicLinkRequest, db: Session = Depends(get_db)) -> dict[str, bool]:
    settings = get_settings()
    email = body.email.strip().lower()
    user = _get_or_create_bootstrap_user(db, email, settings)
    # Always report success so callers cannot probe which emails have accounts.
    if user is None:
        logger.info("magic-link requested for unknown email", extra={"email": email})
        return {"sent": True}

    raw_token = generate_token()
    db.add(
        MagicLinkToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.magic_link_ttl_minutes),
        )
    )

    link = f"{settings.api_base_url}/auth/callback?token={raw_token}"
    get_email_sender().send(
        EmailMessage(
            to=user.email,
            subject="Your Personal Health Agent login link",
            html=f'<p>Click to sign in: <a href="{link}">{link}</a></p>'
            f"<p>This link expires in {settings.magic_link_ttl_minutes} minutes.</p>",
            text=f"Sign in: {link}\nExpires in {settings.magic_link_ttl_minutes} minutes.",
        )
    )
    return {"sent": True}


@router.get("/auth/callback")
def magic_link_callback(token: str, db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    record = db.scalar(select(MagicLinkToken).where(MagicLinkToken.token_hash == hash_token(token)))

    now = datetime.now(UTC)
    valid = (
        record is not None
        and record.used_at is None
        and record.expires_at.replace(tzinfo=record.expires_at.tzinfo or UTC) > now
    )
    if not valid:
        # Send the user back to the web app with an error flag rather than a bare 4xx.
        return RedirectResponse(
            url=f"{settings.web_base_url}/login?error=invalid_link", status_code=303
        )

    record.used_at = now  # single-use
    session_token = create_session_token(str(record.user_id))
    response = RedirectResponse(url=f"{settings.web_base_url}/me", status_code=303)
    _set_session_cookie(response, settings, session_token)
    return response


@router.post("/auth/logout")
def logout() -> Response:
    settings = get_settings()
    response = Response(status_code=204)
    response.delete_cookie(settings.cookie_name, path="/")
    return response


@router.get("/v1/me")
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)

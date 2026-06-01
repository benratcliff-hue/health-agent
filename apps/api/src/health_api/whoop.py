"""Whoop OAuth connect flow.

GET /v1/whoop/connect redirects the logged-in user to Whoop's consent screen; the
callback exchanges the code for tokens, stores them encrypted on a Device row, and
enqueues a 30-day backfill. Webhooks and nightly catch-up sync are a separate change (4b).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from health_api.auth import get_current_user
from health_api.config import get_settings
from health_api.db import get_db
from health_api.queue import defer
from health_db.models import Device, User
from health_shared import encrypt_json
from health_shared.tasks import WHOOP_BACKFILL

logger = logging.getLogger("health_api.whoop")

router = APIRouter(prefix="/v1/whoop")

AUTH_PATH = "/oauth/oauth2/auth"
TOKEN_PATH = "/oauth/oauth2/token"
PROFILE_PATH = "/developer/v2/user/profile/basic"
SCOPES = "read:recovery read:sleep read:cycles read:workout read:profile offline"
_STATE_KIND = "whoop_state"


def _make_state(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "kind": _STATE_KIND,
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        },
        settings.secret_key,
        algorithm="HS256",
    )


def _read_state(state: str) -> str | None:
    try:
        payload = jwt.decode(state, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload.get("sub") if payload.get("kind") == _STATE_KIND else None


@router.get("/connect")
def connect(user: User = Depends(get_current_user)) -> RedirectResponse:
    settings = get_settings()
    if not settings.whoop_client_id:
        raise HTTPException(status_code=503, detail="Whoop is not configured")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.whoop_client_id,
            "redirect_uri": settings.whoop_redirect_uri,
            "scope": SCOPES,
            "state": _make_state(str(user.id)),
        }
    )
    return RedirectResponse(url=f"{settings.whoop_api_base}{AUTH_PATH}?{query}", status_code=303)


@router.get("/callback")
async def callback(code: str, state: str, db: Session = Depends(get_db)) -> RedirectResponse:
    settings = get_settings()
    user_id = _read_state(state)
    if not user_id:
        return RedirectResponse(url=f"{settings.web_base_url}/me?whoop=error", status_code=303)

    async with httpx.AsyncClient(base_url=settings.whoop_api_base, timeout=20) as client:
        token_resp = await client.post(
            TOKEN_PATH,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.whoop_redirect_uri,
                "client_id": settings.whoop_client_id,
                "client_secret": settings.whoop_client_secret,
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        profile_resp = await client.get(
            PROFILE_PATH, headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        profile_resp.raise_for_status()
        external_id = str(profile_resp.json().get("user_id", ""))

    enc = {"enc": encrypt_json(settings.encryption_key, tokens)}
    device = db.scalar(select(Device).where(Device.user_id == user_id, Device.kind == "whoop"))
    if device is None:
        device = Device(user_id=user_id, kind="whoop", external_id=external_id, oauth_tokens=enc)
        db.add(device)
    else:
        device.external_id = external_id
        device.oauth_tokens = enc
    db.flush()

    await defer(WHOOP_BACKFILL, device_id=str(device.id))
    logger.info("whoop connected", extra={"user_id": user_id, "device_id": str(device.id)})
    return RedirectResponse(url=f"{settings.web_base_url}/me?whoop=connected", status_code=303)

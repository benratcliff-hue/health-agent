"""Magic-link auth flow tests.

These require a database (DATABASE_URL). They are skipped when it is unset, so local
`make test` without Docker stays green while CI (Postgres service) runs them.
"""

import os
import re

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; auth tests need a database"
)

ALLOWED_EMAIL = "ben@example.com"


@pytest.fixture(scope="module")
def client():
    # Configure auth before the app reads settings at request time.
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["AUTH_ALLOWED_EMAILS"] = ALLOWED_EMAIL

    from fastapi.testclient import TestClient

    from health_api.config import get_settings
    from health_db import Base, get_engine

    get_settings.cache_clear()
    settings = get_settings()
    # Create the schema for the test database (auth needs the app tables, not the queue).
    Base.metadata.create_all(get_engine(settings.database_url))

    from health_api.main import app

    with TestClient(app) as c:
        yield c


class _CapturingSender:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


def _extract_token(text: str) -> str:
    match = re.search(r"token=([^\s]+)", text)
    assert match, f"no token in email body: {text!r}"
    return match.group(1)


def _login(client, monkeypatch):
    sender = _CapturingSender()
    monkeypatch.setattr("health_api.auth.get_email_sender", lambda: sender)
    client.post("/auth/magic-link", json={"email": ALLOWED_EMAIL})
    token = _extract_token(sender.messages[0].text)
    client.get(f"/auth/callback?token={token}", follow_redirects=False)


def test_me_requires_auth(client):
    assert client.get("/v1/me").status_code == 401


def test_update_me_settings(client, monkeypatch):
    _login(client, monkeypatch)

    resp = client.patch("/v1/me", json={"timezone": "America/Los_Angeles", "coach_tone": "terse"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "America/Los_Angeles"
    assert body["coach_tone"] == "terse"

    # Invalid timezone is rejected.
    assert client.patch("/v1/me", json={"timezone": "Not/AZone"}).status_code == 400


def test_full_magic_link_flow(client, monkeypatch):
    sender = _CapturingSender()
    monkeypatch.setattr("health_api.auth.get_email_sender", lambda: sender)

    resp = client.post("/auth/magic-link", json={"email": ALLOWED_EMAIL})
    assert resp.status_code == 200
    assert resp.json() == {"sent": True}
    assert len(sender.messages) == 1

    token = _extract_token(sender.messages[0].text)
    cb = client.get(f"/auth/callback?token={token}", follow_redirects=False)
    assert cb.status_code == 303
    assert cb.headers["location"].endswith("/me")
    assert client.cookies.get("ha_session")  # session cookie was set

    me = client.get("/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == ALLOWED_EMAIL

    # Single-use: replaying the same token fails and bounces to the login error page.
    replay = client.get(f"/auth/callback?token={token}", follow_redirects=False)
    assert replay.status_code == 303
    assert "error=invalid_link" in replay.headers["location"]


def test_unknown_email_is_silent(client, monkeypatch):
    sender = _CapturingSender()
    monkeypatch.setattr("health_api.auth.get_email_sender", lambda: sender)

    resp = client.post("/auth/magic-link", json={"email": "stranger@example.com"})
    # Same response as a known email, but no link is actually sent (no enumeration).
    assert resp.status_code == 200
    assert resp.json() == {"sent": True}
    assert sender.messages == []

"""Chat coach tests using the stub coach (no ANTHROPIC_API_KEY -> deterministic).

Requires a database (DATABASE_URL); skipped otherwise, like the other DB tests.
"""

import json
import os
import re

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; chat tests need a database"
)

ALLOWED_EMAIL = "chat@example.com"


@pytest.fixture(scope="module")
def client():
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["AUTH_ALLOWED_EMAILS"] = ALLOWED_EMAIL
    os.environ.pop("ANTHROPIC_API_KEY", None)  # force the stub coach

    from fastapi.testclient import TestClient

    from health_api.config import get_settings
    from health_db import Base, get_engine

    get_settings.cache_clear()
    Base.metadata.create_all(get_engine(get_settings().database_url))

    from health_api.main import app

    with TestClient(app) as c:
        yield c


def _login(client, monkeypatch):
    class _Sender:
        def __init__(self):
            self.messages = []

        def send(self, message):
            self.messages.append(message)

    sender = _Sender()
    monkeypatch.setattr("health_api.auth.get_email_sender", lambda: sender)
    client.post("/auth/magic-link", json={"email": ALLOWED_EMAIL})
    token = re.search(r"token=([^\s]+)", sender.messages[0].text).group(1)
    client.get(f"/auth/callback?token={token}", follow_redirects=False)


def _parse_sse(text: str) -> list[dict]:
    return [
        json.loads(line[len("data: ") :]) for line in text.splitlines() if line.startswith("data: ")
    ]


def test_chat_requires_auth(client):
    assert client.post("/v1/chat", json={"message": "hi"}).status_code == 401


def test_chat_streams_and_persists(client, monkeypatch):
    _login(client, monkeypatch)

    resp = client.post("/v1/chat", json={"message": "How did I sleep?"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    conversation_id = events[0]["conversation_id"]
    assert conversation_id
    reply = "".join(e["text"] for e in events if "text" in e)
    assert "stub coach" in reply  # the stub's signature
    assert events[-1].get("done") is True

    # The assistant turn was persisted.
    from sqlalchemy import select

    from health_api.config import get_settings
    from health_db import get_sessionmaker
    from health_db.models import Message

    sm = get_sessionmaker(get_settings().database_url)
    with sm() as db:
        roles = db.scalars(
            select(Message.role)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        ).all()
    assert roles == ["user", "assistant"]


def test_context_builder(client):
    # build_system_prompt should ground the prompt in goals + recent data headers.
    import uuid

    from sqlalchemy import select

    from health_api.config import get_settings
    from health_db import get_sessionmaker
    from health_db.models import Household, User
    from health_shared.coach.context import build_system_prompt

    sm = get_sessionmaker(get_settings().database_url)
    with sm() as db:
        user = db.scalar(select(User).where(User.email == ALLOWED_EMAIL))
        if user is None:
            household = Household(name="Test")
            db.add(household)
            db.flush()
            user = User(
                household_id=household.id, name="ctxuser", email=f"ctx-{uuid.uuid4()}@x.com"
            )
            db.add(user)
            db.flush()
        prompt = build_system_prompt(db, user)
    assert "personal health coach" in prompt
    assert "Goals:" in prompt
    assert "Recent data" in prompt

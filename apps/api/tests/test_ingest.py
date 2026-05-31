"""API key lifecycle and HAE HealthKit ingest tests.

Require a database (skipped without DATABASE_URL), like the auth tests.
"""

import os
import random
import re
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; ingest tests need a database"
)

ALLOWED_EMAIL = "ingest@example.com"
_TZ = timezone(timedelta(hours=-7))


@pytest.fixture(scope="module")
def client():
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["AUTH_ALLOWED_EMAILS"] = ALLOWED_EMAIL

    from fastapi.testclient import TestClient

    from health_api.config import get_settings
    from health_db import Base, get_engine

    get_settings.cache_clear()
    Base.metadata.create_all(get_engine(get_settings().database_url))

    from health_api.main import app

    with TestClient(app) as c:
        yield c


class _CapturingSender:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


def _login(client, monkeypatch):
    sender = _CapturingSender()
    monkeypatch.setattr("health_api.auth.get_email_sender", lambda: sender)
    client.post("/auth/magic-link", json={"email": ALLOWED_EMAIL})
    token = re.search(r"token=([^\s]+)", sender.messages[0].text).group(1)
    client.get(f"/auth/callback?token={token}", follow_redirects=False)


def _hae_payload():
    # Timestamps are randomized per run so re-running the suite never collides with
    # already-stored samples (which would make the idempotency assertions flaky).
    base = datetime.now(_TZ).replace(microsecond=0) - timedelta(days=random.randint(1, 3650))

    def d(mins: int) -> str:
        return (base + timedelta(minutes=mins)).strftime("%Y-%m-%d %H:%M:%S %z")

    payload = {
        "data": {
            "metrics": [
                {
                    "name": "step_count",
                    "units": "count",
                    "data": [{"qty": 1200, "date": d(0)}, {"qty": 800, "date": d(60)}],
                },
                {
                    "name": "heart_rate",
                    "units": "bpm",
                    "data": [{"Min": 55, "Avg": 62, "Max": 70, "date": d(30)}],
                },
            ],
            "workouts": [{"name": "Running", "start": d(-60), "end": d(-30)}],
        }
    }
    return payload, 4  # 2 steps + 1 heart_rate + 1 workout


def test_ingest_requires_api_key(client):
    payload, _ = _hae_payload()
    assert client.post("/v1/ingest/healthkit", json=payload).status_code == 401


def test_api_key_lifecycle_and_ingest(client, monkeypatch):
    _login(client, monkeypatch)

    created = client.post("/v1/api-keys", json={"label": "iPhone HAE"})
    assert created.status_code == 201
    body = created.json()
    assert body["key"].startswith("hak_")
    key, key_id = body["key"], body["id"]

    listed = client.get("/v1/api-keys").json()
    assert any(k["id"] == key_id for k in listed)
    assert "key" not in listed[0]  # plaintext is never listed

    headers = {"Authorization": f"Bearer {key}"}
    payload, n = _hae_payload()

    first = client.post("/v1/ingest/healthkit", headers=headers, json=payload)
    assert first.status_code == 200
    assert first.json() == {"accepted": n, "skipped": 0}

    # Idempotent: replaying the same batch stores nothing new.
    second = client.post("/v1/ingest/healthkit", headers=headers, json=payload)
    assert second.json() == {"accepted": 0, "skipped": n}

    # Revoked keys are rejected.
    assert client.delete(f"/v1/api-keys/{key_id}").status_code == 204
    revoked = client.post("/v1/ingest/healthkit", headers=headers, json=payload)
    assert revoked.status_code == 401

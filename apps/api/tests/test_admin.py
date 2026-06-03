"""Ingest status dashboard endpoint tests. Require a database (skipped without DATABASE_URL)."""

import os
import re
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; admin tests need a database"
)

ALLOWED_EMAIL = "admin@example.com"


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


def test_ingest_status_requires_auth(client):
    client.cookies.clear()
    assert client.get("/v1/admin/ingest").status_code == 401


def test_ingest_status_summary(client, monkeypatch):
    _login(client, monkeypatch)

    # Seed a device + a couple of samples (one recent, one old) for this user.
    from sqlalchemy import select

    from health_api.config import get_settings
    from health_db import get_sessionmaker
    from health_db.models import Device, MetricSample, User

    sm = get_sessionmaker(get_settings().database_url)
    now = datetime.now(UTC)
    with sm() as db:
        user = db.scalar(select(User).where(User.email == ALLOWED_EMAIL))
        db.add(Device(user_id=user.id, kind="whoop", external_id="42", last_sync_at=now))
        db.add(
            MetricSample(
                user_id=user.id,
                source="apple_health_hae",
                metric_type="step_count",
                value_numeric=1000,
                recorded_at=now - timedelta(hours=1),
            )
        )
        db.add(
            MetricSample(
                user_id=user.id,
                source="apple_health_hae",
                metric_type="step_count",
                value_numeric=500,
                recorded_at=now - timedelta(days=10),
            )
        )
        db.commit()

    resp = client.get("/v1/admin/ingest")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_samples"] >= 2
    assert any(d["kind"] == "whoop" and d["external_id"] == "42" for d in body["devices"])

    steps = next(m for m in body["metrics"] if m["metric_type"] == "step_count")
    assert steps["total"] >= 2
    assert steps["count_24h"] >= 1  # the 1h-old sample
    assert steps["count_24h"] <= steps["count_7d"] <= steps["total"]
    assert steps["last_recorded_at"] is not None

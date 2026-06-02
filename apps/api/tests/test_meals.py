"""Meal photo ingest + listing tests.

Use the in-memory StubStorage (the storage dependency is overridden), so nothing touches
R2. Require a database, skipped without DATABASE_URL like the other DB tests.
"""

import os
import re

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; meal tests need a database"
)

ALLOWED_EMAIL = "meals@example.com"

# A 1x1 PNG, smallest valid image bytes.
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module")
def client():
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["AUTH_ALLOWED_EMAILS"] = ALLOWED_EMAIL

    from fastapi.testclient import TestClient

    from health_api.config import get_settings
    from health_api.meals import get_storage
    from health_db import Base, get_engine
    from health_shared import StubStorage

    get_settings.cache_clear()
    Base.metadata.create_all(get_engine(get_settings().database_url))

    from health_api.main import app

    # One shared stub so uploads are visible to later reads within the test.
    stub = StubStorage()
    app.dependency_overrides[get_storage] = lambda: stub

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


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


def _api_key(client) -> str:
    return client.post("/v1/api-keys", json={"label": "Shortcut"}).json()["key"]


def test_meal_upload_requires_auth(client):
    client.cookies.clear()
    resp = client.post("/v1/meals", files={"file": ("m.png", _PNG, "image/png")})
    assert resp.status_code == 401


def test_ingest_meal_requires_api_key(client):
    client.cookies.clear()
    resp = client.post("/v1/ingest/meal", files={"file": ("m.png", _PNG, "image/png")})
    assert resp.status_code == 401


def test_web_upload_and_list(client, monkeypatch):
    _login(client, monkeypatch)

    resp = client.post(
        "/v1/meals",
        files={"file": ("lunch.png", _PNG, "image/png")},
        data={"note": "grilled chicken salad"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["note"] == "grilled chicken salad"
    assert body["source"] == "web"
    assert body["photo_url"]
    assert body["kcal_est"] is None  # macro estimation is M2

    listed = client.get("/v1/meals").json()
    assert any(m["id"] == body["id"] for m in listed)


def test_shortcut_ingest_meal(client, monkeypatch):
    _login(client, monkeypatch)
    key = _api_key(client)
    client.cookies.clear()  # the Shortcut path uses only the API key, no session

    resp = client.post(
        "/v1/ingest/meal",
        headers={"Authorization": f"Bearer {key}"},
        files={"file": ("dinner.jpg", _PNG, "image/jpeg")},
    )
    assert resp.status_code == 201
    assert resp.json()["source"] == "shortcut"


def test_non_image_rejected(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.post("/v1/meals", files={"file": ("note.txt", b"hello", "text/plain")})
    assert resp.status_code == 400

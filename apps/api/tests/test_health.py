"""M0 smoke tests for the api.

`test_healthz` is the guaranteed-passing unit test required by M0 and needs no
database. `test_db_ping` is skipped unless DATABASE_URL is set, so local `make test`
stays green without Docker while CI (which runs a Postgres service) exercises it.
"""

import os

import pytest
from fastapi.testclient import TestClient

from health_api.main import app

client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set; skipping live DB test"
)
def test_db_ping():
    resp = client.get("/db-ping")
    assert resp.status_code == 200
    assert resp.json()["result"] == 1

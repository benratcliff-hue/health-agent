"""Unit tests for the deterministic Whoop pieces.

Crypto round-trip, OAuth state token, and record normalization are testable without a
database or live Whoop access. The OAuth code exchange and backfill HTTP are validated
live once Whoop developer credentials exist.
"""

import os

from cryptography.fernet import Fernet


def test_crypto_roundtrip():
    from health_shared import decrypt_json, encrypt_json

    key = Fernet.generate_key().decode()
    data = {"access_token": "abc", "refresh_token": "def", "expires_in": 3600}
    assert decrypt_json(key, encrypt_json(key, data)) == data


def test_oauth_state_roundtrip():
    os.environ["SECRET_KEY"] = "test-secret"
    from health_api.config import get_settings
    from health_api.whoop import _make_state, _read_state

    get_settings.cache_clear()
    state = _make_state("user-123")
    assert _read_state(state) == "user-123"
    assert _read_state("garbage.token.value") is None


def test_cookie_samesite_normalization():
    from health_api.config import Settings

    assert Settings(cookie_samesite="none").cookie_samesite_value() == "none"
    assert Settings(cookie_samesite="None ").cookie_samesite_value() == "none"
    assert Settings(cookie_samesite='"none"').cookie_samesite_value() == "none"
    assert Settings(cookie_samesite="strict").cookie_samesite_value() == "strict"
    # Anything unexpected falls back safely instead of crashing set_cookie.
    assert Settings(cookie_samesite="bogus").cookie_samesite_value() == "lax"


def test_whoop_signature():
    import base64
    import hashlib
    import hmac

    from health_api.whoop import verify_whoop_signature

    secret, ts, body = "whoop-secret", "1700000000000", b'{"user_id":1}'
    sig = base64.b64encode(
        hmac.new(secret.encode(), ts.encode() + body, hashlib.sha256).digest()
    ).decode()
    assert verify_whoop_signature(secret, ts, body, sig) is True
    assert verify_whoop_signature(secret, ts, body, "wrong") is False
    assert verify_whoop_signature(secret, ts, b'{"user_id":2}', sig) is False  # tampered body


def test_whoop_normalize():
    from health_worker.whoop import normalize

    record = {
        "start": "2026-05-31T08:00:00.000Z",
        "score": {"recovery_score": 66, "resting_heart_rate": 52},
    }
    row = normalize("whoop_recovery", "recovery_score", record)
    assert row is not None
    assert row["metric_type"] == "whoop_recovery"
    assert row["value_numeric"] == 66.0
    assert row["value_json"] == record

    # No usable timestamp -> dropped, not crashed.
    assert normalize("whoop_recovery", "recovery_score", {"score": {}}) is None

"""Whoop v2 client, normalization, and 30-day backfill.

Confirmed against Whoop docs: OAuth token URL, v2 collection paths, and pagination
(limit/start/end/nextToken). The exact record field nesting (score.*) and the response
pagination field name are kept tolerant (best-effort extract, full record kept in
value_json) and should be validated against a real Whoop account.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select, tuple_

from health_db import get_sessionmaker
from health_db.models import Device, MetricSample
from health_shared import decrypt_json, encrypt_json

logger = logging.getLogger("health_worker.whoop")

SOURCE = "whoop"
TOKEN_PATH = "/oauth/oauth2/token"

# (metric_type, collection path, key inside record["score"] for the headline number)
COLLECTIONS = [
    ("whoop_recovery", "/developer/v2/recovery", "recovery_score"),
    ("whoop_sleep", "/developer/v2/activity/sleep", "sleep_performance_percentage"),
    ("whoop_strain", "/developer/v2/cycle", "strain"),
    ("whoop_workout", "/developer/v2/activity/workout", "strain"),
]


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class WhoopClient:
    def __init__(self, base: str, client_id: str, client_secret: str, tokens: dict[str, Any]):
        self._base = base.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._tokens = dict(tokens)
        self.refreshed = False

    @property
    def tokens(self) -> dict[str, Any]:
        return self._tokens

    def _refresh(self) -> None:
        resp = httpx.post(
            f"{self._base}{TOKEN_PATH}",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._tokens.get("refresh_token"),
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "offline",
            },
            timeout=20,
        )
        resp.raise_for_status()
        new = resp.json()
        # Whoop rotates the refresh token; keep the old one only if none is returned.
        new.setdefault("refresh_token", self._tokens.get("refresh_token"))
        self._tokens = new
        self.refreshed = True

    def get_collection(self, path: str, start: str, end: str):
        next_token: str | None = None
        refreshed_once = False
        while True:
            params: dict[str, Any] = {"limit": 25, "start": start, "end": end}
            if next_token:
                params["nextToken"] = next_token
            resp = httpx.get(
                f"{self._base}{path}",
                headers={"Authorization": f"Bearer {self._tokens['access_token']}"},
                params=params,
                timeout=20,
            )
            if resp.status_code == 401 and not refreshed_once and self._tokens.get("refresh_token"):
                self._refresh()
                refreshed_once = True
                continue
            resp.raise_for_status()
            data = resp.json()
            yield from data.get("records", [])
            next_token = data.get("next_token") or data.get("nextToken")
            if not next_token:
                break


def _dig(record: dict[str, Any], *keys: str) -> Any:
    cur: Any = record
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def normalize(metric_type: str, score_key: str, record: dict[str, Any]) -> dict[str, Any] | None:
    recorded_at = _parse_iso(record.get("start") or record.get("created_at"))
    if recorded_at is None:
        return None
    value = _dig(record, "score", score_key)
    return {
        "metric_type": metric_type,
        "unit": None,
        "recorded_at": recorded_at,
        "value_numeric": float(value) if isinstance(value, (int, float)) else None,
        "value_json": record,
    }


def _store(db, user_id, rows: list[dict[str, Any]]) -> int:
    """Idempotent insert keyed on (user_id, metric_type, recorded_at), like HAE ingest."""
    if not rows:
        return 0
    keys = {(r["metric_type"], r["recorded_at"]) for r in rows}
    existing = set(
        db.execute(
            select(MetricSample.metric_type, MetricSample.recorded_at).where(
                MetricSample.user_id == user_id,
                tuple_(MetricSample.metric_type, MetricSample.recorded_at).in_(list(keys)),
            )
        ).all()
    )
    accepted = 0
    seen: set[tuple[str, datetime]] = set()
    for row in rows:
        key = (row["metric_type"], row["recorded_at"])
        if key in existing or key in seen:
            continue
        seen.add(key)
        db.add(MetricSample(user_id=user_id, source=SOURCE, **row))
        accepted += 1
    return accepted


def run_backfill(device_id: str, days: int = 30) -> int:
    """Fetch trailing `days` of Whoop data for a connected device into metric_sample."""
    key = _env("ENCRYPTION_KEY")
    sessionmaker = get_sessionmaker(_env("DATABASE_URL"))
    accepted_total = 0
    with sessionmaker() as db:
        device = db.get(Device, device_id)
        if device is None or device.kind != "whoop" or not device.oauth_tokens:
            logger.warning(
                "whoop backfill: device missing or not whoop", extra={"device_id": device_id}
            )
            return 0
        tokens = decrypt_json(key, device.oauth_tokens["enc"])
        client = WhoopClient(
            base=os.environ.get("WHOOP_API_BASE", "https://api.prod.whoop.com"),
            client_id=_env("WHOOP_CLIENT_ID"),
            client_secret=_env("WHOOP_CLIENT_SECRET"),
            tokens=tokens,
        )
        now = datetime.now(UTC)
        start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        for metric_type, path, score_key in COLLECTIONS:
            rows = [
                row
                for record in client.get_collection(path, start, end)
                if (row := normalize(metric_type, score_key, record)) is not None
            ]
            accepted_total += _store(db, device.user_id, rows)

        device.last_sync_at = now
        if client.refreshed:
            device.oauth_tokens = {"enc": encrypt_json(key, client.tokens)}
        db.commit()

    logger.info(
        "whoop backfill complete", extra={"device_id": device_id, "accepted": accepted_total}
    )
    return accepted_total


def run_all_devices(days: int = 2) -> int:
    """Short catch-up sync across every connected Whoop device (nightly safety net)."""
    sessionmaker = get_sessionmaker(_env("DATABASE_URL"))
    with sessionmaker() as db:
        device_ids = [
            str(d.id) for d in db.scalars(select(Device).where(Device.kind == "whoop")).all()
        ]
    return sum(run_backfill(device_id, days=days) for device_id in device_ids)

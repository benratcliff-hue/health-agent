"""Procrastinate worker app.

M0 registers a single no-op task to prove the queue wiring end to end. Real jobs
(Whoop sync, HealthKit batch processing, meal vision, briefing generation, email
delivery) arrive in M1.

Run the worker with:  procrastinate --app=health_worker.app worker

The dotted path `health_worker.app` resolves to the `app` object defined below.
"""

from __future__ import annotations

import os

from procrastinate import App, PsycopgConnector

from health_shared.tasks import WHOOP_BACKFILL, WHOOP_SYNC

# PsycopgConnector forwards all extra kwargs straight to psycopg's AsyncConnectionPool,
# so the connection string goes in as a top-level `conninfo`. Wrapping it in a `kwargs`
# dict instead makes it a per-connection kwarg that collides with the pool's own
# `conninfo` ("multiple values for argument 'conninfo'"). Empty string when DATABASE_URL
# is unset keeps the module importable (lint/CI) since the pool opens lazily at run time.
app = App(connector=PsycopgConnector(conninfo=os.environ.get("DATABASE_URL", "")))


@app.task(name="noop")
def noop() -> str:
    """Does nothing useful; exists so M0 can enqueue and process one job."""
    return "ok"


@app.task(name=WHOOP_BACKFILL)
def whoop_backfill(device_id: str) -> int:
    """Backfill trailing 30 days of Whoop data for a freshly connected device."""
    # Imported here so the heavy client/deps load only when the task runs.
    from health_worker import whoop

    return whoop.run_backfill(device_id)


@app.task(name=WHOOP_SYNC)
def whoop_sync(device_id: str) -> int:
    """Short catch-up for one device, triggered by a Whoop webhook."""
    from health_worker import whoop

    return whoop.run_backfill(device_id, days=2)


@app.periodic(cron="0 9 * * *")
@app.task(name="whoop_nightly_sync")
def whoop_nightly_sync(timestamp: int) -> int:
    """Nightly safety net in case a webhook was missed (PRD 8.2). 09:00 UTC daily."""
    from health_worker import whoop

    return whoop.run_all_devices(days=2)

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

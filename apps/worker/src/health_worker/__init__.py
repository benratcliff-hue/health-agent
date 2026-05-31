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

# conninfo is left empty when DATABASE_URL is unset so the module stays importable
# (for linting/CI) without a database. The connection pool is opened lazily when the
# worker actually runs, not at construction time.
# NOTE: confirm the PsycopgConnector(kwargs={"conninfo": ...}) form against the pinned
# procrastinate version on first `make dev`; this matches the 3.x docs pattern.
app = App(connector=PsycopgConnector(kwargs={"conninfo": os.environ.get("DATABASE_URL", "")}))


@app.task(name="noop")
def noop() -> str:
    """Does nothing useful; exists so M0 can enqueue and process one job."""
    return "ok"

"""procrastinate queue schema

Applies Procrastinate's own schema (queue tables, functions, triggers) as a migration so
the whole database is brought up by a single `alembic upgrade head`. This retires the M0
worker start-command shortcut (`schema --apply || true`).

Revision ID: procrastinate_0001
Revises: 05f5f2b3e6bf
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "procrastinate_0001"
down_revision: str | None = "05f5f2b3e6bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Skip if the queue schema already exists. The M0 deploy bootstrapped it out-of-band
    # (worker `schema --apply`), so on that database the tables are present but unknown to
    # Alembic; re-running the full CREATE would fail. On a fresh database it applies.
    bind = op.get_bind()
    if bind.execute(text("SELECT to_regclass('public.procrastinate_jobs')")).scalar() is not None:
        return

    # Imported lazily so health_db itself never depends on procrastinate; only the
    # environment that runs migrations (the worker) needs it importable.
    from procrastinate.schema import SchemaManager

    op.execute(SchemaManager.get_schema())


def downgrade() -> None:
    # Procrastinate ships no teardown. Best-effort drop of its objects; CASCADE removes
    # the attached functions and triggers. Downgrading past the initial install is not
    # an expected operation.
    for table in (
        "procrastinate_events",
        "procrastinate_periodic_defers",
        "procrastinate_jobs",
        "procrastinate_workers",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP TYPE IF EXISTS procrastinate_job_status CASCADE")

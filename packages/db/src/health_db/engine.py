"""SQLAlchemy engine construction.

In M0 this exists only to back the api's `/db-ping`. The engine is created lazily and
cached so a single process reuses one connection pool rather than building one per
request.
"""

from __future__ import annotations

import functools
import os

from sqlalchemy import Engine, create_engine


def _normalize_url(url: str) -> str:
    # Railway and most tooling hand out `postgresql://` (or the legacy `postgres://`)
    # URLs. We pin the psycopg 3 driver explicitly so SQLAlchemy does not fall back to
    # psycopg2, which is not installed.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@functools.lru_cache(maxsize=1)
def get_engine(database_url: str | None = None) -> Engine:
    """Return a process-wide SQLAlchemy engine.

    Reads `DATABASE_URL` from the environment when no URL is passed. Raises if neither
    is available, because a silent default would mask a misconfigured deployment.
    """
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at a Postgres instance "
            "(see docker-compose.yml for local development)."
        )
    # pool_pre_ping avoids handing out connections that Postgres has already closed,
    # which Railway-managed Postgres can do across idle periods.
    return create_engine(_normalize_url(url), pool_pre_ping=True)

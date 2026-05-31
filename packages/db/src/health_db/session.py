"""Session factory.

Cached so a process reuses one sessionmaker (and thus one engine/pool). Callers open a
short-lived Session per unit of work (e.g. the api's per-request `get_db` dependency).
"""

from __future__ import annotations

import functools

from sqlalchemy.orm import Session, sessionmaker

from health_db.engine import get_engine


@functools.lru_cache(maxsize=1)
def get_sessionmaker(database_url: str | None = None) -> sessionmaker[Session]:
    # expire_on_commit=False so attributes stay usable after commit (e.g. returning a
    # serialized user from an endpoint without an extra refresh round-trip).
    return sessionmaker(bind=get_engine(database_url), expire_on_commit=False)

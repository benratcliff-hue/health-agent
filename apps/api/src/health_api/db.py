"""Per-request database session dependency."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from health_api.config import get_settings
from health_db import get_sessionmaker


def get_db() -> Iterator[Session]:
    sessionmaker = get_sessionmaker(get_settings().database_url)
    db = sessionmaker()
    try:
        yield db
        # Commit on a clean request so endpoints do not each have to remember to; roll
        # back on any error so a failed request never leaves a partial write.
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

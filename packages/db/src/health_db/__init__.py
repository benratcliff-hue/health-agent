"""Database package: engine factory now, SQLAlchemy models and migrations in M1.

Centralising the engine here (rather than in apps/api) means the worker and cron
services connect the same way and there is a single place to evolve when models and
Alembic migrations land in M1.
"""

from health_db.engine import get_engine

__all__ = ["get_engine"]

"""Application entrypoint. Run with: uvicorn health_api.main:app"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from health_api import api_keys, auth, ingest
from health_api.config import get_settings
from health_api.logging import configure_logging
from health_db import get_engine

logger = logging.getLogger("health_api")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Personal Health Agent API", version="0.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        # allow_credentials so the browser sends/stores the session cookie on calls from
        # the web origin. Requires an explicit origin list (not "*").
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(api_keys.router)
    app.include_router(ingest.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness: process is up. No external dependencies on purpose."""
        return {"status": "ok"}

    @app.get("/db-ping")
    def db_ping() -> dict[str, object]:
        """Readiness for the database: prove we can round-trip a query to Postgres."""
        # A plain `def` endpoint runs in FastAPI's threadpool, so this synchronous DB
        # call does not block the event loop and we avoid an async driver for one SELECT.
        try:
            engine = get_engine(settings.database_url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).scalar_one()
        except Exception:
            logger.exception("db-ping failed")
            raise HTTPException(status_code=503, detail="database unavailable") from None
        return {"status": "ok", "result": result}

    return app


app = create_app()

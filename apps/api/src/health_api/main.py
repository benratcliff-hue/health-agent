"""Application entrypoint. Run with: uvicorn health_api.main:app"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from health_api import admin, api_keys, auth, briefings, chat, ingest, meals, whoop
from health_api.config import get_settings
from health_api.logging import configure_logging
from health_api.queue import get_queue_app
from health_db import get_engine

logger = logging.getLogger("health_api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Open the job-queue connection pool for the process lifetime. Tolerant of failure so
    # the api can still serve /healthz when the database/queue is unavailable.
    queue = get_queue_app()
    opened = False
    try:
        await queue.open_async()
        opened = True
    except Exception:
        logger.exception("could not open job queue; enqueueing will fail until fixed")
    try:
        yield
    finally:
        if opened:
            await queue.close_async()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Personal Health Agent API", version="0.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        # allow_credentials so the browser sends/stores the session cookie on calls from
        # the web origin. Requires an explicit origin list (not "*").
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(api_keys.router)
    app.include_router(ingest.router)
    app.include_router(whoop.router)
    app.include_router(chat.router)
    app.include_router(briefings.router)
    app.include_router(meals.router)
    app.include_router(admin.router)

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

"""Job queue access for the api: enqueue Procrastinate jobs by name.

The api does not import the worker's task code; it defers by task-name string
(`App.configure_task`), so the only contract is the names in health_shared.tasks. The
connection pool is opened once at app startup (see main.lifespan).
"""

from __future__ import annotations

import functools

from procrastinate import App, PsycopgConnector

from health_api.config import get_settings


@functools.lru_cache(maxsize=1)
def get_queue_app() -> App:
    return App(connector=PsycopgConnector(conninfo=get_settings().database_url or ""))


async def defer(task_name: str, **kwargs) -> None:
    await get_queue_app().configure_task(name=task_name).defer_async(**kwargs)

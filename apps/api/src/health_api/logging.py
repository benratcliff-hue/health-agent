"""Structured JSON logging to stdout.

Railway captures stdout, so emitting one JSON object per line keeps logs queryable
without a logging vendor. We hand-roll the formatter rather than add a dependency for
what is a dozen lines.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

# Attributes the stdlib puts on every LogRecord. Anything outside this set was passed
# via `logger.info(..., extra={...})` and is worth surfacing in the JSON line.
_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Replace any default handlers so we do not double-log in plain text.
    root.handlers = [handler]
    root.setLevel(level.upper())

"""Central, structured logging configuration.

Emits JSON logs by default (LOG_FORMAT=json) for ingestion by log tooling, or
human-readable text (LOG_FORMAT=text) for local dev. Also instruments the
SQLAlchemy engine to log database events (connections + statements).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.config import settings

_CONFIGURED = False
_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include any structured extras passed via logger(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload.setdefault(key, value)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler()
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s %(message)s", "%Y-%m-%dT%H:%M:%S"
            )
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    _CONFIGURED = True


def init_db_event_logging(engine: Engine) -> None:
    """Attach SQLAlchemy listeners that log connections and statements (DEBUG)."""
    db_logger = logging.getLogger("sentinelai.db")

    @event.listens_for(engine, "connect")
    def _on_connect(_dbapi_conn, _rec) -> None:
        db_logger.info("db_connect")

    @event.listens_for(engine, "before_cursor_execute")
    def _on_exec(_conn, _cursor, statement, _params, _ctx, _many) -> None:
        db_logger.debug("db_query", extra={"statement": statement.split("\n", 1)[0][:200]})

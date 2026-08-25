"""
Transit Platform — Logging Foundation.

Provides structured logging with timestamp, level, message,
and request/correlation ID support.
"""

import logging
import sys
from contextvars import ContextVar

# Context variable for request correlation ID
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Inject request_id into log records from context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get(None) or "-"  # type: ignore[attr-defined]
        return True


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure application-wide logging.

    Format: timestamp | level | request_id | message
    """
    logger = logging.getLogger("transit")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Prevent duplicate handlers on reload
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(request_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    logger.addHandler(handler)

    # Suppress overly verbose library loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return logger


# Application logger
logger = setup_logging()

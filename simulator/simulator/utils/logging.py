"""
Transit Platform — Safe Redacting Logger.

Ensures that JWT tokens, passwords, and other credentials are never written
to console or disk logs.
"""

import logging
import os
from pathlib import Path
import re
from typing import Optional

# Regex pattern for matching JWT tokens
JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+")
# Regex pattern for password parameters in common strings / URLs / JSON
PASSWORD_PATTERN = re.compile(
    r'(["\']?password["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])',
    re.IGNORECASE
)
BEARER_PATTERN = re.compile(r"(Bearer\s+)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE)


class RedactingFilter(logging.Filter):
    """Filters log records to redact JWT tokens and passwords."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact(str(v)) for v in record.args)
        return True

    @classmethod
    def redact(cls, text: str) -> str:
        """Sanitizes text by replacing sensitive tokens and secrets."""
        if not isinstance(text, str):
            return text
        # Redact JWTs
        text = JWT_PATTERN.sub("[REDACTED_JWT]", text)
        # Redact Bearer tokens
        text = BEARER_PATTERN.sub(r"\1[REDACTED_TOKEN]", text)
        # Redact Passwords
        text = PASSWORD_PATTERN.sub(r"\1***REDACTED***\3", text)
        return text


_configured = False


def setup_logging(level: str = "INFO", log_dir: Optional[Path] = None) -> logging.Logger:
    """Configures safe dual console and file logging."""
    global _configured

    logger = logging.getLogger("simulator")
    if _configured:
        return logger

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = False

    # Clear existing handlers if any
    logger.handlers.clear()

    # Redacting filter
    redactor = RedactingFilter()

    # Format
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redactor)
    logger.addHandler(console_handler)

    # 2. File Handler
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "simulator.log", encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize file logging in {log_dir}: {e}")

    _configured = True
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns a child logger under 'simulator' with redaction enabled."""
    if not _configured:
        setup_logging()
    if name:
        return logging.getLogger(f"simulator.{name}")
    return logging.getLogger("simulator")

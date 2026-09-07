"""
Transit Platform — Database Safety Guard.

Strictly protects the production/live database ('transit_platform')
from accidental truncation, reset scripts, and test suite execution.
"""

import logging
from typing import Any
from urllib.parse import urlparse
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger("db_safety_guard")

PROTECTED_PRODUCTION_DATABASES = {
    "transit_platform",
}

ALLOWED_TEST_SUFFIXES = ("_test", "_testing")
ALLOWED_TEST_PREFIXES = ("test_", "testing_")


def extract_database_name(target: Any) -> str:
    """
    Extracts the database name from an Engine, Session, URL string, or raw name.
    """
    if target is None:
        raise ValueError("Cannot extract database name from None")

    if isinstance(target, Session):
        bind = target.get_bind()
        if bind is not None and hasattr(bind, "url"):
            return bind.url.database or ""
        raise ValueError("Session has no bound engine URL")

    if isinstance(target, Engine):
        return target.url.database or ""

    if hasattr(target, "database"):
        return getattr(target, "database") or ""

    target_str = str(target).strip()
    if "://" in target_str:
        parsed = urlparse(target_str)
        # urlparse path is '/dbname'
        return parsed.path.lstrip("/")

    return target_str


def is_test_database(db_name: str) -> bool:
    """
    Checks whether a database name qualifies as a test database.
    """
    if not db_name:
        return False

    name_lower = db_name.lower()
    if name_lower in PROTECTED_PRODUCTION_DATABASES:
        return False

    if name_lower.endswith(ALLOWED_TEST_SUFFIXES) or name_lower.startswith(ALLOWED_TEST_PREFIXES):
        return True

    return False


def assert_testing_database(target: Any) -> str:
    """
    Asserts that the target database is explicitly a test database.
    Fails closed immediately if target is 'transit_platform' or any non-test database.
    There is NO override or bypass allowed.

    Raises:
        RuntimeError: If the target is a protected production database
                      or not in the test database allowlist.
    """
    db_name = extract_database_name(target)

    if db_name in PROTECTED_PRODUCTION_DATABASES:
        error_msg = (
            f"\n{'='*70}\n"
            f"CRITICAL SAFETY VIOLATION: DESTRUCTIVE ACTION BLOCKED!\n"
            f"Target database is '{db_name}', which is the PROTECTED LIVE/PRODUCTION DATABASE.\n"
            f"Running test suites, truncations, seeders, or reset scripts against '{db_name}' is STRICTLY FORBIDDEN!\n"
            f"Automated destructive tests and fixtures must target 'transit_platform_test'.\n"
            f"{'='*70}\n"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    if not is_test_database(db_name):
        error_msg = (
            f"\n{'='*70}\n"
            f"SAFETY VIOLATION: Database '{db_name}' is not recognized as a testing database!\n"
            f"Only databases explicitly matching '*_test', 'test_*', or '*_testing' are permitted.\n"
            f"{'='*70}\n"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    return db_name

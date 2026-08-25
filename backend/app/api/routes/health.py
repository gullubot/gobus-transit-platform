"""
Transit Platform — Health Check Endpoints.

Infrastructure-only endpoints for BUILD 0.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Basic application health check."""
    return {
        "status": "ok",
        "service": "transit-backend",
    }


@router.get("/health/db")
def health_check_db(db: Session = Depends(get_db)) -> dict:
    """
    Database connectivity health check.

    Actually tests the database connection — does NOT return hardcoded success.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
        }
    except SQLAlchemyError as exc:
        logger.error("Database health check failed: %s", str(exc))
        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(exc),
        }

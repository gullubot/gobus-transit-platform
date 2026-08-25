"""
Transit Platform — Database Engine & Base.

Creates the SQLAlchemy engine and declarative Base.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=(settings.app_env == "development"),
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass

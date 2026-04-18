"""
SQLAlchemy models and database session helpers.

The backend primarily tracks training jobs and (optionally) datasets using
SQLite.  The database file lives inside the writable user-data directory when
the app is packaged, and falls back to the repository copy during development.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Generator

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    from core.config import settings as app_settings
except Exception:  # pragma: no cover - fallback for early bootstrap scripts
    app_settings = None

DB_FILENAME = "craftml.db"


def _resolve_db_path() -> Path:
    """
    Determine where the SQLite file should live.

    - Packaged / production (`CRAFTML_ENV=prod` or `sys.frozen`): store inside
      the per-user data directory managed by `core.config.settings`.
    - Development: keep using the repository-local `apps/backend/craftml.db`
      so existing tooling (e.g., migrate_db.py) keeps working.
    """

    if app_settings and (app_settings.is_frozen or app_settings.env == "prod"):
        path = app_settings.user_data_dir / DB_FILENAME
    else:
        path = Path(__file__).with_name(DB_FILENAME)

    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


DB_PATH = _resolve_db_path()
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)
Base = declarative_base()


class TrainingJob(Base):
    """Persistent record of long-running training operations."""

    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    params = Column(Text, nullable=True)  # JSON blob
    logs = Column(Text, nullable=True)  # Optional serialized logs
    progress = Column(Text, nullable=True)  # JSON blob describing progress
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=True,
    )
    completed_at = Column(DateTime, nullable=True)


class Dataset(Base):
    """Optional dataset metadata table."""

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    format = Column(String(32), nullable=True)
    size_mb = Column(Float, nullable=True)
    num_samples = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    description = Column(Text, nullable=True)


def init_db() -> None:
    """Create tables if they do not exist."""

    Base.metadata.create_all(bind=engine, checkfirst=True)


def get_db() -> Generator:
    """
    FastAPI dependency helper (if needed later).

    Yields a database session with automatic close semantics.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


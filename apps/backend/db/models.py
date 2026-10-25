"""
SQLAlchemy models and database session helpers.

The backend tracks jobs (fine-tune, compress, deploy), job logs and dataset
metadata using SQLite.  The database file lives inside the writable user-data directory when
the app is packaged, and falls back to the repository copy during development.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    LargeBinary,
    DateTime,
        Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    from core.config import settings as app_settings
except Exception:  # pragma: no cover - fallback for early bootstrap scripts
    app_settings = None

DB_FILENAME = "craftml.db"


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (how timestamps are stored in SQLite here)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_from_timestamp(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    """
    ISO 8601 with an explicit UTC offset for a stored (naive UTC) timestamp. Without the offset,
    JavaScript's ``new Date()`` would read it as local time and every time in the UI would be off.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def local_time(value: datetime) -> datetime:
    """A stored (naive UTC) timestamp in the machine's local time zone, for human-readable text."""
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).astimezone()


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


@event.listens_for(engine, "connect")
def _load_sqlite_vec(dbapi_connection, _record) -> None:
    """Load the sqlite-vec extension when available (the KB falls back to brute force without it)."""
    try:
        import sqlite_vec

        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)
    except Exception:  # noqa: BLE001 - optional extension
        pass


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)
Base = declarative_base()


class Job(Base):
    """
    Unified record for every long-running operation.

    ``job_type`` is one of ``finetune``, ``compress`` or ``deploy``.  JSON blobs
    (params, progress, result) are stored as text for simplicity.
    """

    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    job_type = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    params = Column(Text, nullable=True)
    progress = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class JobLog(Base):
    """Append-only log lines for a job."""

    __tablename__ = "job_run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    message = Column(Text, nullable=False)


class JobMetric(Base):
    """One logged training step (for loss curves and resource charts)."""

    __tablename__ = "job_run_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), nullable=False, index=True)
    step = Column(Integer, nullable=False)
    epoch = Column(Float, nullable=True)
    loss = Column(Float, nullable=True)
    learning_rate = Column(Float, nullable=True)
    vram_gb = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ChatSession(Base):
    """A persisted chat conversation and its generation settings."""

    __tablename__ = "chat_sessions"

    id = Column(String(32), primary_key=True)
    title = Column(String(255), nullable=False, default="New chat")
    model_id = Column(String(255), nullable=True)
    system_prompt = Column(Text, nullable=True)
    params = Column(Text, nullable=True)  # JSON: temperature, top_p, ...
    use_kb = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ChatMessage(Base):
    """One message in a chat session. ``sources`` holds RAG citations (JSON)."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class KbDocument(Base):
    """A document ingested into the local knowledge base."""

    __tablename__ = "kb_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    ext = Column(String(16), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    num_chunks = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class KbChunk(Base):
    """A text chunk with its embedding (float32 blob, L2-normalised)."""

    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=False)


class CloudRun(Base):
    """A fine-tune running on a remote GPU. Persisted so a restart can find and terminate leftovers."""

    __tablename__ = "cloud_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    remote_id = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="running", index=True)
    handle = Column(Text, nullable=False)  # RemoteJobHandle JSON (no secrets)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)


class CloudModel(Base):
    """A registered remote inference model (Together, RunPod serverless, Replicate, SSH tunnel)."""

    __tablename__ = "cloud_models"

    id = Column(String(255), primary_key=True)  # cloud:<provider>:<name>
    provider = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    remote_model = Column(String(255), nullable=False)
    base_url = Column(Text, nullable=True)
    endpoint_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


def _migrate_legacy_training_jobs() -> None:
    """Copy rows from the pre-unification ``training_jobs`` table into ``job_runs``."""

    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "training_jobs" not in insp.get_table_names():
        return

    legacy_cols = {c["name"] for c in insp.get_columns("training_jobs")}
    updated_expr = (
        "COALESCE(updated_at, CURRENT_TIMESTAMP)"
        if "updated_at" in legacy_cols
        else "CURRENT_TIMESTAMP"
    )
    completed_expr = "completed_at" if "completed_at" in legacy_cols else "NULL"

    with engine.begin() as conn:
        conn.execute(text(
            f"""
            INSERT INTO job_runs
                (job_id, job_type, status, params, progress, error,
                 created_at, updated_at, completed_at)
            SELECT job_id, 'finetune', status, params, progress, error,
                   COALESCE(created_at, CURRENT_TIMESTAMP),
                   {updated_expr},
                   {completed_expr}
            FROM training_jobs
            WHERE job_id NOT IN (SELECT job_id FROM job_runs)
            """
        ))
        conn.execute(text("DROP TABLE training_jobs"))


def init_db() -> None:
    """Create tables if they do not exist and migrate legacy data."""

    Base.metadata.create_all(bind=engine, checkfirst=True)
    _migrate_legacy_training_jobs()


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


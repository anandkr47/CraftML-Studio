from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
import sys
from pathlib import Path

Base = declarative_base()

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    file_path = Column(String)
    token_count = Column(Integer)
    quality_score = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TrainingJob(Base):
    __tablename__ = "training_jobs"
    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True)
    status = Column(String)
    params = Column(Text)
    logs = Column(Text)
    progress = Column(Text)  # JSON string of progress data
    error = Column(Text)  # Error message if failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime)

def _resolve_db_path() -> str:
    """Resolve DB path with priority:
    1) CRAFTML_DB_PATH env var (absolute file path)
    2) If running as frozen binary (PyInstaller) or CRAFTML_ENV=prod:
       use per-user app data directory (fresh DB per user installation)
    3) Fallback to local 'craftml.db' (development)
    """
    # 1) Explicit override
    override = os.environ.get("CRAFTML_DB_PATH")
    if override:
        db_path = Path(override).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return str(db_path)

    # 2) Production/frozen default: per-user data dir
    is_frozen = getattr(sys, "frozen", False)
    is_prod_env = os.environ.get("CRAFTML_ENV", "").lower() in {"prod", "production", "1", "true"}
    if is_frozen or is_prod_env:
        if os.name == "nt":
            base_dir = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        elif sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            base_dir = Path.home() / ".local" / "share"
        app_dir = base_dir / "CraftML Studio"
        app_dir.mkdir(parents=True, exist_ok=True)
        return str(app_dir / "craftml.db")

    # 3) Development fallback: project/local directory
    return "craftml.db"

_db_file = _resolve_db_path()
DATABASE_URL = f"sqlite:///{_db_file}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

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

DATABASE_URL = "sqlite:///craftml.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

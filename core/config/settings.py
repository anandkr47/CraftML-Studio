"""
Configuration settings for CraftML Studio
"""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings"""
    
    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    models_dir: Path = base_dir / "resources" / "models"
    datasets_dir: Path = base_dir / "resources" / "datasets"
    logs_dir: Path = base_dir / "apps" / "backend" / "logs"
    
    # API
    api_host: str = "127.0.0.1"
    api_port: int = 5000
    
    # Database
    database_url: str = "sqlite:///./craftml.db"
    
    # ML Settings
    default_device: str = "auto"
    default_batch_size: int = 4
    default_learning_rate: float = 2e-4
    
    # Crawler Settings
    max_crawl_depth: int = 3
    max_crawl_pages: int = 100
    crawl_timeout: int = 30
    
    # Redis (for Celery)
    redis_url: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


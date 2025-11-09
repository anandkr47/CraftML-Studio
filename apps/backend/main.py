"""
CraftML Studio Backend API
FastAPI server for ML operations
"""

import sys
from pathlib import Path

# Add core modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api import train, crawler, compress, deploy, monitor, dataset, modelhub, websocket
from api import dataset_upload, tasks, jobs, dedup, convert, docker_deploy, hardware, settings, playground
from db.models import Base, engine
from core.utils import setup_logger
from models.responses import ErrorResponse

# Setup logging
logger = setup_logger("craftml_backend", log_file="logs/backend.log")

app = FastAPI(
    title="CraftML Studio API",
    description="Local-first AI infrastructure management platform",
    version="0.1.0"
)

# Create tables at startup
Base.metadata.create_all(bind=engine)

# CORS middleware - allow Tauri frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",  # Tauri dev
        "http://127.0.0.1:1420",
        "tauri://localhost",      # Tauri production
        "*"  # Allow all for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent error format"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "code": f"HTTP_{exc.status_code}"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "code": "INTERNAL_ERROR",
            "details": str(exc) if app.debug else None
        }
    )


# API routes
app.include_router(crawler.router, prefix="/api/crawler", tags=["Crawler"])
app.include_router(train.router, prefix="/api/train", tags=["Training"])
app.include_router(compress.router, prefix="/api/compress", tags=["Compression"])
app.include_router(deploy.router, prefix="/api/deploy", tags=["Deployment"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["Monitoring"])
app.include_router(dataset.router, prefix="/api/dataset", tags=["Dataset"])
app.include_router(dataset_upload.router, prefix="/api/dataset-upload", tags=["Dataset Upload"])
app.include_router(modelhub.router, prefix="/api/modelhub", tags=["Model Hub"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Task Orchestration"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Job History"])
app.include_router(dedup.router, prefix="/api/dedup", tags=["Deduplication"])
app.include_router(convert.router, prefix="/api/convert", tags=["Model Conversion"])
app.include_router(docker_deploy.router, prefix="/api/docker", tags=["Docker Deployment"])
app.include_router(hardware.router, prefix="/api/hardware", tags=["Hardware Detection"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(playground.router, prefix="/api/playground", tags=["Playground"])


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "CraftML Studio API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "crawler": "/api/crawler",
            "train": "/api/train",
            "compress": "/api/compress",
            "deploy": "/api/deploy",
            "monitor": "/api/monitor",
            "dataset": "/api/dataset",
            "modelhub": "/api/modelhub",
            "tasks": "/api/tasks",
            "jobs": "/api/jobs",
            "dedup": "/api/dedup",
            "convert": "/api/convert",
            "docker": "/api/docker",
            "hardware": "/api/hardware",
            "settings": "/api/settings"
        }
    }


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "craftml-backend"
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting CraftML Studio Backend...")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=5000,
        log_level="info"
    )

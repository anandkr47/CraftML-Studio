"""
CraftML Studio Backend API
FastAPI server for ML operations
"""

import os
import sys
from pathlib import Path

# Add core modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
# Lazy import heavy modules to speed up startup
# Import only what's needed for basic API structure
from api import train, compress, deploy, monitor, dataset, modelhub, websocket
from api import jobs, settings, chat, kb, cloud
from api.openai_compat import create_router as create_openai_router
from api.errors import register_cloud_error_handler
from api.security import LocalOnlyGuard, allowed_origins
from db.models import init_db
from services import jobs as job_store
from core.utils import setup_logger
from core.config import settings as app_settings

# Setup logging
logger = setup_logger("craftml_backend", log_file=str(app_settings.logs_dir / "backend.log"))

app = FastAPI(
    title="CraftML Studio API",
    description="Local-first AI infrastructure management platform",
    version="0.1.0"
)

# Create tables, migrate legacy data, and fail jobs orphaned by a previous run
try:
    init_db()
    interrupted = job_store.fail_interrupted_jobs()
    if interrupted:
        logger.warning(f"Marked {interrupted} interrupted job(s) as failed")
except Exception as e:
    logger.warning(f"Database initialization note: {e}")

# Migrate the legacy HF token and terminate remote GPU runs the previous process left billing
from services import cloud_service  # noqa: E402

cloud_service.startup()
cloud_service.configure_inference()

# CORS: only the desktop app (and the dev server) may call the API from a browser context.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last so it runs first: rejects non-loopback Hosts and foreign Origins (HTTP and WebSocket).
app.add_middleware(LocalOnlyGuard)


register_cloud_error_handler(app)


# Error responses share one shape: {"status": "error", "message": <human text>, "detail": <same / FastAPI detail>, "code"}.
# The frontend reads `message`; `detail` stays for API clients that expect FastAPI's convention.
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": message, "detail": exc.detail, "code": f"HTTP_{exc.status_code}"},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request, exc):
    """Unknown routes / wrong methods (raised by the router, not by our handlers)."""
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": message, "detail": exc.detail, "code": f"HTTP_{exc.status_code}"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """422 with FastAPI's `detail` list plus a readable `message` that names each field."""
    problems = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
        problems.append(f"{'.'.join(loc) or 'request'}: {err.get('msg', 'invalid value')}")
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "; ".join(problems) or "Invalid request",
                 "detail": jsonable_encoder(exc.errors()), "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Unexpected exceptions: logged with a traceback; the client gets a generic message."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error", "detail": "Internal server error",
                 "code": "INTERNAL_ERROR"},
    )


# API routes
app.include_router(train.router, prefix="/api/train", tags=["Training"])
app.include_router(compress.router, prefix="/api/compress", tags=["Compression"])
app.include_router(deploy.router, prefix="/api/deploy", tags=["Deployment"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["Monitoring"])
app.include_router(dataset.router, prefix="/api/dataset", tags=["Dataset"])
app.include_router(modelhub.router, prefix="/api/modelhub", tags=["Model Hub"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Job History"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(kb.router, prefix="/api/kb", tags=["Knowledge Base"])
app.include_router(cloud.router, prefix="/api/cloud", tags=["Cloud GPUs"])
app.include_router(create_openai_router(), prefix="/v1", tags=["OpenAI Compatible"])


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "CraftML Studio API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "train": "/api/train",
            "compress": "/api/compress",
            "deploy": "/api/deploy",
            "monitor": "/api/monitor",
            "dataset": "/api/dataset",
            "modelhub": "/api/modelhub",
            "jobs": "/api/jobs",
            "settings": "/api/settings",
            "chat": "/api/chat",
            "kb": "/api/kb",
            "cloud": "/api/cloud",
            "openai": "/v1"
        }
    }


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "craftml-backend",
        # set by the desktop shell; lets it detect a stale backend left by an older app version
        "app_version": os.environ.get("CRAFTML_APP_VERSION"),
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting CraftML Studio Backend...")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("CRAFTML_PORT", "17860")),
        log_level="info"
    )

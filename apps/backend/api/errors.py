"""Shared exception handlers."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.cloud.errors import CloudError, HostKeyError


def register_cloud_error_handler(app: FastAPI) -> None:
    """Typed cloud failures become precise HTTP errors with a user-facing message."""

    @app.exception_handler(CloudError)
    async def cloud_error_handler(request, exc: CloudError):
        content = {"status": "error", "message": exc.user_message(), "detail": exc.user_message(), "code": exc.code}
        if isinstance(exc, HostKeyError):
            content.update(fingerprint=exc.fingerprint, changed=exc.changed)
        return JSONResponse(status_code=exc.status_code, content=content)

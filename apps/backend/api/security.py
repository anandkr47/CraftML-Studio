"""
Host/Origin guard for the local API.

The backend listens on 127.0.0.1 without authentication.  Without this guard any web page the
user has open could call it from their browser (CSRF) or via DNS rebinding, which matters now
that the API can store cloud credentials and start paid GPUs.

* ``Host`` must be loopback (defeats DNS rebinding).
* A browser-supplied ``Origin`` must be the desktop app (or the dev server).  Requests with no
  ``Origin`` (curl, the Rust sidecar health check, other local tools) are allowed.

Allowed origins by platform (Tauri's WebView uses a different origin on each OS):
  macOS / Linux   tauri://localhost
  Windows         http://tauri.localhost  (https://tauri.localhost with ``useHttpsScheme``)
  dev server      http://localhost:1420, http://127.0.0.1:1420
Extra origins can be added with CRAFTML_ALLOWED_ORIGINS (comma separated).
"""

from __future__ import annotations

import json
import os
from typing import List, Optional, Set

DEFAULT_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:1420",
    "http://127.0.0.1:1420",
)
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def allowed_origins() -> List[str]:
    extra = [o.strip().rstrip("/") for o in os.environ.get("CRAFTML_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return list(DEFAULT_ORIGINS) + extra


def _hostname(host_header: str) -> str:
    host = host_header.strip().lower()
    if host.startswith("["):  # [::1]:17860
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


class LocalOnlyGuard:
    """Pure ASGI middleware (also covers WebSocket handshakes, which CORS does not)."""

    def __init__(self, app, origins: Optional[List[str]] = None, hosts: Optional[Set[str]] = None):
        self.app = app
        self.origins = {o.rstrip("/") for o in (origins if origins is not None else allowed_origins())}
        self.hosts = hosts if hosts is not None else LOOPBACK_HOSTS

    def _violation(self, scope) -> Optional[str]:
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        host = headers.get(b"host", b"").decode("latin-1")
        if not host or _hostname(host) not in self.hosts:
            return "Forbidden host"
        origin = headers.get(b"origin")
        if origin is not None and origin.decode("latin-1").rstrip("/") not in self.origins:
            return "Forbidden origin"
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        problem = self._violation(scope)
        if problem is None:
            return await self.app(scope, receive, send)

        if scope["type"] == "websocket":
            await receive()  # the connect message
            return await send({"type": "websocket.close", "code": 1008})

        body = json.dumps({"detail": problem}).encode()
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

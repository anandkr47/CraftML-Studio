"""
Local OpenAI-compatible API server.

Runs a dedicated uvicorn server (same process, so loaded models are shared
with the Chat page) that exposes only ``/v1`` plus ``/health``.  One server
can run at a time.
"""

import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.openai_compat import create_router
from core.config import settings
from core.utils import setup_logger
from services import inference

logger = setup_logger("api_server", log_file=str(settings.logs_dir / "api_server.log"))


class ServerError(RuntimeError):
    """User-facing failure to start or stop the server."""


class _Server(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # we run in a worker thread
        pass


@dataclass
class _Running:
    server: _Server
    thread: threading.Thread
    host: str
    port: int
    auth_required: bool
    model_id: Optional[str]


_current: Optional[_Running] = None
_lock = threading.Lock()


def build_app(api_key: Optional[str]) -> FastAPI:
    app = FastAPI(title="CraftML Local API", version="1")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(create_router(api_key), prefix="/v1")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "loaded_models": inference.loaded_ids()}

    return app


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _describe(running: _Running) -> Dict[str, Any]:
    shown_host = "127.0.0.1" if running.host == "0.0.0.0" else running.host
    base = f"http://{shown_host}:{running.port}"
    return {
        "running": running.thread.is_alive(),
        "host": running.host,
        "port": running.port,
        "url": base,
        "base_url": f"{base}/v1",
        "auth_required": running.auth_required,
        "model_id": running.model_id,
        "endpoints": {
            "models": f"{base}/v1/models",
            "chat_completions": f"{base}/v1/chat/completions",
            "embeddings": f"{base}/v1/embeddings",
            "health": f"{base}/health",
        },
    }


def start(
    port: int = 5001,
    api_key: Optional[str] = None,
    allow_lan: bool = False,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Start the server; raises ServerError if it can't."""
    global _current
    host = "0.0.0.0" if allow_lan else "127.0.0.1"
    if allow_lan and not api_key:
        raise ServerError("An API key is required to expose the server to your network")

    with _lock:
        if _current and _current.thread.is_alive():
            raise ServerError(f"A server is already running on port {_current.port}. Stop it first.")
        if model_id:
            inference.resolve_model(model_id)  # fail early on an unknown model
        if not _port_is_free(host, port):
            raise ServerError(f"Port {port} is already in use")

        server = _Server(uvicorn.Config(build_app(api_key), host=host, port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, name="openai-api-server", daemon=True)
        thread.start()

        deadline = time.time() + 15
        while not server.started and thread.is_alive() and time.time() < deadline:
            time.sleep(0.05)
        if not server.started:
            server.should_exit = True
            raise ServerError("Server failed to start")

        _current = _Running(server, thread, host, port, bool(api_key), model_id)

    if model_id:  # warm the model in the background; requests also load on demand
        def preload() -> None:
            try:
                inference.load_model(model_id)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Preloading {model_id} failed: {exc}")

        threading.Thread(target=preload, daemon=True).start()

    logger.info(f"API server started on {host}:{port}")
    return _describe(_current)


def stop() -> bool:
    """Stop the server; returns False if none was running."""
    global _current
    with _lock:
        running, _current = _current, None
    if not running:
        return False
    running.server.should_exit = True
    running.thread.join(timeout=10)
    logger.info("API server stopped")
    return True


def status() -> Optional[Dict[str, Any]]:
    running = _current
    return _describe(running) if running and running.thread.is_alive() else None

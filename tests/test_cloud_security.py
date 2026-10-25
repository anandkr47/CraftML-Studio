"""Host/Origin guard: allowed desktop origins on every OS, rejected web origins, HTTP and WebSocket."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest

from api.security import DEFAULT_ORIGINS, LocalOnlyGuard, allowed_origins


async def inner_app(scope, receive, send):
    if scope["type"] == "websocket":
        await receive()
        await send({"type": "websocket.accept"})
        return
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def call(scope_type="http", host="127.0.0.1:5000", origin=None):
    headers = []
    if host is not None:
        headers.append((b"host", host.encode()))
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    scope = {"type": scope_type, "headers": headers, "path": "/api/cloud/providers", "method": "GET"}
    sent = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        sent.append(message)

    asyncio.run(LocalOnlyGuard(inner_app)(scope, receive, send))
    return sent


def status(sent):
    return sent[0].get("status") or sent[0]["type"]


@pytest.mark.parametrize("origin", [
    "tauri://localhost",             # macOS / Linux WebView
    "http://tauri.localhost",        # Windows WebView2
    "https://tauri.localhost",       # Windows with useHttpsScheme
    "http://localhost:1420",         # dev server
    "http://127.0.0.1:1420",
])
def test_desktop_origins_are_allowed(origin):
    assert status(call(origin=origin)) == 200
    assert call("websocket", origin=origin)[0]["type"] == "websocket.accept"


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost:3000", "null", "http://tauri.localhost.evil.com"])
def test_foreign_origins_are_rejected(origin):
    assert status(call(origin=origin)) == 403
    closed = call("websocket", origin=origin)[0]
    assert closed == {"type": "websocket.close", "code": 1008}


def test_requests_without_origin_are_allowed_for_local_tools():
    assert status(call(origin=None)) == 200  # curl, Rust sidecar health check


@pytest.mark.parametrize("host", ["evil.example:5000", "192.168.1.5:5000", "rebind.attacker.com", None])
def test_non_loopback_hosts_are_rejected_dns_rebinding(host):
    assert status(call(host=host)) == 403


@pytest.mark.parametrize("host", ["127.0.0.1:5000", "localhost:5000", "localhost", "[::1]:5000"])
def test_loopback_hosts_are_allowed(host):
    assert status(call(host=host)) == 200


def test_trailing_slash_origin_is_normalised_and_env_extends_the_list(monkeypatch):
    assert status(call(origin="tauri://localhost/")) == 200
    monkeypatch.setenv("CRAFTML_ALLOWED_ORIGINS", "http://custom.local:9000, ")
    assert "http://custom.local:9000" in allowed_origins() and set(DEFAULT_ORIGINS) <= set(allowed_origins())

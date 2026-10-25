"""
The real app returns ONE error shape everywhere: {"status": "error", "message": <text>, "detail", "code"}.
The frontend reads `message`, so every kind of failure must carry readable text there.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ.setdefault("CRAFTML_USER_DATA_DIR", tempfile.mkdtemp(prefix="craftml-test-"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("httpx")
pytest.importorskip("torch")  # main imports routers whose services need the ML stack

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import main

    # The guard only accepts loopback hosts, so talk to it as the desktop app does.
    return TestClient(main.app, base_url="http://127.0.0.1:5000", headers={"Origin": "tauri://localhost"})


def assert_shape(response, status):
    body = response.json()
    assert response.status_code == status, body
    assert body["status"] == "error" and isinstance(body["message"], str) and body["message"]
    assert "detail" in body and body["code"]
    return body


def test_unknown_route(client):
    assert_shape(client.get("/api/definitely-not-a-route"), 404)


def test_http_exception_from_a_handler_carries_its_message(client):
    body = assert_shape(client.get("/api/chat/sessions/does-not-exist"), 404)
    assert body["message"] == "Session not found" and body["detail"] == "Session not found"


def test_validation_errors_name_the_field(client):
    body = assert_shape(client.post("/api/train/start", json={
        "model_name": "m", "dataset_path": "/d.jsonl", "training_config": {"max_seq_length": 99999}}), 422)
    assert "training_config.max_seq_length" in body["message"] and isinstance(body["detail"], list)


def test_typed_cloud_errors(client):
    body = assert_shape(client.post("/api/train/start", json={
        "model_name": "m", "dataset_path": "/d.jsonl", "cloud": {"provider": "runpod", "gpu_id": "x"}}), 400)
    assert "credentials" in body["message"] and body["code"] == "not_configured"


def test_wrong_method(client):
    assert_shape(client.delete("/api/health"), 405)

"""
Tests for the chat sessions API and the OpenAI-compatible router.
Inference is replaced with a fake so no model weights are needed.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ["CRAFTML_USER_DATA_DIR"] = tempfile.mkdtemp(prefix="craftml-test-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat
from api.openai_compat import create_router
from db.models import Base, engine, init_db
from services import inference
from services.inference import InferenceError, ModelInfo


def fake_stream(model_id, messages, params, usage):
    usage.prompt_tokens, usage.completion_tokens = 3, 2
    for piece in ("Hello", " world"):
        yield piece


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    init_db()

    info = ModelInfo(id="tiny", name="tiny", path="/x", kind="full")

    def resolve(model_id):
        if model_id != "tiny":
            raise InferenceError("not found")
        return info

    monkeypatch.setattr(inference, "discover_models", lambda: [info])
    monkeypatch.setattr(inference, "resolve_model", resolve)
    monkeypatch.setattr(inference, "stream_chat", fake_stream)
    monkeypatch.setattr(inference, "chat", lambda m, msgs, p: ("Hello world", type("U", (), {
        "prompt_tokens": 3, "completion_tokens": 2, "finish_reason": "stop"})()))

    app = FastAPI()
    app.include_router(chat.router, prefix="/api/chat")
    app.include_router(create_router(), prefix="/v1")
    app.include_router(create_router("secret"), prefix="/secure")
    return TestClient(app)


def sse_events(text):
    return [line[6:] for line in text.splitlines() if line.startswith("data: ")]


def test_v1_models_lists_local_models(client):
    data = client.get("/v1/models").json()
    assert data["object"] == "list" and data["data"][0]["id"] == "tiny"


def test_chat_completion_non_streaming(client):
    r = client.post("/v1/chat/completions", json={"model": "tiny", "messages": [{"role": "user", "content": "hi"}]})
    body = r.json()
    assert body["choices"][0]["message"]["content"] == "Hello world"
    assert body["usage"]["total_tokens"] == 5


def test_chat_completion_streaming_ends_with_done(client):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "tiny", "stream": True, "messages": [{"role": "user", "content": "hi"}]},
    )
    events = sse_events(r.text)
    assert events[-1] == "[DONE]"
    deltas = [json.loads(e)["choices"][0]["delta"].get("content", "") for e in events[:-1]]
    assert "".join(deltas) == "Hello world"
    assert json.loads(events[-2])["choices"][0]["finish_reason"] == "stop"


def test_unknown_model_is_404_openai_error(client):
    r = client.post("/v1/chat/completions", json={"model": "nope", "messages": [{"role": "user", "content": "x"}]})
    assert r.status_code == 404 and r.json()["error"]["code"] == "model_not_found"


def test_api_key_enforced_when_configured(client):
    assert client.get("/secure/models").status_code == 401
    assert client.get("/secure/models", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_session_roundtrip_and_streamed_reply_is_persisted(client):
    session = client.post("/api/chat/sessions", json={"model_id": "tiny", "system_prompt": "Be brief"}).json()
    sid = session["id"]

    r = client.post(f"/api/chat/sessions/{sid}/messages/stream", json={"content": "Say hello"})
    events = sse_events(r.text)
    done = json.loads(events[-2])
    assert done["object"] == "craftml.done" and done["usage"]["completion_tokens"] == 2

    saved = client.get(f"/api/chat/sessions/{sid}").json()
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]
    assert saved["messages"][1]["content"] == "Hello world"
    assert saved["title"] == "Say hello"  # auto-titled from the first message


def test_send_without_model_is_rejected(client):
    sid = client.post("/api/chat/sessions", json={}).json()["id"]
    assert client.post(f"/api/chat/sessions/{sid}/messages/stream", json={"content": "hi"}).status_code == 400


def test_export_markdown_and_delete(client):
    sid = client.post("/api/chat/sessions", json={"model_id": "tiny"}).json()["id"]
    client.post(f"/api/chat/sessions/{sid}/messages/stream", json={"content": "hi"})
    md = client.get(f"/api/chat/sessions/{sid}/export?format=markdown").text
    assert "### User" in md and "Hello world" in md
    assert client.delete(f"/api/chat/sessions/{sid}").json()["deleted"] is True
    assert client.get(f"/api/chat/sessions/{sid}").status_code == 404


def test_build_prompt_trims_old_history_but_keeps_system_and_last():
    history = [{"role": "user", "content": "x" * 9000}, {"role": "assistant", "content": "y" * 9000},
               {"role": "user", "content": "latest"}]
    prompt = chat.build_prompt("sys", history)
    assert prompt[0] == {"role": "system", "content": "sys"}
    assert prompt[-1]["content"] == "latest"
    assert len(prompt) < len(history) + 1

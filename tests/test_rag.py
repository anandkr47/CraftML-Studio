"""
Tests for chunking, the knowledge-base store/search, the /api/kb routes and
KB-grounded chat. Embeddings are faked (hashed bag-of-words) so no model is needed.
"""

import hashlib
import json
import math
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

from api import chat, kb
from db.models import Base, engine, init_db
from services import embeddings, inference
from services.inference import ModelInfo
from services.rag import build_context_prompt
from services.rag.chunking import chunk_text
from services.rag.store import EMBEDDING_DIM


def fake_embed(texts, model_name=None):
    vectors = []
    for text in texts:
        vec = [0.0] * EMBEDDING_DIM
        for word in text.lower().split():
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    init_db()
    monkeypatch.setattr(embeddings, "embed", fake_embed)

    info = ModelInfo(id="tiny", name="tiny", path="/x", kind="full")
    seen = {}

    def stream(model_id, messages, params, usage):
        seen["messages"] = messages
        yield "ok"

    monkeypatch.setattr(inference, "resolve_model", lambda m: info)
    monkeypatch.setattr(inference, "stream_chat", stream)

    app = FastAPI()
    app.include_router(kb.router, prefix="/api/kb")
    app.include_router(chat.router, prefix="/api/chat")
    test_client = TestClient(app)
    test_client.seen = seen
    return test_client


def upload(client, name, text):
    return client.post("/api/kb/documents", files={"files": (name, text.encode(), "text/plain")})


def test_chunk_text_respects_size_and_overlaps():
    text = " ".join(f"word{i}" for i in range(600))
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) > 3
    assert all(len(c) <= 200 + 40 + 1 for c in chunks)
    assert chunks[0][-20:].strip() in chunks[1]  # overlap carries context forward


def test_chunk_text_empty():
    assert chunk_text("   \n ") == []


def test_upload_list_search_delete(client):
    assert upload(client, "cats.md", "Cats are small furry pets that purr and chase mice.").status_code == 200
    assert upload(client, "rust.txt", "Rust is a systems language with ownership and borrowing.").status_code == 200

    listing = client.get("/api/kb/documents").json()
    assert {d["name"] for d in listing["documents"]} == {"cats.md", "rust.txt"}
    assert listing["stats"]["chunks"] == 2

    hit = client.post("/api/kb/search", json={"query": "ownership and borrowing in rust", "top_k": 1}).json()
    assert hit["results"][0]["document"] == "rust.txt"

    doc_id = next(d["id"] for d in listing["documents"] if d["name"] == "rust.txt")
    assert client.delete(f"/api/kb/documents/{doc_id}").status_code == 200
    after = client.post("/api/kb/search", json={"query": "ownership and borrowing in rust", "top_k": 5}).json()
    assert {r["document"] for r in after["results"]} == {"cats.md"}


def test_unsupported_and_empty_files_are_reported(client):
    r = client.post("/api/kb/documents", files={"files": ("x.exe", b"bin", "application/octet-stream")})
    assert r.status_code == 400 and "Unsupported" in r.json()["detail"]
    assert upload(client, "blank.txt", "   ").status_code == 400


def test_build_context_prompt_numbers_sources():
    prompt = build_context_prompt("Be brief", [{"document": "a.md", "chunk_index": 0, "text": "alpha"}])
    assert prompt.startswith("Be brief") and "[1] (a.md, chunk 0)" in prompt and "alpha" in prompt
    assert build_context_prompt("same", []) == "same"


def test_chat_with_kb_injects_context_and_returns_sources(client):
    upload(client, "cats.md", "Cats are small furry pets that purr and chase mice.")
    sid = client.post("/api/chat/sessions", json={"model_id": "tiny", "use_kb": True}).json()["id"]

    r = client.post(f"/api/chat/sessions/{sid}/messages/stream", json={"content": "what do cats chase?"})
    done = json.loads([l[6:] for l in r.text.splitlines() if l.startswith("data: ")][-2])
    assert done["sources"][0]["document"] == "cats.md"
    assert "chase mice" in client.seen["messages"][0]["content"]  # context went into the system message

    saved = client.get(f"/api/chat/sessions/{sid}").json()["messages"][-1]
    assert saved["sources"][0]["document"] == "cats.md"


def test_chat_without_kb_has_no_sources(client):
    upload(client, "cats.md", "Cats are small furry pets.")
    sid = client.post("/api/chat/sessions", json={"model_id": "tiny"}).json()["id"]
    client.post(f"/api/chat/sessions/{sid}/messages/stream", json={"content": "cats?"})
    assert all(m["role"] != "system" for m in client.seen["messages"])

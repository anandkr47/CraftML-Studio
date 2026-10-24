"""
Tests for model cards, the local API server manager and the deployment service.
The Hugging Face upload is mocked; the local server is a real in-process uvicorn.
"""

import os
import socket
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ["CRAFTML_USER_DATA_DIR"] = tempfile.mkdtemp(prefix="craftml-test-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import httpx
import pytest

from core.ml.deployment import build_model_card
from db.models import Base, engine, init_db
from services import api_server, deployment_service, inference, jobs
from services.inference import ModelInfo


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    api_server.stop()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def tiny_model(monkeypatch):
    info = ModelInfo(id="train_ab12cd34", name="train_ab12cd34", path="/models/train_ab12cd34/final", kind="lora")
    monkeypatch.setattr(inference, "discover_models", lambda: [info])
    monkeypatch.setattr(inference, "resolve_model", lambda m: info if m == info.id else (_ for _ in ()).throw(
        inference.InferenceError("not found")))
    return info


# --- model cards -----------------------------------------------------------

def test_model_card_for_lora_has_peft_usage_and_training_details():
    card = build_model_card(
        "me/tiny-chat", "lora", base_model="org/base", description="Chat tuned.",
        training_details={"Epochs": 3, "Method": "QLORA"},
    )
    assert card.startswith("---\nlibrary_name: peft\nbase_model: org/base")
    assert "Chat tuned." in card and "- **Epochs:** 3" in card
    assert 'PeftModel.from_pretrained(base, "me/tiny-chat")' in card


def test_model_card_for_gguf_mentions_filename():
    card = build_model_card("me/x", "gguf", filename="x.Q4_K_M.gguf")
    assert "library_name: gguf" in card and 'filename="x.Q4_K_M.gguf"' in card


# --- local API server ------------------------------------------------------

def test_server_serves_v1_with_api_key_and_stops(tiny_model):
    port = free_port()
    info = api_server.start(port=port, api_key="secret")
    assert info["auth_required"] and info["base_url"] == f"http://127.0.0.1:{port}/v1"

    assert httpx.get(f"http://127.0.0.1:{port}/health").json()["status"] == "ok"
    assert httpx.get(f"{info['base_url']}/models").status_code == 401
    ok = httpx.get(f"{info['base_url']}/models", headers={"Authorization": "Bearer secret"})
    assert ok.json()["data"][0]["id"] == tiny_model.id

    assert api_server.status()["running"]
    assert api_server.stop() is True
    assert api_server.status() is None


def test_server_rejects_second_instance_busy_port_and_open_lan(tiny_model):
    port = free_port()
    api_server.start(port=port)
    with pytest.raises(api_server.ServerError, match="already running"):
        api_server.start(port=free_port())
    api_server.stop()

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        busy = s.getsockname()[1]
        with pytest.raises(api_server.ServerError, match="in use"):
            api_server.start(port=busy)

    with pytest.raises(api_server.ServerError, match="API key"):
        api_server.start(port=free_port(), allow_lan=True)


# --- deployment service ----------------------------------------------------

def test_start_local_records_job_without_leaking_key(tiny_model):
    port = free_port()
    dep_id = deployment_service.start_local(tiny_model.id, port, "secret", False)
    job = jobs.get(dep_id)
    assert job["status"] == "running" and "api_key" not in job["params"]
    assert job["result"]["port"] == port

    assert deployment_service.stop_deployment(dep_id) is True
    assert jobs.get(dep_id)["status"] == "stopped" and api_server.status() is None


def test_failed_local_start_marks_job_failed(tiny_model):
    with pytest.raises(api_server.ServerError):
        deployment_service.start_local(tiny_model.id, free_port(), None, True)
    failed = jobs.list_jobs(job_type="deploy")[0]
    assert failed["status"] == "failed" and "API key" in failed["error"]


def test_huggingface_export_builds_card_from_finetune_job(tiny_model, monkeypatch):
    train_id = jobs.create("finetune", {
        "model_name": "org/base", "training_method": "qlora", "dataset_path": "/d/data.jsonl",
        "training_config": {"num_epochs": 2, "learning_rate": 0.0002}, "lora_config": {"r": 8, "lora_alpha": 16},
    })
    info = ModelInfo(id=train_id, name=train_id, path="/models/x/final", kind="lora")
    monkeypatch.setattr(inference, "resolve_model", lambda m: info)

    captured = {}

    def fake_deploy(model_path, repo_name, hf_token, private, model_card):
        captured.update(path=model_path, repo=repo_name, token=hf_token, card=model_card)
        return {"status": "success", "url": f"https://huggingface.co/{repo_name}"}

    monkeypatch.setattr(deployment_service, "deploy_to_huggingface", fake_deploy)

    dep_id = deployment_service.start_huggingface(train_id, "me/tuned", hf_token="tok", description="Hi")
    for _ in range(100):
        if jobs.get(dep_id)["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)

    job = jobs.get(dep_id)
    assert job["status"] == "completed" and job["result"]["repo_url"] == "https://huggingface.co/me/tuned"
    assert "hf_token" not in job["params"] and captured["token"] == "tok"
    assert "base_model: org/base" in captured["card"] and "LoRA rank / alpha:** 8 / 16" in captured["card"]
    assert "data.jsonl" in captured["card"]


def test_huggingface_export_failure_is_recorded(tiny_model, monkeypatch):
    monkeypatch.setattr(deployment_service, "deploy_to_huggingface",
                        lambda **kw: {"status": "failed", "error": "401 unauthorized"})
    monkeypatch.setattr("api.modelhub.get_hf_token", lambda: None)
    dep_id = deployment_service.start_huggingface(tiny_model.id, "me/x")
    for _ in range(100):
        if jobs.get(dep_id)["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)
    job = jobs.get(dep_id)
    assert job["status"] == "failed" and "401" in job["error"]

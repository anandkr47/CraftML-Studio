"""Tests for telemetry sampling, OOM alerts, KV-cache estimates and the monitor API."""

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

from api import monitor
from db.models import Base, engine, init_db
from services import inference, jobs
from services.inference import ModelInfo
from services.monitoring import alerts, telemetry


def reading(ram=40.0, gpu_kind=None, vram=0.0, total_mb=16000.0):
    gpu = None
    if gpu_kind:
        gpu = {"kind": gpu_kind, "name": "x", "util_percent": 10.0, "vram_total_mb": total_mb,
               "vram_used_mb": total_mb * vram / 100, "vram_percent": vram}
    return {"timestamp": 0, "cpu": {"percent": 5, "count": 8},
            "memory": {"total_mb": total_mb, "used_mb": total_mb * ram / 100, "percent": ram}, "gpu": gpu}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    init_db()


# --- telemetry -------------------------------------------------------------

def test_sample_is_nonblocking_and_complete():
    import time

    start = time.time()
    r = telemetry.sample()
    assert time.time() - start < 0.5
    assert r["memory"]["total_mb"] > 0 and 0 <= r["memory"]["percent"] <= 100
    assert "percent" in r["cpu"] and "process_rss_mb" in r
    assert telemetry.history(1)[-1]["timestamp"] <= time.time()


# --- alerts ----------------------------------------------------------------

def test_no_alerts_when_memory_is_fine():
    assert alerts.evaluate(reading(ram=50, gpu_kind="nvidia", vram=40)) == []


def test_ram_and_vram_pressure_levels():
    ids = {a["id"]: a["severity"] for a in alerts.evaluate(reading(ram=88, gpu_kind="nvidia", vram=95))}
    assert ids == {"ram": "warning", "vram": "critical"}


def test_apple_unified_memory_only_alerts_once():
    found = alerts.evaluate(reading(ram=94, gpu_kind="apple", vram=94))
    assert [a["id"] for a in found] == ["ram"]


def test_running_finetune_gets_an_oom_alert_under_pressure():
    job_id = jobs.create("finetune", {}, status="running")
    found = alerts.evaluate(reading(ram=40, gpu_kind="nvidia", vram=97))
    training = [a for a in found if a["id"] == f"train-{job_id}"]
    assert training and training[0]["severity"] == "critical" and training[0]["job_id"] == job_id
    assert not [a for a in alerts.evaluate(reading(ram=40, gpu_kind="nvidia", vram=50)) if a["id"].startswith("train-")]


# --- KV cache / context fit ------------------------------------------------

LLAMA_7B = {"num_hidden_layers": 32, "num_attention_heads": 32, "num_key_value_heads": 32, "hidden_size": 4096}


def test_kv_cache_estimate_matches_known_value():
    # 7B Llama, fp16, 4096 tokens: 2 * 32 layers * 32 heads * 128 dim * 4096 * 2 bytes = 2 GiB
    assert alerts.estimate_kv_cache_mb(LLAMA_7B, 4096) == pytest.approx(2048.0)


def test_grouped_query_attention_shrinks_the_cache():
    gqa = {**LLAMA_7B, "num_key_value_heads": 8}
    assert alerts.estimate_kv_cache_mb(gqa, 4096) == pytest.approx(512.0)
    assert alerts.estimate_kv_cache_mb({"hidden_size": 1}, 10) is None


@pytest.fixture()
def local_model(monkeypatch, tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(LLAMA_7B))
    info = ModelInfo(id="m", name="m", path=str(tmp_path), kind="full", size_mb=13000.0)
    monkeypatch.setattr(inference, "resolve_model", lambda m: info if m == "m" else (_ for _ in ()).throw(
        inference.InferenceError("nope")))
    monkeypatch.setattr(inference, "is_loaded", lambda m: False)
    return info


def test_context_fit_risk_levels(local_model):
    roomy = alerts.check_context_fit("m", 4096, reading(ram=0, total_mb=64000))
    assert roomy["risk"] == "ok" and roomy["required_mb"] == pytest.approx(13000 + 2048, abs=1)

    tight = alerts.check_context_fit("m", 4096, reading(ram=0, total_mb=17000))
    assert tight["risk"] == "high"

    small = alerts.check_context_fit("m", 4096, reading(ram=0, total_mb=8000))
    assert small["risk"] == "exceeds"


def test_loaded_model_only_needs_kv_cache(local_model, monkeypatch):
    monkeypatch.setattr(inference, "is_loaded", lambda m: True)
    result = alerts.check_context_fit("m", 4096, reading(ram=50, total_mb=8000))
    assert result["weights_mb"] == 0 and result["risk"] == "ok"


def test_unknown_config_is_reported_not_guessed(monkeypatch):
    info = ModelInfo(id="g", name="g", path="/x.gguf", kind="gguf", size_mb=4000.0)
    monkeypatch.setattr(inference, "resolve_model", lambda m: info)
    assert alerts.check_context_fit("g", 2048, reading())["known"] is False


# --- API -------------------------------------------------------------------

def test_monitor_api(local_model):
    app = FastAPI()
    app.include_router(monitor.router, prefix="/api/monitor")
    client = TestClient(app)

    snap = client.get("/api/monitor/snapshot").json()
    assert "memory" in snap and isinstance(snap["alerts"], list)
    assert client.get("/api/monitor/history?limit=5").json()["points"]
    assert client.get("/api/monitor/context-check?model_id=m&context=2048").json()["known"] is True
    assert client.get("/api/monitor/context-check?model_id=zzz&context=2048").status_code == 404

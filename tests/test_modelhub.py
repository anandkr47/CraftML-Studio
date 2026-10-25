"""
Model Hub routes: local model management must never touch anything outside the models
directory, downloads validate their inputs, and Hub errors map to useful statuses.
(No network: the Hub client calls are replaced.)
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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import modelhub
from core.config import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    data = tmp_path / "data"
    models = data / "models"
    models.mkdir(parents=True)
    (data / "precious.txt").write_text("user data")
    (models / "mine").mkdir()
    (models / "mine" / "config.json").write_text("{}")
    monkeypatch.setattr(settings, "models_dir", models)
    app = FastAPI()
    app.include_router(modelhub.router, prefix="/api/modelhub")
    return TestClient(app), data, models


@pytest.mark.parametrize("name", ["%2E%2E", "..", "%2E", "..%2F..", "a%2F..%2F..", "%5C..%5C.."])
def test_delete_refuses_paths_outside_the_models_dir(client, name):
    c, data, models = client
    r = c.delete(f"/api/modelhub/local/{name}")
    assert r.status_code in (400, 404)
    assert (data / "precious.txt").exists() and (models / "mine").exists()


@pytest.mark.parametrize("name", ["%2E%2E", "..%2F.."])
def test_info_refuses_paths_outside_the_models_dir(client, name):
    c, _, _ = client
    assert c.get(f"/api/modelhub/local/{name}/info").status_code in (400, 404)


def test_delete_and_info_work_for_real_models(client):
    c, _, models = client
    assert c.get("/api/modelhub/local/mine/info").json()["name"] == "mine"
    assert c.delete("/api/modelhub/local/mine").json()["deleted"] is True
    assert not (models / "mine").exists()
    assert c.delete("/api/modelhub/local/mine").status_code == 404


def test_local_listing_hides_work_directories(client):
    c, _, models = client
    (models / ".tmp-compress_1").mkdir()
    names = [m["name"] for m in c.get("/api/modelhub/local").json()["models"]]
    assert names == ["mine"]


@pytest.mark.parametrize("repo", ["../evil", "a/../../b", "/abs", "owner/name/extra", "", "a b"])
def test_download_rejects_bad_repo_ids(client, repo, monkeypatch):
    monkeypatch.setattr(modelhub, "snapshot_download", lambda **k: pytest.fail("must not download"))
    c, _, _ = client
    assert c.post("/api/modelhub/download", json={"model_name": repo}).status_code in (400, 422)


def test_download_rejects_bad_filenames(client, monkeypatch):
    monkeypatch.setattr(modelhub, "hf_hub_download", lambda **k: pytest.fail("must not download"))
    c, _, _ = client
    r = c.post("/api/modelhub/download", json={"model_name": "org/repo", "filename": "../../x.gguf"})
    assert r.status_code == 400


def test_download_maps_hub_errors(client, monkeypatch):
    from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError

    import httpx

    def response(code):
        return httpx.Response(code, request=httpx.Request("GET", "https://huggingface.co/api/models/org/repo"))

    c, _, _ = client
    cases = ((RepositoryNotFoundError("nope", response=response(404)), 404),
             (GatedRepoError("gated", response=response(403)), 403), (RuntimeError("boom"), 502))
    for exc, status in cases:
        def fail(**kwargs):
            raise exc
        monkeypatch.setattr(modelhub, "snapshot_download", fail)
        assert c.post("/api/modelhub/download", json={"model_name": "org/repo"}).status_code == status


def test_download_saves_under_the_models_dir(client, monkeypatch):
    c, _, models = client
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        Path(kwargs["local_dir"]).mkdir(parents=True, exist_ok=True)
        (Path(kwargs["local_dir"]) / "config.json").write_text("{}")

    monkeypatch.setattr(modelhub, "snapshot_download", fake)
    r = c.post("/api/modelhub/download", json={"model_name": "HuggingFaceTB/SmolLM2-135M"})
    assert r.status_code == 200
    assert Path(seen["local_dir"]) == (models / "HuggingFaceTB_SmolLM2-135M").resolve()

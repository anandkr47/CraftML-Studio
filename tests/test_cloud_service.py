"""
Backend integration of the cloud layer (needs SQLAlchemy + cryptography; runs in CI):
DB-backed run store, remote fine-tunes through the real job pipeline, startup reconciliation,
the remote model registry feeding model discovery, and the legacy HF-token migration.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ["CRAFTML_USER_DATA_DIR"] = tempfile.mkdtemp(prefix="craftml-test-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("cryptography")

from core.cloud import events
from core.cloud.errors import ConfigError
from core.cloud.manager import RunRecord
from core.cloud.providers.base import CloudProvider
from core.cloud.providers.remote_inference import TogetherProvider
from core.cloud.schemas import (
    AccountInfo, Capabilities, ProviderId, RemoteJobHandle, parse_event_line,
)
from core.config import settings
from db.models import Base, engine, init_db
from services import cloud_service, hf_auth, inference, jobs, training_service


class FakeSecrets:
    def __init__(self, data=None): self.data, self.directory = dict(data or {}), Path(".")
    def get(self, n): return self.data.get(n)
    def set(self, n, v): self.data[n] = v
    def exists(self, n): return n in self.data
    def delete(self, n): return self.data.pop(n, None) is not None


class ScriptedProvider(CloudProvider):
    id = ProviderId.RUNPOD
    label = "Scripted"
    capabilities = Capabilities(training=True)
    fields: List = []

    def __init__(self, hold=False, configured=True):
        self.hold, self.configured, self.calls = hold, configured, []

    def validate_credentials(self): return AccountInfo(name="x")
    def is_configured(self): return self.configured

    def submit_training(self, spec, bundle):
        self.calls.append("submit")
        return RemoteJobHandle(provider=self.id, remote_id="pod-7", job_id=spec.job_id, gpu_name="RTX 4090", price_per_hour=0.5)

    def stream_events(self, handle, stop):
        lines = [events.encode("status", status="running"),
                 events.encode("progress", current_epoch=1, total_epochs=1, current_step=1, total_steps=2, loss=2.0, vram_gb=9.5, learning_rate=1e-4)]
        for line in lines:
            yield parse_event_line(line)
        if self.hold:
            while not stop():
                time.sleep(0.02)
            return
        yield parse_event_line(events.encode("progress", current_epoch=1, total_epochs=1, current_step=2, total_steps=2, loss=1.0))
        yield parse_event_line(events.encode("status", status="completed"))

    def fetch_artifacts(self, handle, dest):
        final = Path(dest) / "final"
        final.mkdir(parents=True, exist_ok=True)
        (final / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "org/base"}))
        return final

    def cancel(self, handle): self.calls.append("cancel")
    def cleanup(self, handle): self.calls.append("cleanup")
    def get_status(self, handle): return "running"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    init_db()
    monkeypatch.setattr(hf_auth, "get_hf_token", lambda: "hf_testtoken_0123456789abcdef")
    yield


def use(monkeypatch, provider):
    monkeypatch.setattr(cloud_service, "make_provider", lambda pid: provider)
    return provider


def params(tmp_path, **cloud):
    data = tmp_path / "d.jsonl"
    data.write_text('{"instruction":"a","output":"b"}\n')
    return {"model_name": "org/base", "dataset_path": str(data), "training_method": "qlora",
            "cloud": {"provider": "runpod", "gpu_id": "4090", "max_runtime_minutes": 30, **cloud}}


def wait_done(job_id, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        job = jobs.get(job_id)
        if job["status"] not in ("pending", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


# --------------------------------------------------------------------------- run store

def test_run_store_roundtrip_and_orphan_semantics():
    store = cloud_service.DbRunStore()
    handle = RemoteJobHandle(provider=ProviderId.RUNPOD, remote_id="pod-1", job_id="train_a", gpu_name="A", price_per_hour=0.4)
    store.save(RunRecord(handle=handle))
    assert [r.job_id for r in store.active()] == ["train_a"] and store.known_remote_ids(ProviderId.RUNPOD) == {"pod-1"}

    store.update("train_a", status="completed", ended_at=time.time())
    record = store.get("train_a")
    assert record.status == "completed" and record.ended_at and record.handle.gpu_name == "A"
    assert store.active() == [] and store.known_remote_ids(ProviderId.RUNPOD) == set()  # a finished run's leftovers are orphans
    assert store.get("missing") is None


# --------------------------------------------------------------------------- remote fine-tune through the real job pipeline

def test_remote_finetune_runs_through_the_job_pipeline(tmp_path, monkeypatch):
    provider = use(monkeypatch, ScriptedProvider())
    job_id = training_service.start_training(params(tmp_path))
    job = wait_done(job_id)

    assert job["status"] == "completed", job["error"]
    assert Path(job["result"]["output_dir"]).name == "final" and (Path(settings.models_dir) / job_id / "final" / "adapter_config.json").exists()
    assert job["params"]["cloud"]["provider"] == "runpod" and "hf_token" not in json.dumps(job["params"])

    points = jobs.get_metrics(job_id)
    assert [p["step"] for p in points] == [1, 2] and points[0]["vram_gb"] == 9.5 and points[0]["learning_rate"] == 1e-4
    assert points[1]["vram_gb"] == 9.5  # telemetry carried forward when an event has none
    assert any("Running on Scripted (RTX 4090)" in line for line in jobs.get_logs(job_id)["logs"])

    assert provider.calls == ["submit", "cleanup"]
    assert cloud_service.run_store.get(job_id).status == "completed" and cloud_service.active_runs() == []
    assert any(m.id == job_id and m.kind == "lora" for m in inference.discover_models())  # the adapter is chat-ready


def test_stopping_a_remote_job_cancels_and_cleans_up_the_remote_resource(tmp_path, monkeypatch):
    provider = use(monkeypatch, ScriptedProvider(hold=True))
    job_id = training_service.start_training(params(tmp_path))
    deadline = time.time() + 10
    while not jobs.get_metrics(job_id) and time.time() < deadline:
        time.sleep(0.05)
    assert [r["job_id"] for r in cloud_service.active_runs()] == [job_id]  # billing while it runs

    assert training_service.stop_training(job_id) is True
    job = wait_done(job_id)
    assert job["status"] == "stopped"
    deadline = time.time() + 10
    while "cleanup" not in provider.calls and time.time() < deadline:
        time.sleep(0.05)
    assert provider.calls[-2:] == ["cancel", "cleanup"] and cloud_service.run_store.get(job_id).status == "stopped"


def test_unconfigured_or_unsuitable_targets_fail_before_a_job_exists(tmp_path, monkeypatch):
    use(monkeypatch, ScriptedProvider(configured=False))
    with pytest.raises(ConfigError, match="credentials are not set"):
        training_service.start_training(params(tmp_path))
    assert jobs.list_jobs(job_type="finetune") == []

    use(monkeypatch, ScriptedProvider())
    monkeypatch.setattr(hf_auth, "get_hf_token", lambda: None)
    with pytest.raises(ConfigError, match="Hugging Face token"):
        training_service.start_training(params(tmp_path))
    with pytest.raises(ConfigError, match="Choose an SSH host"):
        training_service.start_training(params(tmp_path, provider="ssh", ssh_profile=None))


# --------------------------------------------------------------------------- startup reconciliation

def test_startup_terminates_runs_left_by_the_previous_process(monkeypatch):
    provider = use(monkeypatch, ScriptedProvider())
    monkeypatch.setattr(hf_auth, "migrate_legacy", lambda: False)
    cloud_service.run_store.save(RunRecord(handle=RemoteJobHandle(provider=ProviderId.RUNPOD, remote_id="pod-old", job_id="train_old")))

    report = cloud_service.startup()
    assert provider.calls == ["cleanup"] and any("train_old" in line for line in report)
    row = cloud_service.run_store.get("train_old")
    assert row.status == "interrupted" and "terminated" in row.error


# --------------------------------------------------------------------------- remote model registry

def test_registered_cloud_models_appear_in_discovery_and_resolve_to_endpoints(monkeypatch):
    class Http:
        def request(self, *a, **k): raise AssertionError("no network expected")

    provider = TogetherProvider(FakeSecrets({"cloud/together/api_key": "tgp-key-0123456789"}), http=Http())
    monkeypatch.setattr(cloud_service, "make_provider", lambda pid: provider)
    cloud_service.configure_inference()

    model = cloud_service.add_remote_model(ProviderId.TOGETHER, "llama", "meta/llama-3")
    assert model.id == "cloud:together:llama"
    found = {m.id: m for m in inference.discover_models()}
    assert found["cloud:together:llama"].kind == "remote" and found["cloud:together:llama"].name == "llama (cloud)"
    assert cloud_service.endpoint_for("cloud:together:llama").model == "meta/llama-3"

    with pytest.raises(ConfigError, match="already exists"):
        cloud_service.add_remote_model(ProviderId.TOGETHER, "llama", "meta/llama-3")
    assert cloud_service.delete_remote_model("cloud:together:llama") is True
    assert "cloud:together:llama" not in {m.id for m in inference.discover_models()}
    inference.configure_remote(lambda: [], lambda m: None)


def test_inference_registration_rejects_training_only_and_unconfigured_providers(monkeypatch):
    use(monkeypatch, ScriptedProvider())  # training only
    with pytest.raises(ConfigError, match="doesn't offer remote inference"):
        cloud_service.add_remote_model(ProviderId.RUNPOD, "x", "m", "ep")
    monkeypatch.setattr(cloud_service, "make_provider", lambda pid: TogetherProvider(FakeSecrets({}), http=None))
    with pytest.raises(ConfigError, match="credentials are not set"):
        cloud_service.add_remote_model(ProviderId.TOGETHER, "x", "m")


# --------------------------------------------------------------------------- HF token: encrypted store + legacy migration

class FakeKeyring:
    priority = 5
    def __init__(self): self.items = {}
    def get_password(self, s, u): return self.items.get((s, u))
    def set_password(self, s, u, v): self.items[(s, u)] = v


def test_legacy_hf_token_is_migrated_into_the_encrypted_store_and_old_files_removed(tmp_path):
    from cryptography.fernet import Fernet

    from core.cloud.secrets import SecretStore

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    key = Fernet.generate_key()
    (legacy / ".key").write_bytes(key)
    (legacy / "hf_token.enc").write_bytes(Fernet(key).encrypt(b"hf_legacytoken_abcdefghijklmnop"))
    (legacy / "hf_metadata.json").write_text(json.dumps({"username": "ann", "token_preview": "hf_legac...mnop"}))

    store = SecretStore(tmp_path / "secrets", keyring_backend=FakeKeyring())
    assert hf_auth.migrate_legacy(legacy, store) is True
    assert store.get("hf/token") == "hf_legacytoken_abcdefghijklmnop" and store.get("hf/username") == "ann"
    assert [p.name for p in legacy.iterdir()] == []  # plaintext-equivalent material is gone
    assert hf_auth.migrate_legacy(legacy, store) is False  # nothing left to migrate


def test_a_corrupt_legacy_token_is_left_alone(tmp_path):
    from core.cloud.secrets import SecretStore

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / ".key").write_bytes(b"not a fernet key")
    (legacy / "hf_token.enc").write_bytes(b"garbage")
    assert hf_auth.migrate_legacy(legacy, SecretStore(tmp_path / "s", keyring_backend=FakeKeyring())) is False
    assert (legacy / "hf_token.enc").exists()  # never destroy what couldn't be migrated


def test_hf_status_never_reveals_the_token(monkeypatch, tmp_path):
    from core.cloud.secrets import SecretStore

    monkeypatch.undo()  # use the real hf_auth functions against a temp store
    store = SecretStore(tmp_path / "s", keyring_backend=FakeKeyring())
    monkeypatch.setattr(hf_auth, "_store", lambda: store)
    hf_auth.save_hf_token("hf_secretsecretsecret1234567890", "ann")
    status = hf_auth.status()
    assert status == {"is_authenticated": True, "username": "ann", "token_preview": "hf_…7890"}
    assert "secretsecret" not in json.dumps(status)
    hf_auth.delete_hf_token()
    assert hf_auth.status()["is_authenticated"] is False


def test_settings_api_has_no_endpoint_that_returns_the_token():
    from api import settings as settings_api

    routes = {(m, r.path) for r in settings_api.router.routes for m in r.methods}
    assert ("GET", "/hf-token") not in routes  # the old plaintext endpoint is gone
    assert {("POST", "/hf-token"), ("GET", "/hf-token/status"), ("DELETE", "/hf-token")} <= routes


def test_saved_hf_token_is_exposed_to_hugging_face_downloads(monkeypatch, tmp_path):
    from core.cloud.secrets import SecretStore

    monkeypatch.undo()
    store = SecretStore(tmp_path / "s", keyring_backend=FakeKeyring())
    monkeypatch.setattr(hf_auth, "_store", lambda: store)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    hf_auth.save_hf_token("hf_envtoken_0123456789abcdef", "ann")
    assert os.environ["HF_TOKEN"] == "hf_envtoken_0123456789abcdef"  # huggingface_hub picks this up
    hf_auth.delete_hf_token()
    assert "HF_TOKEN" not in os.environ
    store.set("hf/token", "hf_fromstore_0123456789abcdef")
    hf_auth.apply_to_environment()  # what startup does
    assert os.environ["HF_TOKEN"] == "hf_fromstore_0123456789abcdef"
    monkeypatch.delenv("HF_TOKEN", raising=False)

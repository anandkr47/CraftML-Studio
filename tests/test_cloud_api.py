"""
/api/cloud routes with the service layer stubbed: validation, error mapping, write-only secrets,
and the origin guard in front of them.  Uses a tiny ASGI driver (no httpx/TestClient needed).
"""

import asyncio
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest
from fastapi import FastAPI

from core.cloud.errors import AuthError, CapacityError, HostKeyError
from core.cloud.schemas import Capabilities, FieldSpec, GpuOption, InstanceInfo, ProviderId, ProviderInfo

SECRET = "rpa_THISMUSTNEVERAPPEARINRESPONSES1234"


def asgi(app, method, path, body=None, headers=None):
    payload = json.dumps(body).encode() if body is not None else b""
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "path": path,
        "raw_path": path.encode(), "query_string": b"", "scheme": "http", "root_path": "",
        "server": ("127.0.0.1", 5000), "client": ("127.0.0.1", 1),
        "headers": [(b"host", b"127.0.0.1:5000"), (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode())] + [(k.encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    raw = b"".join(m.get("body", b"") for m in sent[1:])
    return sent[0]["status"], (json.loads(raw) if raw else None)


class FakeStorage:
    def storage_info(self):
        return {"backend": "keychain", "secure": True, "detail": "OS keychain"}


@pytest.fixture()
def api(monkeypatch):
    calls = {}
    fake = types.ModuleType("services.cloud_service")
    fake.secrets = lambda: FakeStorage()
    fake.providers_info = lambda: [ProviderInfo(
        id=ProviderId.RUNPOD, label="RunPod", capabilities=Capabilities(training=True, inference=True),
        fields=[FieldSpec(name="api_key", label="API key")], configured=True)]

    def save_credentials(provider_id, values):
        calls["saved"] = (provider_id, values)
        if values.get("api_key") == "bad":
            raise AuthError("RunPod rejected the API key.", hint="Create a new key.")
        return {"configured": True, "account": {"name": "me"}}

    fake.save_credentials = save_credentials
    fake.clear_credentials = lambda pid: calls.setdefault("cleared", pid)

    def list_gpus(pid):
        if pid is ProviderId.MODAL:
            raise CapacityError("No GPUs listed right now.")
        return [GpuOption(id="4090", name="RTX 4090", vram_gb=24, price_per_hour=0.44)]

    fake.list_gpus = list_gpus
    fake.estimate = lambda target: {"provider": target.provider.value, "price_per_hour": 0.44,
                                    "worst_case_cost": round(0.44 * target.max_runtime_minutes / 60, 2)}
    fake.active_runs = lambda: [{"job_id": "train_1", "provider": "runpod", "estimated_cost": 0.12}]
    fake.orphans = lambda: [InstanceInfo(provider=ProviderId.RUNPOD, remote_id="pod-x", name="craftml-lost", status="RUNNING")]
    fake.terminate = lambda pid, rid: calls.setdefault("terminated", (pid, rid))
    fake.ssh_profiles = lambda: [{"name": "box", "host": "h", "port": 22, "username": "u", "runtime": "venv",
                                  "workdir": "craftml", "inference_port": None, "host_key_pinned": False}]
    fake.ssh_save = lambda profile, key, passphrase: calls.setdefault("ssh_saved", (profile, key, passphrase))
    fake.ssh_delete = lambda name: True
    fake.ssh_probe = lambda name: {"host": "h", "port": 22, "key_type": "ssh-ed25519", "fingerprint": "SHA256:abc", "status": "unknown"}

    def ssh_trust(name, key_type, fingerprint):
        raise HostKeyError("The server's key is different from the one you confirmed.", fingerprint="SHA256:new", changed=True)

    fake.ssh_trust = ssh_trust
    fake.ssh_test = lambda name: {"os": "Linux", "gpus": [], "docker": True, "ready": False}

    from core.cloud.schemas import RemoteModel

    registry = {}

    def add_remote_model(provider, name, remote_model, endpoint_id=None):
        if provider is ProviderId.RUNPOD and not endpoint_id:
            raise CapacityError("An endpoint id is required.")  # any typed error: mapping is tested elsewhere
        model = RemoteModel(id=RemoteModel.make_id(provider, name), provider=provider, name=name,
                            remote_model=remote_model, endpoint_id=endpoint_id)
        registry[model.id] = model
        return model

    fake.list_remote_models = lambda: list(registry.values())
    fake.add_remote_model = add_remote_model
    fake.delete_remote_model = lambda mid: registry.pop(mid, None) is not None
    fake.test_remote_model = lambda mid: f"{mid} responded"
    fake.catalog = lambda pid: [{"id": "meta/llama", "name": "Llama", "context_length": 8192}]

    monkeypatch.setitem(sys.modules, "services.cloud_service", fake)
    import services

    monkeypatch.setattr(services, "cloud_service", fake, raising=False)  # `from services import cloud_service`
    monkeypatch.delitem(sys.modules, "api.cloud", raising=False)
    import api.cloud
    from api.errors import register_cloud_error_handler
    from api.security import LocalOnlyGuard

    app = FastAPI()
    register_cloud_error_handler(app)
    app.include_router(api.cloud.router, prefix="/api/cloud")
    app.calls = calls
    return LocalOnlyGuard(app), app


def test_providers_and_storage(api):
    guarded, _ = api
    status, body = asgi(guarded, "GET", "/api/cloud/providers")
    assert status == 200 and body[0]["id"] == "runpod" and body[0]["fields"][0]["name"] == "api_key" and body[0]["configured"] is True
    assert asgi(guarded, "GET", "/api/cloud/storage")[1]["secure"] is True


def test_saving_credentials_passes_values_to_the_service_but_never_echoes_them(api):
    guarded, app = api
    status, body = asgi(guarded, "PUT", "/api/cloud/providers/runpod/credentials", {"values": {"api_key": SECRET}})
    assert status == 200 and app.calls["saved"][1] == {"api_key": SECRET}
    assert SECRET not in json.dumps(body)


def test_rejected_credentials_map_to_401_with_a_helpful_message(api):
    guarded, _ = api
    status, body = asgi(guarded, "PUT", "/api/cloud/providers/runpod/credentials", {"values": {"api_key": "bad"}})
    assert status == 401 and body["code"] == "auth_failed" and "Create a new key." in body["message"]


def test_unknown_provider_ids_are_422(api):
    guarded, _ = api
    assert asgi(guarded, "PUT", "/api/cloud/providers/aws/credentials", {"values": {}})[0] == 422


def test_gpu_list_and_typed_error_mapping(api):
    guarded, _ = api
    assert asgi(guarded, "GET", "/api/cloud/providers/runpod/gpus")[1][0]["price_per_hour"] == 0.44
    status, body = asgi(guarded, "GET", "/api/cloud/providers/modal/gpus")
    assert status == 409 and body["code"] == "no_capacity"


def test_estimate_validates_the_target(api):
    guarded, _ = api
    ok = asgi(guarded, "POST", "/api/cloud/training/estimate", {"provider": "runpod", "gpu_id": "4090", "max_runtime_minutes": 120})
    assert ok == (200, {"provider": "runpod", "price_per_hour": 0.44, "worst_case_cost": 0.88})
    assert asgi(guarded, "POST", "/api/cloud/training/estimate", {"provider": "together"})[0] == 422  # can't train there
    assert asgi(guarded, "POST", "/api/cloud/training/estimate", {"provider": "ssh", "max_runtime_minutes": 1})[0] == 422


def test_instances_orphans_and_terminate(api):
    guarded, app = api
    assert asgi(guarded, "GET", "/api/cloud/instances")[1]["runs"][0]["job_id"] == "train_1"
    assert asgi(guarded, "GET", "/api/cloud/orphans")[1][0]["remote_id"] == "pod-x"
    assert asgi(guarded, "POST", "/api/cloud/instances/runpod/pod-x/terminate")[1]["terminated"] is True
    assert app.calls["terminated"] == (ProviderId.RUNPOD, "pod-x")


def test_ssh_profiles_never_return_keys_and_validate_input(api):
    guarded, app = api
    listing = asgi(guarded, "GET", "/api/cloud/ssh/profiles")[1]["profiles"][0]
    assert "private_key" not in listing and "passphrase" not in listing and listing["host_key_pinned"] is False

    body = {"host": "gpu.example.com", "username": "ml", "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\nx\n-----END OPENSSH PRIVATE KEY-----"}
    status, saved = asgi(guarded, "PUT", "/api/cloud/ssh/profiles/gpu-box", body)
    assert status == 200 and "PRIVATE KEY" not in json.dumps(saved)
    profile, key, _ = app.calls["ssh_saved"]
    assert profile.name == "gpu-box" and profile.port == 22 and "PRIVATE KEY" in key

    assert asgi(guarded, "PUT", "/api/cloud/ssh/profiles/gpu-box", {**body, "port": 70000})[0] == 422
    assert asgi(guarded, "PUT", "/api/cloud/ssh/profiles/bad%20name", body)[0] == 422


def test_host_key_flow_and_changed_key_error_details(api):
    guarded, _ = api
    assert asgi(guarded, "POST", "/api/cloud/ssh/profiles/box/probe")[1]["fingerprint"] == "SHA256:abc"
    status, body = asgi(guarded, "POST", "/api/cloud/ssh/profiles/box/trust", {"key_type": "ssh-ed25519", "fingerprint": "SHA256:abc"})
    assert status == 409 and body["changed"] is True and body["fingerprint"] == "SHA256:new" and body["code"] == "host_key"
    assert asgi(guarded, "POST", "/api/cloud/ssh/profiles/box/test")[1]["ready"] is False


def test_routes_are_unreachable_from_foreign_origins_and_hosts(api):
    guarded, _ = api
    assert asgi(guarded, "GET", "/api/cloud/providers", headers={"Origin": "https://evil.example"})[0] == 403
    assert asgi(guarded, "GET", "/api/cloud/providers", headers={"Origin": "http://tauri.localhost"})[0] == 200
    assert asgi(guarded, "PUT", "/api/cloud/providers/runpod/credentials", {"values": {"api_key": "x"}},
                headers={"Origin": "null"})[0] == 403


def test_training_request_accepts_only_training_capable_cloud_targets():
    from pydantic import ValidationError

    from models.requests import TrainingStartRequest

    base = {"model_name": "org/m", "dataset_path": "/d.jsonl"}
    assert TrainingStartRequest(**base).cloud is None
    ok = TrainingStartRequest(**base, cloud={"provider": "runpod", "gpu_id": "4090", "max_runtime_minutes": 90})
    assert ok.cloud.provider is ProviderId.RUNPOD and ok.cloud.max_runtime_minutes == 90
    with pytest.raises(ValidationError):
        TrainingStartRequest(**base, cloud={"provider": "together"})


def test_remote_model_registry_roundtrip_with_colon_ids(api):
    guarded, _ = api
    body = {"provider": "together", "name": "llama-70b", "remote_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"}
    status, created = asgi(guarded, "POST", "/api/cloud/models", body)
    assert status == 200 and created["id"] == "cloud:together:llama-70b"

    assert [m["id"] for m in asgi(guarded, "GET", "/api/cloud/models")[1]] == ["cloud:together:llama-70b"]
    assert asgi(guarded, "POST", "/api/cloud/models/cloud:together:llama-70b/test")[1] == {"ok": True, "detail": "cloud:together:llama-70b responded"}
    assert asgi(guarded, "DELETE", "/api/cloud/models/cloud:together:llama-70b")[1] == {"deleted": True}
    assert asgi(guarded, "DELETE", "/api/cloud/models/cloud:together:llama-70b")[1] == {"deleted": False}


def test_remote_model_validation(api):
    guarded, _ = api
    assert asgi(guarded, "POST", "/api/cloud/models", {"provider": "together", "name": "bad name!", "remote_model": "x"})[0] == 422
    assert asgi(guarded, "POST", "/api/cloud/models", {"provider": "together", "name": "ok", "remote_model": ""})[0] == 422
    assert asgi(guarded, "POST", "/api/cloud/models", {"provider": "aws", "name": "ok", "remote_model": "x"})[0] == 422
    assert asgi(guarded, "POST", "/api/cloud/models", {"provider": "runpod", "name": "ok", "remote_model": "x"})[0] == 409  # typed error from the service


def test_provider_catalog(api):
    guarded, _ = api
    assert asgi(guarded, "GET", "/api/cloud/providers/together/catalog")[1]["models"][0]["id"] == "meta/llama"

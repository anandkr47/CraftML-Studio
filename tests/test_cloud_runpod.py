"""
HF transport and the RunPod provider.  Provider logic runs against a fake SDK/transport/HTTP; the pod start
script is executed for real (bash + the real worker in stub mode + fake `huggingface_hub`/`runpodctl`).
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.cloud import events
from core.cloud.bundle import build_bundle
from core.cloud.errors import (
    AuthError, CapacityError, ConfigError, QuotaError, RemoteExecutionError, TransientError,
)
from core.cloud.providers import runpod_provider as rp
from core.cloud.providers.runpod_provider import RunPodApi, RunPodProvider, build_pod_script
from core.cloud.schemas import CloudTarget, RemoteJobHandle, RemoteTrainingSpec, ProviderId
from core.cloud.transport import HubTransport, RunRepos, repo_names

LINUX_TOOLS = all(shutil.which(t) for t in ("bash", "timeout", "sha256sum", "tar"))
needs_linux = pytest.mark.skipif(sys.platform == "win32" or not LINUX_TOOLS, reason="needs bash + GNU timeout/sha256sum")
HF_TOKEN = "hf_supersecrettoken0123456789abcdef"


# --------------------------------------------------------------------------- transport

class HttpError(Exception):
    def __init__(self, status, text="boom"):
        super().__init__(text)
        self.response = type("R", (), {"status_code": status})()


class FakeHfApi:
    def __init__(self):
        self.calls, self.fail = [], {}

    def _do(self, name, **kw):
        self.calls.append((name, kw))
        if name in self.fail:
            raise self.fail[name]

    def whoami(self):
        self._do("whoami")
        return {"name": "me"}

    def create_repo(self, **kw): self._do("create_repo", **kw)
    def upload_file(self, **kw): self._do("upload_file", **kw)
    def delete_repo(self, **kw): self._do("delete_repo", **kw)
    def list_repo_files(self, **kw): self._do("list_repo_files", **kw); return ["adapter_config.json"]


def test_repo_names_are_sanitised():
    r = repo_names("me", "train_AB12")
    assert r == RunRepos("me/craftml-train-ab12", "me/craftml-train-ab12-adapter")


def test_upload_creates_private_dataset_repo_and_uploads_every_file():
    api = FakeHfApi()
    repos = HubTransport(HF_TOKEN, api=api).upload_run_assets("train_1", {"a.txt": b"1", "b.txt": b"2"})
    names = [c[0] for c in api.calls]
    assert names == ["whoami", "create_repo", "upload_file", "upload_file"]
    create = api.calls[1][1]
    assert create["private"] is True and create["repo_type"] == "dataset" and create["repo_id"] == repos.dataset_repo


def test_transport_requires_a_token_and_classifies_errors():
    with pytest.raises(ConfigError):
        HubTransport("", api=FakeHfApi())
    for status, expected in ((401, AuthError), (403, AuthError), (503, TransientError), (404, RemoteExecutionError)):
        api = FakeHfApi()
        api.fail["create_repo"] = HttpError(status)
        with pytest.raises(expected):
            HubTransport(HF_TOKEN, api=api).upload_run_assets("train_1", {})
    api = FakeHfApi()
    api.fail["create_repo"] = ConnectionError("reset")
    with pytest.raises(TransientError):
        HubTransport(HF_TOKEN, api=api).upload_run_assets("train_1", {})


def test_download_adapter_validates_and_removes_the_cache_dir(tmp_path):
    def fake_download(repo_id, repo_type, local_dir, token):
        Path(local_dir, "adapter_config.json").write_text("{}")
        Path(local_dir, ".cache").mkdir()

    final = HubTransport(HF_TOKEN, api=FakeHfApi(), snapshot_download=fake_download).download_adapter("me/x", tmp_path)
    assert final == tmp_path / "final" and (final / "adapter_config.json").exists() and not (final / ".cache").exists()

    with pytest.raises(RemoteExecutionError, match="no model files"):
        HubTransport(HF_TOKEN, api=FakeHfApi(), snapshot_download=lambda **kw: None).download_adapter("me/x", tmp_path / "e")


def test_delete_repos_tolerates_missing_repos_and_reports_real_failures():
    api = FakeHfApi()
    api.fail["delete_repo"] = HttpError(404)
    assert HubTransport(HF_TOKEN, api=api).delete_repos(RunRepos("me/a", "me/b")) == []
    api.fail["delete_repo"] = HttpError(500, "server error")
    assert HubTransport(HF_TOKEN, api=api).delete_repos(RunRepos("me/a", "me/b")) == ["me/a", "me/b"]


# --------------------------------------------------------------------------- tolerant field helpers / classification

def test_pod_field_helpers_accept_both_naming_styles():
    pod = {"id": "p1", "name": "craftml-x", "desiredStatus": "running", "costPerHr": "0.44",
           "machine": {"gpuDisplayName": "RTX 4090"}}
    assert (rp.pod_id(pod), rp.pod_name(pod), rp.pod_state(pod), rp.pod_price(pod), rp.pod_gpu(pod)) == ("p1", "craftml-x", "RUNNING", 0.44, "RTX 4090")
    alt = {"podId": "p2", "status": "exited", "adjustedCostPerHr": 0.5, "gpu": {"displayName": "A100"}}
    assert (rp.pod_id(alt), rp.pod_state(alt), rp.pod_price(alt), rp.pod_gpu(alt)) == ("p2", "EXITED", 0.5, "A100")
    assert rp.pod_price({"costPerHr": "n/a"}) is None and rp.pod_gpu({}) is None


def test_gpu_options_filter_small_cards_pick_cheapest_price_and_sort():
    raw = [
        {"id": "A100", "displayName": "A100 80GB", "memoryInGb": 80, "securePrice": 1.9, "communityPrice": 1.2},
        {"id": "4090", "displayName": "RTX 4090", "memoryInGb": 24, "securePrice": 0.69},
        {"id": "3070", "displayName": "RTX 3070", "memoryInGb": 8, "securePrice": 0.1},   # too small
        {"id": "X", "displayName": "No price", "memoryInGb": 48},
    ]
    options = rp.gpu_options(raw)
    assert [o.id for o in options] == ["4090", "A100", "X"]
    assert options[1].price_per_hour == 1.2 and options[2].price_per_hour is None


@pytest.mark.parametrize("message,expected", [
    ("401 Unauthorized", AuthError), ("Invalid API key", AuthError), ("insufficient balance", QuotaError),
    ("There are no longer any instances available with the requested specifications", CapacityError),
    ("Connection timed out", TransientError), ("something odd", RemoteExecutionError),
])
def test_sdk_errors_are_classified(message, expected):
    assert isinstance(rp.classify(Exception(message)), expected)


class FakeSdk:
    def __init__(self):
        self.api_key = None
        self.seen_keys = []
        self.fail = None

    def _rec(self):
        self.seen_keys.append(self.api_key)
        if self.fail:
            raise self.fail

    def get_gpus(self): self._rec(); return [{"id": "g"}]
    def get_pods(self): self._rec(); return []
    def get_pod(self, pid): self._rec(); return None
    def terminate_pod(self, pid): self._rec()
    def create_pod(self, **kw): self._rec(); return {"id": "p"}


def test_api_adapter_sets_the_key_per_call_and_translates_errors():
    sdk = FakeSdk()
    api = RunPodApi("rpa_key_one_1234567890", sdk_loader=lambda: sdk)
    assert api.gpus() == [{"id": "g"}] and api.pod("x") is None and sdk.seen_keys == ["rpa_key_one_1234567890"] * 2
    sdk.fail = Exception("401 unauthorized")
    with pytest.raises(AuthError):
        api.pods()
    sdk.fail = Exception("pod not found")
    api.terminate("p")  # idempotent: already gone is fine
    sdk.fail = Exception("503 service unavailable")
    with pytest.raises(TransientError):
        api.terminate("p")


# --------------------------------------------------------------------------- provider with fakes

class FakeSecrets:
    def __init__(self, data):
        self.data = data
        self.directory = Path(".")

    def get(self, name): return self.data.get(name)
    def exists(self, name): return name in self.data


class FakeApi:
    def __init__(self, pods=None, create_error=None):
        self.pods_list = list(pods or [])
        self.created, self.terminated, self.create_error = [], [], create_error
        self.pod_after_create = {"id": "pod-1", "name": "craftml-train_1", "desiredStatus": "RUNNING",
                                 "costPerHr": 0.44, "machine": {"gpuDisplayName": "RTX 4090"}}

    def gpus(self): return [{"id": "4090", "displayName": "RTX 4090", "memoryInGb": 24, "securePrice": 0.44}]
    def pods(self): return list(self.pods_list)

    def pod(self, remote_id):
        return next((p for p in self.pods_list if rp.pod_id(p) == remote_id), None)

    def create(self, **kw):
        if self.create_error:
            raise self.create_error
        self.created.append(kw)
        self.pods_list.append(self.pod_after_create)
        return self.pod_after_create

    def terminate(self, remote_id):
        self.terminated.append(remote_id)
        self.pods_list = [p for p in self.pods_list if rp.pod_id(p) != remote_id]


class FakeTransport:
    def __init__(self):
        self.uploads, self.deleted, self.log_text = None, [], None

    def username(self): return "me"

    def upload_run_assets(self, job_id, files):
        self.uploads = files
        return repo_names("me", job_id)

    def read_text(self, repo, filename, repo_type="dataset"): return self.log_text
    def download_adapter(self, repo, dest):
        final = Path(dest) / "final"
        final.mkdir(parents=True, exist_ok=True)
        (final / "adapter_config.json").write_text("{}")
        return final

    def delete_repos(self, repos):
        self.deleted.append(repos)
        return []


class Clock:
    def __init__(self): self.t = 0.0
    def now(self): return self.t
    def sleep(self, s): self.t += s


def make_provider(api=None, transport=None, http=None, secrets=None, clock=None):
    clock = clock or Clock()
    provider = RunPodProvider(
        secrets or FakeSecrets({"cloud/runpod/api_key": "rpa_key_0123456789abcdefgh", "hf/token": HF_TOKEN}),
        api_factory=lambda key: api, transport_factory=lambda token: transport,
        http_get=http or (lambda url, headers, timeout: (404, None)), sleep=clock.sleep, clock=clock.now,
    )
    return provider, clock


def spec(tmp_path, minutes=30, gpu="4090", token=HF_TOKEN):
    data = tmp_path / "train.jsonl"
    data.write_text('{"instruction":"a","output":"b"}\n')
    return RemoteTrainingSpec(
        job_id="train_1", model_name="org/base", dataset_path=str(data), output_dir=str(tmp_path / "out"),
        target=CloudTarget(provider="runpod", gpu_id=gpu, max_runtime_minutes=minutes), hf_token=token,
    )


def bundle():
    return build_bundle()


def test_submit_uploads_assets_creates_the_pod_and_never_leaks_the_token_into_the_command(tmp_path):
    api, transport = FakeApi(), FakeTransport()
    provider, _ = make_provider(api, transport)
    handle = provider.submit_training(spec(tmp_path), bundle())

    assert set(transport.uploads) == {"bundle.tar.gz", "bundle.sha256", "job.json", "train.jsonl"}
    job = json.loads(transport.uploads["job.json"])
    assert job["hf"] == {"dataset_repo": "me/craftml-train-1", "adapter_repo": "me/craftml-train-1-adapter"}
    assert job["model_name"] == "org/base" and job["dataset_filename"] == "train.jsonl"

    created = api.created[0]
    assert created["name"] == "craftml-train_1" and created["gpu_type_id"] == "4090" and created["ports"] == "8000/http"
    assert created["env"]["HF_TOKEN"] == HF_TOKEN and created["env"]["CRAFTML_EVENT_TOKEN"]
    assert HF_TOKEN not in created["docker_args"] and created["env"]["CRAFTML_EVENT_TOKEN"] not in created["docker_args"]
    assert "--serve 8000" in created["docker_args"] and "runpodctl" in created["docker_args"]

    assert handle.remote_id == "pod-1" and handle.gpu_name == "RTX 4090" and handle.price_per_hour == 0.44
    assert handle.meta["adapter_repo"] == "me/craftml-train-1-adapter"
    assert HF_TOKEN not in handle.model_dump_json()  # the persisted handle carries no secrets
    assert created["env"]["CRAFTML_EVENT_TOKEN"] not in handle.model_dump_json()


def test_submit_requires_a_gpu_and_a_token(tmp_path):
    provider, _ = make_provider(FakeApi(), FakeTransport())
    with pytest.raises(ConfigError, match="Choose a GPU"):
        provider.submit_training(spec(tmp_path, gpu=None), bundle())
    provider, _ = make_provider(FakeApi(), FakeTransport(), secrets=FakeSecrets({"cloud/runpod/api_key": "rpa_key_0123456789abcdefgh"}))
    with pytest.raises(ConfigError, match="Hugging Face token"):
        provider.submit_training(spec(tmp_path, token=None), bundle())


def test_stale_pod_with_the_same_name_is_terminated_not_reused(tmp_path):
    stale = {"id": "old-pod", "name": "craftml-train_1", "desiredStatus": "RUNNING"}
    api = FakeApi(pods=[stale])
    provider, _ = make_provider(api, FakeTransport())
    provider.submit_training(spec(tmp_path), bundle())
    assert api.terminated == ["old-pod"] and len(api.created) == 1


def test_retry_after_a_timed_out_create_does_not_start_a_second_pod(tmp_path):
    api = FakeApi()
    real_create, attempts = api.create, {"n": 0}

    def flaky_create(**kw):
        attempts["n"] += 1
        pod = real_create(**kw)  # the pod WAS created...
        if attempts["n"] == 1:
            raise TransientError("timed out")  # ...but the response was lost
        return pod

    api.create = flaky_create
    provider, _ = make_provider(api, FakeTransport())
    provider.submit_training(spec(tmp_path), bundle())
    assert len(api.created) == 1 and attempts["n"] == 1  # found by name on the retry, not created again


def test_failed_create_deletes_the_uploaded_repos_and_raises(tmp_path):
    api, transport = FakeApi(create_error=CapacityError("none free")), FakeTransport()
    provider, _ = make_provider(api, transport)
    with pytest.raises(CapacityError):
        provider.submit_training(spec(tmp_path), bundle())
    assert transport.deleted == [repo_names("me", "train_1")]  # user data doesn't linger on the Hub


def handle_for(**meta):
    return RemoteJobHandle(provider=ProviderId.RUNPOD, remote_id="pod-1", job_id="train_1",
                           meta={"dataset_repo": "me/craftml-train-1", "adapter_repo": "me/craftml-train-1-adapter", "port": "8000", **meta})


def lines(*specs):
    return [events.encode(t, **kw) for t, kw in specs]


def scripted_http(responses, seen):
    queue = list(responses)

    def get(url, headers, timeout):
        seen.append((url, headers))
        return queue.pop(0) if queue else (200, {"events": [], "next": 0, "done": True})

    return get


def test_stream_waits_for_boot_then_follows_events_with_the_bearer_token():
    seen = []
    api = FakeApi(pods=[{"id": "pod-1", "name": "craftml-train_1", "desiredStatus": "RUNNING"}])
    http = scripted_http([
        (404, None), (502, None),
        (200, {"events": lines(("status", {"status": "running"}), ("progress", {"current_step": 1, "loss": 2.0})), "next": 2, "done": False}),
        (200, {"events": lines(("progress", {"current_step": 2, "loss": 1.0}), ("status", {"status": "completed"})), "next": 4, "done": True}),
    ], seen)
    provider, clock = make_provider(api, FakeTransport(), http=http)
    provider._event_tokens["pod-1"] = "tok123"

    received = list(provider.stream_events(handle_for(), lambda: False))
    assert [e.type for e in received] == ["status", "progress", "progress", "status"] and received[-1].status == "completed"
    assert seen[0][0] == "https://pod-1-8000.proxy.runpod.net/events?after=0"
    assert seen[0][1] == {"Authorization": "Bearer tok123"}
    assert seen[2][0].endswith("after=0") and seen[3][0].endswith("after=2")  # resumes from the server's cursor


def test_stream_emits_waiting_notes_while_the_pod_boots_and_times_out_eventually():
    api = FakeApi(pods=[{"id": "pod-1", "name": "craftml-train_1", "desiredStatus": "RUNNING"}])
    provider, clock = make_provider(api, FakeTransport())
    provider._event_tokens["pod-1"] = "t"
    received = list(provider.stream_events(handle_for(), lambda: False))
    assert any("Waiting for the pod" in (e.message or "") for e in received)
    assert received[-1].status == "failed" and "didn't start reporting" in received[-1].error
    assert clock.t >= rp.BOOT_TIMEOUT


def test_stream_reports_a_pod_that_died_with_its_uploaded_log():
    transport = FakeTransport()
    transport.log_text = "\n".join(f"line {i}" for i in range(100)) + f"\nBundle checksum mismatch token={HF_TOKEN}"
    provider, _ = make_provider(FakeApi(pods=[]), transport)  # pod no longer exists
    provider._event_tokens["pod-1"] = "t"
    received = list(provider.stream_events(handle_for(), lambda: False))
    assert received[0].level == "error" and "checksum mismatch" in received[0].message and HF_TOKEN not in received[0].message
    assert "line 0" not in received[0].message  # only the tail
    assert received[-1].status == "failed" and "ended before the job finished" in received[-1].error


def test_stream_respects_stop_and_rejects_a_lost_token():
    provider, _ = make_provider(FakeApi(), FakeTransport())
    with pytest.raises(ConfigError, match="event token"):
        list(provider.stream_events(handle_for(), lambda: False))
    provider._event_tokens["pod-1"] = "t"
    assert list(provider.stream_events(handle_for(), lambda: True)) == []


def test_stream_surfaces_a_rejected_event_token():
    provider, _ = make_provider(FakeApi(), FakeTransport(), http=lambda u, h, t: (401, None))
    provider._event_tokens["pod-1"] = "wrong"
    with pytest.raises(RemoteExecutionError, match="rejected the event token"):
        list(provider.stream_events(handle_for(), lambda: False))


def test_cleanup_terminates_the_pod_before_deleting_repos_and_is_idempotent():
    api, transport = FakeApi(pods=[{"id": "pod-1", "name": "craftml-train_1", "desiredStatus": "RUNNING"}]), FakeTransport()
    provider, _ = make_provider(api, transport)
    provider._event_tokens["pod-1"] = "t"
    provider.cleanup(handle_for())
    assert api.terminated == ["pod-1"] and transport.deleted == [RunRepos("me/craftml-train-1", "me/craftml-train-1-adapter")]
    assert "pod-1" not in provider._event_tokens
    provider.cleanup(handle_for())  # second call: nothing left, no error


def test_a_failing_pod_termination_is_raised_but_repos_are_still_deleted():
    api, transport = FakeApi(), FakeTransport()
    api.terminate = lambda rid: (_ for _ in ()).throw(TransientError("RunPod down"))
    provider, _ = make_provider(api, transport)
    with pytest.raises(TransientError):
        provider.cleanup(handle_for())
    assert transport.deleted  # a repo-cleanup problem never hides (or precedes) the billing-relevant failure


def test_cancel_terminates_and_fetch_downloads_the_adapter(tmp_path):
    api, transport = FakeApi(), FakeTransport()
    provider, _ = make_provider(api, transport)
    provider.cancel(handle_for())
    assert api.terminated == ["pod-1"]
    assert (provider.fetch_artifacts(handle_for(), tmp_path) / "adapter_config.json").exists()


def test_list_instances_only_returns_our_pods_and_status_maps_gone():
    api = FakeApi(pods=[
        {"id": "a", "name": "craftml-train_9", "desiredStatus": "RUNNING", "costPerHr": 0.4},
        {"id": "b", "name": "someone-elses-pod", "desiredStatus": "RUNNING"},
    ])
    provider, _ = make_provider(api, FakeTransport())
    assert [i.remote_id for i in provider.list_instances()] == ["a"]
    assert provider.get_status(handle_for()) == "gone" and provider.validate_credentials().name == "RunPod account"
    assert provider.list_gpus()[0].id == "4090"


# --------------------------------------------------------------------------- the real pod script

FAKE_HUB = '''
import os, pathlib, shutil
def hf_hub_download(repo_id, filename, repo_type=None, token=None, local_dir="."):
    src = pathlib.Path(os.environ["FAKE_HUB_DIR"]) / filename
    if not src.exists():
        raise FileNotFoundError(filename)
    dst = pathlib.Path(local_dir) / filename
    shutil.copy(src, dst)
    return str(dst)
class HfApi:
    def __init__(self, token=None): pass
    def upload_file(self, path_or_fileobj, path_in_repo, repo_id, repo_type=None):
        with open(os.environ["FAKE_HUB_LOG"], "a") as f:
            f.write("upload %s %s\\n" % (path_in_repo, repo_id))
'''

BOOTSTRAP = b'''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec "${CRAFTML_PYTHON:-python3}" worker_main.py --job "$CRAFTML_JOB_FILE" "$@"
'''


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_pod_script(tmp_path, monkeypatch, *, corrupt=False, deadman=1):
    hub, tools, fake_mod = tmp_path / "hub", tmp_path / "tools", tmp_path / "pymods"
    for d in (hub, tools, fake_mod / "huggingface_hub"):
        d.mkdir(parents=True)
    (fake_mod / "huggingface_hub" / "__init__.py").write_text(FAKE_HUB)

    b = build_bundle({"bootstrap.sh": BOOTSTRAP})
    (hub / "bundle.tar.gz").write_bytes(b.data)
    (hub / "bundle.sha256").write_text(f"{'0' * 64 if corrupt else b.sha256}  bundle.tar.gz\n")
    (hub / "job.json").write_text(json.dumps({"job_id": "train_1", "model_name": "org/base", "dataset_filename": "d.jsonl"}))
    (hub / "d.jsonl").write_text("{}\n")

    ctl_log = tmp_path / "runpodctl.log"
    ctl = tools / "runpodctl"
    ctl.write_text(f'#!/bin/bash\necho "$@" >> {ctl_log}\nexit 0\n')
    ctl.chmod(0o755)

    port = free_port()
    script = build_pod_script(dataset_repo="me/craftml-train-1", dataset_filename="d.jsonl", max_seconds=60,
                              port=port, workdir=str(tmp_path / "run"), deadman_grace=deadman)
    env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}", "PYTHONPATH": str(fake_mod),
           "FAKE_HUB_DIR": str(hub), "FAKE_HUB_LOG": str(tmp_path / "hub.log"), "HF_TOKEN": HF_TOKEN,
           "CRAFTML_EVENT_TOKEN": "pod-token", "CRAFTML_WORKER_STUB": "1", "CRAFTML_STUB_DELAY": "0.05",
           "CRAFTML_SERVE_GRACE": "2", "RUNPOD_POD_ID": "pod-123", "CRAFTML_PYTHON": sys.executable}
    proc = subprocess.Popen(["bash", "-c", script], env=env, cwd=tmp_path, start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc, port, ctl_log, tmp_path / "hub.log"


def fetch(port, token, path="/events?after=0"):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def wait_for_server(port, deadline=30):
    end = time.time() + deadline
    while time.time() < end:
        try:
            return fetch(port, "pod-token", "/health")
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    raise AssertionError("worker event server never came up")


@needs_linux
def test_pod_script_runs_the_worker_serves_authenticated_events_and_removes_the_pod(tmp_path, monkeypatch):
    proc, port, ctl_log, hub_log = run_pod_script(tmp_path, monkeypatch)
    try:
        assert wait_for_server(port) == {"ok": True}
        with pytest.raises(HTTPError) as unauthorized:
            fetch(port, "wrong-token")
        assert unauthorized.value.code == 401

        deadline, body = time.time() + 30, {"done": False}
        while not body["done"] and time.time() < deadline:
            body = fetch(port, "pod-token")
            time.sleep(0.1)
        decoded = [events.decode(l) for l in body["events"]]
        assert [e["status"] for e in decoded if e and e["type"] == "status"] == ["running", "completed"]
        assert sum(1 for e in decoded if e and e["type"] == "progress") == 5
        assert fetch(port, "pod-token", f"/events?after={body['next']}")["events"] == []  # cursor semantics
        proc.wait(timeout=60)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, 9)

    assert proc.returncode == 0
    assert "remove pod pod-123" in ctl_log.read_text()          # the pod removes itself when the worker ends
    assert not hub_log.exists() or "pod.log" not in hub_log.read_text()  # no failure log on success


@needs_linux
def test_pod_script_aborts_on_a_checksum_mismatch_uploads_its_log_and_still_removes_the_pod(tmp_path, monkeypatch):
    proc, port, ctl_log, hub_log = run_pod_script(tmp_path, monkeypatch, corrupt=True)
    try:
        output, _ = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, 9)
    assert proc.returncode != 0 and b"Bundle checksum mismatch" in output
    assert "upload pod.log me/craftml-train-1" in hub_log.read_text()  # the app can show *why* the pod died
    assert "remove pod pod-123" in ctl_log.read_text()                 # and the pod still removes itself
    assert not (tmp_path / "run" / "craftml_worker").exists()          # the unverified bundle was never extracted


def test_pod_script_contains_the_safety_layers():
    script = build_pod_script(dataset_repo="me/r", dataset_filename="d.jsonl", max_seconds=120)
    assert "trap finish EXIT" in script and "dead-man switch" in script and "sleep 720" in script
    for variant in ("remove pod", "pod remove", "pod delete", "stop pod"):
        assert f"runpodctl {variant}" in script
    assert "timeout --signal=TERM --kill-after=30 120" in script and "sha256sum -c" in script and "HF_TOKEN\"]" in script
    assert HF_TOKEN not in script

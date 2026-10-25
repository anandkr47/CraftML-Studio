"""
Modal: the in-container entry runs for real (real bundle + stub worker, fake HF); the provider runs against a fake `modal` module.
"""

import json
import shutil
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.cloud import events
from core.cloud.bundle import build_bundle
from core.cloud.errors import AuthError, ConfigError, RemoteExecutionError, TransientError
from core.cloud.providers import modal_provider as mp
from core.cloud.providers.modal_provider import ModalProvider, ModalRunner
from core.cloud.schemas import CloudTarget, RemoteTrainingSpec
from core.cloud.transport import RunRepos, repo_names

LINUX_TOOLS = all(shutil.which(t) for t in ("bash", "tar"))
needs_bash = pytest.mark.skipif(sys.platform == "win32" or not LINUX_TOOLS, reason="needs bash")
HF = "hf_supersecrettoken0123456789abcdef"

BOOTSTRAP = b'''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec "${CRAFTML_PYTHON:-python3}" worker_main.py --job "$CRAFTML_JOB_FILE" "$@"
'''


# --------------------------------------------------------------------------- modal_entry (real)

def load_entry():
    import importlib.util

    spec = importlib.util.spec_from_file_location("modal_entry", mp.entry_path())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_fake_hub(tmp_path, monkeypatch, corrupt=False, missing=False):
    hub = tmp_path / "hub"
    hub.mkdir()
    b = build_bundle({"bootstrap.sh": BOOTSTRAP})
    (hub / "bundle.tar.gz").write_bytes(b.data)
    (hub / "bundle.sha256").write_text(f"{'0' * 64 if corrupt else b.sha256}  bundle.tar.gz\n")
    (hub / "job.json").write_text(json.dumps({"job_id": "train_1", "model_name": "org/base", "dataset_filename": "d.jsonl"}))
    if not missing:
        (hub / "d.jsonl").write_text("{}\n")

    import types

    fake = types.ModuleType("huggingface_hub")

    def hf_hub_download(repo_id, filename, repo_type=None, token=None, local_dir="."):
        src = hub / filename
        if not src.exists():
            raise FileNotFoundError(filename)
        dst = Path(local_dir) / filename
        shutil.copy(src, dst)
        return str(dst)

    fake.hf_hub_download = hf_hub_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    monkeypatch.setenv("HF_TOKEN", HF)
    monkeypatch.setenv("CRAFTML_WORKER_STUB", "1")
    monkeypatch.setenv("CRAFTML_STUB_DELAY", "0.02")
    monkeypatch.setenv("CRAFTML_PYTHON", sys.executable)


@needs_bash
def test_entry_downloads_verifies_runs_the_worker_and_forwards_events(tmp_path, monkeypatch):
    install_fake_hub(tmp_path, monkeypatch)
    lines = []
    code = load_entry().run_job(lines.append, "me/repo", "d.jsonl", 120, workdir=str(tmp_path / "work"))
    decoded = [events.decode(l) for l in lines]
    assert code == 0 and decoded[-1]["type"] == "status" and decoded[-1]["status"] == "completed"
    assert sum(1 for e in decoded if e and e["type"] == "progress") == 5
    assert (tmp_path / "work" / "output" / "final" / "adapter_config.json").exists()


@needs_bash
def test_entry_rejects_a_bundle_with_a_bad_checksum_without_running_it(tmp_path, monkeypatch):
    install_fake_hub(tmp_path, monkeypatch, corrupt=True)
    lines = []
    code = load_entry().run_job(lines.append, "me/repo", "d.jsonl", 120, workdir=str(tmp_path / "work"))
    last = events.decode(lines[-1])
    assert code == 1 and last["status"] == "failed" and "checksum mismatch" in last["error"]
    assert not (tmp_path / "work" / "craftml_worker").exists()


def test_entry_reports_download_failures(tmp_path, monkeypatch):
    install_fake_hub(tmp_path, monkeypatch, missing=True)
    lines = []
    assert load_entry().run_job(lines.append, "me/repo", "d.jsonl", 120, workdir=str(tmp_path / "w")) == 1
    assert "Could not download" in events.decode(lines[-1])["error"]


@needs_bash
def test_entry_enforces_the_runtime_limit(tmp_path, monkeypatch):
    install_fake_hub(tmp_path, monkeypatch)
    monkeypatch.setenv("CRAFTML_STUB_DELAY", "30")
    lines = []
    started = time.time()
    code = load_entry().run_job(lines.append, "me/repo", "d.jsonl", 1, workdir=str(tmp_path / "w"))
    assert code == 1 and time.time() - started < 20
    assert "runtime limit" in events.decode(lines[-1])["error"]


# --------------------------------------------------------------------------- provider with a fake modal module

class FakeSecrets:
    def __init__(self, data): self.data, self.directory = data, Path(".")
    def get(self, n): return self.data.get(n)
    def exists(self, n): return n in self.data


class FakeQueue:
    def __init__(self): self.items, self.lock = [], threading.Lock()
    def put(self, line):
        with self.lock: self.items.append(line)
    def get_many(self, n, block=True, timeout=None):
        deadline = time.time() + (timeout or 0)
        while True:
            with self.lock:
                if self.items:
                    out, self.items = self.items[:n], self.items[n:]
                    return out
            if not block or time.time() >= deadline:
                return []
            time.sleep(0.01)


class FakeCall:
    def __init__(self, thread, state): self.thread, self.state = thread, state
    def get(self, timeout=0):
        if self.thread.is_alive():
            raise TimeoutError()
        if self.state.get("error"):
            raise RuntimeError(self.state["error"])
        return 0
    def cancel(self): self.state["cancelled"] = True


class Ctx:
    def __init__(self, log, name, value=None): self.log, self.name, self.value = log, name, value
    def __enter__(self): self.log.append(f"enter {self.name}"); return self.value
    def __exit__(self, *a): self.log.append(f"exit {self.name}")


class FakeModal:
    """Just enough of the `modal` module for ModalRunner."""

    def __init__(self, script, bad_secret=False):
        self.script, self.bad_secret, self.log, self.captured, self.state = script, bad_secret, [], {}, {}
        outer = self

        class Client:
            @staticmethod
            def from_credentials(token_id, token_secret):
                outer.captured["creds"] = (token_id, token_secret)
                client = type("C", (), {})()
                def hello():
                    if outer.bad_secret:
                        raise RuntimeError("Token missing or invalid (authentication failed)")
                client.hello = hello
                return client

        class Image:
            @staticmethod
            def debian_slim(python_version=None):
                outer.captured["python"] = python_version
                return Image()
            def pip_install(self, *pkgs): outer.captured["pkgs"] = pkgs; return self
            def add_local_file(self, local, remote): outer.captured["file"] = (local, remote); return self

        class Secret:
            @staticmethod
            def from_dict(d): outer.captured["secret_keys"] = sorted(d); return d

        class Queue:
            @staticmethod
            def ephemeral(client=None): return Ctx(outer.log, "queue", FakeQueue())

        class App:
            def __init__(self, name): outer.captured["app"] = name
            def function(self, **kw):
                outer.captured["function"] = kw
                def deco(fn):
                    class F:
                        @staticmethod
                        def spawn(queue, repo, filename, seconds):
                            outer.captured["spawn"] = (repo, filename, seconds)
                            def work():
                                try:
                                    outer.script(queue, outer.state)
                                except Exception as exc:  # noqa: BLE001
                                    outer.state["error"] = str(exc)
                            t = threading.Thread(target=work, daemon=True)
                            t.start()
                            return FakeCall(t, outer.state)
                    return F()
                return deco
            def run(self, client=None): return Ctx(outer.log, "app")

        self.Client, self.Image, self.Secret, self.Queue, self.App = Client, Image, Secret, Queue, App


def lines_for(*pairs):
    return [events.encode(t, **kw) for t, kw in pairs]


GOOD = lambda queue, state: [queue.put(l) for l in lines_for(
    ("status", {"status": "running"}), ("progress", {"current_step": 1, "loss": 2.0}),
    ("progress", {"current_step": 2, "loss": 1.0}), ("status", {"status": "completed"}))]


class FakeTransport:
    def __init__(self): self.uploads, self.deleted = None, []
    def username(self): return "me"
    def upload_run_assets(self, job_id, files): self.uploads = files; return repo_names("me", job_id)
    def download_adapter(self, repo, dest):
        final = Path(dest) / "final"; final.mkdir(parents=True, exist_ok=True)
        (final / "adapter_config.json").write_text("{}"); return final
    def delete_repos(self, repos): self.deleted.append(repos); return []


def make_provider(fake, transport=None, secrets=None):
    transport = transport or FakeTransport()
    provider = ModalProvider(
        secrets or FakeSecrets({"cloud/modal/token_id": "ak-abcdefghij", "cloud/modal/token_secret": "as-abcdefghij", "hf/token": HF}),
        runner_factory=lambda i, s: ModalRunner(i, s, modal_module=fake),
        transport_factory=lambda token: transport, sleep=lambda s: None,
    )
    return provider, transport


def spec(tmp_path, gpu="A10G", minutes=30):
    data = tmp_path / "train.jsonl"
    data.write_text("{}\n")
    return RemoteTrainingSpec(job_id="train_1", model_name="org/base", dataset_path=str(data), output_dir=str(tmp_path / "out"),
                              target=CloudTarget(provider="modal", gpu_id=gpu, max_runtime_minutes=minutes))


def submit(provider, tmp_path, **kw):
    return provider.submit_training(spec(tmp_path, **kw), build_bundle())


def test_submit_validates_first_stages_assets_and_describes_the_run(tmp_path):
    fake = FakeModal(GOOD)
    provider, transport = make_provider(fake)
    handle = submit(provider, tmp_path)
    assert fake.captured["creds"] == ("ak-abcdefghij", "as-abcdefghij")
    assert set(transport.uploads) == {"bundle.tar.gz", "bundle.sha256", "job.json", "train.jsonl"}
    assert handle.gpu_id == "A10G" and handle.price_per_hour == 1.10 and handle.meta["dataset_filename"] == "train.jsonl"
    assert HF not in handle.model_dump_json() and handle.remote_id == "modal-train_1"


def test_bad_credentials_fail_before_anything_is_uploaded(tmp_path):
    fake, transport = FakeModal(GOOD, bad_secret=True), FakeTransport()
    provider, _ = make_provider(fake, transport)
    with pytest.raises(AuthError):
        submit(provider, tmp_path)
    assert transport.uploads is None  # no data left the machine


def test_gpu_must_be_chosen_and_known(tmp_path):
    provider, _ = make_provider(FakeModal(GOOD))
    with pytest.raises(ConfigError, match="Choose a GPU"):
        provider.submit_training(spec(tmp_path, gpu=None), build_bundle())
    with pytest.raises(ConfigError, match="Unknown Modal GPU"):
        submit(provider, tmp_path, gpu="B200")


def test_stream_runs_the_function_with_the_right_configuration_and_stops_at_completion(tmp_path):
    fake = FakeModal(GOOD)
    provider, _ = make_provider(fake)
    handle = submit(provider, tmp_path, minutes=45)
    received = list(provider.stream_events(handle, lambda: False))

    assert [e.type for e in received] == ["status", "progress", "progress", "status"] and received[-1].status == "completed"
    assert fake.captured["spawn"] == ("me/craftml-train-1", "train.jsonl", 45 * 60)
    fn = fake.captured["function"]
    assert fn["gpu"] == "A10G" and fn["timeout"] == 45 * 60 + 300 and fn["serialized"] is True
    assert fake.captured["secret_keys"] == ["HF_TOKEN"] and fake.captured["file"][1] == "/root/modal_entry.py"
    assert any(p.startswith("transformers==") for p in fake.captured["pkgs"])
    assert fake.captured["python"] == f"{sys.version_info.major}.{sys.version_info.minor}"
    assert fake.log == ["enter app", "enter queue", "exit queue", "exit app"]  # the ephemeral app is always torn down


def test_a_crashing_function_becomes_a_failed_status_with_the_reason(tmp_path):
    def crash(queue, state):
        queue.put(events.encode("log", message="loading"))
        raise RuntimeError("CUDA out of memory")

    fake = FakeModal(crash)
    provider, _ = make_provider(fake)
    received = list(provider.stream_events(submit(provider, tmp_path), lambda: False))
    assert received[-1].type == "status" and received[-1].status == "failed" and "out of memory" in received[-1].error
    assert fake.log[-2:] == ["exit queue", "exit app"]


def test_events_queued_just_before_exit_are_not_lost(tmp_path):
    def finish_fast(queue, state):
        for l in lines_for(("status", {"status": "running"}), ("status", {"status": "completed"})):
            queue.put(l)  # function returns immediately after queueing the terminal event

    provider, _ = make_provider(FakeModal(finish_fast))
    received = list(provider.stream_events(submit(provider, tmp_path), lambda: False))
    assert received[-1].status == "completed"


def test_stop_tears_down_the_app_and_cancel_cancels_the_call(tmp_path):
    release = threading.Event()
    fake = FakeModal(lambda queue, state: release.wait(10))
    provider, transport = make_provider(fake)
    handle = submit(provider, tmp_path)
    stream = provider.stream_events(handle, lambda: True)
    assert list(stream) == [] and fake.log[-1] == "exit app"

    fake2 = FakeModal(lambda queue, state: release.wait(10))
    provider2, _ = make_provider(fake2)
    handle2 = submit(provider2, tmp_path)
    gen = provider2.stream_events(handle2, lambda: False)
    threading.Thread(target=lambda: (time.sleep(0.2), provider2.cancel(handle2)), daemon=True).start()
    next(gen, None)  # blocks until cancel() makes the call report failure
    release.set()
    assert fake2.state.get("cancelled") is True
    gen.close()
    assert fake2.log[-1] == "exit app"


def test_cleanup_stops_the_app_and_deletes_the_transfer_repos_idempotently(tmp_path):
    fake = FakeModal(GOOD)
    provider, transport = make_provider(fake)
    handle = submit(provider, tmp_path)
    list(provider.stream_events(handle, lambda: False))
    provider.cleanup(handle)
    provider.cleanup(handle)
    assert transport.deleted[0] == RunRepos("me/craftml-train-1", "me/craftml-train-1-adapter")
    assert provider.get_status(handle) == "gone"


def test_fetch_artifacts_downloads_from_the_adapter_repo(tmp_path):
    provider, _ = make_provider(FakeModal(GOOD))
    handle = submit(provider, tmp_path)
    assert (provider.fetch_artifacts(handle, tmp_path / "out") / "adapter_config.json").exists()


def test_gpu_table_and_error_classification():
    provider, _ = make_provider(FakeModal(GOOD))
    gpus = provider.list_gpus()
    assert [g.id for g in gpus][:3] == ["T4", "L4", "A10G"] and all(g.price_per_hour for g in gpus)
    assert isinstance(mp.classify(Exception("Token missing")), AuthError)
    assert isinstance(mp.classify(ConnectionError("reset")), TransientError)
    assert isinstance(mp.classify(Exception("weird")), RemoteExecutionError)
    assert ModalProvider.capabilities.training and not ModalProvider.capabilities.inference

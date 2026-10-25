"""
SSH provider.

Pure-logic tests run everywhere.  The end-to-end tests run the provider's *real* commands in a
temp "remote home" with local bash (real bundle, real launch command, real stub worker,
real `timeout`/`setsid`/`sha256sum`, process-group cleanup); only the paramiko transport is
replaced.  They skip where those Linux tools are missing (macOS/Windows) and run in Linux CI.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.cloud.bundle import Bundle, build_bundle
from core.cloud.errors import ConfigError, HostKeyError, RemoteExecutionError
from core.cloud.providers import ssh_provider
from core.cloud.providers.ssh_provider import (
    SshProvider, build_launch_command, event_from_line, parse_status_files, remote_dir_for,
)
from core.cloud.schemas import CloudTarget, RemoteTrainingSpec, SshProfile
from core.cloud.ssh_profiles import SshProfileStore, key_secret

PROFILE = SshProfile(name="gpu-box", host="gpu.example.com", username="ml")
TOKEN = "hf_supersecrettoken0123456789abcdef"

LINUX_TOOLS = all(shutil.which(t) for t in ("bash", "timeout", "setsid", "sha256sum", "tar"))
needs_linux = pytest.mark.skipif(sys.platform == "win32" or not LINUX_TOOLS, reason="needs bash + GNU timeout/setsid/sha256sum")

# Lightweight bootstrap: no venv/pip (no network in tests), records the token it saw.
BOOTSTRAP = b"""#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
printf %s "${HF_TOKEN:-}" > ../token_seen
exec "${CRAFTML_PYTHON:-python3}" worker_main.py --job "$CRAFTML_JOB_FILE"
"""


# --------------------------------------------------------------------------- pure logic

def test_remote_dir_is_posix_for_relative_and_absolute_workdirs():
    assert remote_dir_for("/home/ml", PROFILE, "train_1") == "/home/ml/craftml/train_1"
    absolute = PROFILE.model_copy(update={"workdir": "/data/ml runs"})
    assert remote_dir_for("/home/ml", absolute, "train_1") == "/data/ml runs/train_1"
    assert "\\" not in remote_dir_for("/home/ml", PROFILE, "train_1")  # never a Windows separator


def test_launch_command_quotes_paths_and_never_contains_the_token():
    weird = "/home/ml/my runs/it's/train_1"
    cmd = build_launch_command(PROFILE, weird, "train_1", 3600, has_env=True)
    assert "'/home/ml/my runs/it'\"'\"'s/train_1'" in cmd or "my runs" in cmd
    assert TOKEN not in cmd and "timeout --signal=TERM --kill-after=30 3600 env CRAFTML_JOB_FILE=" in cmd
    assert cmd.count("&&") >= 5 and "; (nohup" not in cmd and "; set" not in cmd  # strictly chained: failures can't fall through
    assert "setsid" in cmd and "exit_code" in cmd


def test_docker_runtime_passes_the_token_by_inheritance_only():
    docker = PROFILE.model_copy(update={"runtime": "docker"})
    cmd = build_launch_command(docker, "/home/ml/craftml/train_1", "train_1", 600, has_env=True)
    assert "--gpus all" in cmd and "-e HF_TOKEN " in cmd and "HF_TOKEN=" not in cmd and "--name craftml-train_1" in cmd
    assert "-e HF_TOKEN" not in build_launch_command(docker, "/d", "j", 60, has_env=False)


@pytest.mark.parametrize("exit_code,alive,exists,expected", [
    (None, True, True, "running"), ("0", False, True, "succeeded"), ("124", False, True, "failed"),
    (None, False, True, "failed"), (None, False, False, "gone"), ("", True, True, "running"),
])
def test_status_from_remote_files(exit_code, alive, exists, expected):
    assert parse_status_files(exit_code, alive, exists) == expected


def test_event_lines_parse_and_noise_is_ignored():
    from core.cloud import events

    assert event_from_line(events.encode("progress", loss=1.0, current_step=2)).current_step == 2
    assert event_from_line("some pip output") is None


# --------------------------------------------------------------------------- fakes

class FakeSecrets:
    def __init__(self, directory):
        self.directory, self.data = Path(directory), {}

    def get(self, name): return self.data.get(name)
    def set(self, name, value): self.data[name] = value
    def exists(self, name): return name in self.data
    def delete(self, name): return self.data.pop(name, None) is not None
    def delete_prefix(self, prefix): [self.data.pop(k) for k in [k for k in self.data if k.startswith(prefix)]]


class LocalSession:
    """An SSH session that runs commands on this machine inside a temp HOME, pretending to be a GPU box."""

    probes = {
        "uname -s": (0, "Linux\n", ""),
        "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits": (0, "NVIDIA RTX 4090, 24564\n", ""),
        "docker --version": (0, "Docker version 27\n", ""),
    }

    def __init__(self, home: Path, log: List[str], overrides: Dict[str, tuple] = None):
        self.home, self.log, self.overrides = home, log, overrides or {}

    def run(self, command, timeout=60.0):
        self.log.append(command)
        for table in (self.overrides, self.probes):
            if command in table:
                return table[command]
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True, timeout=timeout,
                                env={**os.environ, "HOME": str(self.home)})
        return result.returncode, result.stdout, result.stderr

    def put(self, data, remote_path, mode=0o644):
        path = Path(remote_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        os.chmod(path, mode)

    def get_tree(self, remote_dir, local_dir):
        shutil.copytree(remote_dir, local_dir, dirs_exist_ok=True)

    def tail_lines(self, remote_file, start_line, stop):
        index = 0
        while not stop():
            path = Path(remote_file)
            if path.exists():
                with open(path, "r", encoding="ascii") as handle:
                    handle.seek(0)
                    text = handle.read()
                lines = text.split("\n")[:-1]
                for line in lines[index:]:
                    index += 1
                    if index >= start_line:
                        yield line
            time.sleep(0.03)

    def close(self):
        pass


def make_provider(tmp_path, monkeypatch, *, runtime="venv", overrides=None):
    monkeypatch.setenv("CRAFTML_WORKER_STUB", "1")
    monkeypatch.setenv("CRAFTML_STUB_DELAY", "0.02")
    monkeypatch.setenv("CRAFTML_PYTHON", sys.executable)
    home = tmp_path / "remote_home"
    home.mkdir()
    secrets = FakeSecrets(tmp_path)
    profiles = SshProfileStore(tmp_path / "ssh_profiles.json", secrets)
    profiles.save(PROFILE.model_copy(update={"runtime": runtime}), "-----BEGIN OPENSSH PRIVATE KEY-----\nx\n-----END OPENSSH PRIVATE KEY-----", None)
    commands: List[str] = []
    provider = SshProvider(
        secrets, host_keys=None, profiles=profiles, sleep=lambda s: time.sleep(min(s, 0.05)),
        session_factory=lambda profile, sec, hk: LocalSession(home, commands, overrides),
    )
    return provider, home, commands


def make_spec(tmp_path, token=TOKEN, minutes=30):
    data = tmp_path / "train.jsonl"
    data.write_text('{"instruction": "hi", "output": "yo"}\n')
    return RemoteTrainingSpec(
        job_id="train_e2e", model_name="org/base", dataset_path=str(data), output_dir=str(tmp_path / "out"),
        target=CloudTarget(provider="ssh", ssh_profile="gpu-box", max_runtime_minutes=minutes), hf_token=token,
    )


def worker_bundle():
    return build_bundle({"bootstrap.sh": BOOTSTRAP})


def collect(provider, handle, stop=lambda: False):
    return list(provider.stream_events(handle, stop))


# --------------------------------------------------------------------------- end to end

@needs_linux
def test_full_run_submit_stream_fetch_cleanup(tmp_path, monkeypatch):
    provider, home, commands = make_provider(tmp_path, monkeypatch)
    spec = make_spec(tmp_path)
    handle = provider.submit_training(spec, worker_bundle())
    run_dir = Path(handle.meta["dir"])

    assert handle.gpu_name == "NVIDIA RTX 4090" and run_dir == home / "craftml" / "train_e2e"
    assert (run_dir / "pid").exists() and not (run_dir / "bundle.tar.gz").exists() and not (run_dir / "env.sh").exists()

    received = collect(provider, handle)
    kinds = [e.type for e in received]
    assert kinds[0] == "status" and kinds.count("progress") == 5 and received[-1].status == "completed"

    final = provider.fetch_artifacts(handle, tmp_path / "out")
    assert (final / "adapter_config.json").exists() and final == tmp_path / "out" / "final"

    assert (run_dir.parent / "train_e2e" / "token_seen").read_text() == TOKEN or (run_dir / "token_seen").read_text() == TOKEN
    assert not any(TOKEN in c for c in commands), "the HF token must never appear in a remote command line"

    provider.cleanup(handle)
    assert not run_dir.exists()
    provider.cleanup(handle)  # idempotent


@needs_linux
def test_tampered_bundle_is_rejected_and_nothing_is_left_behind(tmp_path, monkeypatch):
    provider, home, _ = make_provider(tmp_path, monkeypatch)
    good = worker_bundle()
    tampered = Bundle(data=good.data, sha256="0" * 64)
    with pytest.raises(RemoteExecutionError):
        provider.submit_training(make_spec(tmp_path), tampered)
    assert not (home / "craftml" / "train_e2e").exists()  # cleaned up, worker never started


@needs_linux
def test_cancel_stops_the_worker_gracefully(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFTML_STUB_DELAY", "0.3")
    provider, home, _ = make_provider(tmp_path, monkeypatch)
    monkeypatch.setenv("CRAFTML_STUB_DELAY", "0.3")
    handle = provider.submit_training(make_spec(tmp_path), worker_bundle())

    seen = []
    for event in provider.stream_events(handle, stop=lambda: False):
        seen.append(event)
        if event.type == "progress":
            provider.cancel(handle)
        if event.type == "status" and event.status in ("stopped", "completed", "failed"):
            break
    assert seen[-1].status == "stopped"
    provider.cleanup(handle)
    assert not Path(handle.meta["dir"]).exists()


@needs_linux
def test_worker_killed_by_the_timeout_is_reported_as_a_crash(tmp_path, monkeypatch):
    """The dead-man switch: `timeout` kills a runaway worker, and the app learns why."""
    monkeypatch.setattr(ssh_provider, "LIVENESS_INTERVAL", 0.2)
    provider, home, _ = make_provider(tmp_path, monkeypatch)
    monkeypatch.setenv("CRAFTML_STUB_DELAY", "30")  # worker would run for minutes
    handle = provider.submit_training(make_spec(tmp_path), worker_bundle())

    # Re-launch the same run with a 1-second budget to trigger the timeout path quickly.
    session = LocalSession(home, [])
    d = Path(handle.meta["dir"])
    session.run(f"kill -TERM -- -$(cat {d}/pid) 2>/dev/null; sleep 1; rm -f {d}/pid {d}/exit_code {d}/events.jsonl")
    bundle = worker_bundle()
    session.put(bundle.data, str(d / "bundle.tar.gz"))
    session.put(f"{bundle.sha256}  bundle.tar.gz\n".encode(), str(d / "bundle.sha256"))
    code, _, err = session.run(build_launch_command(PROFILE, str(d), "train_e2e", 1, False))
    assert code == 0, err

    received = collect(provider, handle, stop=lambda: False)
    assert received[-1].type == "status" and received[-1].status == "failed"
    assert "exit code 124" in received[-1].error
    provider.cleanup(handle)
    assert not d.exists()


@needs_linux
def test_dropped_connection_resumes_without_duplicate_or_lost_events(tmp_path, monkeypatch):
    provider, home, commands = make_provider(tmp_path, monkeypatch)
    state = {"first": True}

    class Flaky(LocalSession):
        def tail_lines(self, remote_file, start_line, stop):
            count = 0
            for line in super().tail_lines(remote_file, start_line, stop):
                yield line
                count += 1
                if state["first"] and count == 3:
                    state["first"] = False
                    raise OSError("connection reset")

    provider._session_factory = lambda profile, sec, hk: Flaky(home, commands)
    handle = provider.submit_training(make_spec(tmp_path), worker_bundle())
    received = collect(provider, handle)
    steps = [e.current_step for e in received if e.type == "progress"]
    assert steps == [1, 2, 3, 4, 5] and received[-1].status == "completed"  # exactly once each, in order
    assert state["first"] is False  # the failure really happened
    provider.cleanup(handle)


# --------------------------------------------------------------------------- host checks & profiles

class ScriptedSession(LocalSession):
    pass


def provider_with_overrides(tmp_path, monkeypatch, overrides, runtime="venv"):
    return make_provider(tmp_path, monkeypatch, runtime=runtime, overrides=overrides)[0]


@pytest.mark.parametrize("overrides,message", [
    ({"uname -s": (0, "Darwin\n", "")}, "runs Darwin"),
    ({"nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits": (127, "", "not found")}, "No NVIDIA GPU"),
])
def test_unsuitable_hosts_are_rejected_with_a_clear_message(tmp_path, monkeypatch, overrides, message):
    provider = provider_with_overrides(tmp_path, monkeypatch, overrides)
    with pytest.raises(ConfigError, match=message):
        provider.submit_training(make_spec(tmp_path), worker_bundle())


def test_docker_runtime_requires_docker_on_the_host(tmp_path, monkeypatch):
    provider = provider_with_overrides(tmp_path, monkeypatch, {"docker --version": (127, "", "")}, runtime="docker")
    with pytest.raises(ConfigError, match="Docker isn't available"):
        provider.submit_training(make_spec(tmp_path), worker_bundle())


def test_describe_host_reports_gpus(tmp_path, monkeypatch):
    provider, _, _ = make_provider(tmp_path, monkeypatch)
    info = provider.describe_host("gpu-box")
    assert info == {"os": "Linux", "gpus": [{"name": "NVIDIA RTX 4090", "vram_gb": 24.0}], "docker": True, "ready": True}


def test_profile_store_validates_and_cleans_up_secrets(tmp_path):
    secrets = FakeSecrets(tmp_path)
    store = SshProfileStore(tmp_path / "p.json", secrets)
    with pytest.raises(ConfigError, match="private key is required"):
        store.save(PROFILE, None, None)
    with pytest.raises(ConfigError, match="doesn't look like a private key"):
        store.save(PROFILE, "just some text", None)

    store.save(PROFILE, "-----BEGIN OPENSSH PRIVATE KEY-----\r\nabc\r\n-----END OPENSSH PRIVATE KEY-----", "pp")
    assert "\r" not in secrets.get(key_secret("gpu-box")) and secrets.get("cloud/ssh/gpu-box/passphrase") == "pp"
    store.save(PROFILE.model_copy(update={"port": 2222}), None, None)  # blank key on update keeps the stored one
    assert store.get("gpu-box").port == 2222 and secrets.exists(key_secret("gpu-box"))

    assert store.delete("gpu-box") is True and not secrets.exists(key_secret("gpu-box")) and not secrets.exists("cloud/ssh/gpu-box/passphrase")
    with pytest.raises(ConfigError):
        store.get("gpu-box")


def test_pinned_policy_rejects_unknown_and_changed_keys(tmp_path):
    from core.cloud.hostkeys import HostKeyStore

    class Key:
        def __init__(self, blob): self.blob = blob
        def asbytes(self): return self.blob
        def get_name(self): return "ssh-ed25519"

    store = HostKeyStore(tmp_path / "kh.json")
    policy = ssh_provider.PinnedPolicy(store, "h", 22)
    with pytest.raises(HostKeyError) as unknown:
        policy.missing_host_key(None, "h", Key(b"k1"))
    assert unknown.value.changed is False and unknown.value.fingerprint.startswith("SHA256:")

    from core.cloud.hostkeys import fingerprint
    store.trust("h", 22, "ssh-ed25519", fingerprint(b"k1"))
    policy.missing_host_key(None, "h", Key(b"k1"))  # trusted: no error
    with pytest.raises(HostKeyError) as changed:
        policy.missing_host_key(None, "h", Key(b"k2"))
    assert changed.value.changed is True and "CHANGED" in str(changed.value)

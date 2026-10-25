"""
SSH provider against a REAL sshd with real paramiko (CI "ssh-integration" job).

Skipped unless CRAFTML_TEST_SSH_HOST / _PORT / _USER / _KEY point at an SSH server whose user can run
GNU timeout/setsid/sha256sum/tar/python3 and has a stub `nvidia-smi` on PATH.  The worker runs in stub
mode (no GPU, no network), so what is exercised is the transport: host-key pinning, key auth, SFTP,
launch, event tailing, artifact download, cleanup, and the inference port-forward.
"""

import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "apps" / "backend"))  # services/, api/, db/
sys.path.insert(0, str(HERE))

import pytest

pytest.importorskip("paramiko")
pytest.importorskip("cryptography")

ENV = {k: os.environ.get(f"CRAFTML_TEST_SSH_{k}") for k in ("HOST", "PORT", "USER", "KEY")}
pytestmark = pytest.mark.skipif(not all(ENV.values()), reason="CRAFTML_TEST_SSH_* not configured")

from core.cloud.bundle import build_bundle
from core.cloud.errors import AuthError, HostKeyError
from core.cloud.hostkeys import HostKeyStore
from core.cloud.providers.ssh_provider import SshProvider, probe_host_key
from core.cloud.schemas import CloudTarget, ProviderId, RemoteModel, RemoteTrainingSpec, SshProfile
from core.cloud.secrets import SecretStore
from core.cloud.ssh_profiles import SshProfileStore
from services.inference import GenerationParams, Usage
from services.inference.remote_backend import RemoteBackend
from test_cloud_remote import OpenAIHandler, UrllibHttp

BOOTSTRAP = b"""#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export CRAFTML_WORKER_STUB=1 CRAFTML_STUB_DELAY=0.05
exec python3 worker_main.py --job "$CRAFTML_JOB_FILE" "$@"
"""


@pytest.fixture()
def env(tmp_path):
    secrets = SecretStore(tmp_path / "secrets", keyring_backend=None)
    profiles = SshProfileStore(tmp_path / "profiles.json", secrets)
    host_keys = HostKeyStore(tmp_path / "known_hosts.json")
    profile = SshProfile(name="ci", host=ENV["HOST"], port=int(ENV["PORT"]), username=ENV["USER"])
    profiles.save(profile, Path(ENV["KEY"]).read_text(), None)
    provider = SshProvider(secrets, host_keys=host_keys, profiles=profiles)
    return provider, profiles, host_keys, profile, secrets


def trust(host_keys, profile):
    key_type, fingerprint = probe_host_key(profile.host, profile.port)
    host_keys.trust(profile.host, profile.port, key_type, fingerprint)
    return key_type, fingerprint


def test_unverified_host_is_refused_with_its_fingerprint_then_accepted_once_trusted(env):
    provider, _, host_keys, profile, _ = env
    key_type, fingerprint = probe_host_key(profile.host, profile.port)
    with pytest.raises(HostKeyError) as refused:
        provider.describe_host("ci")
    assert refused.value.fingerprint == fingerprint and refused.value.changed is False

    host_keys.trust(profile.host, profile.port, key_type, fingerprint)
    info = provider.describe_host("ci")
    assert info["os"] == "Linux" and info["gpus"][0]["name"] == "NVIDIA CI Stub GPU" and info["ready"] is True


def test_a_changed_host_key_is_a_hard_error(env):
    provider, _, host_keys, profile, _ = env
    host_keys.trust(profile.host, profile.port, "ssh-ed25519", "SHA256:" + "A" * 43)
    with pytest.raises(HostKeyError) as err:
        provider.describe_host("ci")
    assert err.value.changed is True and "CHANGED" in err.value.message


def test_a_key_the_server_does_not_accept_is_an_auth_error(env, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    provider, profiles, host_keys, profile, _ = env
    trust(host_keys, profile)
    stranger = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()).decode()
    profiles.save(profile, stranger, None)
    with pytest.raises(AuthError):
        provider.describe_host("ci")


def test_full_training_run_over_real_ssh(env, tmp_path):
    provider, _, host_keys, profile, _ = env
    trust(host_keys, profile)
    data = tmp_path / "train.jsonl"
    data.write_text('{"instruction": "a", "output": "b"}\n')
    spec = RemoteTrainingSpec(
        job_id="train_ci_e2e", model_name="org/base", dataset_path=str(data), output_dir=str(tmp_path / "out"),
        target=CloudTarget(provider="ssh", ssh_profile="ci", max_runtime_minutes=10),
    )
    handle = provider.submit_training(spec, build_bundle({"bootstrap.sh": BOOTSTRAP}))
    try:
        received = list(provider.stream_events(handle, lambda: False))
        assert sum(1 for e in received if e.type == "progress") == 5 and received[-1].status == "completed"
        final = provider.fetch_artifacts(handle, tmp_path / "out")
        assert (final / "adapter_config.json").exists()
        for _ in range(50):  # the worker writes exit_code just after its final event
            if provider.get_status(handle) == "succeeded":
                break
            time.sleep(0.1)
        assert provider.get_status(handle) == "succeeded"
    finally:
        provider.cleanup(handle)
    assert provider.get_status(handle) == "gone"  # the run directory is removed


def test_inference_through_a_real_ssh_port_forward(env):
    provider, profiles, host_keys, profile, _ = env
    trust(host_keys, profile)
    server = ThreadingHTTPServer(("127.0.0.1", 0), OpenAIHandler)
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    profiles.save(profile.model_copy(update={"inference_port": server.server_address[1]}), None, None)
    try:
        model = RemoteModel(id="cloud:ssh:ci", provider=ProviderId.SSH, name="ci", remote_model="m", endpoint_id="ci")
        endpoint = provider.inference_endpoint(model)
        text = "".join(RemoteBackend(endpoint, UrllibHttp()).stream([{"role": "user", "content": "hi"}], GenerationParams(), Usage()))
        assert text == "tunnel works" and server.seen[0][0] == "/v1/chat/completions"
    finally:
        provider.close_tunnels()
        server.shutdown()

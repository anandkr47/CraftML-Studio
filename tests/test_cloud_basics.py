"""Errors, retry/backoff and the worker event protocol (pure Python, no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.cloud import events
from core.cloud.errors import AuthError, CloudError, HostKeyError, TransientError
from core.cloud.retry import backoff_delay, retry_after_seconds, retry_call
from core.cloud.schemas import CloudTarget, ProviderId, RemoteEvent, RemoteModel, SshProfile


def test_errors_carry_status_and_hint():
    err = AuthError("Key rejected", hint="Generate a new key.")
    assert err.status_code == 401 and err.user_message() == "Key rejected Generate a new key."
    assert CloudError("x").user_message() == "x"
    assert HostKeyError("changed", fingerprint="SHA256:abc", changed=True).changed is True


def test_backoff_is_bounded_and_jittered():
    assert backoff_delay(0, rng=lambda: 1.0) == 0.5
    assert backoff_delay(10, cap=20, rng=lambda: 1.0) == 20  # capped
    assert backoff_delay(3, rng=lambda: 0.0) == 0.0  # full jitter can be zero


def test_retry_after_parsing():
    assert retry_after_seconds({"Retry-After": "12"}) == 12.0
    assert retry_after_seconds({"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}, now=1445412480 - 5) == 5.0
    assert retry_after_seconds({"Retry-After": "garbage"}) is None
    assert retry_after_seconds({}) is None


def test_retry_call_retries_only_transient_errors_and_honours_retry_after():
    sleeps, calls = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TransientError("503", retry_after=2.5)
        return "ok"

    assert retry_call(flaky, sleep=sleeps.append) == "ok"
    assert sleeps == [2.5, 2.5]

    with pytest.raises(AuthError):  # non-retryable: fails immediately
        retry_call(lambda: (_ for _ in ()).throw(AuthError("no")), sleep=sleeps.append)


def test_retry_call_gives_up_after_the_attempt_budget():
    calls = []

    def always():
        calls.append(1)
        raise TransientError("down")

    with pytest.raises(TransientError):
        retry_call(always, attempts=3, sleep=lambda s: None, rng=lambda: 0.0)
    assert len(calls) == 3


def test_event_roundtrip_is_ascii_safe():
    line = events.encode("log", message="Entraînement ✓ 日本語")
    assert line.isascii() and line.startswith(events.EVENT_PREFIX)
    assert events.decode(line)["message"] == "Entraînement ✓ 日本語"
    assert events.decode(line + "\r\n")["type"] == "log"  # Windows line endings


def test_decode_ignores_plain_output_and_foreign_versions():
    assert events.decode("Epoch 1/3 loss=2.0") is None
    assert events.decode('@@craftml {"v": 99, "type": "log"}') is None
    assert events.decode('@@craftml {"v": 1, "type": "nope"}') is None
    assert events.decode("@@craftml {not json") is None


def test_encode_drops_none_fields_and_models_accept_decoded_events():
    payload = events.decode(events.encode("progress", loss=1.5, current_step=2, vram_gb=None))
    assert "vram_gb" not in payload
    event = RemoteEvent(**{k: v for k, v in payload.items() if k != "v"})
    assert event.loss == 1.5 and event.current_step == 2


def test_cloud_target_only_allows_training_providers():
    assert CloudTarget(provider="runpod").max_runtime_minutes == 240
    for bad in ("together", "replicate"):
        with pytest.raises(ValueError):
            CloudTarget(provider=bad)
    with pytest.raises(ValueError):
        CloudTarget(provider="ssh", max_runtime_minutes=1)


def test_ssh_profile_validation_and_remote_model_ids():
    assert SshProfile(name="gpu-box", host="h", username="u").port == 22
    with pytest.raises(ValueError):
        SshProfile(name="bad name!", host="h", username="u")
    assert RemoteModel.make_id(ProviderId.TOGETHER, "llama") == "cloud:together:llama"

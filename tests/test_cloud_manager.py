"""Manager lifecycle with a scripted fake provider: success, failure, cancel, runtime cap, cleanup, reconcile."""

import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from core.cloud import manager
from core.cloud.errors import AuthError, CapacityError, NotSupported, RemoteExecutionError
from core.cloud.manager import ProgressSink, RunRecord
from core.cloud.providers.base import CloudProvider
from core.cloud.schemas import (
    AccountInfo, Capabilities, CloudTarget, InstanceInfo, ProviderId, RemoteEvent, RemoteJobHandle,
    RemoteTrainingSpec,
)


def ev(type_, **kw):
    return RemoteEvent(type=type_, **kw)


SUCCESS = [
    ev("status", status="running"),
    ev("log", message="loading model with token hf_abcdefghijklmnopqrstuvwxyz123456"),
    ev("telemetry", vram_gb=7.5),
    ev("progress", current_epoch=1, total_epochs=2, current_step=1, total_steps=4, loss=2.0, learning_rate=2e-4),
    ev("progress", current_epoch=2, total_epochs=2, current_step=4, total_steps=4, loss=1.0, vram_gb=8.0),
    ev("artifact", kind="path", path="output/final"),
    ev("status", status="completed"),
]


class FakeProvider(CloudProvider):
    id = ProviderId.RUNPOD
    label = "Fake"
    capabilities = Capabilities(training=True)
    fields: List = []

    def __init__(self, script=SUCCESS, *, cleanup_error=None, submit_error=None, status="running", instances=None):
        self.script, self.cleanup_error, self.submit_error = script, cleanup_error, submit_error
        self._status, self._instances = status, instances or []
        self.calls: List[str] = []
        self.configured = True

    def validate_credentials(self):
        return AccountInfo(name="fake")

    def is_configured(self):
        return self.configured

    def submit_training(self, spec, bundle):
        self.calls.append("submit")
        if self.submit_error:
            raise self.submit_error
        return RemoteJobHandle(provider=self.id, remote_id="pod-1", job_id=spec.job_id, gpu_name="RTX 4090")

    def stream_events(self, handle, stop):
        for event in self.script:
            if stop():
                return
            yield event

    def fetch_artifacts(self, handle, dest):
        self.calls.append("fetch")
        final = Path(dest) / "final"
        final.mkdir(parents=True, exist_ok=True)
        (final / "adapter_config.json").write_text("{}")
        return final

    def get_status(self, handle):
        if isinstance(self._status, Exception):
            raise self._status
        return self._status

    def cancel(self, handle):
        self.calls.append("cancel")

    def cleanup(self, handle):
        self.calls.append("cleanup")
        if self.cleanup_error:
            raise self.cleanup_error

    def list_instances(self):
        return self._instances

    def terminate(self, remote_id):
        self.calls.append(f"terminate:{remote_id}")


class MemoryStore:
    def __init__(self):
        self.records: Dict[str, RunRecord] = {}

    def save(self, record):
        self.records[record.job_id] = record

    def update(self, job_id, **fields):
        for key, value in fields.items():
            setattr(self.records[job_id], key, value)

    def get(self, job_id):
        return self.records.get(job_id)

    def active(self):
        return [r for r in self.records.values() if r.status == "running"]

    def known_remote_ids(self, provider):
        return {r.handle.remote_id for r in self.records.values() if r.handle.provider == provider}


class Sink:
    def __init__(self):
        self.logs, self.progress_calls = [], []

    def as_sink(self):
        return ProgressSink(log=self.logs.append, progress=lambda **kw: self.progress_calls.append(kw))


def make_spec(tmp_path, minutes=60):
    return RemoteTrainingSpec(
        job_id="train_abc", model_name="org/base", dataset_path=str(tmp_path / "d.jsonl"),
        output_dir=str(tmp_path / "out"), target=CloudTarget(provider="runpod", max_runtime_minutes=minutes),
    )


def run(tmp_path, provider, *, cancel=lambda: False, clock=None, minutes=60):
    store, sink = MemoryStore(), Sink()
    kwargs = {"clock": clock} if clock else {}
    try:
        result = manager.run_training(
            make_spec(tmp_path, minutes), secrets=None, store=store, sink=sink.as_sink(),
            should_cancel=cancel, provider=provider, **kwargs,
        )
        return result, store, sink, None
    except Exception as exc:  # noqa: BLE001
        return None, store, sink, exc


def test_success_collects_adapter_cleans_up_and_maps_events(tmp_path):
    provider = FakeProvider()
    result, store, sink, error = run(tmp_path, provider)
    assert error is None and result["output_dir"].endswith("final")
    assert (Path(result["output_dir"]) / "adapter_config.json").exists()
    assert provider.calls == ["submit", "fetch", "cleanup"]
    assert store.records["train_abc"].status == "completed"

    first, second = sink.progress_calls
    assert first["current_step"] == 1 and first["metrics"]["vram_gb"] == 7.5  # telemetry carried forward
    assert first["metrics"]["learning_rate"] == 2e-4
    assert second["loss"] == 1.0 and second["metrics"]["vram_gb"] == 8.0  # event's own value wins
    assert any("Running on Fake (RTX 4090)" in line for line in sink.logs)


def test_secrets_in_remote_logs_are_redacted(tmp_path):
    _, _, sink, _ = run(tmp_path, FakeProvider())
    joined = "\n".join(sink.logs)
    assert "hf_abcdefghijklmnop" not in joined and "***" in joined


def test_failed_event_raises_and_still_cleans_up(tmp_path):
    script = [ev("status", status="running"), ev("status", status="failed", error="CUDA out of memory")]
    provider = FakeProvider(script)
    _, store, _, error = run(tmp_path, provider)
    assert isinstance(error, RemoteExecutionError) and "out of memory" in str(error)
    assert "fetch" not in provider.calls and provider.calls[-1] == "cleanup"
    record = store.records["train_abc"]
    assert record.status == "failed" and "out of memory" in record.error


def test_stream_ending_without_completion_is_an_error(tmp_path):
    provider = FakeProvider([ev("status", status="running"), ev("log", message="hi")])
    _, _, _, error = run(tmp_path, provider)
    assert isinstance(error, RemoteExecutionError) and "without reporting completion" in str(error)
    assert provider.calls[-1] == "cleanup"


def test_user_cancel_cancels_remote_and_cleans_up(tmp_path):
    seen = {"n": 0}

    def cancel():
        seen["n"] += 1
        return seen["n"] > 2

    provider = FakeProvider()
    result, store, _, error = run(tmp_path, provider, cancel=cancel)
    assert error is None and result == {"stopped": True}
    assert provider.calls == ["submit", "cancel", "cleanup"]
    assert store.records["train_abc"].status == "stopped"


def test_max_runtime_stops_the_run_with_a_clear_error(tmp_path):
    ticks = iter(range(0, 10_000, 600))  # each clock() call advances 10 minutes
    provider = FakeProvider()
    _, store, _, error = run(tmp_path, provider, clock=lambda: next(ticks), minutes=15)
    assert isinstance(error, RemoteExecutionError) and "15-minute runtime limit" in error.user_message()
    assert provider.calls[-2:] == ["cancel", "cleanup"]
    assert store.records["train_abc"].status == "failed"


def test_submit_failure_propagates_without_a_record(tmp_path):
    provider = FakeProvider(submit_error=CapacityError("No RTX 4090 available"))
    _, store, _, error = run(tmp_path, provider)
    assert isinstance(error, CapacityError) and store.records == {}
    assert provider.calls == ["submit"]  # nothing to clean: submit() must clean up after itself


def test_cleanup_failure_is_reported_loudly_but_does_not_mask_success(tmp_path):
    provider = FakeProvider(cleanup_error=RuntimeError("API down; key hf_abcdefghijklmnopqrstuvwxyz123456"))
    result, _, sink, error = run(tmp_path, provider)
    assert error is None and result["output_dir"]
    warning = [l for l in sink.logs if "Could not clean up" in l]
    assert warning and "pod-1" in warning[0] and "still billing" in warning[0] and "hf_abcdef" not in warning[0]


def test_provider_without_training_is_rejected(tmp_path):
    provider = FakeProvider()
    provider.capabilities = Capabilities(training=False, inference=True)
    _, _, _, error = run(tmp_path, provider)
    assert isinstance(error, NotSupported) and provider.calls == []


def test_worst_case_cost():
    assert manager.worst_case_cost(0.44, 240) == 1.76
    assert manager.worst_case_cost(None, 240) is None


# --- reconcile / orphans / listing -------------------------------------------

def stale_store():
    store = MemoryStore()
    store.save(RunRecord(handle=RemoteJobHandle(provider=ProviderId.RUNPOD, remote_id="pod-9", job_id="old")))
    return store


def test_reconcile_terminates_runs_left_by_a_previous_process():
    store, provider = stale_store(), FakeProvider(status="running")
    report = manager.reconcile(store, None, factory=lambda pid, s: provider)
    assert provider.calls == ["cleanup"] and store.records["old"].status == "interrupted"
    assert "terminated" in store.records["old"].error and "was running" in report[0]


def test_reconcile_cleans_up_even_when_the_status_check_fails():
    store, provider = stale_store(), FakeProvider(status=AuthError("expired key"))
    report = manager.reconcile(store, None, factory=lambda pid, s: provider)
    assert provider.calls == ["cleanup"]  # a pod may still be billing; never skip cleanup
    assert store.records["old"].status == "interrupted" and any("status check failed" in l for l in report)


def test_reconcile_flags_runs_it_could_not_terminate():
    store = stale_store()
    provider = FakeProvider(cleanup_error=RuntimeError("boom"))
    report = manager.reconcile(store, None, factory=lambda pid, s: provider)
    assert "NOT be terminated" in store.records["old"].error and any("cleanup failed" in l for l in report)


def test_reconcile_with_unreachable_provider_marks_interrupted():
    def factory(pid, secrets):
        raise NotSupported("SDK not installed")

    store = stale_store()
    manager.reconcile(store, None, factory=factory)
    assert store.records["old"].status == "interrupted" and "NOT be terminated" in store.records["old"].error


def test_find_orphans_excludes_known_runs_and_skips_unconfigured():
    store = stale_store()
    mine = InstanceInfo(provider=ProviderId.RUNPOD, remote_id="pod-9", name="craftml-old", status="RUNNING")
    stray = InstanceInfo(provider=ProviderId.RUNPOD, remote_id="pod-stray", name="craftml-lost", status="RUNNING")
    provider = FakeProvider(instances=[mine, stray])

    def factory(pid, secrets):
        if pid is ProviderId.RUNPOD:
            return provider
        raise NotSupported("not installed")

    assert [o.remote_id for o in manager.find_orphans(store, None, factory)] == ["pod-stray"]
    provider.configured = False
    assert manager.find_orphans(store, None, factory) == []


def test_list_providers_skips_unavailable_ones():
    def factory(pid, secrets):
        if pid is ProviderId.RUNPOD:
            return FakeProvider()
        raise NotSupported("missing sdk")

    infos = manager.list_providers(None, factory)
    assert [i.id for i in infos] == [ProviderId.RUNPOD] and infos[0].configured is True

"""
Cloud manager: provider selection and the lifecycle of one remote run.

Persistence and job callbacks are injected (``RunStore``, ``ProgressSink``), so this module
has no database dependency and can be tested with fakes.  The invariants that protect the
user's money:

* ``cleanup`` always runs (success, failure, cancel, max-runtime), and a failure to clean up
  is logged loudly rather than swallowed silently;
* the run is persisted *before* streaming starts, so a crash leaves a record to reconcile;
* ``reconcile`` (called at startup) terminates runs that outlived the previous process.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

from core.cloud.bundle import build_bundle
from core.cloud.errors import CloudError, NotSupported, RemoteExecutionError
from core.cloud.providers import get_provider_class, provider_ids
from core.cloud.providers.base import CloudProvider
from core.cloud.schemas import (
    InstanceInfo,
    ProviderId,
    ProviderInfo,
    RemoteEvent,
    RemoteJobHandle,
    RemoteTrainingSpec,
)
from core.cloud.secrets import SecretStore, redact

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("running",)


@dataclass
class RunRecord:
    handle: RemoteJobHandle
    status: str = "running"  # running | completed | failed | stopped | interrupted
    error: Optional[str] = None
    ended_at: Optional[float] = None

    @property
    def job_id(self) -> str:
        return self.handle.job_id


class RunStore(Protocol):
    def save(self, record: RunRecord) -> None: ...
    def update(self, job_id: str, **fields: Any) -> None: ...
    def get(self, job_id: str) -> Optional[RunRecord]: ...
    def active(self) -> List[RunRecord]: ...
    def known_remote_ids(self, provider: ProviderId) -> Set[str]: ...


@dataclass
class ProgressSink:
    """Where run output goes (the backend maps these onto the job store)."""

    log: Callable[[str], None]
    progress: Callable[..., None]  # (current_epoch, total_epochs, current_step, total_steps, loss, metrics)


ProviderFactory = Callable[[ProviderId, SecretStore], CloudProvider]


def default_provider_factory(provider: ProviderId, secrets: SecretStore) -> CloudProvider:
    return get_provider_class(provider)(secrets)


def list_providers(secrets: SecretStore, factory: ProviderFactory = default_provider_factory) -> List[ProviderInfo]:
    infos = []
    for pid in provider_ids():
        try:
            provider = factory(pid, secrets)
        except CloudError as exc:  # SDK-less builds still list the other providers
            logger.warning("Provider %s unavailable: %s", pid.value, exc)
            continue
        infos.append(ProviderInfo(
            id=pid, label=provider.label, capabilities=provider.capabilities, fields=provider.fields,
            configured=provider.is_configured(), description=provider.description,
        ))
    return infos


def worst_case_cost(price_per_hour: Optional[float], max_runtime_minutes: int) -> Optional[float]:
    """Upper bound on spend if the run uses its whole runtime allowance (an estimate)."""
    return None if price_per_hour is None else round(price_per_hour * max_runtime_minutes / 60.0, 2)


def _dispatch(event: RemoteEvent, sink: ProgressSink, state: Dict[str, Any]) -> None:
    if event.type == "log":
        sink.log(redact(event.message or ""))
    elif event.type == "telemetry":
        if event.vram_gb is not None:
            state["vram_gb"] = event.vram_gb
    elif event.type == "progress":
        if event.vram_gb is not None:
            state["vram_gb"] = event.vram_gb
        sink.progress(
            current_epoch=event.current_epoch or 0,
            total_epochs=event.total_epochs or 0,
            current_step=event.current_step or 0,
            total_steps=event.total_steps or 0,
            loss=event.loss if event.loss is not None else 0.0,
            metrics={
                "epoch": event.epoch,
                "learning_rate": event.learning_rate,
                "vram_gb": event.vram_gb if event.vram_gb is not None else state.get("vram_gb"),
            },
        )
    elif event.type == "status":
        if event.status == "running":
            sink.log("Remote job started")
        elif event.status == "completed":
            state["succeeded"] = True
        elif event.status == "failed":
            raise RemoteExecutionError(redact(event.error or "Remote training failed"))
        elif event.status == "stopped":
            state["remote_stopped"] = True


def run_training(
    spec: RemoteTrainingSpec,
    *,
    secrets: SecretStore,
    store: RunStore,
    sink: ProgressSink,
    should_cancel: Callable[[], bool],
    provider: Optional[CloudProvider] = None,
    factory: ProviderFactory = default_provider_factory,
    clock: Callable[[], float] = time.time,
) -> Dict[str, Any]:
    """Run one fine-tune remotely. Returns ``{"output_dir": ...}`` or ``{"stopped": True}``."""
    provider = provider or factory(spec.target.provider, secrets)
    if not provider.capabilities.training:
        raise NotSupported(f"{provider.label} doesn't support remote training.")

    deadline = clock() + spec.target.max_runtime_minutes * 60
    stop = lambda: should_cancel() or clock() > deadline  # noqa: E731

    sink.log(f"Preparing worker bundle for {provider.label}…")
    handle = provider.submit_training(spec, build_bundle())
    store.save(RunRecord(handle=handle))
    where = handle.gpu_name or handle.gpu_id or "remote host"
    sink.log(f"Running on {provider.label} ({where})")

    state: Dict[str, Any] = {}
    try:
        stream = provider.stream_events(handle, stop)
        try:
            for event in stream:
                _dispatch(event, sink, state)
                if stop():
                    break
        finally:
            close = getattr(stream, "close", None)
            if close:
                close()  # runs the provider's finally blocks now (closes tails/apps), not whenever GC gets to it

        if should_cancel():
            provider.cancel(handle)
            store.update(spec.job_id, status="stopped", ended_at=clock())
            return {"stopped": True}
        if clock() > deadline and not state.get("succeeded"):
            provider.cancel(handle)
            raise RemoteExecutionError(
                f"Stopped after reaching the {spec.target.max_runtime_minutes}-minute runtime limit.",
                hint="Raise the limit or use a faster GPU.",
            )
        if state.get("remote_stopped"):
            raise RemoteExecutionError("The remote job was stopped before finishing.")
        if not state.get("succeeded"):
            raise RemoteExecutionError("The remote job ended without reporting completion.")

        sink.log("Downloading the trained adapter…")
        final = provider.fetch_artifacts(handle, Path(spec.output_dir))
        store.update(spec.job_id, status="completed", ended_at=clock())
        return {"output_dir": str(final)}
    except BaseException as exc:
        record = store.get(spec.job_id)
        if record and record.status == "running":
            store.update(spec.job_id, status="failed", error=redact(str(exc)), ended_at=clock())
        raise
    finally:
        try:
            provider.cleanup(handle)
        except Exception as exc:  # noqa: BLE001 - must not mask the real outcome, but must be visible
            message = (f"Could not clean up remote resource {handle.remote_id} on {provider.label}: "
                       f"{redact(str(exc))}. Check the provider console to make sure it isn't still billing.")
            logger.error(message)
            sink.log(message)


def reconcile(
    store: RunStore, secrets: SecretStore, factory: ProviderFactory = default_provider_factory
) -> List[str]:
    """
    Resolve runs left active by a previous process (call once at startup, before new runs).

    A run that finished is collected if possible; anything still running is terminated, since
    nothing is streaming it any more and it would keep billing.
    """
    report: List[str] = []
    for record in store.active():
        handle = record.handle
        provider: Optional[CloudProvider] = None
        status = "unknown"
        try:
            provider = factory(handle.provider, secrets)
            status = provider.get_status(handle)
        except CloudError as exc:
            report.append(f"{handle.job_id}: status check failed ({exc.message})")

        cleaned = False
        if provider is not None:
            try:  # always attempt cleanup, even when the status check failed: a pod may still be billing
                provider.cleanup(handle)
                cleaned = True
            except Exception as exc:  # noqa: BLE001
                report.append(f"{handle.job_id}: cleanup failed ({redact(str(exc))}); check {provider.label}")

        detail = "terminated" if cleaned else "could NOT be terminated automatically"
        store.update(
            record.job_id, status="interrupted", ended_at=time.time(),
            error=f"App restarted while the remote job was {status}; the remote resource {detail}.",
        )
        report.append(f"{handle.job_id}: was {status}, {detail}, marked interrupted")
    return report


def find_orphans(
    store: RunStore, secrets: SecretStore, factory: ProviderFactory = default_provider_factory
) -> List[InstanceInfo]:
    """Provider resources we created (``craftml-*``) that no stored run accounts for."""
    orphans: List[InstanceInfo] = []
    for pid in provider_ids():
        try:
            provider = factory(pid, secrets)
            if not provider.capabilities.training or not provider.is_configured():
                continue
            known = store.known_remote_ids(pid)
            orphans += [i for i in provider.list_instances() if i.remote_id not in known]
        except CloudError as exc:
            logger.info("Orphan scan skipped for %s: %s", pid.value, exc.message)
    return orphans


def terminate_instance(
    provider_id: ProviderId, remote_id: str, secrets: SecretStore, factory: ProviderFactory = default_provider_factory
) -> None:
    factory(provider_id, secrets).terminate(remote_id)

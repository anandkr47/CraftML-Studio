"""
Modal provider: serverless GPU functions for training.

The remote function downloads the run assets from a private HF repo (the same transport and
worker bundle RunPod uses) and pushes the worker's event lines into a ``modal.Queue`` that the
app polls.  Cancelling is ``FunctionCall.cancel()``, which works from any thread.

Every Modal call lives in ``ModalRunner`` and takes the ``modal`` module as a parameter, because
Modal's client API evolves quickly: that surface stays small, isolated and tested against a fake.
"""

from __future__ import annotations

import logging
import sys
import time
from importlib import resources
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Optional

from core.cloud.errors import AuthError, CloudError, ConfigError, RemoteExecutionError, TransientError
from core.cloud.providers.base import CloudProvider
from core.cloud.schemas import (
    AccountInfo,
    Capabilities,
    FieldSpec,
    GpuOption,
    ProviderId,
    RemoteEvent,
    RemoteJobHandle,
    RemoteStatus,
    RemoteTrainingSpec,
    parse_event_line,
)
from core.cloud.secrets import HF_TOKEN, SecretStore
from core.cloud.transport import HubTransport, RunRepos, stage_training

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0
TORCH_VERSION = "2.14.1"  # matches apps/backend/requirements.lock.txt
STARTUP_GRACE = 600  # image build / cold start before the first event
TERMINAL = ("completed", "failed", "stopped")

# Modal bills per second; these are approximate list prices in $/hour for the estimate shown to the user.
GPU_TABLE = [
    ("T4", "NVIDIA T4", 16, 0.59),
    ("L4", "NVIDIA L4", 24, 0.80),
    ("A10G", "NVIDIA A10G", 24, 1.10),
    ("L40S", "NVIDIA L40S", 48, 1.95),
    ("A100-40GB", "NVIDIA A100 40GB", 40, 2.10),
    ("A100-80GB", "NVIDIA A100 80GB", 80, 2.50),
    ("H100", "NVIDIA H100", 80, 3.95),
]


def classify(exc: Exception) -> CloudError:
    low = str(exc).lower()
    if any(k in low for k in ("token", "unauthorized", "unauthenticated", "authentication", "401")):
        return AuthError("Modal rejected the token.", hint="Create a new token at modal.com/settings/tokens.")
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)) or "unavailable" in low or "timed out" in low:
        return TransientError(f"Modal is unreachable ({str(exc)[:120]}).")
    return RemoteExecutionError(f"Modal error: {str(exc)[:300]}")


def worker_packages() -> List[str]:
    """Pinned worker requirements (baked into the image so later runs start fast) plus torch."""
    text = resources.files("core.cloud.worker").joinpath("requirements.txt").read_text(encoding="utf-8")
    pins = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    return [f"torch=={TORCH_VERSION}"] + pins


def entry_path() -> str:
    return str(Path(str(resources.files("core.cloud.worker").joinpath("modal_entry.py"))))


class ModalRun:
    """A running (or finished) remote call. Created by ``ModalRunner.start``."""

    def __init__(self, *, queue_ctx, queue, app_ctx, call):
        self._queue_ctx, self._queue, self._app_ctx, self._call = queue_ctx, queue, app_ctx, call
        self.closed = False

    def poll(self, timeout: float) -> List[str]:
        """New event lines (may be empty)."""
        try:
            return list(self._queue.get_many(100, block=True, timeout=timeout) or [])
        except Exception as exc:  # noqa: BLE001
            raise classify(exc) from exc

    def finished(self) -> Optional[str]:
        """None while running; '' on success; the error text if the function failed or was cancelled."""
        try:
            self._call.get(timeout=0)
            return ""
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, TimeoutError) or type(exc).__name__ == "TimeoutError":
                return None  # still running
            return str(exc) or type(exc).__name__

    def cancel(self) -> None:
        try:
            self._call.cancel()
        except Exception as exc:  # noqa: BLE001 - already finished is fine
            logger.info("Modal cancel: %s", exc)

    def close(self) -> None:
        """Stop the ephemeral app and queue (idempotent)."""
        if self.closed:
            return
        self.closed = True
        for ctx in (self._queue_ctx, self._app_ctx):
            try:
                ctx.__exit__(None, None, None)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Modal cleanup: %s", exc)


class ModalRunner:
    """The only code that talks to the ``modal`` package."""

    def __init__(self, token_id: str, token_secret: str, modal_module: Optional[Any] = None):
        self.token_id, self.token_secret = token_id, token_secret
        self._modal = modal_module

    @property
    def modal(self):
        if self._modal is None:
            try:
                import modal
            except ImportError as exc:
                raise ConfigError("Modal support needs the 'modal' package.", hint="pip install modal") from exc
            self._modal = modal
        return self._modal

    def client(self):
        try:
            return self.modal.Client.from_credentials(self.token_id, self.token_secret)
        except CloudError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise classify(exc) from exc

    def validate(self) -> None:
        try:
            self.client().hello()
        except CloudError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise classify(exc) from exc

    def start(
        self, *, job_id: str, gpu: str, max_seconds: int, hf_token: str, dataset_repo: str, dataset_filename: str,
        packages: List[str], entry_file: str,
    ) -> ModalRun:
        modal = self.modal
        client = self.client()
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"  # serialized functions need a matching minor
        image = (
            modal.Image.debian_slim(python_version=python_version)
            .pip_install(*packages)
            .add_local_file(entry_file, "/root/modal_entry.py")
        )
        app = modal.App(f"craftml-{job_id}")

        @app.function(
            image=image, gpu=gpu, timeout=max_seconds + 300,
            secrets=[modal.Secret.from_dict({"HF_TOKEN": hf_token})], serialized=True,
        )
        def run(queue, repo, filename, seconds):
            import sys as _sys

            _sys.path.insert(0, "/root")
            import modal_entry

            return modal_entry.run_job(queue.put, repo, filename, seconds)

        app_ctx = app.run(client=client)
        queue_ctx = None
        try:
            app_ctx.__enter__()
            queue_ctx = modal.Queue.ephemeral(client=client)
            queue = queue_ctx.__enter__()
            call = run.spawn(queue, dataset_repo, dataset_filename, max_seconds)
        except BaseException as exc:
            for ctx in (queue_ctx, app_ctx):
                try:
                    if ctx is not None:
                        ctx.__exit__(None, None, None)
                except Exception:  # noqa: BLE001
                    pass
            if isinstance(exc, CloudError):
                raise
            raise classify(exc) from exc
        return ModalRun(queue_ctx=queue_ctx, queue=queue, app_ctx=app_ctx, call=call)


class ModalProvider(CloudProvider):
    id: ClassVar[ProviderId] = ProviderId.MODAL
    label: ClassVar[str] = "Modal"
    description: ClassVar[str] = "Serverless GPUs billed per second. Nothing keeps running after your job ends."
    capabilities: ClassVar[Capabilities] = Capabilities(training=True, inference=False)
    fields: ClassVar[List[FieldSpec]] = [
        FieldSpec(name="token_id", label="Token ID", placeholder="ak-…"),
        FieldSpec(name="token_secret", label="Token secret", placeholder="as-…"),
    ]

    def __init__(
        self,
        secrets: SecretStore,
        runner_factory: Callable[[str, str], ModalRunner] = ModalRunner,
        transport_factory: Callable[[str], HubTransport] = HubTransport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(secrets)
        self._runner_factory, self._transport_factory = runner_factory, transport_factory
        self._sleep, self._clock = sleep, clock
        self._runs: Dict[str, ModalRun] = {}

    def _runner(self) -> ModalRunner:
        return self._runner_factory(self.credential("token_id"), self.credential("token_secret"))

    def _transport(self, token: Optional[str] = None) -> HubTransport:
        token = token or self.secrets.get(HF_TOKEN)
        if not token:
            raise ConfigError("Modal runs need a Hugging Face token.", hint="Add one in Settings → Hugging Face.")
        return self._transport_factory(token)

    def validate_credentials(self) -> AccountInfo:
        self._runner().validate()
        return AccountInfo(name="Modal workspace")

    def list_gpus(self) -> List[GpuOption]:
        return [GpuOption(id=i, name=n, vram_gb=v, price_per_hour=p) for i, n, v, p in GPU_TABLE]

    # -- training ---------------------------------------------------------------

    def submit_training(self, spec: RemoteTrainingSpec, bundle) -> RemoteJobHandle:
        gpu = spec.target.gpu_id
        if not gpu:
            raise ConfigError("Choose a GPU for the Modal run.")
        if gpu not in {g[0] for g in GPU_TABLE}:
            raise ConfigError(f"Unknown Modal GPU '{gpu}'.")
        token = spec.hf_token.get_secret_value() if spec.hf_token else None
        transport = self._transport(token)
        self._runner().validate()  # fail now, before uploading the dataset
        repos = stage_training(transport, spec, bundle)
        price = next(p for i, _, _, p in GPU_TABLE if i == gpu)
        name = next(n for i, n, _, _ in GPU_TABLE if i == gpu)
        return RemoteJobHandle(
            provider=self.id, remote_id=f"modal-{spec.job_id}", job_id=spec.job_id, gpu_id=gpu, gpu_name=name,
            price_per_hour=price,
            meta={"dataset_repo": repos.dataset_repo, "adapter_repo": repos.adapter_repo,
                  "dataset_filename": Path(spec.dataset_path).name,
                  "max_seconds": str(spec.target.max_runtime_minutes * 60)},
        )

    def stream_events(self, handle: RemoteJobHandle, stop: Callable[[], bool]) -> Iterator[RemoteEvent]:
        token = self.secrets.get(HF_TOKEN)
        if not token:
            raise ConfigError("Modal runs need a Hugging Face token.")
        run = self._runner().start(
            job_id=handle.job_id, gpu=handle.gpu_id or "", max_seconds=int(handle.meta["max_seconds"]),
            hf_token=token, dataset_repo=handle.meta["dataset_repo"], dataset_filename=handle.meta["dataset_filename"],
            packages=worker_packages(), entry_file=entry_path(),
        )
        self._runs[handle.remote_id] = run
        started, last_note = self._clock(), self._clock()
        got_event = False
        try:
            while not stop():
                for line in run.poll(POLL_SECONDS):
                    event = parse_event_line(line)
                    if event is None:
                        continue
                    got_event = True
                    yield event
                    if event.type == "status" and event.status in TERMINAL:
                        return

                outcome = run.finished()
                if outcome is not None:
                    for line in run.poll(0.5):  # events written just before the function returned
                        event = parse_event_line(line)
                        if event is not None:
                            yield event
                            if event.type == "status" and event.status in TERMINAL:
                                return
                    yield RemoteEvent(type="status", status="failed",
                                      error=outcome or "The Modal function ended without reporting a result.")
                    return

                if not got_event and self._clock() - started > STARTUP_GRACE:
                    yield RemoteEvent(type="status", status="failed", error="The Modal function didn't start in time.")
                    return
                if not got_event and self._clock() - last_note >= 30:
                    last_note = self._clock()
                    yield RemoteEvent(type="log", message=f"Starting the Modal container ({int(self._clock() - started)} s)…")
        finally:
            run.close()

    def fetch_artifacts(self, handle: RemoteJobHandle, dest: Path) -> Path:
        return self._transport().download_adapter(handle.meta["adapter_repo"], dest)

    def get_status(self, handle: RemoteJobHandle) -> RemoteStatus:
        return "gone"  # ephemeral apps die with the process that started them

    def cancel(self, handle: RemoteJobHandle) -> None:
        run = self._runs.get(handle.remote_id)
        if run:
            run.cancel()

    def cleanup(self, handle: RemoteJobHandle) -> None:
        run = self._runs.pop(handle.remote_id, None)
        try:
            if run:
                run.cancel()
                run.close()
        finally:
            if handle.meta.get("dataset_repo"):
                try:
                    self._transport().delete_repos(RunRepos(handle.meta["dataset_repo"], handle.meta.get("adapter_repo", "")))
                except CloudError as exc:
                    logger.warning("Could not delete transfer repos: %s", exc.message)

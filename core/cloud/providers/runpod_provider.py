"""
RunPod provider: on-demand GPU pods for training (serverless endpoints for inference).

Training flow (Hugging Face transport, stock PyTorch image, no custom image):
  1. upload bundle + job + dataset to a private HF dataset repo;
  2. create a pod whose start command downloads them, verifies the bundle SHA-256, and runs the
     worker with an authenticated HTTP event endpoint on the pod's proxy URL;
  3. poll ``/events`` through ``https://<pod>-<port>.proxy.runpod.net`` (requests are capped at
     ~100 s by the proxy, so each poll returns immediately);
  4. download the adapter from a private HF model repo, then terminate the pod and delete the repos.

Billing safety, in layers: the pod removes itself when the worker ends (``trap EXIT``) and again
after ``max_runtime + 10 min`` (dead-man switch); the app terminates it in ``cleanup``; startup
reconciliation and the orphan scan catch anything left over.

All vendor SDK calls are confined to ``RunPodApi``: the SDK's pod field names aren't a stable
documented contract, so extraction is tolerant and covered by tests with a mocked SDK.
"""

from __future__ import annotations

import json
import logging
import os
import secrets as pysecrets
import shlex
import threading
import time
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Optional, Tuple

from core.cloud.errors import (
    AuthError,
    CapacityError,
    CloudError,
    ConfigError,
    QuotaError,
    RemoteExecutionError,
    TransientError,
)
from core.cloud.providers.base import NAME_PREFIX, CloudProvider, InferenceEndpoint
from core.cloud.retry import retry_call
from core.cloud.schemas import (
    AccountInfo,
    Capabilities,
    FieldSpec,
    GpuOption,
    InstanceInfo,
    ProviderId,
    RemoteEvent,
    RemoteModel,
    RemoteJobHandle,
    RemoteStatus,
    RemoteTrainingSpec,
    parse_event_line as event_from_line,
)
from core.cloud.secrets import HF_TOKEN, SecretStore, redact
from core.cloud.transport import HubTransport, RunRepos, stage_training

logger = logging.getLogger(__name__)

IMAGE = os.environ.get("CRAFTML_RUNPOD_IMAGE", "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04")
EVENT_PORT = 8000
POLL_INTERVAL = 3.0
BOOT_TIMEOUT = 25 * 60  # pulling the image + pip install can be slow
NOTE_INTERVAL = 30.0
DEADMAN_GRACE = 600
MIN_VRAM_GB = 16
TERMINAL = ("completed", "failed", "stopped")
GONE_STATES = ("EXITED", "TERMINATED", "DEAD", "STOPPED")

_SDK_LOCK = threading.Lock()  # runpod.api_key is a module global


# --------------------------------------------------------------------------- tolerant pod fields

def _first(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if data.get(key) not in (None, ""):
            return data[key]
    return None


def pod_id(pod: Dict[str, Any]) -> str:
    return str(_first(pod, "id", "podId") or "")


def pod_name(pod: Dict[str, Any]) -> str:
    return str(_first(pod, "name") or "")


def pod_state(pod: Dict[str, Any]) -> str:
    return str(_first(pod, "desiredStatus", "status", "state") or "").upper()


def pod_price(pod: Dict[str, Any]) -> Optional[float]:
    value = _first(pod, "costPerHr", "adjustedCostPerHr", "cost_per_hr")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def pod_gpu(pod: Dict[str, Any]) -> Optional[str]:
    machine = pod.get("machine") or {}
    gpu = pod.get("gpu") or {}
    return _first(machine, "gpuDisplayName", "gpuTypeId") or _first(gpu, "displayName", "id") or _first(pod, "gpuDisplayName")


def gpu_options(raw: List[Dict[str, Any]]) -> List[GpuOption]:
    options = []
    for gpu in raw:
        memory = _first(gpu, "memoryInGb", "memory_in_gb")
        price = None
        for key in ("securePrice", "communityPrice"):
            if isinstance(gpu.get(key), (int, float)) and gpu[key] > 0:
                price = float(gpu[key]) if price is None else min(price, float(gpu[key]))
        if memory is None or float(memory) < MIN_VRAM_GB:
            continue
        options.append(GpuOption(
            id=str(_first(gpu, "id")), name=str(_first(gpu, "displayName", "id")), vram_gb=float(memory),
            price_per_hour=price, available=True,
        ))
    return sorted(options, key=lambda o: (o.price_per_hour is None, o.price_per_hour or 0, o.vram_gb))


def classify(exc: Exception) -> CloudError:
    text = str(exc)
    low = text.lower()
    if any(k in low for k in ("unauthorized", "401", "invalid api key", "api key", "forbidden", "403")):
        return AuthError("RunPod rejected the API key.", hint="Create a new key in the RunPod console (Settings → API Keys).")
    if any(k in low for k in ("insufficient", "balance", "credit", "payment")):
        return QuotaError("RunPod reports insufficient credit.", hint="Add funds in the RunPod console.")
    if any(k in low for k in ("no longer any instances", "no available", "out of stock", "capacity", "not available")):
        return CapacityError("That GPU isn't available on RunPod right now.", hint="Pick another GPU or try again later.")
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)) or any(k in low for k in ("timeout", "timed out", "connection", "502", "503", "504")):
        return TransientError(f"RunPod is unreachable ({text[:120]}).")
    return RemoteExecutionError(f"RunPod error: {text[:300]}")


# --------------------------------------------------------------------------- SDK adapter

class RunPodApi:
    """The only place the ``runpod`` SDK is used."""

    def __init__(self, api_key: str, sdk_loader: Optional[Callable[[], Any]] = None):
        self.api_key = api_key
        self._load = sdk_loader or self._default_loader

    @staticmethod
    def _default_loader():
        try:
            import runpod
        except ImportError as exc:
            raise ConfigError("RunPod support needs the 'runpod' package.", hint="pip install runpod") from exc
        return runpod

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        sdk = self._load()
        with _SDK_LOCK:
            sdk.api_key = self.api_key
            try:
                return getattr(sdk, name)(*args, **kwargs)
            except CloudError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise classify(exc) from exc

    def gpus(self) -> List[Dict[str, Any]]:
        return list(self._call("get_gpus") or [])

    def pods(self) -> List[Dict[str, Any]]:
        return list(self._call("get_pods") or [])

    def pod(self, remote_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self._call("get_pod", remote_id) or None
        except RemoteExecutionError as exc:
            if "not found" in str(exc).lower() or "404" in str(exc):
                return None
            raise

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        return self._call("create_pod", **kwargs) or {}

    def terminate(self, remote_id: str) -> None:
        try:
            self._call("terminate_pod", remote_id)
        except RemoteExecutionError as exc:
            if "not found" in str(exc).lower() or "404" in str(exc):
                return  # already gone
            raise


# --------------------------------------------------------------------------- pod start script

def build_pod_script(
    *, dataset_repo: str, dataset_filename: str, max_seconds: int, port: int = EVENT_PORT,
    workdir: str = "/workspace/run", deadman_grace: int = DEADMAN_GRACE,
) -> str:
    """
    Bash run inside the pod. Downloads the run assets, verifies the bundle, runs the worker, and
    ALWAYS removes the pod on exit.  ``runpodctl``'s subcommand order differs between versions, so
    the known forms are tried in turn, ending with a plain stop (which at least ends GPU billing).
    """
    files = json.dumps(["bundle.tar.gz", "bundle.sha256", "job.json", dataset_filename])
    return f"""set -uo pipefail
mkdir -p {shlex.quote(workdir)} && cd {shlex.quote(workdir)}
exec > >(tee -a pod.log) 2>&1
sd() {{
  runpodctl remove pod "${{RUNPOD_POD_ID:-}}" || runpodctl pod remove "${{RUNPOD_POD_ID:-}}" \\
    || runpodctl pod delete "${{RUNPOD_POD_ID:-}}" || runpodctl stop pod "${{RUNPOD_POD_ID:-}}" || true
}}
upload_log() {{
  python3 - <<'PY' || true
import os
from huggingface_hub import HfApi
HfApi(token=os.environ["HF_TOKEN"]).upload_file(path_or_fileobj="pod.log", path_in_repo="pod.log", repo_id={dataset_repo!r}, repo_type="dataset")
PY
}}
finish() {{
  code=$?
  [ -n "${{DM:-}}" ] && kill "$DM" 2>/dev/null
  if [ "$code" -ne 0 ]; then upload_log; fi
  sd
}}
trap finish EXIT
# Dead-man switch: removes the pod even if the worker hangs; killable so a normal exit leaves nothing behind.
( trap 'kill "$SP" 2>/dev/null; exit 0' TERM
  sleep {int(max_seconds) + int(deadman_grace)} & SP=$!
  wait "$SP" && {{ echo "dead-man switch fired"; sd; }} ) &
DM=$!
python3 -c "import huggingface_hub" 2>/dev/null || python3 -m pip install -q huggingface_hub
python3 - <<'PY'
import os
from huggingface_hub import hf_hub_download
for name in {files}:
    hf_hub_download(repo_id={dataset_repo!r}, filename=name, repo_type="dataset", token=os.environ["HF_TOKEN"], local_dir=".")
PY
[ $? -eq 0 ] || {{ echo "Could not download the run assets"; exit 1; }}
sha256sum -c bundle.sha256 >/dev/null || {{ echo "Bundle checksum mismatch"; exit 1; }}
tar xzf bundle.tar.gz || exit 1
timeout --signal=TERM --kill-after=30 {int(max_seconds)} env CRAFTML_JOB_FILE="$PWD/job.json" bash craftml_worker/bootstrap.sh --serve {int(port)}
"""


# --------------------------------------------------------------------------- provider

HttpGet = Callable[[str, Dict[str, str], float], Tuple[int, Optional[Dict[str, Any]]]]


def default_http_get(url: str, headers: Dict[str, str], timeout: float) -> Tuple[int, Optional[Dict[str, Any]]]:
    import httpx

    try:
        response = httpx.get(url, headers=headers, timeout=httpx.Timeout(timeout, connect=10.0))
    except httpx.HTTPError:
        return 0, None
    try:
        return response.status_code, (response.json() if response.status_code == 200 else None)
    except ValueError:
        return response.status_code, None


class RunPodProvider(CloudProvider):
    id: ClassVar[ProviderId] = ProviderId.RUNPOD
    label: ClassVar[str] = "RunPod"
    description: ClassVar[str] = "Rent an on-demand GPU pod for fine-tuning, or call a serverless vLLM endpoint."
    capabilities: ClassVar[Capabilities] = Capabilities(training=True, inference=True)
    fields: ClassVar[List[FieldSpec]] = [
        FieldSpec(name="api_key", label="API key", placeholder="From RunPod → Settings → API Keys"),
    ]

    def __init__(
        self,
        secrets: SecretStore,
        api_factory: Callable[[str], RunPodApi] = RunPodApi,
        transport_factory: Callable[[str], HubTransport] = HubTransport,
        http_get: HttpGet = default_http_get,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(secrets)
        self._api_factory, self._transport_factory = api_factory, transport_factory
        self._http_get, self._sleep, self._clock = http_get, sleep, clock
        self._event_tokens: Dict[str, str] = {}  # per-run bearer tokens, memory only

    # -- helpers -----------------------------------------------------------------

    def api(self) -> RunPodApi:
        return self._api_factory(self.credential("api_key"))

    def _transport(self, token: Optional[str] = None) -> HubTransport:
        token = token or self.secrets.get(HF_TOKEN)
        if not token:
            raise ConfigError("RunPod runs need a Hugging Face token.", hint="Add one in Settings → Hugging Face.")
        return self._transport_factory(token)

    # -- credentials / discovery ---------------------------------------------------

    def validate_credentials(self) -> AccountInfo:
        gpus = self.api().gpus()  # any authenticated call; rejected keys raise AuthError
        return AccountInfo(name="RunPod account", detail=f"{len(gpus)} GPU types visible")

    def list_gpus(self) -> List[GpuOption]:
        return gpu_options(self.api().gpus())

    def list_instances(self) -> List[InstanceInfo]:
        return [
            InstanceInfo(provider=self.id, remote_id=pod_id(p), name=pod_name(p), status=pod_state(p),
                         gpu=pod_gpu(p), price_per_hour=pod_price(p))
            for p in self.api().pods() if pod_name(p).startswith(NAME_PREFIX)
        ]

    def terminate(self, remote_id: str) -> None:
        self.api().terminate(remote_id)

    # -- inference (serverless vLLM endpoint, OpenAI-compatible) -----------------------

    def inference_endpoint(self, model: RemoteModel) -> InferenceEndpoint:
        if not model.endpoint_id:
            raise ConfigError("A RunPod endpoint id is required for serverless inference.")
        return InferenceEndpoint(
            kind="openai", base_url=f"https://api.runpod.ai/v2/{model.endpoint_id}/openai/v1",
            headers={"Authorization": f"Bearer {self.credential('api_key')}"}, model=model.remote_model,
        )

    def test_model(self, model: RemoteModel) -> str:
        from core.cloud.http import default_http
        from core.cloud.providers.remote_inference import _probe_openai

        return _probe_openai(default_http(), self.inference_endpoint(model), "RunPod")

    # -- training --------------------------------------------------------------------

    def submit_training(self, spec: RemoteTrainingSpec, bundle) -> RemoteJobHandle:
        if not spec.target.gpu_id:
            raise ConfigError("Choose a GPU for the RunPod run.")
        token = spec.hf_token.get_secret_value() if spec.hf_token else None
        transport = self._transport(token)
        api = self.api()
        name = f"{NAME_PREFIX}{spec.job_id}"
        max_seconds = spec.target.max_runtime_minutes * 60

        for stale in api.pods():  # a pod with this name from an earlier attempt has an unknown event token
            if pod_name(stale) == name and pod_state(stale) not in GONE_STATES:
                logger.warning("Terminating stale pod %s", pod_id(stale))
                api.terminate(pod_id(stale))
        existing: Optional[Dict[str, Any]] = None
        dataset = Path(spec.dataset_path)
        repos = RunRepos("", "")
        try:
            repos = stage_training(transport, spec, bundle)

            event_token = pysecrets.token_urlsafe(24)
            script = build_pod_script(
                dataset_repo=repos.dataset_repo, dataset_filename=dataset.name, max_seconds=max_seconds,
            )

            def find_or_create() -> Dict[str, Any]:
                # A retry after a timed-out create must not start a second (billing) pod.
                for pod in api.pods():
                    if pod_name(pod) == name and pod_state(pod) not in GONE_STATES:
                        return pod
                return api.create(
                    name=name, image_name=IMAGE, gpu_type_id=spec.target.gpu_id, cloud_type="ALL",
                    container_disk_in_gb=50, volume_in_gb=0, ports=f"{EVENT_PORT}/http", start_ssh=False,
                    docker_args=f"bash -c {shlex.quote(script)}",
                    env={"HF_TOKEN": token, "CRAFTML_EVENT_TOKEN": event_token, "CRAFTML_SERVE_GRACE": "60",
                         "PYTHONUNBUFFERED": "1", "CRAFTML_USE_VENV": "1"},
                )

            existing = retry_call(find_or_create, attempts=3, sleep=self._sleep)
        except BaseException:
            self._best_effort_cleanup(api, transport, None, repos)
            raise

        remote_id = pod_id(existing or {})
        if not remote_id:
            self._best_effort_cleanup(api, transport, None, repos)
            raise RemoteExecutionError("RunPod didn't return a pod id.")
        self._event_tokens[remote_id] = event_token
        return RemoteJobHandle(
            provider=self.id, remote_id=remote_id, job_id=spec.job_id, gpu_id=spec.target.gpu_id,
            gpu_name=pod_gpu(existing or {}) or spec.target.gpu_id, price_per_hour=pod_price(existing or {}),
            meta={"dataset_repo": repos.dataset_repo, "adapter_repo": repos.adapter_repo, "port": str(EVENT_PORT)},
        )

    def _best_effort_cleanup(self, api: RunPodApi, transport: HubTransport, pod: Optional[str], repos: RunRepos) -> None:
        try:
            if pod:
                api.terminate(pod)
        finally:
            if repos.dataset_repo:
                transport.delete_repos(repos)

    def stream_events(self, handle: RemoteJobHandle, stop: Callable[[], bool]) -> Iterator[RemoteEvent]:
        token = self._event_tokens.get(handle.remote_id)
        if not token:
            raise ConfigError("This run's event token is only kept in memory and was lost (the app restarted).")
        base = f"https://{handle.remote_id}-{handle.meta.get('port', EVENT_PORT)}.proxy.runpod.net"
        headers = {"Authorization": f"Bearer {token}"}
        api = self.api()
        after = 0
        started = last_note = self._clock()

        while not stop():
            status, body = self._http_get(f"{base}/events?after={after}", headers, 30.0)

            if status == 200 and body is not None:
                after = int(body.get("next", after))
                for line in body.get("events", []):
                    event = event_from_line(line)
                    if event is None:
                        continue
                    yield event
                    if event.type == "status" and event.status in TERMINAL:
                        return
                if body.get("done"):
                    return
                self._sleep(POLL_INTERVAL)
                continue

            if status in (401, 403):
                raise RemoteExecutionError("The pod rejected the event token.")

            # Not reachable yet (starting, image pulling, pip installing) or gone.
            pod = api.pod(handle.remote_id)
            if pod is None or pod_state(pod) in GONE_STATES:
                yield from self._pod_died(handle)
                return
            waited = self._clock() - started
            if waited > BOOT_TIMEOUT and after == 0:
                yield RemoteEvent(type="status", status="failed",
                                  error=f"The pod didn't start reporting within {BOOT_TIMEOUT // 60} minutes.")
                return
            if self._clock() - last_note >= NOTE_INTERVAL:
                last_note = self._clock()
                yield RemoteEvent(type="log", message=f"Waiting for the pod to start ({int(waited)} s)…")
            self._sleep(POLL_INTERVAL * 2)

    def _pod_died(self, handle: RemoteJobHandle) -> Iterator[RemoteEvent]:
        tail = ""
        try:
            log = self._transport().read_text(handle.meta["dataset_repo"], "pod.log")
            tail = "\n".join((log or "").strip().splitlines()[-30:])
        except CloudError:
            pass
        if tail:
            yield RemoteEvent(type="log", level="error", message=redact(tail))
        yield RemoteEvent(type="status", status="failed", error="The RunPod pod ended before the job finished.")

    def fetch_artifacts(self, handle: RemoteJobHandle, dest: Path) -> Path:
        return self._transport().download_adapter(handle.meta["adapter_repo"], dest)

    def get_status(self, handle: RemoteJobHandle) -> RemoteStatus:
        pod = self.api().pod(handle.remote_id)
        if pod is None or pod_state(pod) in GONE_STATES:
            return "gone"
        return "running"

    def cancel(self, handle: RemoteJobHandle) -> None:
        self.api().terminate(handle.remote_id)  # no graceful path through the proxy; the adapter isn't wanted anyway

    def cleanup(self, handle: RemoteJobHandle) -> None:
        """Terminate the pod first (that's what bills), then delete the transfer repos."""
        error: Optional[BaseException] = None
        try:
            self.api().terminate(handle.remote_id)
        except Exception as exc:  # noqa: BLE001
            error = exc
        finally:
            self._event_tokens.pop(handle.remote_id, None)
            try:
                failed = self._transport().delete_repos(
                    RunRepos(handle.meta.get("dataset_repo", ""), handle.meta.get("adapter_repo", ""))
                ) if handle.meta.get("dataset_repo") else []
                if failed:
                    logger.warning("Transfer repos not deleted: %s", failed)
            except Exception as exc:  # noqa: BLE001 - repo leftovers matter less than pod termination
                logger.warning("Could not delete transfer repos: %s", exc)
        if error is not None:
            raise error

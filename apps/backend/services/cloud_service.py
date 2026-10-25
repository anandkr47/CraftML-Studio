"""
Cloud service: wires the DB-free ``core.cloud`` layer into the backend.

* owns the process-wide SecretStore and SSH host-key store (paths follow the OS app-data dir);
* persists remote runs in ``cloud_runs`` (the ``RunStore`` the manager needs);
* runs remote fine-tunes on behalf of ``training_service``;
* credential management, GPU/price lookup, orphan scan and startup reconciliation for the API.
"""

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.cloud import manager
from core.cloud.errors import CloudError, ConfigError, HostKeyError
from core.cloud.hostkeys import HostKeyStore
from core.cloud.manager import ProgressSink, RunRecord
from core.cloud.providers import get_provider_class
from core.cloud.providers.base import CloudProvider
from core.cloud.schemas import (
    CloudTarget,
    GpuOption,
    InstanceInfo,
    ProviderId,
    ProviderInfo,
    RemoteJobHandle,
    RemoteModel,
    RemoteTrainingSpec,
    SshProfile,
)
from core.cloud.secrets import SecretStore
from core.config import settings
from core.utils import setup_logger
from db.models import CloudModel, CloudRun, SessionLocal, utc_from_timestamp
from services import inference
from services.inference import InferenceError, ModelInfo

logger = setup_logger("cloud_service", log_file=str(settings.logs_dir / "cloud_service.log"))

_lock = threading.Lock()
_secrets: Optional[SecretStore] = None
_host_keys: Optional[HostKeyStore] = None


def secrets() -> SecretStore:
    global _secrets
    with _lock:
        if _secrets is None:
            _secrets = SecretStore(Path(settings.user_data_dir) / "secrets")
        return _secrets


def host_keys() -> HostKeyStore:
    global _host_keys
    with _lock:
        if _host_keys is None:
            _host_keys = HostKeyStore(Path(settings.user_data_dir) / "ssh_known_hosts.json")
        return _host_keys


def make_provider(provider_id: ProviderId) -> CloudProvider:
    """Instantiate a provider (SSH gets the host-key store)."""
    cls = get_provider_class(provider_id)
    if provider_id is ProviderId.SSH:
        return cls(secrets(), host_keys=host_keys())
    return cls(secrets())


def _factory(provider_id: ProviderId, store: SecretStore) -> CloudProvider:  # matches manager.ProviderFactory
    return make_provider(provider_id)


# --------------------------------------------------------------------------- run persistence

class DbRunStore:
    """``manager.RunStore`` backed by the ``cloud_runs`` table."""

    @staticmethod
    def _record(row: CloudRun) -> RunRecord:
        return RunRecord(
            handle=RemoteJobHandle.model_validate_json(row.handle),
            status=row.status,
            error=row.error,
            ended_at=row.ended_at.timestamp() if row.ended_at else None,
        )

    def save(self, record: RunRecord) -> None:
        with SessionLocal() as db:
            row = db.query(CloudRun).filter(CloudRun.job_id == record.job_id).first() or CloudRun(job_id=record.job_id)
            row.provider = record.handle.provider.value
            row.remote_id = record.handle.remote_id
            row.status = record.status
            row.handle = record.handle.model_dump_json()
            row.error = record.error
            db.add(row)
            db.commit()

    def update(self, job_id: str, **fields: Any) -> None:
        with SessionLocal() as db:
            row = db.query(CloudRun).filter(CloudRun.job_id == job_id).first()
            if not row:
                return
            if "status" in fields:
                row.status = fields["status"]
            if "error" in fields:
                row.error = fields["error"]
            if fields.get("ended_at"):
                row.ended_at = utc_from_timestamp(fields["ended_at"])
            db.commit()

    def get(self, job_id: str) -> Optional[RunRecord]:
        with SessionLocal() as db:
            row = db.query(CloudRun).filter(CloudRun.job_id == job_id).first()
            return self._record(row) if row else None

    def active(self) -> List[RunRecord]:
        with SessionLocal() as db:
            return [self._record(r) for r in db.query(CloudRun).filter(CloudRun.status == "running").all()]

    def known_remote_ids(self, provider: ProviderId) -> Set[str]:
        """Remote ids of runs that are still active; anything else on the provider is an orphan."""
        with SessionLocal() as db:
            rows = db.query(CloudRun.remote_id).filter(
                CloudRun.provider == provider.value, CloudRun.status == "running"
            ).all()
            return {r[0] for r in rows}


run_store = DbRunStore()


# --------------------------------------------------------------------------- training

def validate_target(target: CloudTarget) -> CloudProvider:
    """Fail fast (before a job exists) when the chosen target can't work."""
    provider = make_provider(target.provider)
    if not provider.capabilities.training:
        raise ConfigError(f"{provider.label} doesn't support remote training.")
    if not provider.is_configured():
        raise ConfigError(f"{provider.label} credentials are not set.", hint="Add them in Settings → Cloud GPUs.")
    if target.provider in (ProviderId.RUNPOD, ProviderId.MODAL):
        from services import hf_auth

        if not hf_auth.get_hf_token():
            raise ConfigError(
                f"{provider.label} runs need a Hugging Face token to move your dataset and adapter.",
                hint="Add one in Settings → Hugging Face.",
            )
    if target.provider is ProviderId.SSH and not target.ssh_profile:
        raise ConfigError("Choose an SSH host.")
    return provider


def run_remote_training(
    job_id: str, params: Dict[str, Any], sink: ProgressSink, should_cancel
) -> Dict[str, Any]:
    """Run a fine-tune remotely (called on the job thread). Returns the job result dict."""
    from services import hf_auth

    target = CloudTarget(**params["cloud"])
    token = hf_auth.get_hf_token()
    spec = RemoteTrainingSpec(
        job_id=job_id,
        model_name=params["model_name"],
        dataset_path=params["dataset_path"],
        output_dir=params["output_dir"],
        training_method=params.get("training_method") or "qlora",
        lora_config=params.get("lora_config") or {},
        training_config=params.get("training_config") or {},
        target=target,
        hf_token=token,
    )
    return manager.run_training(
        spec, secrets=secrets(), store=run_store, sink=sink, should_cancel=should_cancel,
        provider=make_provider(target.provider),
    )


# --------------------------------------------------------------------------- API helpers

def providers_info() -> List[ProviderInfo]:
    return manager.list_providers(secrets(), _factory)


def save_credentials(provider_id: ProviderId, values: Dict[str, str]) -> Dict[str, Any]:
    """Store credentials, then verify them with the provider; roll back if they're rejected."""
    provider = make_provider(provider_id)
    provider.save_credentials(values)
    try:
        account = provider.validate_credentials()
    except Exception:
        provider.clear_credentials()
        raise
    return {"configured": True, "account": account.model_dump()}


def clear_credentials(provider_id: ProviderId) -> None:
    make_provider(provider_id).clear_credentials()


def list_gpus(provider_id: ProviderId) -> List[GpuOption]:
    return make_provider(provider_id).list_gpus()


def estimate(target: CloudTarget) -> Dict[str, Any]:
    price, name = None, None
    if target.gpu_id:
        for gpu in list_gpus(target.provider):
            if gpu.id == target.gpu_id:
                price, name = gpu.price_per_hour, gpu.name
                break
    return {
        "provider": target.provider.value,
        "gpu": name or target.gpu_id,
        "price_per_hour": price,
        "max_runtime_minutes": target.max_runtime_minutes,
        "worst_case_cost": manager.worst_case_cost(price, target.max_runtime_minutes),
        "note": "An estimate from the provider's listed price; your invoice is authoritative.",
    }


def active_runs() -> List[Dict[str, Any]]:
    now = time.time()
    runs = []
    for record in run_store.active():
        h = record.handle
        elapsed_h = max(0.0, now - h.started_at) / 3600
        runs.append({
            "job_id": h.job_id, "provider": h.provider.value, "remote_id": h.remote_id, "gpu": h.gpu_name or h.gpu_id,
            "price_per_hour": h.price_per_hour, "started_at": h.started_at,
            "estimated_cost": round(h.price_per_hour * elapsed_h, 2) if h.price_per_hour else None,
        })
    return runs


def orphans() -> List[InstanceInfo]:
    return manager.find_orphans(run_store, secrets(), _factory)


def terminate(provider_id: ProviderId, remote_id: str) -> None:
    manager.terminate_instance(provider_id, remote_id, secrets(), _factory)


def startup() -> List[str]:
    """Migrate the legacy HF token and terminate remote runs the previous process left behind."""
    from services import hf_auth

    report: List[str] = []
    try:
        if hf_auth.migrate_legacy():
            report.append("Migrated the Hugging Face token into the encrypted secret store")
        hf_auth.apply_to_environment()
        report += manager.reconcile(run_store, secrets(), _factory)
    except CloudError as exc:
        logger.warning("Cloud startup check failed: %s", exc.user_message())
    except Exception as exc:  # noqa: BLE001 - never block app startup
        logger.error("Cloud startup check failed: %s", exc, exc_info=True)
    for line in report:
        logger.warning(line)
    return report


# --------------------------------------------------------------------------- SSH hosts

def _ssh():
    return make_provider(ProviderId.SSH)


def ssh_profiles() -> List[Dict[str, Any]]:
    provider = _ssh()
    return [
        {**p.model_dump(), "host_key_pinned": host_keys().get(p.host, p.port) is not None}
        for p in provider.profiles.list()
    ]


def ssh_save(profile: SshProfile, private_key: Optional[str], passphrase: Optional[str]) -> None:
    _ssh().profiles.save(profile, private_key, passphrase)


def ssh_delete(name: str) -> bool:
    provider = _ssh()
    profile = provider.profiles.get(name)
    deleted = provider.profiles.delete(name)
    if deleted:
        host_keys().forget(profile.host, profile.port)
    return deleted


def ssh_probe(name: str) -> Dict[str, Any]:
    """Fetch the server's host key (no login) so the user can verify the fingerprint."""
    from core.cloud.providers.ssh_provider import probe_host_key

    profile = _ssh().profiles.get(name)
    key_type, fp = probe_host_key(profile.host, profile.port)
    return {"host": profile.host, "port": profile.port, "key_type": key_type, "fingerprint": fp,
            "status": host_keys().check(profile.host, profile.port, key_type, fp)}


def ssh_trust(name: str, key_type: str, fingerprint: str) -> Dict[str, Any]:
    """Pin the host key, but only if the server still presents the fingerprint the user confirmed."""
    current = ssh_probe(name)
    if current["fingerprint"] != fingerprint or current["key_type"] != key_type:
        raise HostKeyError(
            "The server's key is different from the one you confirmed.", fingerprint=current["fingerprint"],
            changed=True, hint="Check the fingerprint again.",
        )
    profile = _ssh().profiles.get(name)
    host_keys().trust(profile.host, profile.port, key_type, fingerprint)
    return {**current, "status": "trusted"}


def ssh_test(name: str) -> Dict[str, Any]:
    return _ssh().describe_host(name)


# --------------------------------------------------------------------------- remote inference models

def _model(row: CloudModel) -> RemoteModel:
    return RemoteModel(id=row.id, provider=ProviderId(row.provider), name=row.name, remote_model=row.remote_model,
                       base_url=row.base_url, endpoint_id=row.endpoint_id)


def list_remote_models() -> List[RemoteModel]:
    with SessionLocal() as db:
        return [_model(r) for r in db.query(CloudModel).order_by(CloudModel.created_at).all()]


def add_remote_model(provider_id: ProviderId, name: str, remote_model: str, endpoint_id: Optional[str] = None) -> RemoteModel:
    provider = make_provider(provider_id)
    if not provider.capabilities.inference:
        raise ConfigError(f"{provider.label} doesn't offer remote inference.")
    if not provider.is_configured():
        raise ConfigError(f"{provider.label} credentials are not set.", hint="Add them in Settings → Cloud GPUs.")
    model = RemoteModel(id=RemoteModel.make_id(provider_id, name), provider=provider_id, name=name,
                        remote_model=remote_model, endpoint_id=endpoint_id)
    provider.inference_endpoint(model)  # validates provider-specific requirements (e.g. RunPod endpoint id)
    with SessionLocal() as db:
        if db.get(CloudModel, model.id):
            raise ConfigError(f"A cloud model named '{name}' already exists for {provider.label}.")
        db.add(CloudModel(id=model.id, provider=provider_id.value, name=name, remote_model=remote_model,
                          base_url=model.base_url, endpoint_id=endpoint_id))
        db.commit()
    return model


def delete_remote_model(model_id: str) -> bool:
    with SessionLocal() as db:
        row = db.get(CloudModel, model_id)
        if not row:
            return False
        db.delete(row)
        db.commit()
    inference.unload_model(model_id)
    return True


def _get_remote_model(model_id: str) -> RemoteModel:
    with SessionLocal() as db:
        row = db.get(CloudModel, model_id)
        if not row:
            raise InferenceError(f"Cloud model '{model_id}' not found")
        return _model(row)


def endpoint_for(model_id: str):
    model = _get_remote_model(model_id)
    return make_provider(model.provider).inference_endpoint(model)


def test_remote_model(model_id: str) -> str:
    model = _get_remote_model(model_id)
    return make_provider(model.provider).test_model(model)


def catalog(provider_id: ProviderId) -> List[Dict[str, Any]]:
    provider = make_provider(provider_id)
    getter = getattr(provider, "catalog", None)
    return getter() if getter else []


def configure_inference() -> None:
    """Let the inference engine list and call registered cloud models."""
    def source() -> List[ModelInfo]:
        return [ModelInfo(id=m.id, name=f"{m.name} (cloud)", path=m.id, kind="remote", size_mb=0.0)
                for m in list_remote_models()]

    inference.configure_remote(source, endpoint_for)

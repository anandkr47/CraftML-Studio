"""
Cloud GPU API: credentials, GPU/price lookup, cost estimates, running remote jobs and orphan cleanup.
Secrets are write-only: no endpoint ever returns a credential.
"""

from typing import Annotated, Dict, List, Literal, Optional

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from core.cloud.schemas import CloudTarget, GpuOption, InstanceInfo, ProviderId, ProviderInfo, RemoteModel, SshProfile
from services import cloud_service

router = APIRouter()

# Validated at the path level so a bad name is a clean 422, not an error inside a handler.
ProfileName = Annotated[str, Path(pattern=r"^[\w.-]{1,64}$")]


class CredentialsRequest(BaseModel):
    values: Dict[str, str]


class SshProfileRequest(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1)
    runtime: Literal["venv", "docker"] = "venv"
    workdir: str = "craftml"
    inference_port: Optional[int] = Field(default=None, ge=1, le=65535)
    private_key: Optional[str] = None  # write-only; blank on update keeps the stored key
    passphrase: Optional[str] = None


class RemoteModelRequest(BaseModel):
    provider: ProviderId
    name: str = Field(pattern=r"^[\w.-]{1,64}$", description="Display name (letters, digits, . _ -)")
    remote_model: str = Field(min_length=1, description="The provider's model id, e.g. meta-llama/Llama-3.3-70B-Instruct-Turbo")
    endpoint_id: Optional[str] = Field(default=None, description="RunPod endpoint id, or the SSH host name")


class TrustRequest(BaseModel):
    key_type: str
    fingerprint: str


@router.get("/providers", response_model=List[ProviderInfo])
def list_providers():
    return cloud_service.providers_info()


@router.get("/storage")
def secret_storage():
    """Where credentials are kept (OS keychain vs protected file) so the UI can warn if it's the weaker option."""
    return cloud_service.secrets().storage_info()


@router.put("/providers/{provider_id}/credentials")
def save_credentials(provider_id: ProviderId, body: CredentialsRequest):
    """Save and verify credentials. Rejected credentials are discarded and reported as 401."""
    return cloud_service.save_credentials(provider_id, body.values)


@router.delete("/providers/{provider_id}/credentials")
def delete_credentials(provider_id: ProviderId):
    cloud_service.clear_credentials(provider_id)
    return {"configured": False}


@router.get("/providers/{provider_id}/gpus", response_model=List[GpuOption])
def list_gpus(provider_id: ProviderId):
    return cloud_service.list_gpus(provider_id)


@router.post("/training/estimate")
def estimate_training_cost(target: CloudTarget):
    return cloud_service.estimate(target)


@router.get("/instances")
def active_instances():
    """Remote runs currently billing, with an estimated cost so far."""
    return {"runs": cloud_service.active_runs()}


@router.get("/orphans", response_model=List[InstanceInfo])
def find_orphans():
    """Provider resources named ``craftml-*`` that no active run accounts for (possibly still billing)."""
    return cloud_service.orphans()


@router.post("/instances/{provider_id}/{remote_id}/terminate")
def terminate_instance(provider_id: ProviderId, remote_id: str):
    cloud_service.terminate(provider_id, remote_id)
    return {"terminated": True, "remote_id": remote_id}


# --------------------------------------------------------------------------- SSH hosts

@router.get("/ssh/profiles")
def list_ssh_profiles():
    return {"profiles": cloud_service.ssh_profiles()}


@router.put("/ssh/profiles/{name}")
def save_ssh_profile(name: ProfileName, body: SshProfileRequest):
    profile = SshProfile(name=name, **body.model_dump(exclude={"private_key", "passphrase"}))
    cloud_service.ssh_save(profile, body.private_key, body.passphrase)
    return {"saved": True, "name": name}


@router.delete("/ssh/profiles/{name}")
def delete_ssh_profile(name: ProfileName):
    return {"deleted": cloud_service.ssh_delete(name)}


@router.post("/ssh/profiles/{name}/probe")
def probe_ssh_host(name: ProfileName):
    """The server's host-key fingerprint and whether it is already trusted."""
    return cloud_service.ssh_probe(name)


@router.post("/ssh/profiles/{name}/trust")
def trust_ssh_host(name: ProfileName, body: TrustRequest):
    """Pin the host key the user verified (re-checked against the server to prevent a swap)."""
    return cloud_service.ssh_trust(name, body.key_type, body.fingerprint)


@router.post("/ssh/profiles/{name}/test")
def test_ssh_host(name: ProfileName):
    """Log in and report OS, GPUs and whether the host is ready for training."""
    return cloud_service.ssh_test(name)


# --------------------------------------------------------------------------- remote inference models

@router.get("/models", response_model=List[RemoteModel])
def list_remote_models():
    return cloud_service.list_remote_models()


@router.post("/models", response_model=RemoteModel)
def add_remote_model(body: RemoteModelRequest):
    return cloud_service.add_remote_model(body.provider, body.name, body.remote_model, body.endpoint_id)


@router.post("/models/{model_id:path}/test")
def test_remote_model(model_id: str):
    """Send a one-token request to prove the credentials, model and endpoint work together."""
    return {"ok": True, "detail": cloud_service.test_remote_model(model_id)}


@router.delete("/models/{model_id:path}")
def delete_remote_model(model_id: str):
    return {"deleted": cloud_service.delete_remote_model(model_id)}


@router.get("/providers/{provider_id}/catalog")
def provider_catalog(provider_id: ProviderId):
    """Models the provider hosts (where it publishes a list), for the model picker."""
    return {"models": cloud_service.catalog(provider_id)}

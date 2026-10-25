"""Pydantic v2 models shared by the cloud layer, manager and API."""

from __future__ import annotations

import enum
import time
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ProviderId(str, enum.Enum):
    RUNPOD = "runpod"
    MODAL = "modal"
    TOGETHER = "together"
    REPLICATE = "replicate"
    SSH = "ssh"


class Capabilities(BaseModel):
    training: bool = False
    inference: bool = False


class FieldSpec(BaseModel):
    """One credential field, so the UI can render a form without hardcoding providers."""

    name: str
    label: str
    secret: bool = True
    multiline: bool = False
    required: bool = True
    placeholder: Optional[str] = None


class ProviderInfo(BaseModel):
    id: ProviderId
    label: str
    capabilities: Capabilities
    fields: List[FieldSpec]
    configured: bool = False
    description: str = ""


class AccountInfo(BaseModel):
    """Result of validating credentials."""

    name: str
    detail: Optional[str] = None


class GpuOption(BaseModel):
    id: str
    name: str
    vram_gb: float
    price_per_hour: Optional[float] = None
    available: bool = True


class CloudTarget(BaseModel):
    """Where a fine-tune should run (the ``cloud`` block of a training request)."""

    provider: ProviderId
    gpu_id: Optional[str] = None
    max_runtime_minutes: int = Field(default=240, ge=5, le=24 * 60)
    ssh_profile: Optional[str] = None

    @field_validator("provider")
    @classmethod
    def _training_provider(cls, v: ProviderId) -> ProviderId:
        if v not in (ProviderId.RUNPOD, ProviderId.MODAL, ProviderId.SSH):
            raise ValueError(f"{v.value} doesn't support remote training")
        return v


class RemoteTrainingSpec(BaseModel):
    """Everything a provider needs to run one fine-tune."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str
    model_name: str
    dataset_path: str
    output_dir: str
    training_method: str = "qlora"
    lora_config: Dict[str, Any] = Field(default_factory=dict)
    training_config: Dict[str, Any] = Field(default_factory=dict)
    target: CloudTarget
    hf_token: Optional[SecretStr] = None


class RemoteJobHandle(BaseModel):
    """Persisted reference to a remote resource (pod id, function-call id, remote directory…)."""

    provider: ProviderId
    remote_id: str
    job_id: str
    gpu_id: Optional[str] = None
    gpu_name: Optional[str] = None
    price_per_hour: Optional[float] = None
    started_at: float = Field(default_factory=time.time)
    meta: Dict[str, str] = Field(default_factory=dict)


class RemoteEvent(BaseModel):
    """A decoded worker event (see ``core.cloud.events``)."""

    type: Literal["log", "status", "progress", "metric", "telemetry", "artifact"]
    message: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    loss: Optional[float] = None
    learning_rate: Optional[float] = None
    epoch: Optional[float] = None
    vram_gb: Optional[float] = None
    vram_total_gb: Optional[float] = None
    gpu_util: Optional[float] = None
    kind: Optional[str] = None
    path: Optional[str] = None
    repo: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


RemoteStatus = Literal["pending", "running", "succeeded", "failed", "gone"]


class InstanceInfo(BaseModel):
    provider: ProviderId
    remote_id: str
    name: str
    status: str
    gpu: Optional[str] = None
    price_per_hour: Optional[float] = None
    started_at: Optional[float] = None
    job_id: Optional[str] = None


class RemoteModel(BaseModel):
    """A registered remote inference model (shows up in Chat as ``cloud:<provider>:<name>``)."""

    id: str
    provider: ProviderId
    name: str
    remote_model: str
    base_url: Optional[str] = None
    endpoint_id: Optional[str] = None

    @staticmethod
    def make_id(provider: ProviderId, name: str) -> str:
        return f"cloud:{provider.value}:{name}"


class SshProfile(BaseModel):
    """Non-secret SSH settings; the private key and passphrase live in the SecretStore."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[\w.-]+$")
    host: str = Field(min_length=1)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1)
    runtime: Literal["venv", "docker"] = "venv"
    workdir: str = "craftml"  # relative to the remote home directory
    inference_port: Optional[int] = Field(default=None, ge=1, le=65535)


def parse_event_line(line: str) -> Optional[RemoteEvent]:
    """A worker output line as a ``RemoteEvent``; None for plain output or other protocol versions."""
    from core.cloud import events

    payload = events.decode(line)
    if payload is None:
        return None
    payload.pop("v", None)
    return RemoteEvent(**payload)

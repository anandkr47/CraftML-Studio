"""
Provider contract.

A provider wraps one cloud service.  Capabilities differ (training vs inference), so
every optional operation has a default that raises ``NotSupported``.  Providers must:

* import their vendor SDK lazily inside methods (a missing SDK is a clear error, not a
  startup crash);
* never log or return secrets;
* make ``cancel`` and ``cleanup`` idempotent and safe on already-gone resources;
* poll the ``stop`` callable given to ``stream_events`` and return promptly once it is true.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import TYPE_CHECKING, Callable, ClassVar, Dict, Iterator, List

from pydantic import BaseModel

from core.cloud.errors import ConfigError, NotSupported
from core.cloud.schemas import (
    AccountInfo,
    Capabilities,
    FieldSpec,
    GpuOption,
    InstanceInfo,
    ProviderId,
    RemoteEvent,
    RemoteJobHandle,
    RemoteModel,
    RemoteStatus,
    RemoteTrainingSpec,
)
from core.cloud.secrets import SecretStore

if TYPE_CHECKING:  # avoid importing the bundle builder at module load
    from core.cloud.bundle import Bundle

NAME_PREFIX = "craftml-"  # every remote resource we create is named craftml-<job_id>


class InferenceEndpoint(BaseModel):
    """How to call a remote model. ``kind='openai'`` speaks the OpenAI chat protocol."""

    kind: str  # "openai" | "replicate"
    base_url: str
    headers: Dict[str, str]
    model: str


def secret_name(provider: ProviderId, field: str) -> str:
    return f"cloud/{provider.value}/{field}"


class CloudProvider(abc.ABC):
    id: ClassVar[ProviderId]
    label: ClassVar[str]
    description: ClassVar[str] = ""
    capabilities: ClassVar[Capabilities]
    fields: ClassVar[List[FieldSpec]]

    def __init__(self, secrets: SecretStore):
        self.secrets = secrets

    # -- credentials ---------------------------------------------------------

    def credential(self, field: str) -> str:
        value = self.secrets.get(secret_name(self.id, field))
        if not value:
            raise ConfigError(
                f"{self.label} credentials are not set.", hint="Add them in Settings → Cloud GPUs."
            )
        return value

    def is_configured(self) -> bool:
        return all(
            self.secrets.exists(secret_name(self.id, f.name)) for f in self.fields if f.required
        )

    def save_credentials(self, values: Dict[str, str]) -> None:
        for spec in self.fields:
            value = (values.get(spec.name) or "").strip() if not spec.multiline else (values.get(spec.name) or "")
            if value:
                self.secrets.set(secret_name(self.id, spec.name), value)
            elif spec.required:
                raise ConfigError(f"{spec.label} is required.")

    def clear_credentials(self) -> None:
        self.secrets.delete_prefix(f"cloud/{self.id.value}/")

    @abc.abstractmethod
    def validate_credentials(self) -> AccountInfo:
        """Call the provider with the stored credentials; raise ``AuthError`` if rejected."""

    # -- discovery -------------------------------------------------------------

    def list_gpus(self) -> List[GpuOption]:
        raise NotSupported(f"{self.label} doesn't list GPUs.")

    def list_instances(self) -> List[InstanceInfo]:
        """Resources we created (name starts with ``craftml-``), for orphan detection."""
        return []

    def terminate(self, remote_id: str) -> None:
        raise NotSupported(f"{self.label} can't terminate resources.")

    # -- training --------------------------------------------------------------

    def submit_training(self, spec: RemoteTrainingSpec, bundle: "Bundle") -> RemoteJobHandle:
        raise NotSupported(f"{self.label} doesn't support remote training.")

    def stream_events(
        self, handle: RemoteJobHandle, stop: Callable[[], bool]
    ) -> Iterator[RemoteEvent]:
        raise NotSupported(f"{self.label} doesn't support remote training.")

    def fetch_artifacts(self, handle: RemoteJobHandle, dest: Path) -> Path:
        """Download the trained adapter into ``dest/final`` and return that path."""
        raise NotSupported(f"{self.label} doesn't support remote training.")

    def get_status(self, handle: RemoteJobHandle) -> RemoteStatus:
        raise NotSupported(f"{self.label} doesn't support remote training.")

    def cancel(self, handle: RemoteJobHandle) -> None:
        """Ask the remote job to stop (best effort, idempotent)."""

    def cleanup(self, handle: RemoteJobHandle) -> None:
        """Release everything billed or stored for this run (idempotent, never raises on 'gone')."""

    # -- inference ---------------------------------------------------------------

    def inference_endpoint(self, model: RemoteModel) -> InferenceEndpoint:
        raise NotSupported(f"{self.label} doesn't offer remote inference.")

    def test_model(self, model: RemoteModel) -> str:
        """Cheap connectivity check for a registered model; returns a short description."""
        raise NotSupported(f"{self.label} doesn't offer remote inference.")

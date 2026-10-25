"""Provider registry. Provider modules import vendor SDKs lazily, so importing them is cheap."""

from __future__ import annotations

import importlib
from typing import Dict, List, Tuple, Type

from core.cloud.errors import NotSupported
from core.cloud.providers.base import CloudProvider
from core.cloud.schemas import ProviderId

_REGISTRY: Dict[ProviderId, Tuple[str, str]] = {
    ProviderId.SSH: ("core.cloud.providers.ssh_provider", "SshProvider"),
    ProviderId.RUNPOD: ("core.cloud.providers.runpod_provider", "RunPodProvider"),
    ProviderId.MODAL: ("core.cloud.providers.modal_provider", "ModalProvider"),
    ProviderId.TOGETHER: ("core.cloud.providers.remote_inference", "TogetherProvider"),
    ProviderId.REPLICATE: ("core.cloud.providers.remote_inference", "ReplicateProvider"),
}


def get_provider_class(provider: ProviderId) -> Type[CloudProvider]:
    try:
        module_name, class_name = _REGISTRY[provider]
    except KeyError:
        raise NotSupported(f"Unknown provider '{provider}'.")
    try:
        return getattr(importlib.import_module(module_name), class_name)
    except ModuleNotFoundError as exc:
        raise NotSupported(f"{provider.value} support isn't installed: {exc}") from exc


def provider_ids() -> List[ProviderId]:
    return list(_REGISTRY)


__all__ = ["CloudProvider", "get_provider_class", "provider_ids"]

"""
Inference engine: model discovery, loading, and generation.

Models are discovered under ``settings.models_dir``:
  * ``<id>/final``      - output of a fine-tune job (full model or LoRA adapter)
  * ``<id>``            - any directory with a ``config.json`` (downloaded / compressed)
  * ``*.gguf``          - llama.cpp models
Any other id containing ``/`` is treated as a Hugging Face repo id.
"""

import threading
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from core.config import settings
from core.utils import setup_logger

from .types import Backend, GenerationParams, InferenceError, Message, ModelInfo, Usage

logger = setup_logger("inference_engine", log_file=str(settings.logs_dir / "inference_service.log"))

_loaded: Dict[str, Backend] = {}
_load_lock = threading.Lock()

# Remote (cloud) models are registered by the cloud service so the engine stays free of DB/provider imports.
_remote_source: Optional[Callable[[], List[ModelInfo]]] = None
_remote_resolver: Optional[Callable[[str], Any]] = None  # model id -> InferenceEndpoint


def configure_remote(source: Callable[[], List[ModelInfo]], resolver: Callable[[str], Any]) -> None:
    global _remote_source, _remote_resolver
    _remote_source, _remote_resolver = source, resolver


def _dir_size_mb(path: Path) -> float:
    try:
        return round(sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024), 2)
    except OSError:
        return 0.0


def _dir_kind(path: Path) -> Optional[str]:
    if (path / "adapter_config.json").exists():
        return "lora"
    if (path / "config.json").exists():
        return "full"
    return None


def discover_models() -> List[ModelInfo]:
    models_dir = Path(settings.models_dir)
    found: Dict[str, ModelInfo] = {}

    if models_dir.exists():
        for entry in sorted(models_dir.iterdir()):
            if entry.is_dir():
                target = entry / "final" if (entry / "final").is_dir() else entry
                kind = _dir_kind(target)
                if kind:
                    found[entry.name] = ModelInfo(
                        id=entry.name,
                        name=entry.name,
                        path=str(target.resolve()),
                        kind=kind,
                        size_mb=_dir_size_mb(target),
                    )
        for gguf in sorted(models_dir.rglob("*.gguf")):
            model_id = gguf.stem
            if model_id in found:
                model_id = f"{gguf.parent.name}/{gguf.stem}"
            found[model_id] = ModelInfo(
                id=model_id,
                name=gguf.stem,
                path=str(gguf.resolve()),
                kind="gguf",
                size_mb=round(gguf.stat().st_size / (1024 * 1024), 2),
            )
    if _remote_source is not None:
        try:
            for remote in _remote_source():
                found.setdefault(remote.id, remote)
        except Exception as exc:  # noqa: BLE001 - a broken registry must not hide local models
            logger.warning(f"Could not list remote models: {exc}")
    return list(found.values())


def resolve_model(model_id: str) -> ModelInfo:
    for info in discover_models():
        if info.id == model_id:
            return info
    if "/" in model_id and not Path(model_id).exists():
        return ModelInfo(id=model_id, name=model_id, path=model_id, kind="hf")
    raise InferenceError(f"Model '{model_id}' not found")


def loaded_ids() -> List[str]:
    return list(_loaded)


def is_loaded(model_id: str) -> bool:
    return model_id in _loaded


def load_model(model_id: str, device: str = "auto", n_ctx: Optional[int] = None) -> Backend:
    """Load a model (or return the cached instance)."""
    with _load_lock:
        if model_id in _loaded:
            return _loaded[model_id]

        info = resolve_model(model_id)
        if info.kind == "remote":
            from .remote_backend import RemoteBackend

            if _remote_resolver is None:
                raise InferenceError("Cloud models aren't available.")
            backend = RemoteBackend(_remote_resolver(model_id))
        elif info.kind == "gguf":
            from .llama_cpp_backend import DEFAULT_CONTEXT, LlamaCppBackend

            backend = LlamaCppBackend(info.path, n_ctx=n_ctx or DEFAULT_CONTEXT)
        else:
            from .transformers_backend import TransformersBackend

            backend = TransformersBackend(info.path, device=device)

        _loaded[model_id] = backend
        logger.info(f"Loaded model {model_id} ({info.kind}) on {backend.device}")
        return backend


def unload_model(model_id: str) -> bool:
    with _load_lock:
        backend = _loaded.pop(model_id, None)
    if backend is None:
        return False
    backend.close()
    logger.info(f"Unloaded model {model_id}")
    return True


def stream_chat(model_id: str, messages: List[Message], params: GenerationParams, usage: Usage) -> Iterator[str]:
    """Stream a chat completion, loading the model on first use."""
    backend = load_model(model_id)
    yield from backend.stream(messages, params, usage)


def chat(model_id: str, messages: List[Message], params: GenerationParams) -> Tuple[str, Usage]:
    usage = Usage()
    text = "".join(stream_chat(model_id, messages, params, usage))
    return text, usage

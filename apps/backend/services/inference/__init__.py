"""Local inference engine (transformers + llama.cpp)."""

from .engine import (
    chat,
    discover_models,
    is_loaded,
    load_model,
    loaded_ids,
    resolve_model,
    stream_chat,
    unload_model,
)
from .types import GenerationParams, InferenceError, Message, ModelInfo, Usage

__all__ = [
    "GenerationParams",
    "InferenceError",
    "Message",
    "ModelInfo",
    "Usage",
    "chat",
    "discover_models",
    "is_loaded",
    "load_model",
    "loaded_ids",
    "resolve_model",
    "stream_chat",
    "unload_model",
]

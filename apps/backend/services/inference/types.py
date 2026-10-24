"""Shared types for the inference engine."""

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Protocol

Message = Dict[str, str]  # {"role": "system|user|assistant", "content": "..."}


@dataclass
class GenerationParams:
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    stop: List[str] = field(default_factory=list)


@dataclass
class Usage:
    """Filled in by a backend once a stream has finished."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"


@dataclass
class ModelInfo:
    id: str
    name: str
    path: str
    kind: str  # "full" | "lora" | "gguf" | "hf"
    size_mb: float = 0.0


class Backend(Protocol):
    device: str

    def stream(self, messages: List[Message], params: GenerationParams, usage: Usage) -> Iterator[str]:
        """Yield text deltas; set ``usage`` before the iterator is exhausted."""
        ...

    def count_tokens(self, text: str) -> int: ...

    def close(self) -> None: ...


class InferenceError(RuntimeError):
    """Raised for user-visible inference failures (missing model, missing dependency)."""

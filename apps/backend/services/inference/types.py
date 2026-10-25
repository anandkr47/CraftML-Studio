"""Shared types for the inference engine."""

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Protocol

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
    kind: str  # "full" | "lora" | "gguf" | "hf" | "remote"
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


def format_messages_fallback(messages: List[Message]) -> str:
    """Plain-text prompt for models that ship without a chat template (same for every backend)."""
    lines = []
    for m in messages:
        role = {"system": "System", "user": "User", "assistant": "Assistant"}.get(m["role"], m["role"])
        lines.append(f"{role}: {m['content']}")
    lines.append("Assistant:")
    return "\n".join(lines)


# Stop sequence that ends the assistant turn of ``format_messages_fallback`` prompts.
FALLBACK_STOP = "\nUser:"


class StopTrimmer:
    """
    Removes stop sequences from streamed text (OpenAI semantics: the stop sequence is not part of
    the reply). ``feed`` returns what can be shown so far, holding back only a tail that could be the
    start of a stop sequence; once a stop sequence appears, ``done`` is set and the rest is dropped.
    """

    def __init__(self, stops: List[str]):
        self.stops = [s for s in stops if s]
        self.buffer = ""
        self.done = False

    def feed(self, delta: str) -> str:
        if self.done:
            return ""
        self.buffer += delta
        hits = [self.buffer.find(s) for s in self.stops if s in self.buffer]
        if hits:
            out, self.buffer, self.done = self.buffer[: min(hits)], "", True
            return out
        hold = 0
        for s in self.stops:
            for k in range(min(len(s) - 1, len(self.buffer)), 0, -1):
                if self.buffer.endswith(s[:k]):
                    hold = max(hold, k)
                    break
        out, self.buffer = self.buffer[: len(self.buffer) - hold], self.buffer[len(self.buffer) - hold:]
        return out

    def flush(self) -> str:
        out, self.buffer = ("" if self.done else self.buffer), ""
        return out

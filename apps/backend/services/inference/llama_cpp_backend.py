"""llama.cpp backend for GGUF models (via llama-cpp-python)."""

import threading
from typing import Iterator, List, Optional

from core.utils import setup_logger
from core.config import settings

from .types import GenerationParams, InferenceError, Message, Usage

logger = setup_logger("inference_llama_cpp", log_file=str(settings.logs_dir / "inference_service.log"))

DEFAULT_CONTEXT = 4096


class LlamaCppBackend:
    def __init__(self, path: str, n_ctx: int = DEFAULT_CONTEXT, logits_all: bool = False):
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise InferenceError(
                "GGUF models need llama-cpp-python. Install it with: pip install llama-cpp-python"
            ) from exc

        self.path = path
        self.n_ctx = n_ctx
        self._lock = threading.Lock()
        try:
            # n_gpu_layers=-1 offloads everything it can (Metal / CUDA builds), else runs on CPU.
            self.llm = Llama(
                model_path=path, n_ctx=n_ctx, n_gpu_layers=-1, verbose=False, logits_all=logits_all
            )
        except Exception as exc:
            raise InferenceError(f"Failed to load GGUF model '{path}': {exc}") from exc
        self.device = "gpu/cpu (llama.cpp)"

    def count_tokens(self, text: str) -> int:
        return len(self.llm.tokenize(text.encode("utf-8"), add_bos=False))

    def perplexity(self, texts: List[str], max_length: int = 512) -> Optional[float]:
        """Perplexity over ``texts``; requires the model to be loaded with logits_all=True."""
        import math

        import numpy as np

        total_nll, total_tokens = 0.0, 0
        for text in texts:
            tokens = self.llm.tokenize(text.encode("utf-8"), add_bos=True)[:max_length]
            if len(tokens) < 2:
                continue
            self.llm.reset()
            self.llm.eval(tokens)
            logits = np.array(self.llm.scores[: len(tokens) - 1], dtype=np.float64)
            peak = logits.max(axis=1, keepdims=True)
            log_probs = logits - peak - np.log(np.exp(logits - peak).sum(axis=1, keepdims=True))
            total_nll -= log_probs[np.arange(len(tokens) - 1), tokens[1:]].sum()
            total_tokens += len(tokens) - 1
        return math.exp(total_nll / total_tokens) if total_tokens else None

    def stream(self, messages: List[Message], params: GenerationParams, usage: Usage) -> Iterator[str]:
        usage.prompt_tokens = self.count_tokens("\n".join(m["content"] for m in messages))
        completion = ""
        finish = "stop"

        with self._lock:
            chunks = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=params.max_tokens,
                temperature=params.temperature,
                top_p=params.top_p,
                top_k=params.top_k,
                repeat_penalty=params.repetition_penalty,
                stop=params.stop or None,
                stream=True,
            )
            for chunk in chunks:
                choice = chunk["choices"][0]
                delta = choice.get("delta", {}).get("content")
                if delta:
                    completion += delta
                    yield delta
                if choice.get("finish_reason"):
                    finish = choice["finish_reason"]

        usage.completion_tokens = self.count_tokens(completion) if completion else 0
        usage.finish_reason = finish

    def close(self) -> None:
        self.llm.close()

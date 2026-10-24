"""
Model benchmark used for the Compress before/after report:
perplexity on a small text sample, generation speed, load time and memory.
"""

import time
from typing import Any, Dict, List, Optional

import psutil

from core.ml.compression.calibration import SAMPLE_TEXTS
from services.inference import GenerationParams, Usage

SPEED_PROMPT = [{"role": "user", "content": "Write a short story about a robot who learns to paint."}]
SPEED_TOKENS = 64


def _rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1024 ** 2


def benchmark_model(
    path: str, kind: str, texts: Optional[List[str]] = None, speed_tokens: int = SPEED_TOKENS
) -> Dict[str, Any]:
    """
    Load the model at ``path`` ("gguf" file or Hugging Face directory), measure it, unload it.

    Returns perplexity (lower is better), tokens_per_second, load_seconds and memory_mb
    (accelerator memory on CUDA, otherwise growth in process memory).
    """
    texts = texts or SAMPLE_TEXTS
    rss_before = _rss_mb()
    started = time.time()

    if kind == "gguf":
        from services.inference.llama_cpp_backend import LlamaCppBackend

        backend = LlamaCppBackend(path, n_ctx=1024, logits_all=True)
    else:
        from services.inference.transformers_backend import TransformersBackend

        backend = TransformersBackend(path)
    load_seconds = time.time() - started

    try:
        memory_mb = _rss_mb() - rss_before
        if kind != "gguf" and backend.device == "cuda":
            import torch

            memory_mb = torch.cuda.memory_allocated() / 1024 ** 2

        perplexity = backend.perplexity(texts)

        usage = Usage()
        begin = time.time()
        text = "".join(backend.stream(SPEED_PROMPT, GenerationParams(max_tokens=speed_tokens, temperature=0), usage))
        elapsed = max(time.time() - begin, 1e-6)
        generated = usage.completion_tokens or backend.count_tokens(text)
    finally:
        backend.close()

    return {
        "perplexity": round(perplexity, 3) if perplexity is not None else None,
        "tokens_per_second": round(generated / elapsed, 2),
        "load_seconds": round(load_seconds, 2),
        "memory_mb": round(max(memory_mb, 0.0), 1),
    }


def build_report(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Derived comparison numbers between two measurement dicts (each includes size_mb)."""
    def ratio(a, b):
        return round(a / b, 2) if a and b else None

    report: Dict[str, Any] = {"before": before, "after": after}
    report["size_reduction_percent"] = (
        round((1 - after["size_mb"] / before["size_mb"]) * 100, 1) if before.get("size_mb") else None
    )
    report["compression_ratio"] = ratio(before.get("size_mb"), after.get("size_mb"))
    report["speedup"] = ratio(after.get("tokens_per_second"), before.get("tokens_per_second"))
    if before.get("perplexity") and after.get("perplexity"):
        report["perplexity_increase_percent"] = round((after["perplexity"] / before["perplexity"] - 1) * 100, 1)
    return report

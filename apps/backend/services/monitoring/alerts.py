"""
Out-of-memory alerts: memory pressure while jobs run, and whether a model's
context window (KV cache) fits in the memory that is left.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services import inference, jobs

WARN_PERCENT = 85.0
CRITICAL_PERCENT = 93.0


def _pressure(percent: float) -> Optional[str]:
    if percent >= CRITICAL_PERCENT:
        return "critical"
    if percent >= WARN_PERCENT:
        return "warning"
    return None


def evaluate(reading: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Alerts for a telemetry reading, given the jobs currently running."""
    alerts: List[Dict[str, Any]] = []
    gpu = reading.get("gpu")
    unified = bool(gpu and gpu["kind"] == "apple")

    ram_level = _pressure(reading["memory"]["percent"])
    if ram_level:
        alerts.append({
            "id": "ram", "severity": ram_level, "title": "System memory is almost full",
            "message": f"RAM is {reading['memory']['percent']:.0f}% used. Close other apps or unload models to avoid a crash.",
        })

    if gpu and not unified:
        vram_level = _pressure(gpu["vram_percent"])
        if vram_level:
            alerts.append({
                "id": "vram", "severity": vram_level, "title": "GPU memory is almost full",
                "message": f"VRAM is {gpu['vram_percent']:.0f}% used. Unload a model or lower batch size / context length.",
            })

    worst = ram_level if unified else (_pressure(gpu["vram_percent"]) if gpu else None) or ram_level
    if worst:
        for job in jobs.list_jobs(job_type="finetune", status="running", limit=5):
            alerts.append({
                "id": f"train-{job['job_id']}", "severity": worst, "job_id": job["job_id"],
                "title": "Training may run out of memory",
                "message": "Memory is nearly exhausted while fine-tuning. If it crashes, restart with QLoRA, "
                           "a smaller batch size or a shorter max sequence length.",
            })
    return alerts


def estimate_kv_cache_mb(config: Dict[str, Any], context_tokens: int, dtype_bytes: int = 2) -> Optional[float]:
    """KV-cache size for ``context_tokens`` from a Hugging Face ``config.json``; None if the config lacks the fields."""
    try:
        layers = config["num_hidden_layers"]
        heads = config["num_attention_heads"]
        kv_heads = config.get("num_key_value_heads") or heads
        head_dim = config.get("head_dim") or config["hidden_size"] // heads
    except (KeyError, TypeError, ZeroDivisionError):
        return None
    return 2 * layers * kv_heads * head_dim * context_tokens * dtype_bytes / 1024 ** 2


def _available_mb(reading: Dict[str, Any]) -> float:
    gpu = reading.get("gpu")
    if gpu and gpu["kind"] == "nvidia":
        return gpu["vram_total_mb"] - gpu["vram_used_mb"]
    return reading["memory"]["total_mb"] - reading["memory"]["used_mb"]


def check_context_fit(model_id: str, context_tokens: int, reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    Will ``context_tokens`` of context fit in memory for ``model_id``?

    Risk is "exceeds" when the estimate is above what is free, "high" above 80% of it.
    """
    info = inference.resolve_model(model_id)
    result: Dict[str, Any] = {"model_id": model_id, "context_tokens": context_tokens, "known": False}

    if info.kind == "remote":
        result["message"] = "Runs on the provider's hardware; local memory isn't used."
        return result

    config: Optional[Dict[str, Any]] = None
    if info.kind == "full":
        try:
            config = json.loads((Path(info.path) / "config.json").read_text())
        except (OSError, ValueError):
            pass
    kv_mb = estimate_kv_cache_mb(config, context_tokens) if config else None
    if kv_mb is None:
        result["message"] = "Memory needs for this model's context can't be estimated."
        return result

    weights_mb = 0.0 if inference.is_loaded(model_id) else info.size_mb
    required, available = weights_mb + kv_mb, _available_mb(reading)
    risk = "exceeds" if required > available else "high" if required > 0.8 * available else "ok"
    messages = {
        "ok": "Fits in available memory.",
        "high": "Close to the memory limit; generation may fail on long conversations.",
        "exceeds": "Likely to run out of memory. Lower max tokens, or use a smaller or more compressed model.",
    }
    result.update(
        known=True, kv_cache_mb=round(kv_mb, 1), weights_mb=round(weights_mb, 1),
        required_mb=round(required, 1), available_mb=round(available, 1), risk=risk, message=messages[risk],
    )
    return result

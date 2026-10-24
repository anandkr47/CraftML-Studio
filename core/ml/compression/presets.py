"""
Compression methods and target-device presets (pure data, no ML imports).
"""

from typing import Any, Dict, List, Optional

# Approximate bits per weight, used for size estimates relative to a 16-bit source.
GGUF_QUANTS: Dict[str, Dict[str, Any]] = {
    "Q8_0": {"bits": 8.5, "ftype": 7, "note": "Near-lossless"},
    "Q6_K": {"bits": 6.6, "ftype": 18, "note": "Very high quality"},
    "Q5_K_M": {"bits": 5.7, "ftype": 17, "note": "High quality"},
    "Q4_K_M": {"bits": 4.85, "ftype": 15, "note": "Best size/quality balance"},
    "Q4_0": {"bits": 4.5, "ftype": 2, "note": "Small and fast"},
    "Q3_K_M": {"bits": 3.9, "ftype": 12, "note": "Very small, some quality loss"},
    "Q2_K": {"bits": 2.6, "ftype": 10, "note": "Smallest, noticeable quality loss"},
}

METHODS: Dict[str, Dict[str, Any]] = {
    "gguf": {
        "label": "GGUF (llama.cpp)",
        "needs": "llama.cpp tooling",
        "runs_on": "CPU, Apple Silicon, any GPU",
        "bits": None,  # depends on the quantization type
    },
    "int4": {"label": "INT4 (bitsandbytes NF4)", "needs": "NVIDIA GPU", "runs_on": "NVIDIA GPU", "bits": 4.5},
    "int8": {"label": "INT8 (bitsandbytes)", "needs": "NVIDIA GPU", "runs_on": "NVIDIA GPU", "bits": 8.0},
    "gptq": {"label": "GPTQ 4-bit", "needs": "NVIDIA GPU + auto-gptq", "runs_on": "NVIDIA GPU", "bits": 4.2},
    "awq": {"label": "AWQ 4-bit", "needs": "NVIDIA GPU + autoawq", "runs_on": "NVIDIA GPU", "bits": 4.2},
}

PRESETS: List[Dict[str, Any]] = [
    {
        "id": "fit_8gb",
        "title": "Fit on 8 GB VRAM",
        "description": "4-bit weights for an 8 GB NVIDIA GPU. A 7B model shrinks to roughly 4 GB.",
        "method": "int4",
        "quantization": None,
        "target": "cuda",
    },
    {
        "id": "apple_cpu",
        "title": "Apple Silicon / CPU",
        "description": "GGUF Q4_K_M: the usual best balance for llama.cpp on Metal or CPU.",
        "method": "gguf",
        "quantization": "Q4_K_M",
        "target": "mps",
    },
    {
        "id": "edge",
        "title": "Edge device",
        "description": "GGUF Q3_K_M for phones, Raspberry Pi and other tight-memory targets.",
        "method": "gguf",
        "quantization": "Q3_K_M",
        "target": "cpu",
    },
    {
        "id": "quality",
        "title": "Max quality",
        "description": "GGUF Q8_0: roughly half the size of 16-bit with almost no quality loss.",
        "method": "gguf",
        "quantization": "Q8_0",
        "target": "any",
    },
]


def effective_bits(method: str, quantization: Optional[str] = None) -> float:
    if method == "gguf":
        return GGUF_QUANTS[quantization or "Q4_K_M"]["bits"]
    return METHODS[method]["bits"]


def estimate_size_mb(source_size_mb: float, method: str, quantization: Optional[str] = None) -> float:
    """Rough output size assuming the source stores 16-bit weights."""
    return round(source_size_mb * effective_bits(method, quantization) / 16.0, 1)


def validate_choice(method: str, quantization: Optional[str]) -> None:
    if method not in METHODS:
        raise ValueError(f"Unknown compression method '{method}'. Choose from: {', '.join(METHODS)}")
    if method == "gguf" and quantization and quantization not in GGUF_QUANTS:
        raise ValueError(f"Unknown GGUF quantization '{quantization}'. Choose from: {', '.join(GGUF_QUANTS)}")


def output_suffix(method: str, quantization: Optional[str] = None) -> str:
    return (quantization or "Q4_K_M").lower() if method == "gguf" else method


def recommended_preset(device_type: str, vram_gb: float) -> str:
    """Preset id that suits the detected hardware."""
    if device_type == "cuda" and vram_gb and vram_gb <= 12:
        return "fit_8gb"
    if device_type == "cuda":
        return "quality"
    return "apple_cpu"

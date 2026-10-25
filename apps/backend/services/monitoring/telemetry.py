"""
Low-overhead system telemetry: CPU, RAM and GPU (NVIDIA via NVML, Apple Silicon unified memory).

``sample()`` never blocks: CPU usage is measured since the previous call.  Samples are
also kept in a short in-memory history (for sparklines).
"""

import platform
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

import psutil

HISTORY_SECONDS = 120

_history: Deque[Dict[str, Any]] = deque(maxlen=HISTORY_SECONDS)
_history_lock = threading.Lock()
_nvml_state: Dict[str, Any] = {"tried": False, "ok": False}

psutil.cpu_percent(interval=None)  # prime the counter so the first sample is meaningful


def _nvml():
    """Initialise NVML once; returns the module or None when unavailable."""
    if not _nvml_state["tried"]:
        _nvml_state["tried"] = True
        try:
            import pynvml

            pynvml.nvmlInit()
            _nvml_state.update(ok=True, module=pynvml)
        except Exception:  # noqa: BLE001 - no NVIDIA driver / library
            pass
    return _nvml_state.get("module") if _nvml_state["ok"] else None


def _nvidia_gpu() -> Optional[Dict[str, Any]]:
    nvml = _nvml()
    if nvml is None:
        return None
    try:
        handle = nvml.nvmlDeviceGetHandleByIndex(0)
        mem = nvml.nvmlDeviceGetMemoryInfo(handle)
        util = nvml.nvmlDeviceGetUtilizationRates(handle)
        name = nvml.nvmlDeviceGetName(handle)
        try:
            temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
        except Exception:  # noqa: BLE001
            temp = None
        return {
            "kind": "nvidia",
            "name": name.decode() if isinstance(name, bytes) else name,
            "util_percent": float(util.gpu),
            "vram_total_mb": mem.total / 1024 ** 2,
            "vram_used_mb": mem.used / 1024 ** 2,
            "temperature_c": temp,
        }
    except Exception:  # noqa: BLE001
        return None


def _apple_gpu(ram_total_mb: float, ram_used_mb: float) -> Optional[Dict[str, Any]]:
    """Apple Silicon shares system memory with the GPU; macOS exposes no unprivileged GPU load."""
    if not (platform.system() == "Darwin" and platform.machine() == "arm64"):
        return None
    allocated_mb = None
    try:
        import torch

        if torch.backends.mps.is_available():
            allocated_mb = torch.mps.current_allocated_memory() / 1024 ** 2
    except Exception:  # noqa: BLE001
        pass
    return {
        "kind": "apple",
        "name": "Apple Silicon (unified memory)",
        "util_percent": None,
        "vram_total_mb": ram_total_mb,
        "vram_used_mb": ram_used_mb,
        "app_gpu_mb": allocated_mb,
        "temperature_c": None,
    }


def sample() -> Dict[str, Any]:
    """Current CPU / RAM / GPU readings (non-blocking)."""
    vm = psutil.virtual_memory()
    ram_total_mb, ram_used_mb = vm.total / 1024 ** 2, (vm.total - vm.available) / 1024 ** 2

    gpu = _nvidia_gpu() or _apple_gpu(ram_total_mb, ram_used_mb)
    if gpu:
        gpu["vram_percent"] = round(100 * gpu["vram_used_mb"] / gpu["vram_total_mb"], 1) if gpu["vram_total_mb"] else 0.0

    reading = {
        "timestamp": time.time(),
        "cpu": {"percent": psutil.cpu_percent(interval=None), "count": psutil.cpu_count(logical=True)},
        "memory": {
            "total_mb": round(ram_total_mb, 1),
            "used_mb": round(ram_used_mb, 1),
            "percent": round(vm.percent, 1),
        },
        "gpu": gpu,
        "process_rss_mb": round(psutil.Process().memory_info().rss / 1024 ** 2, 1),
    }

    with _history_lock:
        if not _history or reading["timestamp"] - _history[-1]["timestamp"] >= 0.9:
            _history.append(reading)
    return reading


def history(limit: int = HISTORY_SECONDS) -> List[Dict[str, Any]]:
    with _history_lock:
        return list(_history)[-limit:]

"""
Compression Service
Quantizes a local model (INT8/INT4, GPTQ, AWQ or GGUF) as a background job and,
optionally, benchmarks the original and compressed models for a before/after report.

Results are written under the models directory, so they show up in Chat,
Deploy and the Hugging Face export like any other local model.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import settings
from core.ml.compression import merge_lora_adapter, presets, quantize_model
from core.ml.compression.gguf import convert_to_gguf
from core.ml.training import hardware_detector
from core.utils import setup_logger
from services import inference, jobs
from services.benchmark import benchmark_model, build_report

logger = setup_logger("compression_service", log_file=str(settings.logs_dir / "compression_service.log"))

JOB_TYPE = "compress"


def _size_mb(path: Path) -> float:
    files = [path] if path.is_file() else [f for f in path.rglob("*") if f.is_file()]
    return round(sum(f.stat().st_size for f in files) / 1024 ** 2, 2)


def list_presets(model_id: Optional[str] = None) -> Dict[str, Any]:
    """Presets with size estimates for ``model_id`` and the one suited to this hardware."""
    source_mb: Optional[float] = None
    if model_id:
        try:
            source_mb = inference.resolve_model(model_id).size_mb
        except inference.InferenceError:
            source_mb = None

    device = hardware_detector.device_info
    items = []
    for preset in presets.PRESETS:
        entry = dict(preset)
        if source_mb:
            entry["estimated_size_mb"] = presets.estimate_size_mb(source_mb, preset["method"], preset["quantization"])
        items.append(entry)

    return {
        "presets": items,
        "recommended": presets.recommended_preset(device["device_type"], device["total_vram_gb"]),
        "hardware": {k: device[k] for k in ("device_type", "device_name", "total_vram_gb")},
        "methods": presets.METHODS,
        "gguf_quantizations": presets.GGUF_QUANTS,
    }


def start_compression(params: Dict[str, Any]) -> str:
    """
    Start a compression job.

    Args:
        params: model_id (a local model), method (gguf/int4/int8/gptq/awq),
            quantization (GGUF type, e.g. Q4_K_M), benchmark (bool, default True).

    Returns:
        job_id
    """
    model_id = params.get("model_id")
    method = params.get("method", "gguf")
    quantization = params.get("quantization") or ("Q4_K_M" if method == "gguf" else None)
    run_benchmark = params.get("benchmark", True)

    if not model_id:
        raise ValueError("model_id is required")
    presets.validate_choice(method, quantization)

    info = inference.resolve_model(model_id)
    if info.kind not in ("full", "lora"):
        raise ValueError("Only Hugging Face-format models and LoRA adapters can be compressed")

    name = f"{info.id}-{presets.output_suffix(method, quantization)}"
    out_dir = Path(settings.models_dir) / name
    if out_dir.exists():
        raise ValueError(f"'{name}' already exists. Delete it first or choose another method.")

    job_id = jobs.create(
        JOB_TYPE,
        {"model_id": model_id, "method": method, "quantization": quantization,
         "benchmark": run_benchmark, "output_id": name},
    )

    def log(message: str) -> None:
        jobs.append_log(job_id, message)

    logger.info(f"Starting compression job {job_id}: {model_id} -> {name}")

    def run() -> Dict[str, Any]:
        work_dir = Path(settings.models_dir) / f".tmp-{job_id}"
        try:
            source_dir = info.path
            if info.kind == "lora":
                log("Merging the LoRA adapter into its base model…")
                source_dir = merge_lora_adapter(info.path, str(work_dir / "merged"))

            label = presets.METHODS[method]["label"] + (f" ({quantization})" if method == "gguf" else "")
            log(f"Compressing with {label}…")
            if method == "gguf":
                output = out_dir / f"{name}.gguf"
                convert_to_gguf(source_dir, str(output), quantization, log=log)
                output_kind = "gguf"
            else:
                out_dir.mkdir(parents=True)
                quantize_model(source_dir, str(out_dir), method)
                output, output_kind = out_dir, "full"
            log(f"Saved {name} ({_size_mb(output)} MB)")

            before = {"size_mb": _size_mb(Path(source_dir))}
            after = {"size_mb": _size_mb(output)}
            if run_benchmark:
                try:
                    log("Benchmarking the original model…")
                    before.update(benchmark_model(source_dir, "full"))
                    log("Benchmarking the compressed model…")
                    after.update(benchmark_model(str(output), output_kind))
                except Exception as exc:  # noqa: BLE001 - the compressed model is still valid
                    log(f"Benchmark skipped: {exc}")

            report = build_report(before, after)
            report.update(
                model_id=model_id, output_id=name, output_path=str(output),
                method=method, quantization=quantization,
            )
            return report
        except BaseException:
            shutil.rmtree(out_dir, ignore_errors=True)  # don't leave a half-written model behind
            raise
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    jobs.run_in_thread(job_id, run)
    return job_id


def get_status(job_id: str) -> Dict[str, Any]:
    job = jobs.get(job_id)
    if not job or job["job_type"] != JOB_TYPE:
        return {"job_id": job_id, "status": "not_found", "error": "Job not found"}

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "started_at": job["started_at"] or job["created_at"],
        "completed_at": job["completed_at"],
        "params": job["params"],
        "result": job["result"],
        "error": job["error"],
    }


def list_jobs() -> Dict[str, Any]:
    return {
        "jobs": [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "started_at": job["started_at"] or job["created_at"],
                "model_id": job["params"].get("model_id"),
                "output_id": job["params"].get("output_id"),
                "method": job["params"].get("method"),
                "quantization": job["params"].get("quantization"),
            }
            for job in jobs.list_jobs(job_type=JOB_TYPE, limit=1000)
        ]
    }

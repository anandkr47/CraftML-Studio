"""
Compression Service
Handles model compression jobs using core ML modules
"""

from typing import Any, Dict

from core.ml.compression import quantize_model
from core.utils import setup_logger
from core.config import settings
from services import jobs

logger = setup_logger("compression_service", log_file=str(settings.logs_dir / "compression_service.log"))

JOB_TYPE = "compress"


def start_compression(params: Dict[str, Any]) -> str:
    """
    Start a compression job on a background thread.

    Args:
        params: Compression parameters including:
            - model_path: Path to model to compress
            - output_path: Where to save compressed model
            - method: Compression method (int8, int4, gptq)
            - options: Method-specific options

    Returns:
        job_id: Unique job identifier
    """
    model_path = params.get("model_path")
    output_path = params.get("output_path")
    method = params.get("method", "int4")
    options = params.get("options") or {}

    if not model_path:
        raise ValueError("model_path is required")
    if not output_path:
        raise ValueError("output_path is required")
    if method not in ("int8", "int4", "gptq"):
        raise ValueError(f"Unknown compression method: {method}")

    job_id = jobs.create(JOB_TYPE, params)
    logger.info(f"Starting compression job {job_id} with params: {params}")

    def run() -> Dict[str, Any]:
        jobs.append_log(job_id, f"Compressing {model_path} using {method}")
        result = quantize_model(
            model_path=model_path,
            output_path=output_path,
            method=method,
            **options,
        )
        jobs.append_log(job_id, f"Compressed model saved to {output_path}")
        return result

    jobs.run_in_thread(job_id, run)
    return job_id


def get_status(job_id: str) -> Dict[str, Any]:
    """Get compression job status."""
    job = jobs.get(job_id)
    if not job:
        return {"job_id": job_id, "status": "not_found", "error": "Job not found"}

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "started_at": job["started_at"] or job["created_at"],
        "completed_at": job["completed_at"],
        "method": job["params"].get("method"),
        "result": job["result"],
        "error": job["error"],
    }


def compare_models(model_a_path: str, model_b_path: str) -> Dict[str, Any]:
    """
    Compare two models (original vs compressed)
    
    Args:
        model_a_path: Path to first model
        model_b_path: Path to second model
        
    Returns:
        Comparison results
    """
    from core.ml.utils import calculate_model_size
    import torch
    from transformers import AutoModelForCausalLM
    
    try:
        logger.info(f"Comparing models: {model_a_path} vs {model_b_path}")
        
        # Load models
        model_a = AutoModelForCausalLM.from_pretrained(model_a_path)
        model_b = AutoModelForCausalLM.from_pretrained(model_b_path)
        
        # Calculate sizes
        size_a = calculate_model_size(model_a)
        size_b = calculate_model_size(model_b)
        
        # Calculate compression ratio
        compression_ratio = size_a["total_memory_mb"] / size_b["total_memory_mb"]
        
        return {
            "model_a": {
                "path": model_a_path,
                "total_params": size_a["total_params"],
                "trainable_params": size_a["trainable_params"],
                "size_mb": size_a["total_memory_mb"]
            },
            "model_b": {
                "path": model_b_path,
                "total_params": size_b["total_params"],
                "trainable_params": size_b["trainable_params"],
                "size_mb": size_b["total_memory_mb"]
            },
            "compression_ratio": f"{compression_ratio:.2f}x",
            "size_reduction_mb": size_a["total_memory_mb"] - size_b["total_memory_mb"],
            "size_reduction_percent": ((size_a["total_memory_mb"] - size_b["total_memory_mb"]) / size_a["total_memory_mb"]) * 100
        }
        
    except Exception as e:
        logger.error(f"Model comparison failed: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }


def list_jobs() -> Dict[str, Any]:
    """List all compression jobs."""
    return {
        "jobs": [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "started_at": job["started_at"] or job["created_at"],
                "method": job["params"].get("method"),
            }
            for job in jobs.list_jobs(job_type=JOB_TYPE, limit=1000)
        ]
    }

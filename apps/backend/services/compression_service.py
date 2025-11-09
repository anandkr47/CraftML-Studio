"""
Compression Service
Handles model compression jobs using core ML modules
"""

import sys
from pathlib import Path
import uuid
import logging
from typing import Dict, Any, Literal
from datetime import datetime

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.ml.compression import quantize_model, prune_model, distill_model
from core.utils import setup_logger

logger = setup_logger("compression_service", log_file="logs/compression_service.log")

# In-memory job storage
active_jobs: Dict[str, Dict[str, Any]] = {}


def start_compression(params: Dict[str, Any]) -> str:
    """
    Start a new compression job
    
    Args:
        params: Compression parameters including:
            - model_path: Path to model to compress
            - output_path: Where to save compressed model
            - method: Compression method (int8, int4, gptq, pruning, distillation)
            - options: Method-specific options
            
    Returns:
        job_id: Unique job identifier
    """
    job_id = f"compress_{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Starting compression job {job_id} with params: {params}")
    
    # Validate parameters
    model_path = params.get("model_path")
    output_path = params.get("output_path")
    method = params.get("method", "int4")
    options = params.get("options", {})
    
    if not model_path:
        raise ValueError("model_path is required")
    if not output_path:
        raise ValueError("output_path is required")
    
    # Store job info
    active_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "params": params,
        "started_at": datetime.now().isoformat(),
        "method": method
    }
    
    # Start compression in background
    try:
        active_jobs[job_id]["status"] = "running"
        
        logger.info(f"Compressing model from {model_path} using {method}")
        
        if method in ["int8", "int4", "gptq"]:
            # Quantization
            result = quantize_model(
                model_path=model_path,
                output_path=output_path,
                method=method,
                **options
            )
        elif method == "pruning":
            # Pruning - load model, apply pruning, save
            logger.info(f"Applying pruning to model at {model_path}")
            
            from transformers import AutoModelForCausalLM
            import torch
            
            # Load model
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="auto"
            )
            
            # Apply pruning
            pruning_amount = options.get("amount", 0.3)
            pruning_type = options.get("type", "magnitude")
            
            result = prune_model(
                model=model,
                method=pruning_type,
                amount=pruning_amount
            )
            
            # Save pruned model
            model.save_pretrained(output_path)
            
            # Also save tokenizer
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            tokenizer.save_pretrained(output_path)
            
            result["output_path"] = output_path
            result["model_path"] = model_path
            
            logger.info(f"Pruned model saved to {output_path}")
            
        elif method == "distillation":
            # Distillation - requires teacher, student, and dataset
            logger.info("Starting knowledge distillation")
            
            teacher_path = options.get("teacher_model", model_path)
            student_path = options.get("student_model")
            dataset_path = options.get("dataset_path")
            
            if not student_path:
                raise ValueError("student_model is required for distillation")
            if not dataset_path:
                raise ValueError("dataset_path is required for distillation")
            
            result = distill_model(
                teacher_model_path=teacher_path,
                student_model_path=student_path,
                train_dataset=dataset_path,
                output_path=output_path,
                temperature=options.get("temperature", 2.0),
                alpha=options.get("alpha", 0.7),
                num_epochs=options.get("num_epochs", 3),
                learning_rate=options.get("learning_rate", 5e-5),
                batch_size=options.get("batch_size", 4),
                max_length=options.get("max_length", 512)
            )
            
            logger.info("Distillation completed")
            
        else:
            raise ValueError(f"Unknown compression method: {method}")
        
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        active_jobs[job_id]["result"] = result
        
        logger.info(f"Compression job {job_id} completed")
        
    except Exception as e:
        logger.error(f"Compression job {job_id} failed: {e}")
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
    
    return job_id


def get_status(job_id: str) -> Dict[str, Any]:
    """
    Get compression job status
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status information
    """
    if job_id not in active_jobs:
        return {
            "job_id": job_id,
            "status": "not_found",
            "error": "Job not found"
        }
    
    return active_jobs[job_id]


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
    """
    List all compression jobs
    
    Returns:
        List of jobs with summary information
    """
    jobs = []
    
    for job_id, job_data in active_jobs.items():
        jobs.append({
            "job_id": job_id,
            "status": job_data.get("status"),
            "started_at": job_data.get("started_at"),
            "method": job_data.get("method"),
        })
    
    return {"jobs": jobs}

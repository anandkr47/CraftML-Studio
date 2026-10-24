"""
Training Service
Runs LoRA / QLoRA fine-tuning jobs and records them in the unified job store.
"""

from pathlib import Path
import json
from typing import Any, Dict, Optional

from core.config import settings
from core.utils import setup_logger
from db.models import Dataset, SessionLocal
from services import jobs
from services.training.efficient_trainer import start_efficient_training

logger = setup_logger("training_service", log_file=str(settings.logs_dir / "training_service.log"))

JOB_TYPE = "finetune"
PROGRESS_KEYS = ("current_epoch", "total_epochs", "current_step", "total_steps")
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_dataset_path(params: Dict[str, Any]) -> None:
    """Resolve ``dataset_id`` to a file path and make relative paths absolute."""
    if "dataset_id" in params and not params.get("dataset_path"):
        with SessionLocal() as session:
            dataset = session.query(Dataset).filter(Dataset.id == params["dataset_id"]).first()
        if dataset:
            params["dataset_path"] = dataset.file_path
            logger.info(f"Resolved dataset_id {params['dataset_id']} to {dataset.file_path}")
        else:
            raise ValueError(f"Dataset {params['dataset_id']} not found")

    dataset_path = params.get("dataset_path")
    if dataset_path and not Path(dataset_path).is_absolute():
        params["dataset_path"] = str(PROJECT_ROOT / dataset_path)


def _add_log(job_id: str, message: str) -> None:
    """
    Trainer log callback.

    Messages of the form ``STATUS:<status>[:<error>]`` update the job status;
    everything else is appended to the job log.
    """
    if message.startswith("STATUS:"):
        _, status, *rest = message.split(":", 2)
        jobs.update(job_id, status=status, error=rest[0] if rest else None)
        return

    jobs.append_log(job_id, message)
    logger.info(f"Job {job_id}: {message}")


def update_progress(
    job_id: str,
    current_epoch: int,
    total_epochs: int,
    current_step: int,
    total_steps: int,
    loss: float,
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    """Trainer progress callback."""
    progress = {
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "current_step": current_step,
        "total_steps": total_steps,
        "loss": loss,
    }
    if metrics:
        progress["metrics"] = metrics
    jobs.update(job_id, progress=progress)
    _add_log(
        job_id,
        f"Epoch {current_epoch}/{total_epochs}, "
        f"Step {current_step}/{total_steps}, Loss: {loss:.4f}",
    )


def start_training(params: Dict[str, Any]) -> str:
    """
    Start a fine-tuning job.

    Args:
        params: model_name, dataset_path or dataset_id, training_method
            (qlora/lora/full), lora_config, training_config, output_dir.

    Returns:
        job_id
    """
    if not params.get("model_name"):
        raise ValueError("model_name is required for fine-tuning")

    _resolve_dataset_path(params)
    if not params.get("dataset_path"):
        raise ValueError("dataset_path is required for training")

    job_id = jobs.create(JOB_TYPE, params, status="running")
    logger.info(f"Starting training job {job_id} with params: {params}")

    training_method = (params.get("training_method") or "qlora").lower()
    output_dir = params.get("output_dir") or str(settings.models_dir / job_id)

    _add_log(job_id, f"[START] Training job {job_id} started")
    _add_log(job_id, f"Model: {params['model_name']}")
    _add_log(job_id, f"Dataset: {params['dataset_path']}")
    _add_log(job_id, f"Training method: {training_method.upper()}")
    _add_log(job_id, f"Output directory: {output_dir}")

    def run() -> Dict[str, Any]:
        result = start_efficient_training(
            job_id=job_id,
            model_name=params["model_name"],
            dataset_path=params["dataset_path"],
            output_dir=output_dir,
            training_method=training_method,
            lora_config=params.get("lora_config"),
            training_config=params.get("training_config") or {},
            progress_callback=update_progress,
            log_callback=_add_log,
            should_cancel=lambda: jobs.should_cancel(job_id),
            run_async=False,
        )
        if result.get("status") == "failed":
            raise RuntimeError(result.get("error", "Training failed"))
        return {"output_dir": result.get("output_dir", output_dir)}

    jobs.run_in_thread(job_id, run)
    return job_id


def stop_training(job_id: str) -> bool:
    """Request cancellation of a running job."""
    job = jobs.get(job_id)
    if not job or job["status"] not in ("pending", "running"):
        return False

    jobs.request_cancel(job_id)
    jobs.append_log(job_id, "[STOP] Cancellation requested - stopping training...")
    jobs.update(job_id, status="stopped")
    return True


def delete_training_job(job_id: str) -> bool:
    """Delete a finished job (running jobs must be stopped first)."""
    return jobs.delete(job_id)


def get_status(job_id: str) -> Dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        return {"job_id": job_id, "status": "not_found", "error": "Job not found"}

    progress = job["progress"]
    if not progress or not all(k in progress for k in PROGRESS_KEYS):
        progress = None

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "started_at": job["started_at"] or job["created_at"],
        "completed_at": job["completed_at"],
        "progress": progress,
        "params": job["params"],
        "metrics": (job["progress"] or {}).get("metrics"),
        "error": job["error"],
    }


def get_logs(job_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    return jobs.get_logs(job_id, limit=limit, offset=offset)


def list_jobs() -> Dict[str, Any]:
    summaries = []
    for job in jobs.list_jobs(job_type=JOB_TYPE, limit=1000):
        params = job["params"]
        progress = job["progress"] or {}
        model_name = params.get("model_name")
        summaries.append({
            "job_id": job["job_id"],
            "status": job["status"],
            "started_at": job["started_at"] or job["created_at"],
            "completed_at": job["completed_at"],
            "base_model": model_name,
            "model_name": model_name,
            "dataset_id": params.get("dataset_id", 0),
            "progress": json.dumps(job["progress"]) if job["progress"] else None,
            "error": job["error"],
            "epochs": (params.get("training_config") or {}).get("num_epochs"),
            "current_epoch": progress.get("current_epoch", 0),
        })
    return {"jobs": summaries}


def get_job_counts() -> Dict[str, int]:
    found = jobs.counts(JOB_TYPE)
    return {
        "total": found["total"],
        "running": found["running"],
        "completed": found["completed"],
        "failed": found["failed"],
        "cancelled": found["stopped"],
        "pending": found["pending"],
    }

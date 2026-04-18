"""
Training Service
Handles model fine-tuning jobs using core ML modules
"""

import sys
from pathlib import Path
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.ml.training import start_lora_training
from core.utils import setup_logger
from core.config import settings
from db.models import SessionLocal, TrainingJob
from services.training import train_from_scratch
from services.training.efficient_trainer import start_efficient_training

logger = setup_logger("training_service", log_file=str(settings.logs_dir / "training_service.log"))

# In-memory job storage (replace with Redis in production)
active_jobs: Dict[str, Dict[str, Any]] = {}
job_logs: Dict[str, list] = {}
# Track training threads and cancellation flags
training_threads: Dict[str, Any] = {}  # job_id -> thread object
cancellation_flags: Dict[str, bool] = {}  # job_id -> should_cancel flag


def should_cancel_job(job_id: str) -> bool:
    """Check if a job should be cancelled"""
    return cancellation_flags.get(job_id, False)


def start_training(params: Dict[str, Any]) -> str:
    """
    Start a new training job
    
    Args:
        params: Training parameters including:
            - model_name: Base model to fine-tune
            - dataset_path: Path to training dataset (or dataset_id)
            - output_dir: Where to save the model (optional)
            - lora_config: LoRA hyperparameters (optional)
            - training_config: Training hyperparameters (optional)
            
    Returns:
        job_id: Unique job identifier
    """
    import json
    job_id = f"train_{uuid.uuid4().hex[:8]}"
    
    # Handle dataset_id vs dataset_path
    if 'dataset_id' in params and 'dataset_path' not in params:
        # Convert dataset_id to path
        from db.models import Dataset
        session = SessionLocal()
        try:
            dataset = session.query(Dataset).filter(Dataset.id == params['dataset_id']).first()
            if dataset:
                params['dataset_path'] = dataset.file_path
                logger.info(f"Resolved dataset_id {params['dataset_id']} to path: {dataset.file_path}")
            else:
                logger.warning(f"Dataset ID {params['dataset_id']} not found, using as-is")
                params['dataset_path'] = f"dataset_{params['dataset_id']}.jsonl"
        except Exception as e:
            logger.error(f"Error resolving dataset: {e}")
            params['dataset_path'] = f"dataset_{params.get('dataset_id', 'unknown')}.jsonl"
        finally:
            session.close()
    
    logger.info(f"Starting training job {job_id} with params: {params}")
    
    # Create job record in database FIRST (like Docker)
    session = SessionLocal()
    try:
        job = TrainingJob(
            job_id=job_id,
            status="running",  # ✅ Set to running immediately like Docker
            params=json.dumps(params),  # ✅ Store as JSON
            created_at=datetime.now()
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        logger.info(f"[OK] Job {job_id} created in DB with status 'running'")
    except Exception as e:
        logger.error(f"Failed to create job record: {e}")
        session.rollback()
        raise
    finally:
        session.close()
    
    # Store job in memory for faster access
    active_jobs[job_id] = {
        "job_id": job_id,
        "status": "running",  # ✅ Match DB status
        "params": params,
        "started_at": datetime.now().isoformat(),
        "progress": {
            "current_epoch": 0,
            "total_epochs": params.get("training_config", {}).get("num_epochs", 3),
            "current_step": 0,
            "total_steps": 0,
            "loss": None,
        },
        "metrics": {}
    }
    job_logs[job_id] = []
    
    # Initialize cancellation flag
    cancellation_flags[job_id] = False
    
    # Start training in background thread (like Docker)
    try:
        _add_log(job_id, f"[START] Training job {job_id} started")
        
        # Check if training from scratch
        train_from_scratch_flag = params.get('train_from_scratch', False)
        
        if train_from_scratch_flag:
            # Training from scratch
            import threading
            model_type = params.get('model_type')
            _add_log(job_id, f"Training {model_type} from scratch")
            _add_log(job_id, f"Dataset: {params.get('dataset_path', 'unknown')}")
            logger.info(f"Initiating scratch training for job {job_id}")
            _add_log(job_id, "Initializing model from scratch...")

            def _run_scratch():
                try:
                    # Handle None or empty string for output_dir
                    output_dir = params.get('output_dir') or str(settings.models_dir / job_id)
                    _add_log(job_id, f"Output directory: {output_dir}")
                    
                    # Resolve dataset path relative to project root
                    dataset_path = params['dataset_path']
                    if not Path(dataset_path).is_absolute():
                        # Get project root (4 levels up from this file)
                        project_root = Path(__file__).parent.parent.parent.parent
                        dataset_path = str(project_root / dataset_path)
                    _add_log(job_id, f"Resolved dataset path: {dataset_path}")
                    
                    result = train_from_scratch(
                        model_type=model_type,
                        dataset_path=dataset_path,
                        output_dir=output_dir,
                        config={
                            **(params.get('training_config') or {}),
                            'vocab_size': params.get('vocab_size', 32000),
                            'hidden_size': params.get('hidden_size', 768),
                            'num_layers': params.get('num_layers', 12),
                            'num_heads': params.get('num_heads', 12),
                            # Provide sensible faster defaults for scratch
                            'num_epochs': (params.get('training_config') or {}).get('num_epochs', 2),
                            'batch_size': (params.get('training_config') or {}).get('batch_size', 4),
                            'learning_rate': (params.get('training_config') or {}).get('learning_rate', 5e-4),
                            'logging_steps': (params.get('training_config') or {}).get('logging_steps', 20),
                        },
                        progress_callback=lambda **kwargs: update_progress(job_id, **kwargs),
                        log_callback=lambda msg: _add_log(job_id, msg)
                    )
                    if result.get('success'):
                        _add_log(job_id, "STATUS:completed")
                        _add_log(job_id, "[OK] Scratch model saved successfully")
                        _add_log(job_id, f"Model saved to: {output_dir}")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        _add_log(job_id, f"STATUS:failed:{error_msg}")
                        logger.error(f"Scratch training failed for {job_id}: {error_msg}")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Scratch training failed for {job_id}: {error_msg}", exc_info=True)
                    _add_log(job_id, f"STATUS:failed:{error_msg}")

            thread = threading.Thread(target=_run_scratch, daemon=False)
            thread.start()
            
        else:
            # Fine-tuning pretrained model with selected method (QLoRA/LoRA/Full)
            training_method = params.get('training_method', 'qlora').lower()
            model_name = params.get('model_name')
            dataset_path = params.get('dataset_path')
            
            # Validate required parameters
            if not model_name:
                error_msg = "model_name is required for fine-tuning"
                _add_log(job_id, f"ERROR: {error_msg}")
                _add_log(job_id, f"STATUS:failed:{error_msg}")
                logger.error(f"Job {job_id} failed: {error_msg}")
                return job_id
            
            if not dataset_path:
                error_msg = "dataset_path is required for training"
                _add_log(job_id, f"ERROR: {error_msg}")
                _add_log(job_id, f"STATUS:failed:{error_msg}")
                logger.error(f"Job {job_id} failed: {error_msg}")
                return job_id
            
            _add_log(job_id, f"Model: {model_name}")
            _add_log(job_id, f"Dataset: {dataset_path}")
            _add_log(job_id, f"Training method: {training_method.upper()}")
            logger.info(f"Initiating {training_method.upper()} training for job {job_id}")
            
            # Method-specific logging
            if training_method == 'qlora':
                _add_log(job_id, "✨ Initializing QLoRA (4-bit quantization + LoRA adapters)...")
                _add_log(job_id, "⚡ Expected training time: ~2-5 epochs (fastest method)")
            elif training_method == 'lora':
                _add_log(job_id, "✨ Initializing LoRA (Low-Rank Adaptation)...")
                _add_log(job_id, "⚡ Expected training time: ~3-5 epochs (fast method)")
            else:
                _add_log(job_id, "✨ Initializing Full Fine-tuning (all parameters trainable)...")
                _add_log(job_id, "⚡ Expected training time: ~5-10 epochs (thorough method)")
            
            # Prepare training config with method-specific defaults
            training_config = params.get('training_config', {})
            if not training_config:
                training_config = {}
            
            # Resolve dataset path relative to project root
            if not Path(dataset_path).is_absolute():
                # Get project root (4 levels up from this file)
                project_root = Path(__file__).parent.parent.parent.parent
                dataset_path = str(project_root / dataset_path)
            _add_log(job_id, f"Resolved dataset path: {dataset_path}")
            
            # Prepare output directory (handle None or empty string)
            output_dir = params.get('output_dir') or str(settings.models_dir / job_id)
            _add_log(job_id, f"Output directory: {output_dir}")
            
            # Debug logging
            logger.info(f"Starting efficient training with: model_name={model_name}, dataset_path={dataset_path}, output_dir={output_dir}")
            _add_log(job_id, f"Debug: model_name={model_name}, dataset_path={dataset_path}")
            
            # Start efficient training in background thread
            start_efficient_training(
                job_id=job_id,
                model_name=model_name,
                dataset_path=dataset_path,
                output_dir=output_dir,
                training_method=training_method,
                lora_config=params.get('lora_config'),
                training_config=training_config,
                progress_callback=update_progress,
                log_callback=_add_log,
                should_cancel=lambda: should_cancel_job(job_id),
                run_async=True,  # Run in background thread
            )
        
        _add_log(job_id, "[OK] Training started in background thread")
        active_jobs[job_id]["status"] = "running"
        
    except Exception as e:
        logger.error(f"Training job {job_id} failed: {e}")
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)
        _add_log(job_id, f"ERROR: {str(e)}")
    
    return job_id


def stop_training(job_id: str) -> bool:
    """
    Stop a running training job (like Docker stop)
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if stopped successfully
    """
    logger.info(f"[STOP] Stopping training job {job_id}")
    
    # Set cancellation flag FIRST so training loop can check it
    if job_id in cancellation_flags:
        cancellation_flags[job_id] = True
        logger.info(f"[OK] Cancellation flag set for job {job_id}")
        _add_log(job_id, "[STOP] Cancellation requested - stopping training...")
    
    # Update database
    session = SessionLocal()
    try:
        job = session.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found in DB")
            return False
            
        job.status = "stopped"
        job.completed_at = datetime.now()
        session.commit()
        logger.info(f"[OK] Job {job_id} marked as stopped in DB")
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
        session.rollback()
        return False
    finally:
        session.close()
    
    # Update memory
    if job_id in active_jobs:
        active_jobs[job_id]["status"] = "stopped"
        active_jobs[job_id]["stopped_at"] = datetime.now().isoformat()
    
    # Log completion
    _add_log(job_id, "[STOP] Training stopped by user")
    logger.info(f"[OK] Stop request completed for job {job_id}")
    
    return True


def delete_training_job(job_id: str) -> bool:
    """
    Delete a training job (like Docker rm)
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if deleted successfully
    """
    logger.info(f"[DELETE] Deleting training job {job_id}")
    
    # Delete from database
    session = SessionLocal()
    try:
        job = session.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found in DB")
            return False
        
        # Only allow deletion of stopped/completed/failed jobs
        if job.status == "running":
            logger.warning(f"Cannot delete running job {job_id}. Stop it first.")
            return False
            
        session.delete(job)
        session.commit()
        logger.info(f"[OK] Job {job_id} deleted from DB")
    except Exception as e:
        logger.error(f"Failed to delete job: {e}")
        session.rollback()
        return False
    finally:
        session.close()
    
    # Remove from memory
    if job_id in active_jobs:
        del active_jobs[job_id]
    if job_id in job_logs:
        del job_logs[job_id]
    
    return True


def get_status(job_id: str) -> Dict[str, Any]:
    """
    Get training job status (check DB first, like Docker inspect)
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status information
    """
    import json
    
    # Check database first (source of truth)
    session = SessionLocal()
    try:
        job = session.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
        if job:
            # Parse stored JSON
            try:
                params = json.loads(job.params) if isinstance(job.params, str) else {}
                progress_data = json.loads(job.progress) if job.progress and isinstance(job.progress, str) else {}
            except:
                params = {}
                progress_data = {}
            
            # Format progress correctly for Pydantic validation
            # If progress is empty or incomplete, use None instead of empty dict
            if progress_data and all(k in progress_data for k in ['current_epoch', 'total_epochs', 'current_step', 'total_steps']):
                progress = progress_data
            else:
                progress = None
            
            return {
                "job_id": job.job_id,
                "status": job.status,
                "started_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "progress": progress,
                "params": params,
                "error": job.error
            }
    except Exception as e:
        logger.error(f"Failed to get job status from DB: {e}")
    finally:
        session.close()
    
    # Fallback to memory (for backward compatibility)
    if job_id in active_jobs:
        return active_jobs[job_id]
    
    # Not found anywhere
    return {
        "job_id": job_id,
        "status": "not_found",
        "error": "Job not found"
    }


def get_logs(job_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    Get training logs for a job
    
    Args:
        job_id: Job identifier
        limit: Maximum number of log lines
        offset: Log offset
        
    Returns:
        Log lines and metadata
    """
    if job_id not in job_logs:
        return {
            "job_id": job_id,
            "logs": [],
            "total": 0
        }
    
    logs = job_logs[job_id]
    return {
        "job_id": job_id,
        "logs": logs[offset:offset + limit],
        "total": len(logs)
    }


def update_progress(
    job_id: str,
    current_epoch: int,
    total_epochs: int,
    current_step: int,
    total_steps: int,
    loss: float,
    metrics: Optional[Dict[str, Any]] = None
):
    """
    Update training progress (called by training worker)
    
    Args:
        job_id: Job identifier
        current_epoch: Current epoch number
        total_epochs: Total epochs
        current_step: Current step
        total_steps: Total steps
        loss: Current loss value
        metrics: Additional metrics
    """
    if job_id not in active_jobs:
        return
        
    active_jobs[job_id]["progress"] = {
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "current_step": current_step,
        "total_steps": total_steps,
        "loss": loss,
    }
    
    if metrics:
        active_jobs[job_id]["metrics"] = metrics
    
    # Update database (with error handling but don't block training)
    import json
    session = SessionLocal()
    try:
        job = session.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
        if job:
            job.progress = json.dumps({
                "current_epoch": current_epoch,
                "total_epochs": total_epochs,
                "current_step": current_step,
                "total_steps": total_steps,
                "loss": loss,
            })
            job.status = "running"
            session.commit()
        else:
            logger.warning(f"Job {job_id} not found in DB during progress update")
    except Exception as e:
        logger.error(f"Failed to update job progress in DB: {e}")
        session.rollback()
        # Don't stop training on DB errors, just log them
    finally:
        session.close()
    
    # Log progress
    _add_log(
        job_id,
        f"Epoch {current_epoch}/{total_epochs}, "
        f"Step {current_step}/{total_steps}, "
        f"Loss: {loss:.4f}"
    )


def _add_log(job_id: str, message: str):
    """Add a log message to job logs and handle status updates"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if this is a status update
    if message.startswith("STATUS:"):
        parts = message.split(":", 2)
        status = parts[1]
        error_msg = parts[2] if len(parts) > 2 else None
        
        # Update in-memory status first
        if job_id in active_jobs:
            active_jobs[job_id]["status"] = status
            if error_msg:
                active_jobs[job_id]["error"] = error_msg
            if status in ["completed", "failed"]:
                active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        
        # Update database with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            session = SessionLocal()
            try:
                job = session.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
                if job:
                    job.status = status
                    if status in ["completed", "failed", "stopped"]:
                        job.completed_at = datetime.now()
                    if error_msg:
                        job.error = error_msg
                    session.commit()
                    logger.info(f"[OK] Job {job_id} status updated to '{status}' in DB")
                    break  # Success
                else:
                    logger.warning(f"Job {job_id} not found in DB during status update")
                    break
            except Exception as e:
                logger.error(f"Failed to update job status in DB (attempt {attempt+1}/{max_retries}): {e}")
                session.rollback()
                if attempt == max_retries - 1:
                    logger.error(f"[ERROR] All retries failed for job {job_id}")
            finally:
                session.close()
        
        return  # Don't add status updates to logs
    
    # Regular log entry
    log_entry = f"[{timestamp}] {message}"
    
    if job_id not in job_logs:
        job_logs[job_id] = []
    
    job_logs[job_id].append(log_entry)
    logger.info(f"Job {job_id}: {message}")


def list_jobs() -> Dict[str, Any]:
    """
    List all training jobs from database and memory
    
    Returns:
        List of jobs with summary information
    """
    jobs = []
    
    # Load from database first
    session = SessionLocal()
    try:
        db_jobs = session.query(TrainingJob).order_by(TrainingJob.created_at.desc()).all()
        for db_job in db_jobs:
            # Parse params
            import json
            try:
                params = json.loads(db_job.params) if isinstance(db_job.params, str) else {}
            except:
                params = {}
            
            model_name = params.get("model_name")
            
            # Parse progress to get current_epoch
            current_epoch = 0
            try:
                if db_job.progress:
                    progress_data = json.loads(db_job.progress) if isinstance(db_job.progress, str) else {}
                    current_epoch = progress_data.get("current_epoch", 0)
            except:
                current_epoch = 0
            
            jobs.append({
                "job_id": db_job.job_id,
                "status": db_job.status,
                "started_at": db_job.created_at.isoformat() if db_job.created_at else None,
                "completed_at": db_job.completed_at.isoformat() if db_job.completed_at else None,
                "base_model": model_name,
                "model_name": model_name,  # Include both for compatibility
                "dataset_id": params.get("dataset_id", 0),
                "progress": db_job.progress,
                "error": db_job.error,
                "epochs": params.get("training_config", {}).get("num_epochs"),
                "current_epoch": current_epoch,  # Parsed from progress
            })
    except Exception as e:
        logger.error(f"Failed to load jobs from database: {e}")
    finally:
        session.close()
    
    # Add any in-memory jobs not in DB (shouldn't happen, but fallback)
    db_job_ids = {job["job_id"] for job in jobs}
    for job_id, job_data in active_jobs.items():
        if job_id not in db_job_ids:
            jobs.append({
                "job_id": job_id,
                "status": job_data.get("status"),
                "started_at": job_data.get("started_at"),
                "base_model": job_data.get("params", {}).get("model_name"),
            })
    
    return {"jobs": jobs}


def get_job_counts() -> Dict[str, int]:
    """
    Get job statistics
    
    Returns:
        Counts by status
    """
    counts = {
        "total": len(active_jobs),
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "pending": 0
    }
    
    for job_data in active_jobs.values():
        status = job_data.get("status", "unknown")
        if status in counts:
            counts[status] += 1
    
    return counts


def check_stalled_jobs(timeout_minutes: int = 60) -> list:
    """
    Check for jobs that might be stalled (no progress updates for timeout_minutes)
    
    Args:
        timeout_minutes: Minutes of no activity before considering a job stalled
        
    Returns:
        List of potentially stalled job IDs
    """
    from datetime import datetime, timedelta
    
    stalled_jobs = []
    timeout_threshold = datetime.now() - timedelta(minutes=timeout_minutes)
    
    session = SessionLocal()
    try:
        jobs = session.query(TrainingJob).filter(
            TrainingJob.status == "running"
        ).all()
        
        for job in jobs:
            # Check if job has been running too long without updates
            if job.created_at and job.created_at < timeout_threshold:
                # Check if there's been any progress updates
                if not job.progress or job.progress == "null":
                    stalled_jobs.append(job.job_id)
                    logger.warning(f"Job {job.job_id} appears stalled (no progress for {timeout_minutes}+ minutes)")
    except Exception as e:
        logger.error(f"Error checking for stalled jobs: {e}")
    finally:
        session.close()
    
    return stalled_jobs

"""
Training API Routes
Handles model fine-tuning endpoints with Pydantic validation
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from services import jobs as job_store
from services.training_service import (
    start_training,
    stop_training,
    delete_training_job,
    get_status,
    get_logs,
    list_jobs,
    get_job_counts
)
from models.requests import TrainingStartRequest
from models.responses import (
    JobResponse,
    TrainingStatusResponse,
    TrainingJobsResponse,
    TrainingJobCountsResponse,
    ErrorResponse
)

router = APIRouter()


@router.post("/start", response_model=JobResponse)
async def start_train(request: TrainingStartRequest, background_tasks: BackgroundTasks):
    """
    Start a new training job
    
    Args:
        request: Training configuration
        background_tasks: FastAPI background tasks
        
    Returns:
        Job ID and status
    """
    try:
        # Convert Pydantic model to dict
        params = request.dict()
        
        # Start training
        job_id = start_training(params)
        
        return JobResponse(
            job_id=job_id,
            status="running",  # Match DB status
            message="Training job created successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start training: {str(e)}")


@router.get("/status/{job_id}", response_model=TrainingStatusResponse)
async def train_status(job_id: str):
    """
    Get training job status
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status and progress information
    """
    try:
        status = get_status(job_id)
        
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return TrainingStatusResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{job_id}")
async def train_logs(job_id: str, limit: int = 100, offset: int = 0):
    """
    Get training logs for a job
    
    Args:
        job_id: Job identifier
        limit: Maximum number of log lines
        offset: Log offset
        
    Returns:
        Log lines and metadata
    """
    try:
        logs = get_logs(job_id, limit=limit, offset=offset)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=TrainingJobsResponse)
async def list_training_jobs():
    """
    List all training jobs
    
    Returns:
        List of training jobs
    """
    try:
        result = list_jobs()
        return TrainingJobsResponse(
            jobs=result.get("jobs", []),
            total=len(result.get("jobs", []))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{job_id}")
async def stop_train(job_id: str):
    """
    Stop a training job (like Docker stop)
    
    Args:
        job_id: Job identifier
        
    Returns:
        Success status
    """
    try:
        success = stop_training(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or already stopped")
        
        return {
            "stopped": True,
            "job_id": job_id,
            "message": "Training job stopped successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{job_id}")
async def delete_train(job_id: str):
    """
    Delete a training job (like Docker rm)
    Only works for stopped/completed/failed jobs
    
    Args:
        job_id: Job identifier
        
    Returns:
        Success status
    """
    try:
        success = delete_training_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete job {job_id}. It may be running or not found."
            )
        
        return {
            "deleted": True,
            "job_id": job_id,
            "message": "Training job deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job_counts", response_model=TrainingJobCountsResponse)
async def training_job_counts():
    """
    Get training job statistics
    
    Returns:
        Job counts by status
    """
    try:
        counts = get_job_counts()
        return TrainingJobCountsResponse(**counts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{job_id}")
async def train_metrics(job_id: str, after_step: int = -1):
    """Logged training steps (loss, learning rate, VRAM) with step > after_step."""
    if not job_store.get(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"job_id": job_id, "points": job_store.get_metrics(job_id, after_step)}

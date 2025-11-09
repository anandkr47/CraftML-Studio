"""
Compression API Routes
Handles model compression endpoints with Pydantic validation
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from services.compression_service import (
    start_compression,
    get_status,
    compare_models,
    list_jobs
)
from models.requests import CompressionStartRequest, ModelCompareRequest
from models.responses import (
    JobResponse,
    CompressionStatusResponse,
    ModelComparisonResponse
)

router = APIRouter()


@router.post("/start", response_model=JobResponse)
async def start_compress(request: CompressionStartRequest, background_tasks: BackgroundTasks):
    """
    Start a new compression job
    
    Args:
        request: Compression configuration
        background_tasks: FastAPI background tasks
        
    Returns:
        Job ID and status
    """
    try:
        # Convert Pydantic model to dict
        params = request.dict()
        
        # Start compression
        job_id = start_compression(params)
        
        return JobResponse(
            job_id=job_id,
            status="pending",
            message="Compression job started successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start compression: {str(e)}")


@router.get("/status/{job_id}", response_model=CompressionStatusResponse)
async def compress_status(job_id: str):
    """
    Get compression job status
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status and results
    """
    try:
        status = get_status(job_id)
        
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return CompressionStatusResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", response_model=ModelComparisonResponse)
async def compare_models_api(request: ModelCompareRequest):
    """
    Compare two models (original vs compressed)
    
    Args:
        request: Model paths to compare
        
    Returns:
        Comparison results
    """
    try:
        result = compare_models(request.model_a_path, request.model_b_path)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return ModelComparisonResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def list_compression_jobs():
    """
    List all compression jobs
    
    Returns:
        List of compression jobs
    """
    try:
        return list_jobs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
Crawler API Routes
Handles web crawling endpoints with Pydantic validation
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from services.crawler_service import (
    start_crawler,
    stop_crawler,
    get_status,
    get_preview,
    save_dataset,
    list_jobs
)
from models.requests import CrawlerStartRequest, CrawlerSaveRequest
from models.responses import (
    JobResponse,
    CrawlerStatusResponse,
    CrawlerPreviewResponse,
    ErrorResponse
)

router = APIRouter()


@router.post("/start", response_model=JobResponse)
async def start_crawl_task(request: CrawlerStartRequest, background_tasks: BackgroundTasks):
    """
    Start a new web crawling job
    
    Args:
        request: Crawler configuration
        background_tasks: FastAPI background tasks
        
    Returns:
        Job ID and status
    """
    try:
        # Convert Pydantic model to dict
        params = request.dict()
        
        # Start crawler
        job_id = start_crawler(params)
        
        return JobResponse(
            job_id=job_id,
            status="pending",
            message="Crawler job started successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start crawler: {str(e)}")


@router.get("/status/{job_id}", response_model=CrawlerStatusResponse)
async def crawl_status(job_id: str):
    """
    Get crawler job status
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status and progress
    """
    try:
        status = get_status(job_id)
        
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return CrawlerStatusResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview/{job_id}", response_model=CrawlerPreviewResponse)
async def crawl_preview(job_id: str, limit: int = 10):
    """
    Preview crawled data
    
    Args:
        job_id: Job identifier
        limit: Number of pages to preview
        
    Returns:
        Preview of crawled pages
    """
    try:
        preview = get_preview(job_id, limit=limit)
        return CrawlerPreviewResponse(**preview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{job_id}")
async def stop_crawl(job_id: str):
    """
    Stop a running crawler job
    
    Args:
        job_id: Job identifier
        
    Returns:
        Success status
    """
    try:
        success = stop_crawler(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return {
            "stopped": True,
            "job_id": job_id,
            "message": "Crawler job stopped successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_crawled_dataset(request: CrawlerSaveRequest):
    """
    Save crawled data as a dataset
    
    Args:
        request: Save configuration
        
    Returns:
        Saved dataset information
    """
    try:
        result = save_dataset(
            job_id=request.job_id,
            output_path=request.output_path,
            format_type=request.format_type
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def list_crawler_jobs():
    """
    List all crawler jobs
    
    Returns:
        List of crawler jobs
    """
    try:
        return list_jobs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

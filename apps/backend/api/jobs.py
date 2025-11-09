"""
Job History and Tracking API
Provides endpoints for viewing job history across all task types
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from services.job_tracker import job_tracker

router = APIRouter()


@router.get("/history")
async def get_job_history(
    job_type: Optional[str] = Query(None, description="Filter by job type (train, crawl, compress, deploy)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get job history with optional filters
    
    Args:
        job_type: Filter by job type
        status: Filter by status
        limit: Maximum results
        offset: Pagination offset
        
    Returns:
        List of jobs
    """
    try:
        jobs = job_tracker.list_jobs(
            job_type=job_type,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return {
            'jobs': jobs,
            'total': len(jobs),
            'limit': limit,
            'offset': offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_job_stats():
    """
    Get job statistics (counts by status and type)
    
    Returns:
        Job statistics
    """
    try:
        counts = job_tracker.get_job_counts()
        return counts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/counts")
async def get_job_counts():
    """
    Get job counts by status
    
    Returns:
        Job count statistics
    """
    try:
        counts = job_tracker.get_job_counts()
        return counts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    limit: int = Query(1000, ge=1, le=10000, description="Maximum log entries")
):
    """
    Get logs for a specific job
    
    Args:
        job_id: Job identifier
        limit: Maximum log entries
        
    Returns:
        Job logs
    """
    try:
        logs = job_tracker.get_logs(job_id, limit=limit)
        
        return {
            'job_id': job_id,
            'logs': logs,
            'total': len(logs)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
async def get_job_details(job_id: str):
    """
    Get detailed information about a specific job
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job details
    """
    try:
        job = job_tracker.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a job and its history
    
    Args:
        job_id: Job identifier
        
    Returns:
        Deletion confirmation
    """
    try:
        job = job_tracker.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job_tracker.delete_job(job_id)
        
        return {
            'status': 'success',
            'message': f'Job {job_id} deleted successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


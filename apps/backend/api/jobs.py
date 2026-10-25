"""
Job History API
Unified view over fine-tune, compress and deploy jobs.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from services import jobs

router = APIRouter()


@router.get("/history")
async def get_job_history(
    job_type: Optional[str] = Query(None, description="Filter by type (finetune, compress, deploy)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    found = jobs.list_jobs(job_type=job_type, status=status, limit=limit, offset=offset)
    return {"jobs": found, "total": len(found), "limit": limit, "offset": offset}


@router.get("/stats")
@router.get("/stats/counts")
async def get_job_stats(job_type: Optional[str] = Query(None)):
    return jobs.counts(job_type)


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    if not jobs.get(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return jobs.get_logs(job_id, limit=limit, offset=offset)


@router.get("/{job_id}")
async def get_job_details(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    if not jobs.get(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if not jobs.delete(job_id):
        raise HTTPException(status_code=400, detail="Running jobs must be stopped before deletion")
    return {"status": "success", "message": f"Job {job_id} deleted successfully"}

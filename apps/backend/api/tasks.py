"""
Task Orchestration API Routes
Provides unified interface for managing all Celery tasks
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
from tasks.task_manager import task_manager
from models.responses import ErrorResponse

router = APIRouter()


class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str
    state: str
    status: str
    info: dict
    result: Optional[dict] = None
    error: Optional[str] = None


class ActiveTasksResponse(BaseModel):
    """Active tasks response"""
    tasks: list
    total: int


class WorkerStatsResponse(BaseModel):
    """Worker statistics response"""
    workers: dict
    queues: dict
    total_workers: int
    total_active_tasks: int


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get status of a specific task
    
    Args:
        task_id: Celery task ID or job ID
        
    Returns:
        Task status information
    """
    try:
        status = task_manager.get_task_status(task_id)
        return TaskStatusResponse(**status)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a running task
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Cancellation confirmation
    """
    try:
        result = task_manager.cancel_task(task_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=ActiveTasksResponse)
async def list_active_tasks():
    """
    List all currently active tasks
    
    Returns:
        List of active tasks
    """
    try:
        tasks = task_manager.list_active_tasks()
        return ActiveTasksResponse(
            tasks=tasks,
            total=len(tasks)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers", response_model=WorkerStatsResponse)
async def get_worker_stats():
    """
    Get Celery worker statistics
    
    Returns:
        Worker statistics
    """
    try:
        stats = task_manager.get_worker_stats()
        return WorkerStatsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purge")
async def purge_tasks(queue_name: Optional[str] = None):
    """
    Purge pending tasks from queue
    
    Args:
        queue_name: Optional queue name (None = all queues)
        
    Returns:
        Number of tasks purged
    """
    try:
        count = task_manager.purge_queue(queue_name)
        return {
            'status': 'success',
            'purged': count,
            'message': f'Purged {count} tasks'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def task_system_health():
    """
    Check task system health
    
    Returns:
        Health status of Celery + Redis
    """
    try:
        # Check if workers are available
        stats = task_manager.get_worker_stats()
        
        workers_available = stats['total_workers'] > 0
        
        return {
            'status': 'healthy' if workers_available else 'degraded',
            'workers': stats['total_workers'],
            'active_tasks': stats['total_active_tasks'],
            'message': 'Task system is operational' if workers_available else 'No workers available'
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'message': 'Task system is not responding'
        }


"""
Monitoring API Routes
Handles system resource monitoring endpoints
"""

from fastapi import APIRouter, HTTPException
from services.monitoring.resource import (
    get_system_metrics,
    get_gpu_metrics,
    get_cpu_metrics,
    get_memory_metrics,
    get_disk_metrics
)
from models.responses import ResourceMetricsResponse

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    """
    Get all system metrics
    
    Returns:
        Complete system metrics (CPU, memory, disk, GPU)
    """
    try:
        metrics = get_system_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/system", response_model=ResourceMetricsResponse)
async def get_system_metrics_api():
    """
    Get system metrics (alias for /metrics)
    
    Returns:
        Complete system metrics
    """
    try:
        metrics = get_system_metrics()
        return ResourceMetricsResponse(**metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/gpu")
async def get_gpu_info():
    """
    Get GPU-specific metrics
    
    Returns:
        GPU information and utilization
    """
    try:
        return get_gpu_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cpu")
async def get_cpu_info():
    """
    Get CPU-specific metrics
    
    Returns:
        CPU information and utilization
    """
    try:
        return get_cpu_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory")
async def get_memory_info():
    """
    Get memory metrics
    
    Returns:
        Memory usage information
    """
    try:
        return get_memory_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/disk")
async def get_disk_info():
    """
    Get disk metrics
    
    Returns:
        Disk usage information
    """
    try:
        return get_disk_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_metrics_history(limit: int = 60):
    """
    Get historical metrics
    
    Args:
        limit: Number of data points to return
        
    Returns:
        Historical metrics data
    """
    try:
        from core.ml.utils import ResourceMonitor
        
        # Create monitor instance
        monitor = ResourceMonitor()
        
        # Get historical data (if available)
        history = monitor.get_history(limit=limit)
        
        return {
            "history": history,
            "limit": limit,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
Resource Monitoring
System and GPU monitoring using core utilities
"""


from core.ml.utils import (
    get_gpu_info,
    get_cpu_info,
    get_memory_info,
    get_disk_info,
    get_system_info,
    get_all_metrics
)


def get_system_metrics():
    """
    Get current system metrics
    
    Returns:
        Dictionary with CPU, memory, disk, and GPU metrics
    """
    return get_all_metrics()


def get_gpu_metrics():
    """
    Get GPU-specific metrics
    
    Returns:
        List of GPU information
    """
    return {"gpus": get_gpu_info()}


def get_cpu_metrics():
    """
    Get CPU-specific metrics
    
    Returns:
        CPU information
    """
    return get_cpu_info()


def get_memory_metrics():
    """
    Get memory-specific metrics
    
    Returns:
        Memory information
    """
    return get_memory_info()


def get_disk_metrics():
    """
    Get disk-specific metrics
    
    Returns:
        Disk information
    """
    return get_disk_info()
